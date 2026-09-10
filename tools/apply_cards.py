"""Вставить карточки из cards.json в index.html.

Отдельный шаг, а не часть `make_cards.py`, потому что делает другое: тот
достаёт карточки из базы и проверяет ссылки (долго, ходит в сеть), этот
только переписывает разметку (мгновенно, ничего не знает про базу). Значит
страницу можно пересобрать из уже собранного набора, ничего не выкачивая.

    python3 tools/apply_cards.py

Что делается:

* каждый из восьми пузырей на странице (первый экран и разбор, четыре языка)
  заполняется первой карточкой набора — на своём языке, с рабочей ссылкой;
* весь набор кладётся в документ как <script type="application/json">, откуда
  его берёт скрипт и при загрузке подставляет случайную.

Первая карточка вписана в разметку, а не только в JSON, ради того, у кого
скрипты выключены: он увидит настоящую карточку с рабочей ссылкой, а не
пустой пузырь.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANGS = ("ru", "uk", "de", "en")

OPEN = '<div class="bubble">'
DIV = re.compile(r"<div\b|</div>")
MAIN = re.compile(r'<main id="main-(\w+)"')


def bubble_spans(page: str) -> list[tuple[int, int]]:
    """Границы каждого пузыря — со счётом вложенных div, а не регулярным
    выражением до первого `</div>`.

    Так уже ошиблись один раз: внутри пузыря лежит `<div class="bubble-body">`,
    и нежадное `<div class="bubble">.*?</div>` закрывалось на нём. Замена
    съедала половину пузыря, кнопка оставалась сиротой ниже, и разметка
    расходилась ровно на восьми местах — по числу пузырей.
    """
    spans = []
    start = page.find(OPEN)
    while start != -1:
        depth = 0
        for match in DIV.finditer(page, start):
            depth += 1 if match.group(0) != "</div>" else -1
            if depth == 0:
                spans.append((start, match.end()))
                break
        else:
            raise SystemExit(f"незакрытый пузырь на позиции {start}")
        start = page.find(OPEN, spans[-1][1])
    return spans


def bubble_html(card: dict, label: str, lang: str) -> str:
    """Один пузырь: тело карточки, ссылка на объявление и больше ничего.

    Времени отправки здесь нет намеренно. Раньше стояло «9:03» — число,
    которое я придумал, чтобы пузырь был похож на переписку. Карточка
    настоящая, и выдуманному времени рядом с ней не место.
    """
    lines = card["cards"][lang]
    body = [f'<span class="title">{lines[0]}</span>']
    body += [f'<span class="row">{line}</span>' for line in lines[1:]]
    inner = "\n        ".join(body)
    return (
        '<div class="bubble">\n'
        f'      <div class="bubble-body">\n        {inner}\n      </div>\n'
        f'      <a class="bubble-btn" href="{card["url"]}"\n'
        f'         target="_blank" rel="noopener nofollow ugc">{label} ({card["source"]})</a>\n'
        "    </div>"
    )


def main() -> int:
    data = json.loads((ROOT / "cards.json").read_text(encoding="utf-8"))
    cards, labels = data["cards"], data["labels"]
    if not cards:
        raise SystemExit("cards.json пуст — сначала соберите набор make_cards.py")

    page = (ROOT / "index.html").read_text(encoding="utf-8")

    # Язык пузыря — тот, в чьём <main> он стоит. Считать по порядку («первые
    # два русские») было бы короче и сломалось бы в тот день, когда у одного
    # из языков появится третья карточка.
    bounds = [(m.start(), m.group(1)) for m in MAIN.finditer(page)]

    def lang_at(position: int) -> str:
        found = "ru"
        for start, lang in bounds:
            if start < position:
                found = lang
        return found

    spans = bubble_spans(page)
    if len(spans) != len(LANGS) * 2:
        raise SystemExit(f"ожидалось {len(LANGS) * 2} пузырей, найдено {len(spans)}")

    # С конца, чтобы замена не сдвигала границы ещё не заменённых пузырей.
    for start, end in reversed(spans):
        lang = lang_at(start)
        page = page[:start] + bubble_html(cards[0], labels.get(lang, "Go to listing"), lang) + page[end:]
    replaced = len(spans)

    block = (
        '<script type="application/json" id="hh-cards">\n'
        + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        + "\n</script>"
    )
    if '<script type="application/json" id="hh-cards">' in page:
        page = re.sub(
            r'<script type="application/json" id="hh-cards">.*?</script>',
            lambda _: block,
            page,
            flags=re.DOTALL,
        )
    else:
        # Перед скриптом, а не в конце документа: скрипт читает набор сразу
        # при разборе страницы, и положенный ниже он не находит ничего —
        # ошибки при этом нет, просто случайный выбор молча не работает и
        # всем достаётся карточка, вписанная в разметку.
        anchor = page.index("\n<script>")
        page = page[:anchor] + "\n" + block + page[anchor:]

    (ROOT / "index.html").write_text(page, encoding="utf-8")
    print(f"пузырей заполнено: {replaced}, карточек в наборе: {len(cards)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
