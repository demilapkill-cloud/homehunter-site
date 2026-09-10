"""Вынуть из страницы то, что читает человек, — по одному файлу на язык.

Зачем. Правила Vale про слова работают и по разметке, а правило про длину
предложения — нет: Vale не видит границ блоков и склеивает заголовок, подписи
кнопок и абзац в одно «предложение» на сотню слов. Поэтому текст сначала
вынимают, а уже потом меряют.

Заодно выбрасывается то, чего человек не читает и за что мы не отвечаем:
комментарии в коде, скрипты, стили и карточки квартир — заголовки чужих
объявлений написаны арендодателями, и «машинности» с них не спрашивают.

    python3 tools/prose.py            # положит prose-ru.txt и остальные в /tmp
    slop /tmp/homehunter-prose        # проверит их
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/homehunter-prose")

#: Куски документа, которые человек не читает как текст.
DROP = (
    re.compile(r"<script.*?</script>", re.S),
    re.compile(r"<style.*?</style>", re.S),
    re.compile(r"<!--.*?-->", re.S),
    # Карточка квартиры — чужой текст: заголовок объявления написал
    # арендодатель, и мерить его нашими правилами незачем.
    re.compile(r'<div class="bubble">.*?</div>\s*<a class="bubble-btn".*?</a>', re.S),
)

#: Теги, после которых предложение точно кончилось. Без этого «Шестнадцать
#: городов» и следующий за ним абзац склеиваются в одну строку — ровно та
#: беда, из-за которой этот скрипт и появился.
BLOCK = re.compile(r"</(p|h[1-6]|li|div|section|main|header|footer|td|th)>", re.I)


def text_of(fragment: str) -> str:
    # Разрез по `<main id="main-(\w+)"` оставляет в начале хвост самого тега
    # (` data-lang-block="ru" class="on">`); человек его не читает.
    fragment = fragment[fragment.index(">") + 1 :] if ">" in fragment[:120] else fragment
    for pattern in DROP:
        fragment = pattern.sub(" ", fragment)
    fragment = BLOCK.sub("\n\n", fragment)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    fragment = html.unescape(fragment)
    lines = []
    for line in fragment.split("\n"):
        line = " ".join(line.split())
        if line:
            lines.append(line)
    return "\n\n".join(lines) + "\n"


#: Длиннее этого предложение читается ровно и одинаково — главный признак
#: машинной прозы после слов-пустышек. Немецкий длиннее прочих, и тридцать
#: пять слов там нормальны, поэтому у него своя граница.
LIMIT = {"de": 35}
DEFAULT_LIMIT = 30


def long_sentences(prose: str, limit: int = DEFAULT_LIMIT) -> list[tuple[int, str]]:
    """Предложения длиннее предела — по абзацам, а не по всему тексту сразу.

    Считается здесь, а не правилом Vale, потому что там оно считало не то:
    `occurrence` со `scope: sentence` склеивает разделы через пустые строки и
    показывал двадцать семь длинных предложений там, где их ноль.
    """
    out = []
    for paragraph in prose.split("\n\n"):
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
            count = len(re.findall(r"[^\W\d_]+", sentence, re.UNICODE))
            if count > limit:
                out.append((count, " ".join(sentence.split())))
    return out


def main() -> int:
    page = (ROOT / "index.html").read_text(encoding="utf-8")
    blocks = re.split(r'<main id="main-(\w+)"', page)
    if len(blocks) < 3:
        raise SystemExit("в index.html не нашлось ни одного <main id=\"main-…\">")

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("prose-*.txt"):
        old.unlink()

    found = 0
    for lang, body in zip(blocks[1::2], blocks[2::2], strict=True):
        prose = text_of(body)
        target = OUT / f"prose-{lang}.txt"
        target.write_text(prose, encoding="utf-8")
        words = len(re.findall(r"[^\W\d_]+", prose, re.UNICODE))
        long = long_sentences(prose, LIMIT.get(lang, DEFAULT_LIMIT))
        found += len(long)
        print(f"{target}: {words} слов, длинных предложений {len(long)}")
        for count, sentence in long:
            print(f"    {count} слов: {sentence[:120]}…")
    if found:
        print(f"\nВсего длинных предложений: {found}. Машинная проза длинная и ровная;")
        print("живая рваная — короткое, длинное, снова короткое.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
