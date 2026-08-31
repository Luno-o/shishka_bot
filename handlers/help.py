"""User-facing help and start commands."""

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from filters import HelpRequestFilter
from utils import get_string

router = Router(name="help")


async def send_help(message: Message) -> None:
    await message.answer(get_string("help-message"))


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    await send_help(message)


@router.message(Command("help", "помощь", "помоги", prefix="!/"))
async def on_help_command(message: Message) -> None:
    await send_help(message)


@router.message(HelpRequestFilter())
async def on_help_request(message: Message) -> None:
    await send_help(message)
