import pytest

from filters.text_requests import is_help_request, is_tarot_request


@pytest.mark.parametrize(
    "text",
    [
        "шишка хэлп",
        "Шишка, помоги!",
        "помогити шишка",
        "помощь",
        "HELP SHISHKA",
    ],
)
def test_help_requests(text):
    assert is_help_request(text)


@pytest.mark.parametrize(
    "text",
    [
        "что у меня сегодня шишка",
        "Шишка, какая у меня сегодня судьба?",
        "моя карта на сегодня",
        "шиш-таро",
    ],
)
def test_tarot_requests(text):
    assert is_tarot_request(text)


@pytest.mark.parametrize("text", ["помоги Пете", "что сегодня на обед", "обычная шишка"])
def test_unrelated_text_is_not_a_request(text):
    assert not is_help_request(text)
    assert not is_tarot_request(text)
