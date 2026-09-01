from zoneinfo import ZoneInfo

import pytest

from config.settings import _parse_bool
from core.i18n import FluentLocalization


@pytest.mark.parametrize("locale", ["ru", "en"])
@pytest.mark.parametrize("key", ["help-message", "rules-message", "rules-short"])
def test_user_facing_messages_compile(locale, key):
    value = FluentLocalization(default_locale=locale).get(key, locale)

    assert value != key
    assert value.strip()
    assert "rules-full =" not in value


@pytest.mark.parametrize("value", ["true", "1", "yes", "on", "TRUE"])
def test_true_environment_values(value):
    assert _parse_bool(value)


def test_moscow_timezone_is_available():
    assert ZoneInfo("Europe/Moscow").key == "Europe/Moscow"
