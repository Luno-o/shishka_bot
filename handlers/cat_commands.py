import logging
import random
from aiogram import Router, F
from aiogram.types import Message, ContentType
from aiogram.filters import Command, CommandObject

from config import config
from db.models import CatPhoto
from filters import InMainGroups
from utils import get_string, user_mention, write_log

logger = logging.getLogger(__name__)
router = Router(name="cat_commands")

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
        media_list = await CatPhoto.objects.all()
        
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


@router.message(
    InMainGroups(),
    Command("add_shishka", prefix="!/")
)
async def add_cat_media(message: Message) -> None:
    """Add a cat photo or animation to the database (admin only)."""
    # Проверяем права администратора
    if not await is_chat_admin(message):
        await message.answer("❌ Только администраторы могут добавлять фото!")
        return
    
    try:
        logger.info(f"🔍 Начало добавления медиа от {message.from_user.id}")
        
        if not message.reply_to_message:
            logger.warning("Нет ответа на сообщение")
            await message.answer("🐱 Ответьте на **фото** или **гифку** командой /add_shishka")
            return
        
        reply = message.reply_to_message
        
        # Проверяем тип контента
        media_type = None
        file_id = None
        file_unique_id = None
        
        if reply.photo:
            media_type = 'photo'
            photo = reply.photo[-1]
            file_id = photo.file_id
            file_unique_id = photo.file_unique_id
            logger.info(f"📸 Получено фото: file_id={file_id[:20]}...")
        elif reply.animation:
            media_type = 'animation'
            animation = reply.animation
            file_id = animation.file_id
            file_unique_id = animation.file_unique_id
            logger.info(f"🎬 Получена гифка: file_id={file_id[:20]}...")
        else:
            await message.answer("❌ Пожалуйста, ответьте на **фото** или **гифку** (анимацию)")
            return
        
        # Проверяем, есть ли уже такое медиа
        from ormar.exceptions import NoMatch
        try:
            existing = await CatPhoto.objects.filter(file_unique_id=file_unique_id).first()
            if existing:
                logger.info("Медиа уже есть в базе")
                await message.answer(f"🐱 Это {media_type} уже есть в базе! (ID: {existing.id})")
                return
        except NoMatch:
            pass
        
        # Получаем описание
        description = None
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            description = parts[1]
            logger.info(f"📝 Описание: {description}")
        
        logger.info("💾 Сохранение в базу...")
        new_media = await CatPhoto.objects.create(
            file_id=file_id,
            file_unique_id=file_unique_id,
            added_by=message.from_user.id,
            description=description,
            media_type=media_type
        )
        
        media_emoji = "🎬" if media_type == 'animation' else "📸"
        logger.info(f"✅ Медиа сохранено! ID: {new_media.id}")
        await message.answer(
            f"{media_emoji} Шишка #{new_media.id} добавлена в базу!\n"
            f"📝 Описание: {description or 'нет'}"
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении медиа: {e}", exc_info=True)
        await message.answer(f"❌ Не удалось добавить медиа. Ошибка: {e}")


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
        
        media = await CatPhoto.objects.filter(id=media_id).first()
        if not media:
            await message.answer(f"❌ Медиа с ID {media_id} не найдено.")
            return
        
        media_type = media.media_type
        await media.delete()
        
        media_emoji = "🎬" if media_type == 'animation' else "📸"
        await message.answer(f"{media_emoji} Шишка #{media_id} удалена из базы.")
        
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
        
        # Группируем по типу
        photos = [m for m in media_list if m.media_type == 'photo']
        animations = [m for m in media_list if m.media_type == 'animation']
        
        text = "📸 <b>Медиа Шишки в базе:</b>\n\n"
        text += f"📸 Фото: {len(photos)}\n"
        text += f"🎬 Гифки: {len(animations)}\n"
        text += f"📊 Всего: {len(media_list)}\n\n"
        
        # Показываем последние 10
        text += "<b>Последние 10:</b>\n"
        for media in sorted(media_list, key=lambda x: x.id, reverse=True)[:10]:
            emoji = "🎬" if media.media_type == 'animation' else "📸"
            desc = media.description or "без описания"
            text += f"• #{media.id} {emoji} — {desc}\n"
        
        await message.answer(text)
        
    except Exception as e:
        logger.error(f"Error listing cat media: {e}")
        await message.answer("❌ Не удалось получить список медиа.")
