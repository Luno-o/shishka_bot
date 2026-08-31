"""Shish-tarot: one cat media fortune per user per calendar day."""

import logging
from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from filters import TarotRequestFilter
from services.shish_tarot import get_daily_shishka

logger = logging.getLogger(__name__)
router = Router(name="shish_tarot")


async def send_daily_shishka(message: Message) -> None:
    if message.from_user is None:
        return

    try:
        media = await get_daily_shishka(message.from_user.id)
        if media is None:
            await message.answer("🔮 В колоде пока нет Шишек. Попросите администратора добавить фото.")
            return

        caption = "🔮 <b>Твоя Шишка дня</b>\nЭта судьба закреплена за тобой до завтра."
        if media.description:
            caption += f"\n\n{escape(media.description)}"

        if media.media_type == "animation":
            await message.answer_animation(animation=media.file_id, caption=caption)
        else:
            await message.answer_photo(photo=media.file_id, caption=caption)
    except Exception:
        logger.exception("Failed to send Shish-tarot reading")
        await message.answer("🔮 Шиш-таро временно недоступно. Попробуйте позже.")


@router.message(Command("shish_tarot", "шиш_таро", prefix="!/"))
async def on_tarot_command(message: Message) -> None:
    await send_daily_shishka(message)


@router.message(TarotRequestFilter())
async def on_tarot_request(message: Message) -> None:
    await send_daily_shishka(message)
