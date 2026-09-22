import logging
import random
from aiogram import Router, F
from aiogram.types import Message, ContentType, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command, CommandObject

from config import config
from db.models import CatPhoto
from filters import InMainGroups
from services.cat_submissions import queue_submission, peek_submission, pop_submission
from services.metrics import increment as record_metric
from utils import get_string, user_mention, write_log

logger = logging.getLogger(__name__)
router = Router(name="cat_commands")

CATEGORY_SHISHKA = "shishka"
CATEGORY_FRIEND = "friend"
CATEGORY_LABELS = {CATEGORY_SHISHKA: "Шишка", CATEGORY_FRIEND: "кот-друг"}
CATEGORY_EMOJI = {CATEGORY_SHISHKA: "🐱", CATEGORY_FRIEND: "🐾"}

# Все варианты команды "шишка" (регистр не важен)
CAT_COMMANDS = {
    # Основные
    "шишка", "shishka", "sishka", "сышка",
    "кошка", "cat", "кот", "котяра", "киса", "киска",

    # Уменьшительно-ласкательные
    "шишуля", "шишулька", "шишечка", "шишонок", "шиш", "шишик",
    "shishulya", "shishulka", "shishechka", "шишня", "пушишка", "пушня", "пух",

    # Кошачьи
    "мяу", "meow", "мур", "purr", "мурка", "кис-кис", "кис кис",

    # Игровые
    "шиши", "шишка-бот", "shishka-bot",
    "котик", "котейка", "котёнок", "котэ", "кыс", "кыся",
}

@router.message(
    InMainGroups(),
    F.text.lower().in_(CAT_COMMANDS),
)
@router.message(
    InMainGroups(),
    Command("shishka", prefix="!/"),
)
async def send_random_cat(message: Message) -> None:
    """Send a random cat photo or animation from the database."""
    try:
        media_list = await CatPhoto.objects.filter(category=CATEGORY_SHISHKA).all()

        if not media_list:
            await message.answer("🐱 В базе пока нет фотографий или гифок Шишки! Добавьте первую командой /add_shishka")
            return

        media = random.choice(media_list)
        caption = f"🐱 Шишка!"
        if media.description:
            caption += f"\n📝 {media.description}"

        # Отправляем в зависимости от типа
        if media.media_type == 'animation':
            await message.answer_animation(
                animation=media.file_id,
                caption=caption
            )
            logger.info(f"🎬 Отправлена гифка Шишки #{media.id}")
        else:
            await message.answer_photo(
                photo=media.file_id,
                caption=caption
            )
            logger.info(f"📸 Отправлено фото Шишки #{media.id}")

    except Exception as e:
        logger.error(f"Error sending cat media: {e}")
        await message.answer("🐱 Что-то пошло не так... Попробуйте позже.")


@router.message(
    InMainGroups(),
    Command("shis_friends", "shisfriend", "shis_friend", "друзья_шишки", prefix="!/")
)
async def send_random_friend_cat(message: Message) -> None:
    """Send a random photo/animation of one of Shishka's cat friends."""
    try:
        media_list = await CatPhoto.objects.filter(category=CATEGORY_FRIEND).all()

        if not media_list:
            await message.answer(
                "🐾 В базе пока нет фото друзей Шишки! "
                "Добавьте первое командой /add_shis_friend (админ) "
                "или предложите своё через !submit_shis_friend"
            )
            return

        media = random.choice(media_list)
        caption = "🐾 Друг Шишки!"
        if media.description:
            caption += f"\n📝 {media.description}"

        if media.media_type == 'animation':
            await message.answer_animation(animation=media.file_id, caption=caption)
            logger.info(f"🎬 Отправлена гифка друга Шишки #{media.id}")
        else:
            await message.answer_photo(photo=media.file_id, caption=caption)
            logger.info(f"📸 Отправлено фото друга Шишки #{media.id}")

    except Exception as e:
        logger.error(f"Error sending friend cat media: {e}")
        await message.answer("🐾 Что-то пошло не так... Попробуйте позже.")


async def is_chat_admin(message: Message) -> bool:
    """Проверяет, является ли пользователь администратором чата."""
    try:
        # Проверяем обычного пользователя
        member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status in ['administrator', 'creator']:
            return True

        # Проверяем анонимного админа (sender_chat)
        if message.sender_chat:
            try:
                sender_member = await message.bot.get_chat_member(message.chat.id, message.sender_chat.id)
                if sender_member.status in ['administrator', 'creator']:
                    return True
            except:
                pass

        return False
    except Exception as e:
        logger.error(f"Ошибка проверки прав: {e}")
        return False


def _extract_reply_media(reply: Message) -> tuple[str, str, str] | None:
    """Return (media_type, file_id, file_unique_id) from a reply, or None."""
    if reply.photo:
        photo = reply.photo[-1]
        return 'photo', photo.file_id, photo.file_unique_id
    if reply.animation:
        animation = reply.animation
        return 'animation', animation.file_id, animation.file_unique_id
    return None


async def _add_cat_media(message: Message, category: str, command_name: str) -> None:
    """Add a cat photo or animation to the database (admin only)."""
    if not await is_chat_admin(message):
        await message.answer("❌ Только администраторы могут добавлять фото!")
        return

    try:
        logger.info(f"🔍 Начало добавления медиа ({category}) от {message.from_user.id}")

        if not message.reply_to_message:
            await message.answer(f"🐱 Ответьте на **фото** или **гифку** командой /{command_name}")
            return

        extracted = _extract_reply_media(message.reply_to_message)
        if extracted is None:
            await message.answer("❌ Пожалуйста, ответьте на **фото** или **гифку** (анимацию)")
            return
        media_type, file_id, file_unique_id = extracted

        from ormar.exceptions import NoMatch
        try:
            existing = await CatPhoto.objects.filter(file_unique_id=file_unique_id).first()
            if existing:
                await message.answer(f"🐱 Это {media_type} уже есть в базе! (ID: {existing.id})")
                return
        except NoMatch:
            pass

        description = None
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            description = parts[1]

        new_media = await CatPhoto.objects.create(
            file_id=file_id,
            file_unique_id=file_unique_id,
            added_by=message.from_user.id,
            description=description,
            media_type=media_type,
            category=category,
        )

        record_metric("cat_photos_added")
        media_emoji = "🎬" if media_type == 'animation' else CATEGORY_EMOJI[category]
        label = CATEGORY_LABELS[category]
        await message.answer(
            f"{media_emoji} {label.capitalize()} #{new_media.id} добавлен(а) в базу!\n"
            f"📝 Описание: {description or 'нет'}"
        )

    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении медиа ({category}): {e}", exc_info=True)
        await message.answer(f"❌ Не удалось добавить медиа. Ошибка: {e}")


@router.message(
    InMainGroups(),
    Command("add_shishka", prefix="!/")
)
async def add_cat_media(message: Message) -> None:
    """Add a Shishka photo/animation to the database (admin only)."""
    await _add_cat_media(message, CATEGORY_SHISHKA, "add_shishka")


@router.message(
    InMainGroups(),
    Command("add_shis_friend", prefix="!/")
)
async def add_friend_cat_media(message: Message) -> None:
    """Add a photo/animation of one of Shishka's cat friends (admin only)."""
    await _add_cat_media(message, CATEGORY_FRIEND, "add_shis_friend")


### USER SUBMISSIONS (moderation queue) ###

def _submission_keyboard(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"catsub_ok_{key}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"catsub_no_{key}"),
        ]
    ])


async def _submit_cat_media(message: Message, category: str, command_name: str) -> None:
    """Queue a user-submitted photo/animation for admin approval."""
    if not message.reply_to_message:
        await message.answer(
            f"🐱 Ответьте на **фото** или **гифку** командой /{command_name}, "
            f"чтобы предложить её на модерацию."
        )
        return

    extracted = _extract_reply_media(message.reply_to_message)
    if extracted is None:
        await message.answer("❌ Пожалуйста, ответьте на **фото** или **гифку** (анимацию)")
        return
    media_type, file_id, file_unique_id = extracted

    from ormar.exceptions import NoMatch
    try:
        existing = await CatPhoto.objects.filter(file_unique_id=file_unique_id).first()
        if existing:
            await message.answer(f"🐱 Это уже есть в базе! (ID: {existing.id})")
            return
    except NoMatch:
        pass

    description = None
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1:
        description = parts[1]

    review_chat_id = config.groups.reports or config.groups.logs
    if not review_chat_id:
        await message.answer("❌ Очередь модерации не настроена (нет reports/logs чата). Сообщите админу.")
        return

    key = queue_submission(
        file_id=file_id,
        file_unique_id=file_unique_id,
        media_type=media_type,
        category=category,
        description=description,
        submitted_by=message.from_user.id,
    )

    label = CATEGORY_LABELS[category]
    caption = (
        f"🆕 Предложено фото на модерацию ({label})\n\n"
        f"<i>От:</i> {user_mention(message.from_user)}\n"
        f"<i>Чат:</i> {message.chat.title or message.chat.id}\n"
        f"<i>Описание:</i> {description or 'нет'}"
    )

    try:
        if media_type == 'animation':
            await message.bot.send_animation(
                review_chat_id, file_id, caption=caption, reply_markup=_submission_keyboard(key)
            )
        else:
            await message.bot.send_photo(
                review_chat_id, file_id, caption=caption, reply_markup=_submission_keyboard(key)
            )
    except Exception:
        logger.exception("Failed to send cat submission to review chat")
        pop_submission(key)
        await message.answer("❌ Не удалось отправить на модерацию. Попробуйте позже.")
        return

    await message.answer(f"✅ Спасибо! Ваше фото ({label}) отправлено на модерацию.")


@router.message(
    InMainGroups(),
    Command("submit_shishka", prefix="!/")
)
async def submit_shishka(message: Message) -> None:
    """Any user can propose a Shishka photo for admin approval."""
    await _submit_cat_media(message, CATEGORY_SHISHKA, "submit_shishka")


@router.message(
    InMainGroups(),
    Command("submit_shis_friend", prefix="!/")
)
async def submit_shis_friend(message: Message) -> None:
    """Any user can propose a cat-friend photo for admin approval."""
    await _submit_cat_media(message, CATEGORY_FRIEND, "submit_shis_friend")


@router.message(
    InMainGroups(),
    Command("del_shishka", prefix="!/")
)
async def delete_cat_media(message: Message, command: CommandObject = None) -> None:
    """Delete a cat media from the database (admin only)."""
    # Проверяем права администратора
    if not await is_chat_admin(message):
        await message.answer("❌ Только администраторы могут удалять фото!")
        return

    try:
        if not command or not command.args:
            await message.answer(
                "🐱 Укажите ID медиа для удаления:\n"
                "`/del_shishka 5`\n"
                "Чтобы узнать ID, используйте команду `/list_shishka`"
            )
            return

        try:
            media_id = int(command.args.split()[0])
        except ValueError:
            await message.answer("❌ ID должен быть числом!")
            return

        from ormar.exceptions import NoMatch
        try:
            media = await CatPhoto.objects.filter(id=media_id).first()
        except NoMatch:
            media = None
        if not media:
            await message.answer(f"❌ Медиа с ID {media_id} не найдено.")
            return

        media_type = media.media_type
        category = media.category
        await media.delete()

        media_emoji = "🎬" if media_type == 'animation' else CATEGORY_EMOJI.get(category, "📸")
        await message.answer(f"{media_emoji} Медиа #{media_id} удалено из базы.")

    except Exception as e:
        logger.error(f"Error deleting cat media: {e}")
        await message.answer("❌ Не удалось удалить медиа.")


@router.message(
    InMainGroups(),
    Command("list_shishka", prefix="!/")
)
async def list_cat_media(message: Message) -> None:
    """List all cat media in the database (admin only)."""
    # Проверяем права администратора
    if not await is_chat_admin(message):
        await message.answer("❌ Только администраторы могут просматривать список!")
        return

    try:
        media_list = await CatPhoto.objects.all()

        if not media_list:
            await message.answer("🐱 В базе нет медиа Шишки.")
            return

        # Группируем по типу и категории
        photos = [m for m in media_list if m.media_type == 'photo']
        animations = [m for m in media_list if m.media_type == 'animation']
        shishka_count = sum(1 for m in media_list if m.category == CATEGORY_SHISHKA)
        friend_count = sum(1 for m in media_list if m.category == CATEGORY_FRIEND)

        text = "📸 <b>Медиа Шишки в базе:</b>\n\n"
        text += f"📸 Фото: {len(photos)}\n"
        text += f"🎬 Гифки: {len(animations)}\n"
        text += f"🐱 Шишка: {shishka_count}\n"
        text += f"🐾 Друзья: {friend_count}\n"
        text += f"📊 Всего: {len(media_list)}\n\n"

        # Показываем последние 10
        text += "<b>Последние 10:</b>\n"
        for media in sorted(media_list, key=lambda x: x.id, reverse=True)[:10]:
            type_emoji = "🎬" if media.media_type == 'animation' else "📸"
            cat_emoji = CATEGORY_EMOJI.get(media.category, "🐱")
            desc = media.description or "без описания"
            text += f"• #{media.id} {type_emoji}{cat_emoji} — {desc}\n"

        await message.answer(text)

    except Exception as e:
        logger.error(f"Error listing cat media: {e}")
        await message.answer("❌ Не удалось получить список медиа.")
