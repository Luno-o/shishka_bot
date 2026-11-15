"""User-facing help, start, and rules commands."""

import logging
import random

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from config import config
from db.models import CatPhoto
from filters import HelpRequestFilter
from services.ephemeral import cleanup_trigger, make_ephemeral
from utils import get_string
from utils.text_split import CAPTION_LIMIT, MESSAGE_LIMIT, split_paragraphs, visible_length

router = Router(name="help")
logger = logging.getLogger(__name__)


async def send_help(message: Message) -> None:
    """Send friendly help, optionally accompanied by a random Shishka.

    Ephemeral in groups: the reply auto-deletes after config.ephemeral.help_ttl.
    """
    help_text = get_string("help-message")
    ttl = config.ephemeral.help_ttl
    # Why: a caption over Telegram's limit is rejected outright, so a long help
    # goes as the media alone followed by the text, never squeezed into one.
    fits_caption = visible_length(help_text) <= CAPTION_LIMIT

    try:
        media_list = await CatPhoto.objects.all()
        media = random.choice(media_list) if media_list else None
        if media is not None:
            caption = help_text if fits_caption else None
            if media.media_type == "animation":
                sent = await message.answer_animation(media.file_id, caption=caption)
            else:
                sent = await message.answer_photo(media.file_id, caption=caption)
            make_ephemeral(message, sent, ttl)
            if fits_caption:
                return
    except Exception:
        logger.exception("Failed to attach a random Shishka to help")

    for chunk in split_paragraphs(help_text, MESSAGE_LIMIT):
        make_ephemeral(message, await message.answer(chunk), ttl)


async def send_rules(message: Message) -> None:
    """Send rules in groups and private chats without a silent cooldown.

    Ephemeral in groups: the reply auto-deletes after config.ephemeral.rules_ttl.
    """
    sent = await message.answer(get_string("rules-message"))
    make_ephemeral(message, sent, config.ephemeral.rules_ttl)


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    await send_help(message)


@router.message(Command("help", "помощь", "помоги", prefix="!/"))
async def on_help_command(message: Message) -> None:
    await send_help(message)
    await cleanup_trigger(message)


@router.message(HelpRequestFilter())
async def on_help_request(message: Message) -> None:
    await send_help(message)
    await cleanup_trigger(message)


@router.message(Command("rules", "правила", prefix="!/"))
async def on_rules_command(message: Message) -> None:
    await send_rules(message)
    await cleanup_trigger(message)


@router.callback_query(F.data == "show_rules")
async def on_rules_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await send_rules(callback.message)


@router.callback_query(F.data == "show_help")
async def on_help_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await send_help(callback.message)
