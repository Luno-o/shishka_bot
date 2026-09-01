# 🐱 Шишка-бот Telegram
![Шишка-бот](https://i.imgur.com/S9BPDMt.jpeg "te")

Простой, но эффективный **автоматический модератор для Telegram**.  
С репортами, логами, фильтром мата, ИИ для анти-спама, обнаружением NSFW, системой репутации и не только :3

---

## Что умеет Шишка-бот?

- **Анти-спам**: ML-детекция спама от новых пользователей
- **Доверенные пользователи**: Участники с репутацией выше 10 не проходят автоматические проверки модерации
- **NSFW-детекция**: Проверка фото в чате и аватаров
- **Система репутации**: Пользователи получают репутацию за активность
- **Система репортов**: Пользователи могут жаловаться на сообщения админам
- **Плановые объявления**: Периодические автоматические сообщения
- **Анти-бот**: Автоматическое удаление ботов без прав администратора (с белым списком) 🆕
- **Система фото кошек**: Случайные фото Шишки с возможностью загрузки админами 🐱🆕
- **Шиш-таро**: Одна случайная Шишка закрепляется за пользователем на текущий день

---

## 🆕 Новые функции в этой версии

### 🐱 Команда `шишка`

Любой пользователь может получить случайное фото кошки из базы:

| Команда | Описание |
|---------|----------|
| `шишка` / `shishka` / `кошка` / `cat` | Случайное фото кошки 🐱 |
| `/add_shishka` | Добавить фото (ответом на фото) — админы |
| `/del_shishka <ID>` | Удалить фото по ID — админы |
| `/list_shishka` | Список всех фото — админы |
| `/shish_tarot` / `что у меня сегодня шишка` | Получить Шишку дня |
| `/help` / `шишка хэлп` / `шишка помоги` | Показать справку |

### 🛡️ Белый список ботов

Боты из белого списка **никогда не удаляются**, даже без прав администратора.

Настройка в `.env`:
```env
BOT_WHITELIST=123456789,987654321
👋 Приветствия с Шишкой
При входе нового пользователя:

Удаляется служебное сообщение

Отправляется случайное приветствие с упоминанием Шишки

Если в базе есть фото — отправляется случайное фото

Кнопки: 📋 Правила и 🐱 Ещё Шишку!

Структура кода
text
shishka-bot/
├── bot.py                 # Главная точка входа
├── config/
│   ├── __init__.py
│   ├── settings.py        # Pydantic конфигурация
│   └── config.toml        # Файл настроек
├── core/
│   ├── __init__.py
│   └── i18n.py            # Fluent интернационализация
├── db/
│   ├── __init__.py
│   ├── database.py        # Подключение, создание схемы и миграции БД
│   └── models/
│       ├── member.py      # Модель участника
│       ├── spam.py        # Модель спам-записи
│       └── cat_photo.py   # Модель фото кошки 🆕
├── filters/
│   ├── is_owner.py
│   ├── is_admin.py
│   ├── throttle.py
│   └── .. другие полезные фильтры
├── handlers/
│   ├── admin_actions.py   # Команды бана/разбана
│   ├── callbacks.py       # Обработчики инлайн-кнопок
│   ├── exceptions.py      # Обработчик ошибок
│   ├── group_events.py    # Основная обработка сообщений
│   ├── personal_actions.py# Пинг, проверка мата
│   ├── user_actions.py    # Команда репорта
│   └── cat_commands.py    # Команды для фото кошек 🆕
├── locales/
│   ├── en/
│   │   ├── strings.ftl    # Английские переводы
│   │   └── announcements.ftl
│   └── ru/
│       ├── strings.ftl    # Русские переводы
│       └── announcements.ftl
├── middlewares/
│   ├── __init__.py
│   ├── throttling.py      # Мидлварь для ограничения запросов
│   └── i18n.py            # I18n мидлварь
├── services/
│   ├── announcements.py   # Плановые объявления
│   ├── cache.py           # LRU кэширование
│   ├── gender.py          # Определение пола
│   ├── nsfw.py            # NSFW детекция
│   ├── profanity.py       # Детекция мата
│   ├── healthcheck.py     # Сервер healthcheck для оркестрации
│   ├── ml_manager.py      # Выгрузка неиспользуемых ML моделей
│   └── spam.py            # Спам-детекция
├── utils/
│   ├── helpers.py         # Вспомогательные функции
│   ├── enums.py           # Полезные енумы
│   └── localization.py    # Экспорты локализации
├── libs/                  # Внешние библиотеки (censure, gender_extractor)
├── ruspam_model/          # ML модель для спама (~328 MB)
├── nsfw_model/            # ML модель для NSFW (~3.55 GB) 🆕
├── requirements.txt
├── Dockerfile
├── config.py              # Конфигурация бота
├── download_model.py      # Скачивание спам-модели 🆕
├── nsfwmodel_down.py      # Скачивание NSFW-модели
├── tests/                 # Все автоматические тесты
└── .env.example
Интернационализация (i18n)
Бот использует Project Fluent для переводов.

Использование в обработчиках
python
# Способ 1: Импорт функции _ напрямую
from core.i18n import _

async def handler(message: Message) -> None:
    text = _("error-no-reply")
    await message.reply(text)

# Способ 2: Использование i18n из мидлвари (локаль пользователя)
async def handler(message: Message, i18n: Callable) -> None:
    text = i18n("error-no-reply")
    await message.reply(text)

# С переменными
text = _("report-message", date="2024-01-01", chat_id="123", msg_id="456")
Добавление новых переводов
Создайте/отредактируйте .ftl файлы в locales/{lang}/

Используйте ключи через дефис: error-no-reply

Переменные используют синтаксис { $var }

Пример locales/ru/strings.ftl:

fluent
error-no-reply = Эта команда должна быть ответом на сообщение!
report-message = 👆 Отправлено { $date }
    <a href="https://t.me/c/{ $chat_id }/{ $msg_id }">Перейти</a>

# Приветствия с Шишкой 🐱
welcome-v1 = 👋 { $username }, добро пожаловать! 🐱 Наша кошка Шишка уже ждёт новых друзей! 🎉
Установка
Требования
Python 3.11+

Токен бота от @BotFather

~4 ГБ свободного места для ML моделей

Процесс установки
Клонируйте репозиторий:

bash
git clone https://github.com/Luno-o/shishka_bot.git
cd shishka_bot
Создайте виртуальное окружение:

bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
Установите зависимости:

bash
pip install -r requirements.txt
Скопируйте .env.example в .env и заполните значения:

bash
cp .env.example .env
Настройте config.toml под свои нужды.

Скачайте ML модели (они НЕ включены в репозиторий):

bash
python download_model.py      # Спам-модель (~328 MB)
python nsfwmodel_down.py       # NSFW-модель

База данных и все миграции применяются автоматически при запуске бота.
Запустите бота:

bash
python bot.py
Переменные окружения в продакшене
bash
# Экспорт переменных напрямую
export BOT_TOKEN="your_bot_token"
export BOT_OWNER="your_user_id"
export GROUPS_MAIN="-1001234567890"
export BOT_WHITELIST="123456789,987654321"  # ID ботов, которых не трогать 🆕
export DB_URL="sqlite+aiosqlite:///data/db.sqlite"

# Или передача строкой
BOT_TOKEN="..." BOT_OWNER="..." python bot.py
Для systemd сервисов, добавьте их в unit файл:

ini
[Service]
Environment="BOT_TOKEN=your_token"
Environment="BOT_OWNER=123456789"
Environment="BOT_WHITELIST=123456789,987654321"
Для Docker, используйте флаги -e или --env-file:

bash
docker run -e BOT_TOKEN="..." -e BOT_OWNER="..." shishka-bot
# или
docker run --env-file .env shishka-bot
Инициализация базы данных

Создание таблиц и безопасные идемпотентные миграции выполняются одним вызовом
`db.init_db()` при старте. Существующие данные не удаляются.

Тесты

bash
python -m pip install -e ".[dev]"
python -m pytest
Docker
bash
docker build -t shishka-bot .
docker run -d --name shishka-bot -v $(pwd)/config.toml:/app/config.toml shishka-bot
Использование RAM
В данный момент бот использует ~800 МБ RAM для ML моделей и кэширования данных.
~~Возможно, мы могли бы снизить использование RAM, внедрив ONNX runtime модели, но это планы на будущее.~~
Это не сработало, единственное жизнеспособное решение — квантование моделей :3

Если ваш сервер не справляется и процесс убивается с ошибкой Out of memory, простое решение — добавить swap:

bash
# Создать swap файл на 2 ГБ
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile

# Сделать постоянным
echo '/swapfile none swap sw 0 0' >> /etc/fstab
Конфигурация
Переменные окружения
Переменная	Описание
BOT_TOKEN	Токен бота Telegram
BOT_OWNER	Telegram ID владельца
BOT_WHITELIST	ID ботов, которых никогда не удалять (через запятую) 🆕
GROUPS_MAIN	ID основной группы (можно через запятую)
GROUPS_REPORTS	ID группы для репортов
GROUPS_LOGS	ID группы для логов
LINKED_CHANNEL	ID связанного канала (можно через запятую)
DB_URL	URL базы данных
PROXY_URL	URL прокси (http/socks5)
PROXY_ENABLED	Включить прокси (true/false)
Встроенные команды
Пользовательские команды
Команда	Описание
!rules / /rules	Показать правила чата
!report / /report	Пожаловаться на сообщение (ответом)
!me / !info	Показать информацию о пользователе
!бу	Развлекательная команда (бот притворяется испуганным)
@admin	Вызвать внимание админов
шишка / shishka / кошка / cat	Случайное фото кошки 🐱🆕
Административные команды
Команда	Описание
!ban	Забанить пользователя (ответом)
!unban	Разбанить пользователя (ответом)
!ping	Проверить статус бота
!prof <текст>	Проверить текст на мат
/add_shishka	Добавить фото кошки (ответом на фото) 🆕
/del_shishka <ID>	Удалить фото кошки 🆕
/list_shishka	Список всех фото кошек 🆕
Команды владельца
Команда	Описание
!spam	Отметить сообщение как спам (ответом)
!reward <очки>	Добавить очки репутации
!punish <очки>	Отнять очки репутации
!setlvl <уровень>	Установить уровень пользователя
!rreset	Сбросить репутацию пользователя
!msg <текст>	Отправить сообщение от бота
!chatid	Получить ID текущего чата
!reload	Перезагрузить объявления из файлов локализации
!log <текст>	Записать тестовый лог
Внешние библиотеки
Бот использует две внешние библиотеки в папке libs/:

censure: Детекция мата (русский/английский)

gender_extractor: Определение пола по имени

Благодарности
https://github.com/masteroncluster/py-censure — Фильтр мата

https://github.com/MasterGroosha/telegram-report-bot — Система репортов

https://huggingface.co/RUSpam/spam_deberta_v4 — ML модель для спама

https://github.com/wwydmanski/gender-extractor — Определение пола

https://huggingface.co/prithivMLmods/siglip2-x256-explicit-content — NSFW модель

Авторы
Оригинальный Samurai
(C) 2026 Abraham Tugalov

Форк Шишка-бот
Luno-o — Система фото кошек, белый список ботов, улучшенные приветствия и многое другое!

Лицензия
MIT

Поддержка
По вопросам и предложениям: GitHub Issues

🐱 Удачи в модерации! И пусть Шишка всегда будет с тобой!
