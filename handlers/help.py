"""User-facing help, start, and rules commands."""

import logging
import random

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from db.models import CatPhoto
from filters import HelpRequestFilter
from utils import get_string

router = Router(name="help")
logger = logging.getLogger(__name__)


async def send_help(message: Message) -> None:
    """Send friendly help, optionally accompanied by a random Shishka."""
    help_text = get_string("help-message")
    try:
        media_list = await CatPhoto.objects.all()
        media = random.choice(media_list) if media_list else None
        if media is None:
            await message.answer(help_text)
        elif media.media_type == "animation":
            await message.answer_animation(media.file_id, caption=help_text)
        else:
            await message.answer_photo(media.file_id, caption=help_text)
    except Exception:
        logger.exception("Failed to attach a random Shishka to help")
        await message.answer(help_text)


async def send_rules(message: Message) -> None:
    """Send rules in groups and private chats without a silent cooldown."""
    await message.answer(get_string("rules-message"))


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    await send_help(message)


@router.message(Command("help", "помощь", "помоги", prefix="!/"))
async def on_help_command(message: Message) -> None:
    await send_help(message)


@router.message(HelpRequestFilter())
async def on_help_request(message: Message) -> None:
    await send_help(message)


@router.message(Command("rules", "правила", prefix="!/"))
async def on_rules_command(message: Message) -> None:
    await send_rules(message)


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
