import pytest

from utils.text_split import CAPTION_LIMIT, MESSAGE_LIMIT, split_paragraphs, visible_length


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("", 0),
        ("<b>abc</b>", 3),
        ("a &lt; b", 5),
        ("привет", 6),
        ("🐱", 2),  # Telegram counts UTF-16 code units
    ],
    ids=["empty", "tags-ignored", "entity-unescaped", "cyrillic", "emoji-two-units"],
)
def test_visible_length(html, expected):
    assert visible_length(html) == expected


def test_short_text_is_one_chunk():
    assert split_paragraphs("one\n\ntwo", 100) == ["one\n\ntwo"]


def test_exactly_at_limit_is_one_chunk():
    text = "a" * 10
    assert split_paragraphs(text, 10) == [text]


def test_split_on_paragraph_boundary_keeps_tags_intact():
    text = "<b>first</b> block\n\n<b>second</b> block"
    chunks = split_paragraphs(text, 12)
    assert chunks == ["<b>first</b> block", "<b>second</b> block"]


def test_paragraph_over_limit_is_split_by_lines():
    text = "line one\nline two\nline three"
    chunks = split_paragraphs(text, 10)
    assert all(visible_length(c) <= 10 for c in chunks)
    assert "\n".join(chunks) == text


def test_every_chunk_within_limit_for_long_text():
    text = "\n\n".join(f"Абзац {i} 🐱 " + "x" * 50 for i in range(40))
    chunks = split_paragraphs(text, MESSAGE_LIMIT // 4)
    assert len(chunks) > 1
    assert all(visible_length(c) <= MESSAGE_LIMIT // 4 for c in chunks)


def test_limits_match_telegram():
    assert CAPTION_LIMIT == 1024
    assert MESSAGE_LIMIT == 4096
