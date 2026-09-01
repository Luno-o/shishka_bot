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
    return SimpleNamespace(objects=SimpleNamespace(all=AsyncMock(return_value=items)))


@pytest.mark.asyncio
async def test_help_falls_back_to_text_when_database_has_no_media(monkeypatch):
    message = FakeMessage()
    monkeypatch.setattr(help_handlers, "CatPhoto", _cat_model([]))

    await help_handlers.send_help(message)

    message.answer.assert_awaited_once()
    message.answer_photo.assert_not_awaited()
    message.answer_animation.assert_not_awaited()


@pytest.mark.asyncio
async def test_help_attaches_random_shishka(monkeypatch):
    message = FakeMessage()
    media = SimpleNamespace(file_id="telegram-file-id", media_type="photo")
    monkeypatch.setattr(help_handlers, "CatPhoto", _cat_model([media]))

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
