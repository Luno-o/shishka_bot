from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from handlers import help as help_handlers


class FakeMessage:
    def __init__(self):
        self.answer = AsyncMock()
        self.answer_photo = AsyncMock()
        self.answer_animation = AsyncMock()


def _cat_model(items):
    """Stand-in for services.cat_media.random_media; records the category asked for."""
    picker = AsyncMock(return_value=items[0] if items else None)
    return picker


@pytest.mark.asyncio
async def test_help_falls_back_to_text_when_database_has_no_media(monkeypatch):
    message = FakeMessage()
    monkeypatch.setattr(help_handlers, "random_media", _cat_model([]))

    await help_handlers.send_help(message)

    message.answer.assert_awaited_once()
    message.answer_photo.assert_not_awaited()
    message.answer_animation.assert_not_awaited()


@pytest.mark.asyncio
async def test_help_attaches_random_shishka(monkeypatch):
    message = FakeMessage()
    media = SimpleNamespace(file_id="telegram-file-id", media_type="photo")
    monkeypatch.setattr(help_handlers, "random_media", _cat_model([media]))

    await help_handlers.send_help(message)

    message.answer_photo.assert_awaited_once()
    assert message.answer_photo.await_args.args[0] == "telegram-file-id"
    assert "Шишка-бот" in message.answer_photo.await_args.kwargs["caption"]


@pytest.mark.asyncio
async def test_rules_are_sent_without_group_or_throttle_dependencies():
    message = FakeMessage()

    await help_handlers.send_rules(message)

    message.answer.assert_awaited_once()
    assert "защитить чат" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_long_help_goes_as_media_plus_separate_text(monkeypatch):
    message = FakeMessage()
    media = SimpleNamespace(file_id="telegram-file-id", media_type="photo")
    monkeypatch.setattr(help_handlers, "random_media", _cat_model([media]))
    long_text = "\n\n".join(f"<b>Раздел {i}</b> " + "ш" * 90 for i in range(15))
    monkeypatch.setattr(help_handlers, "get_string", lambda key: long_text)

    await help_handlers.send_help(message)

    message.answer_photo.assert_awaited_once()
    assert not message.answer_photo.await_args.kwargs.get("caption")
    sent_text = "\n\n".join(c.args[0] for c in message.answer.await_args_list)
    assert sent_text == long_text
    assert message.answer.await_count >= 1


def test_user_help_does_not_advertise_admin_help():
    from utils import get_string as real_get_string

    assert "adminhelp" not in real_get_string("help-message")


@pytest.mark.asyncio
async def test_help_photo_is_shishka_only(monkeypatch):
    picker = _cat_model([])
    monkeypatch.setattr(help_handlers, "random_media", picker)

    await help_handlers.send_help(FakeMessage())

    picker.assert_awaited_once_with("shishka")
