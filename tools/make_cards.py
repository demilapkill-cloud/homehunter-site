"""Собрать для страницы набор настоящих карточек — тех самых, что бот шлёт людям.

Зачем скрипт, а не разметка руками: на странице показано, как выглядит
сообщение бота, и нарисованная от руки карточка врёт ровно в тот день, когда
бот начинает писать иначе. Здесь карточка рисуется той же функцией
`application/match_alerts.match_alert_html`, что и в чате, из настоящего
объявления, и ссылка ведёт на само объявление.

Запуск (из каталога HomeHunter, там лежит окружение):

    cd ~/Projects/HomeHunter
    uv run python ~/Projects/homehunter-site/tools/make_cards.py \
        --db ~/Projects/HomeHunter/var/db/homehunter.sqlite3 \
        --out ~/Projects/homehunter-site/cards.json

Боевая база бота вместо местной — тем же ключом, только строкой подключения:

    --db 'postgresql+psycopg://homehunter:...@127.0.0.1:5432/homehunter'

Там же появляется таблица `bot_deliveries`, и тогда берутся ровно те
объявления, которые действительно ушли подписчикам, а не всё, что нашёл поиск.

Ссылки живут не вечно: квартиру сдают, и объявление исчезает. Поэтому каждая
ссылка перед записью проверяется запросом, а сам набор стоит пересобирать
время от времени — мёртвая ссылка на первой странице хуже, чем её отсутствие.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from sqlalchemy import create_engine, text  # noqa: E402

from homehunter.application.match_alerts import match_alert_html  # noqa: E402
from homehunter.bot.matching import _sane_deposit, advert_text  # noqa: E402
from homehunter.bot.texts import Texts  # noqa: E402
from homehunter.discovery.registry import build_default_discovery_sources  # noqa: E402
from homehunter.domain.berlin_geo import display_district  # noqa: E402
from homehunter.domain.discovery import NewMatchCard  # noqa: E402
from homehunter.domain.listing import Listing, ListingType  # noqa: E402
from homehunter.domain.rules.amenities import stated  # noqa: E402
from homehunter.domain.source_kinds import origin_note  # noqa: E402
from homehunter.sources.semantics.scam import find_scam_signs  # noqa: E402

LANGS = ("ru", "uk", "de", "en")

#: Сколько ссылок проверять и сколько карточек оставить. Проверенных берём
#: заметно больше, чем нужно: часть объявлений к моменту сборки уже снята.
CANDIDATES = 90
KEEP = 12

#: Столько же секунд браузер ждать не станет, но здесь спешить некуда, а
#: медленный ответ — всё ещё живая страница.
TIMEOUT = 12

#: Тот самый User-Agent, которым ходит обычный браузер. Не маскировка: без
#: него часть сайтов отвечает отказом всему, что не похоже на человека, и
#: живое объявление попало бы в мёртвые.
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"
)

NAMES = {str(s.source_id.value): s.display_name for s in build_default_discovery_sources()}

#: Источники, чьё объявление ведёт не на страницу, а в чужой чат или в почту.
#: Кнопка «перейти на объявление» с такой ссылкой на публичной странице
#: бессмысленна, поэтому они сюда не идут.
SKIP_SOURCES = {"telegram_is24_bot", "newspaper"}


def rows_from(db: str, days: int) -> list[dict]:
    """Объявления-кандидаты: сначала те, что бот действительно разослал."""
    url = db
    if not url.startswith(("postgresql", "sqlite")):
        url = f"sqlite:///{Path(db).expanduser()}"
    engine = create_engine(url)
    since = datetime.now() - timedelta(days=days)

    delivered = text(
        """
        select distinct on (d.listing_id)
               d.listing_id as id, d.source as source, l.url as url, l.data as data
        from bot_deliveries d
        join listings l on l.id = d.listing_id
        where d.status = 'sent' and d.sent_at > :since and d.recalled_at is null
          and l.availability = 'active' and l.url <> ''
        order by d.listing_id, d.sent_at desc
        """
    )
    found = text(
        """
        select id, source, url, data
        from listings
        where availability = 'active' and url <> '' and last_seen_at > :since
        order by last_seen_at desc
        """
    )

    with engine.connect() as conn:
        if engine.dialect.name == "postgresql":
            try:
                rows = conn.execute(delivered, {"since": since}).mappings().all()
                if rows:
                    print(f"разосланных объявлений: {len(rows)}", file=sys.stderr)
                    return [dict(r) for r in rows]
            except Exception as exc:  # noqa: BLE001
                print(f"журнал доставки не прочитан ({exc}), беру найденное", file=sys.stderr)
        rows = conn.execute(found, {"since": since}).mappings().all()
    print(f"найденных объявлений: {len(rows)}", file=sys.stderr)
    return [dict(r) for r in rows]


def card_for(listing: Listing, source_id: str, translate) -> NewMatchCard:
    """Ровно те поля, которые складывает `bot/matching.py:alert_for`.

    Личного здесь нет и быть не может: расчёт Jobcenter, письмо и причины
    «надо посмотреть» считаются под конкретного подписчика, и на публичной
    странице им не место.

    Одно поле пропущено намеренно и о нём стоит помнить: `contact`. У доски
    объявлений там телефон частного человека, и место ему в личной переписке
    с подписчиком, а не на общедоступной странице.
    """
    return NewMatchCard(
        listing_id=listing.id,
        title=listing.title,
        url=listing.url,
        source=NAMES.get(source_id, source_id),
        cold_rent=listing.price.cold_rent,
        warm_rent=listing.price.warm_rent,
        rooms=listing.property.rooms,
        is_room=listing.listing_type is ListingType.ROOM,
        area_m2=listing.property.area_m2,
        district=display_district(listing.address.district, listing.address.postal_code),
        available_from=listing.rental.available_from,
        available_until=listing.rental.available_until,
        deposit=_sane_deposit(listing.price.deposit, listing.price.cold_rent),
        furnished=listing.features.furnished,
        balcony=listing.features.balcony,
        elevator=listing.features.elevator,
        kitchen=listing.features.kitchen,
        pets_allowed=stated(listing, "pets_allowed"),
        origin_note=origin_note(listing.source, listing.attributes, translate),
        scam_signs=[f.sign.value for f in find_scam_signs(advert_text(listing))],
        additional_costs=listing.price.additional_costs,
        heating_costs=listing.price.heating_costs,
        postal_code=listing.address.postal_code or "",
        street=listing.address.street or "",
        published_at=listing.published_at,
    )


def as_lines(rendered: str) -> list[str]:
    """Карточка построчно, как её видно в чате.

    Телеграм разделяет строки переводом строки, HTML — нет, и отдавать
    страницу с `white-space: pre-line` оказалось нельзя: заголовок настоящего
    объявления сам содержит переводы строк («Möblierte 1-Zimmer-Wohnung an\n\n
    der U-Bahn» — так его написал человек на wg-gesucht), и пузырь разъезжался
    на пустые строки. Поэтому строки разбираются здесь: пробелы внутри строки
    схлопываются, пустые строки выбрасываются, а отступ между заголовком и
    фактами делает CSS.
    """
    lines = []
    for line in rendered.split("\n"):
        line = " ".join(line.split())
        if line:
            lines.append(line)
    return lines


def alive(url: str) -> bool:
    """Отвечает ли объявление до сих пор.

    404 и 410 — снято, и такая ссылка на страницу не идёт. Всё остальное,
    включая отказ бот-защиты, считается живым: страница есть, просто она не
    хочет разговаривать с программой, а человек её откроет.
    """
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status < 400
    except urllib.error.HTTPError as error:
        return error.code not in (404, 410)
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="путь к sqlite или строка подключения")
    parser.add_argument("--out", required=True, help="куда положить JSON")
    parser.add_argument("--days", type=int, default=7, help="насколько свежие объявления брать")
    parser.add_argument("--keep", type=int, default=KEEP, help="сколько карточек оставить")
    args = parser.parse_args()

    rows = rows_from(args.db, args.days)
    random.shuffle(rows)

    built: list[dict] = []
    for row in rows:
        if len(built) >= CANDIDATES:
            break
        if row["source"] in SKIP_SOURCES:
            continue
        data = row["data"]
        if isinstance(data, (str, bytes)):
            data = json.loads(data)
        try:
            listing = Listing.model_validate(data)
        except Exception:  # noqa: BLE001
            continue
        # Карточка без цены и без размера не показывает того, ради чего её
        # показывают. Такие бот людям тоже не шлёт (`states_nothing`).
        if listing.price.warm_rent is None and listing.price.cold_rent is None:
            continue
        if listing.property.area_m2 is None:
            continue
        # `origin_note` переводится, поэтому карточка собирается заново на
        # каждом языке, а не рисуется один раз и переводится потом.
        rendered = {}
        for lang in LANGS:
            translate = Texts(lang).t
            rendered[lang] = as_lines(
                match_alert_html(card_for(listing, row["source"], translate), translate)
            )
        built.append(
            {
                "url": listing.url,
                "source": NAMES.get(row["source"], row["source"]),
                "cards": rendered,
            }
        )

    print(f"собрано карточек: {len(built)}, проверяю ссылки", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=8) as pool:
        checked = list(pool.map(lambda item: alive(item["url"]), built))
    live = [item for item, ok in zip(built, checked) if ok]
    print(f"живых ссылок: {len(live)} из {len(built)}", file=sys.stderr)

    # Порядок внутри набора решает, какая карточка попадёт в разметку и
    # достанется тому, у кого выключены скрипты. Вперёд идут те, что
    # показывают карточку с лучшей стороны: обычная квартира (а не комната в
    # WG, где число комнат относится к чужой квартире) и побольше названных
    # объявлением фактов. Случайный выбор в браузере берёт из всего набора,
    # так что показываются в итоге все.
    def richness(item: dict) -> tuple[int, int]:
        lines = item["cards"]["ru"]
        return (0 if len(lines) < 4 else 1, len(lines))

    live.sort(key=richness, reverse=True)

    # По одной карточке на источник, пока хватает источников: набор из десяти
    # объявлений одного портала не показывает, что бот смотрит куда-то ещё.
    seen: set[str] = set()
    chosen: list[dict] = []
    for item in live:
        if item["source"] not in seen:
            seen.add(item["source"])
            chosen.append(item)
    for item in live:
        if len(chosen) >= args.keep:
            break
        if item not in chosen:
            chosen.append(item)
    chosen = chosen[: args.keep]

    # Подпись кнопки берётся из того же словаря, что и в боте, и лежит
    # рядом с карточками: страница не должна знать, как «Перейти на
    # объявление» звучит на четырёх языках.
    payload = {
        "labels": {lang: Texts(lang).t("Go to listing") for lang in LANGS},
        "cards": chosen,
    }

    # Единственная разметка, которую рисует `match_alert_html`, — это <b>.
    # Всё прочее в тексте объявления экранировано (`match_alerts._esc`).
    # Проверка стоит здесь, а не на странице: карточки попадают в документ
    # как готовый HTML, и узнать о чужом теге лучше при сборке, чем в
    # браузере читателя.
    for item in chosen:
        for lang, lines in item["cards"].items():
            for tag in re.findall(r"</?([a-zA-Z][^\s>/]*)", " ".join(lines)):
                if tag.lower() not in ("b", "i", "u", "s", "code"):
                    raise SystemExit(f"неожиданный тег <{tag}> в карточке {item['url']} ({lang})")

    out = Path(args.out).expanduser()
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"записано {len(chosen)} карточек в {out}", file=sys.stderr)
    for item in chosen:
        print(f"  {item['source']:20} {item['url']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
