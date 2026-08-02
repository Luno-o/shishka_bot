"""
Profanity detection service using censure library.
"""
import sys
import re
import unicodedata

# path setup is centralized in services/__init__.py, guard for direct imports
if "./libs" not in sys.path:
    sys.path.insert(0, "./libs")

from libs.censure import Censor
from services.spam import SpamDetector

# Create censor instances for different languages
censor_ru = Censor.get(lang='ru')
censor_en = Censor.get(lang='en')

# Создаём экземпляр детектора спама (для ML детекции мата)
spam_detector = None  # Будет инициализирован при первом использовании


def get_spam_detector():
    """Ленивая инициализация спам-детектора."""
    global spam_detector
    if spam_detector is None:
        spam_detector = SpamDetector()
    return spam_detector


def advanced_text_cleaner(text: str) -> str:
    """
    Продвинутая очистка текста для детекции мата.
    Обрабатывает:
    - Пробелы между буквами
    - Замену кириллицы на латиницу и наоборот
    - Цифры вместо букв
    - Спецсимволы между буквами
    """
    # Приводим к нижнему регистру
    text = text.lower()
    
    # Словарь замен для русских букв
    russian_replacements = {
        'а': ['a', '@', '4'],
        'б': ['b', '6'],
        'в': ['b', 'v'],
        'г': ['r', 'g'],
        'д': ['d'],
        'е': ['e', '3'],
        'ё': ['e'],
        'ж': ['j', 'zh'],
        'з': ['z', '3'],
        'и': ['u', 'i', '1'],
        'й': ['u', 'i', 'j'],
        'к': ['k'],
        'л': ['l'],
        'м': ['m'],
        'н': ['h', 'n'],
        'о': ['o', '0'],
        'п': ['p'],
        'р': ['p', 'r'],
        'с': ['c', 's'],
        'т': ['t'],
        'у': ['y', 'u'],
        'ф': ['f'],
        'х': ['x', 'h'],
        'ц': ['c'],
        'ч': ['ch', '4'],
        'ш': ['sh', 'w'],
        'щ': ['sh', 'w'],
        'ъ': [''],
        'ы': ['y', 'i'],
        'ь': [''],
        'э': ['e'],
        'ю': ['u', 'yu'],
        'я': ['ya', 'y']
    }
    
    # Словарь замен для английских букв
    english_replacements = {
        'a': ['а', '@', '4'],
        'b': ['б', '6'],
        'c': ['с', 'ц'],
        'd': ['д'],
        'e': ['е', 'ё', '3'],
        'f': ['ф'],
        'g': ['г', 'ж'],
        'h': ['н', 'х'],
        'i': ['и', 'й', '1'],
        'j': ['ж', 'й'],
        'k': ['к'],
        'l': ['л'],
        'm': ['м'],
        'n': ['н'],
        'o': ['о', '0'],
        'p': ['п', 'р'],
        'q': ['к'],
        'r': ['р', 'г'],
        's': ['с', 'ш'],
        't': ['т'],
        'u': ['у', 'ю', 'и'],
        'v': ['в'],
        'w': ['ш', 'щ'],
        'x': ['х', 'кс'],
        'y': ['у', 'ы', 'й'],
        'z': ['з']
    }
    
    # Определяем язык текста
    lang = detect_name_language(text)
    
    # Заменяем символы на буквы
    if lang in ['russian', 'unknown']:
        for eng, rus_list in english_replacements.items():
            for rus in rus_list:
                text = text.replace(rus, eng)
    else:
        for rus, eng_list in russian_replacements.items():
            for eng in eng_list:
                text = text.replace(eng, rus)
    
    # Удаляем все небуквенные символы
    text = re.sub(r'[^a-zA-Zа-яА-ЯёЁ]', '', text)
    
    # Убираем повторяющиеся буквы (ааааа -> а)
    text = re.sub(r'(.)\1{2,}', r'\1', text)
    
    return text


def prepare_word(word: str) -> str:
    """Prepare word for profanity checking."""
    word = word.lower()
    word = word.strip()
    return censor_ru.prepare_word(word)


def detect_name_language(name: str) -> str:
    """
    Detects if a name is written in Russian or English.

    Returns:
        'russian', 'english', or 'unknown'
    """
    russian_chars = set('абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ')
    english_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')

    russian_count = sum(1 for char in name if char in russian_chars)
    english_count = sum(1 for char in name if char in english_chars)

    total_letters = russian_count + english_count

    if total_letters == 0:
        return 'unknown'
    elif russian_count > english_count:
        return 'russian'
    elif english_count > russian_count:
        return 'english'
    else:
        return 'unknown'


def check_profanity_censure(text: str, lang: str = "ru") -> tuple[bool, str | None, tuple]:
    """
    Check text for profanity using censure library (словарный метод).
    """
    _profanity_detected = False
    _word = None

    # Применяем очистку текста
    cleaned_text = advanced_text_cleaner(text)
    
    # Если после очистки текст пустой - пропускаем
    if len(cleaned_text) < 2:
        return False, None, (text, 0, 0, [], [])

    if lang == "ru" or lang == "russian":
        line_info = censor_ru.clean_line(cleaned_text)
    else:
        line_info = censor_en.clean_line(cleaned_text)

    if line_info[1] or line_info[2]:
        if line_info[1]:
            _word = line_info[3][0] if line_info[3] else "unknown"
        else:
            _word = line_info[4][0] if line_info[4] else "unknown"
        _profanity_detected = True

    return _profanity_detected, _word, line_info


async def check_profanity_ml(text: str) -> tuple[bool, str | None]:
    """
    Использует ML модель для детекции мата.
    Возвращает (обнаружен_мат, слово)
    """
    try:
        # Очищаем текст
        clean = advanced_text_cleaner(text)
        
        if len(clean) < 2:
            return False, None
        
        # Получаем детектор
        detector = get_spam_detector()
        
        # Проверяем через ML модель
        result = detector.predict(clean)
        
        # Проверяем, является ли спамом или содержит мат
        # Можно настроить порог
        if hasattr(result, 'is_spam'):
            return result.is_spam, "ML_detected"
        elif hasattr(result, 'profanity_score'):
            return result.profanity_score > 0.5, "ML_detected"
        else:
            return False, None
    except Exception as e:
        print(f"ML profanity check error: {e}")
        return False, None


async def check_for_profanity(text: str, lang: str = "ru") -> tuple[bool, str | None, tuple]:
    """
    Check text for profanity using multiple methods:
    1. Словарный метод (censure)
    2. ML метод (spam detector)
    """
    # Сначала проверяем словарным методом
    is_profane, word, line_info = check_profanity_censure(text, lang)
    
    # Если не нашли - проверяем ML
    if not is_profane:
        is_profane_ml, word_ml = await check_profanity_ml(text)
        if is_profane_ml:
            return True, word_ml, (text, 0, 0, [word_ml], [])
    
    return is_profane, word, line_info


async def check_for_profanity_all(text: str) -> tuple[bool, str | None]:
    """
    Check text for profanity in all supported languages.
    Использует комбинацию словарного и ML методов.

    Returns:
        Tuple of (is_profanity_detected, detected_word)
    """
    # Сначала словарный метод
    is_profane, word = False, None
    
    # Проверяем русский
    is_profane, word, _ = check_profanity_censure(text, lang="ru")
    
    if not is_profane:
        # Проверяем английский
        is_profane, word, _ = check_profanity_censure(text, lang="en")
    
    # Если словарный метод не нашёл - используем ML
    if not is_profane:
        is_profane_ml, word_ml = await check_profanity_ml(text)
        if is_profane_ml:
            return True, word_ml
    
    return is_profane, word


def check_name_for_violations(name: str) -> bool:
    """
    Check if a name contains violations (blacklisted words or profanity).

    Returns:
        True if name is clean, False if it contains violations.
    """
    blacklist_words = [
        "профиль",
        "посмотри",
        "кликай",
        "загляни",
        "проф"
    ]

    prepared_name = prepare_word(name)
    is_clean = not any(sub.lower() in prepared_name.lower() for sub in blacklist_words)

    profanity_detected, _, _ = check_profanity_censure(prepared_name, detect_name_language(name))

    return not profanity_detected and is_clean