import logging
import random
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandObject

from config import config
from db.models import CatPhoto
from filters import InMainGroups, IsAdminFilter
from utils import get_string

logger = logging.getLogger(__name__)
router = Router(name="cat_commands")

# Все варианты команды "шишка" (регистр не важен)
CAT_COMMANDS = {
    # Основные
    "шишка", "shishka", "sishka", "сышка",
    "кошка", "cat", "кот", "котяра", "киса", "киска",
    
    # Уменьшительно-ласкательные
    "шишуля", "шишулька", "шишечка", "шишонок", "шиш", "шишик",
    "shishulya", "shishulka", "shishechka", "шишня", "пушишка", "пушня", "пух"
    
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
async def send_random_cat(message: Message) -> None:
    """Send a random cat photo from the database."""
    try:
        photos = await CatPhoto.objects.all()
        
        if not photos:
            await message.answer("🐱 В базе пока нет фотографий Шишки! Добавьте первую командой /add_shishka")
            return
        
        photo = random.choice(photos)
        caption = f"🐱 Шишка! #{photo.id}"
        if photo.description:
            caption += f"\n📝 {photo.description}"
        
        await message.answer_photo(photo=photo.file_id, caption=caption)
        
    except Exception as e:
        logger.error(f"Error sending cat photo: {e}")
        await message.answer("🐱 Что-то пошло не так... Попробуйте позже.")

@router.message(
    InMainGroups(),
    IsAdminFilter(),
    Command("add_shishka", prefix="!/")
)
async def add_cat_photo(message: Message) -> None:
    """Add a cat photo to the database (admin only)."""
    try:
        logger.info("🔍 Начало добавления фото")
        
        if not message.reply_to_message:
            logger.warning("Нет ответа на сообщение")
            await message.answer("🐱 Ответьте на фото командой /add_shishka")
            return
            
        if not message.reply_to_message.photo:
            logger.warning("Ответ не содержит фото")
            await message.answer("🐱 Ответьте на ФОТО командой /add_shishka")
            return
        
        photo = message.reply_to_message.photo[-1]
        logger.info(f"📸 Получено фото: file_id={photo.file_id[:20]}...")
        
        # Проверяем, есть ли уже такое фото
        from ormar.exceptions import NoMatch
        try:
            existing = await CatPhoto.objects.filter(file_unique_id=photo.file_unique_id).first()
            if existing:
                logger.info("Фото уже есть в базе")
                await message.answer("🐱 Это фото уже есть в базе!")
                return
        except NoMatch:
            logger.info("Фото новое, сохраняем...")
            pass
        
        # Получаем описание
        description = None
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            description = parts[1]
            logger.info(f"📝 Описание: {description}")
        
        logger.info("💾 Сохранение в базу...")
        new_photo = await CatPhoto.objects.create(
            file_id=photo.file_id,
            file_unique_id=photo.file_unique_id,
            added_by=message.from_user.id,
            description=description
        )
        
        logger.info(f"✅ Фото сохранено! ID: {new_photo.id}")
        await message.answer(
            f"✅ Фото Шишки добавлено в базу!\n"
            f"🆔 ID: {new_photo.id}\n"
            f"📝 Описание: {description or 'нет'}"
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении фото: {e}", exc_info=True)
        await message.answer(f"❌ Не удалось добавить фото. Ошибка: {e}")

@router.message(
    InMainGroups(),
    IsAdminFilter(),
    Command("del_shishka", prefix="!/")
)
async def delete_cat_photo(message: Message, command: CommandObject = None) -> None:
    """Delete a cat photo from the database (admin only)."""
    try:
        if not command or not command.args:
            await message.answer(
                "🐱 Укажите ID фото для удаления:\n"
                "`/del_shishka 5`\n"
                "Чтобы узнать ID, используйте команду `/list_shishka`"
            )
            return
        
        try:
            photo_id = int(command.args.split()[0])
        except ValueError:
            await message.answer("❌ ID должен быть числом!")
            return
        
        photo = await CatPhoto.objects.filter(id=photo_id).first()
        if not photo:
            await message.answer(f"❌ Фото с ID {photo_id} не найдено.")
            return
        
        await photo.delete()
        await message.answer(f"✅ Фото #{photo_id} удалено из базы.")
        
    except Exception as e:
        logger.error(f"Error deleting cat photo: {e}")
        await message.answer("❌ Не удалось удалить фото.")

@router.message(
    InMainGroups(),
    IsAdminFilter(),
    Command("list_shishka", prefix="!/")
)
async def list_cat_photos(message: Message) -> None:
    """List all cat photos in the database (admin only)."""
    try:
        photos = await CatPhoto.objects.all()
        
        if not photos:
            await message.answer("🐱 В базе нет фотографий Шишки.")
            return
        
        text = "📸 <b>Фото Шишки в базе:</b>\n\n"
        for photo in photos:
            desc = photo.description or "без описания"
            text += f"• #{photo.id} — {desc}\n"
        
        text += f"\n📊 Всего: {len(photos)} фото"
        await message.answer(text)
        
    except Exception as e:
        logger.error(f"Error listing cat photos: {e}")
        await message.answer("❌ Не удалось получить список фото.")