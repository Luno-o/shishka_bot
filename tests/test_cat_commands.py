from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from handlers import cat_commands


class FakeMessage:
    def __init__(self, reply_to_message=None):
        self.answer = AsyncMock()
        self.answer_photo = AsyncMock()
        self.answer_animation = AsyncMock()
        self.reply_to_message = reply_to_message


def _filterable_cat_model(items):
    """A CatPhoto stand-in whose .objects.filter(...).all() records the filter kwargs."""
    calls = []

    def _filter(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(all=AsyncMock(return_value=items))

    model = SimpleNamespace(objects=SimpleNamespace(filter=_filter))
    return model, calls


def test_extract_reply_media_photo():
    photo = SimpleNamespace(file_id="fid", file_unique_id="uid")
    reply = SimpleNamespace(photo=[photo], animation=None)
    result = cat_commands._extract_reply_media(reply)
    assert result == ("photo", "fid", "uid")


def test_extract_reply_media_animation():
    animation = SimpleNamespace(file_id="fid2", file_unique_id="uid2")
    reply = SimpleNamespace(photo=None, animation=animation)
    result = cat_commands._extract_reply_media(reply)
    assert result == ("animation", "fid2", "uid2")


def test_extract_reply_media_none_for_text():
    reply = SimpleNamespace(photo=None, animation=None)
    assert cat_commands._extract_reply_media(reply) is None


@pytest.mark.asyncio
async def test_send_random_cat_filters_by_shishka_category(monkeypatch):
    media = SimpleNamespace(file_id="fid", description=None, media_type="photo")
    model, calls = _filterable_cat_model([media])
    monkeypatch.setattr(cat_commands, "CatPhoto", model)

    message = FakeMessage()
    await cat_commands.send_random_cat(message)

    assert calls == [{"category": cat_commands.CATEGORY_SHISHKA}]
    message.answer_photo.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_random_friend_cat_filters_by_friend_category(monkeypatch):
    media = SimpleNamespace(file_id="fid", description=None, media_type="photo")
    model, calls = _filterable_cat_model([media])
    monkeypatch.setattr(cat_commands, "CatPhoto", model)

    message = FakeMessage()
    await cat_commands.send_random_friend_cat(message)

    assert calls == [{"category": cat_commands.CATEGORY_FRIEND}]
    message.answer_photo.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_random_friend_cat_empty_database_suggests_submit(monkeypatch):
    model, _ = _filterable_cat_model([])
    monkeypatch.setattr(cat_commands, "CatPhoto", model)

    message = FakeMessage()
    await cat_commands.send_random_friend_cat(message)

    message.answer.assert_awaited_once()
    assert "add_shis_friend" in message.answer.call_args.args[0]
