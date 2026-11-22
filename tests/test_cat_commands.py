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
    assert "add_shish_friend" in message.answer.call_args.args[0]


# --- regression: members could not use !submit_shish_friend / !submit_shishka ---
# Low-rep members' photos are deleted by auto-moderation at once, so they cannot
# reply to their own photo; sending the photo with the command as its caption
# must work instead.

def _photo(fid="fid", uid="uid"):
    return [SimpleNamespace(file_id=fid, file_unique_id=uid)]


def _submit_message(*, photo=None, caption=None, text=None, reply=None):
    bot = MagicMock()
    bot.send_photo = AsyncMock()
    bot.send_animation = AsyncMock()
    msg = MagicMock()
    msg.bot = bot
    msg.photo = photo
    msg.animation = None
    msg.caption = caption
    msg.text = text
    msg.reply_to_message = reply
    msg.from_user = SimpleNamespace(
        id=10, full_name="Участник", username=None, url="tg://user?id=10",
        mention_html=lambda: '<a href="tg://user?id=10">Участник</a>',
    )
    msg.chat = SimpleNamespace(id=-100, title="Чат", type="supergroup")
    msg.answer = AsyncMock()
    msg.delete = AsyncMock()
    return msg


@pytest.fixture
def submit_env(monkeypatch):
    queued = []
    monkeypatch.setattr(cat_commands.config.groups, "reports", -555)
    empty = SimpleNamespace(first=AsyncMock(return_value=None))
    monkeypatch.setattr(
        cat_commands, "CatPhoto", SimpleNamespace(objects=SimpleNamespace(filter=lambda **kw: empty))
    )

    def _queue(**kwargs):
        queued.append(kwargs)
        return "key123"

    monkeypatch.setattr(cat_commands, "queue_submission", _queue)
    return queued


@pytest.mark.parametrize(
    ("command", "category"),
    [
        ("/submit_shish_friend", cat_commands.CATEGORY_FRIEND),
        ("/submit_shishka", cat_commands.CATEGORY_SHISHKA),
    ],
    ids=["friend", "shishka"],
)
@pytest.mark.asyncio
async def test_photo_with_command_caption_is_submitted(submit_env, command, category):
    msg = _submit_message(photo=_photo(), caption=f"{command} рыжий 🐾")
    handler = (
        cat_commands.submit_shish_friend if category == cat_commands.CATEGORY_FRIEND
        else cat_commands.submit_shishka
    )

    await handler(msg)

    assert len(submit_env) == 1
    assert submit_env[0]["file_id"] == "fid"
    assert submit_env[0]["category"] == category
    assert submit_env[0]["description"] == "рыжий 🐾"
    msg.bot.send_photo.assert_awaited_once()
    assert msg.bot.send_photo.await_args.args[0] == -555
    # the photo now lives in the review chat; it must not bypass the media rule in the group
    msg.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_reply_with_text_command_still_works_and_keeps_replied_photo(submit_env):
    reply = SimpleNamespace(photo=_photo("rf", "ru"), animation=None)
    msg = _submit_message(text="/submit_shish_friend", reply=reply)

    await cat_commands.submit_shish_friend(msg)

    assert submit_env[0]["file_id"] == "rf"
    assert submit_env[0]["description"] is None
    msg.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_own_photo_wins_over_reply_and_caption_without_text_does_not_crash(submit_env):
    reply = SimpleNamespace(photo=_photo("rf", "ru"), animation=None)
    msg = _submit_message(photo=_photo("own", "ou"), caption="/submit_shish_friend", reply=reply)

    await cat_commands.submit_shish_friend(msg)

    assert submit_env[0]["file_id"] == "own"
    assert submit_env[0]["description"] is None


@pytest.mark.asyncio
async def test_no_media_anywhere_explains_both_ways(submit_env):
    msg = _submit_message(text="/submit_shish_friend")

    await cat_commands.submit_shish_friend(msg)

    assert submit_env == []
    text = msg.answer.await_args.args[0]
    assert "подпис" in text  # tells the member they can send the photo with the command as caption


@pytest.mark.asyncio
async def test_review_caption_escapes_title_and_description(submit_env):
    msg = _submit_message(photo=_photo(), caption="/submit_shish_friend <b>кот & пёс")
    msg.chat = SimpleNamespace(id=-100, title="Коты <3 & друзья", type="supergroup")

    await cat_commands.submit_shish_friend(msg)

    caption = msg.bot.send_photo.await_args.kwargs["caption"]
    assert "&lt;b&gt;кот &amp; пёс" in caption
    assert "Коты &lt;3 &amp; друзья" in caption


@pytest.mark.asyncio
async def test_reports_chat_failure_falls_back_to_logs(submit_env, monkeypatch):
    from aiogram.exceptions import TelegramBadRequest

    monkeypatch.setattr(cat_commands.config.groups, "logs", -777)
    msg = _submit_message(photo=_photo(), caption="/submit_shish_friend")
    targets = []

    async def send_photo(chat_id, file_id, **kw):
        targets.append(chat_id)
        if chat_id == -555:
            raise TelegramBadRequest(method=MagicMock(), message="chat not found")

    msg.bot.send_photo = AsyncMock(side_effect=send_photo)

    await cat_commands.submit_shish_friend(msg)

    assert targets == [-555, -777]
    assert "отправлено на модерацию" in msg.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_migrated_reports_group_is_retried_at_new_id(submit_env):
    from aiogram.exceptions import TelegramMigrateToChat

    msg = _submit_message(photo=_photo(), caption="/submit_shish_friend")
    targets = []

    async def send_photo(chat_id, file_id, **kw):
        targets.append(chat_id)
        if chat_id == -555:
            raise TelegramMigrateToChat(method=MagicMock(), message="group upgraded", migrate_to_chat_id=-100555)

    msg.bot.send_photo = AsyncMock(side_effect=send_photo)

    await cat_commands.submit_shish_friend(msg)

    assert targets == [-555, -100555]
    assert "отправлено на модерацию" in msg.answer.await_args.args[0]
