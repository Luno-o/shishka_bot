"""Split long HTML texts into Telegram-sized messages."""
import re
from html import unescape

# Telegram limits, counted in UTF-16 code units of the visible text.
CAPTION_LIMIT = 1024
MESSAGE_LIMIT = 4096

_TAG_RE = re.compile(r"<[^>]+>")


def visible_length(html: str) -> int:
    """Return the length Telegram counts for ``html``: tags stripped, entities unescaped, UTF-16 units."""
    text = unescape(_TAG_RE.sub("", html))
    return len(text.encode("utf-16-le")) // 2


def _pack(parts: list[str], sep: str, limit: int) -> list[str]:
    """Greedily join ``parts`` with ``sep`` into chunks no longer than ``limit``."""
    chunks: list[str] = []
    current = ""
    for part in parts:
        candidate = f"{current}{sep}{part}" if current else part
        if current and visible_length(candidate) > limit:
            chunks.append(current)
            current = part
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def split_paragraphs(html: str, limit: int) -> list[str]:
    """Split ``html`` into chunks of at most ``limit`` visible units.

    Splits on blank lines first, then on single lines for an oversized
    paragraph. Assumes tags never span a line break, which holds for the
    bot's help texts; a single line longer than ``limit`` is left as is.
    """
    if visible_length(html) <= limit:
        return [html]
    paragraphs: list[str] = []
    for para in html.split("\n\n"):
        if visible_length(para) <= limit:
            paragraphs.append(para)
        else:
            paragraphs.extend(_pack(para.split("\n"), "\n", limit))
    return _pack(paragraphs, "\n\n", limit)
