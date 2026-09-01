import pytest

from libs.censure import Censor


@pytest.mark.parametrize(
    ("language", "text"),
    [
        ("ru", "хуй"),
        ("ru", "пизда"),
        ("ru", "3.14здец"),
        ("en", "shit"),
        ("en", "motherfucker"),
        ("en", "blow job"),
    ],
)
def test_obscene_text_is_detected(language, text):
    cleaned, bad_words, bad_phrases, *_ = Censor.get(lang=language, do_compile=False).clean_line(text)

    assert cleaned == "[beep]"
    assert bad_words + bad_phrases == 1
