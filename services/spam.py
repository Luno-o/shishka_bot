"""
Spam detection service using ML model.

Features:
- Lazy loading of ML models (faster startup)
- Quick substring check before expensive ML inference
- Auto-unload after TTL to save RAM
"""
from typing import Optional
import time
import gc

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import logging
logger = logging.getLogger(__name__)

MODEL_PATH = "./ruspam_model"

# lazy-loaded model and tokenizer
_tokenizer: Optional[AutoTokenizer] = None
_model: Optional[AutoModelForSequenceClassification] = None
_last_used: float = 0.0  # timestamp of last usage

# known spam substrings to check first (faster than ML)
SPAM_SUBSTRINGS = [
    "official_vpnbot",
    "rkt_vpn_bot",
    "vpnbot",
    "vpn_bot",
    "oflvpn"
]

# precompute lowercase versions for faster matching
_SPAM_SUBSTRINGS_LOWER = [s.lower() for s in SPAM_SUBSTRINGS]


def _get_tokenizer() -> AutoTokenizer:
    """Lazy load tokenizer on first use."""
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, local_files_only=True)
    return _tokenizer


def _get_model() -> AutoModelForSequenceClassification:
    """Lazy load model on first use."""
    global _model
    if _model is None:
        _model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH, local_files_only=True)
        _model.eval()  # Set to evaluation mode
    return _model


def _touch() -> None:
    """Update last used timestamp."""
    global _last_used
    _last_used = time.time()


import asyncio

async def predict_async(text: str) -> bool:
    """
    Асинхронная обёртка для predict.
    Используется в асинхронном коде для вызова синхронной ML-функции.
    """
    logger.debug(f"🔍 Асинхронная проверка спама: {text[:50]}...")
    try:
        # Запускаем синхронную функцию в отдельном потоке
        result = await asyncio.to_thread(predict, text)
        logger.debug(f"🔍 Результат: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Ошибка в predict_async: {e}")
        return False  # В случае ошибки считаем, что это не спам


def preload_model() -> None:
    """
    Preload the ML model (call during startup if you want eager loading).
    Useful if you want to avoid latency on first spam check.
    """
    _get_tokenizer()
    _get_model()
    _touch()


def unload_model() -> bool:
    """Free memory by unloading model."""
    global _model, _tokenizer, _last_used
    
    if _model is None and _tokenizer is None:
        return False
    
    _model = None
    _tokenizer = None
    _last_used = 0.0
    gc.collect()
    return True


def is_loaded() -> bool:
    """Check if model is currently loaded."""
    return _model is not None


def get_last_used() -> float:
    """Get timestamp of last model usage."""
    return _last_used
# ===== ДОБАВЛЯЕМ КЛАСС ДЛЯ СОВМЕСТИМОСТИ =====
class SpamDetector:
    """
    Wrapper class for spam detection.
    Provides compatibility with imports expecting a class.
    """
    
    def __init__(self):
        """Initialize spam detector."""
        pass
    
    @staticmethod
    def predict(text: str) -> bool:
        """
        Predict if text is spam.
        
        Args:
            text: Text to check for spam
            
        Returns:
            True if spam, False otherwise
        """
        return predict(text)
    
    @staticmethod
    def preload():
        """Preload the ML model."""
        preload_model()
    
    @staticmethod
    def unload():
        """Unload the ML model to free memory."""
        unload_model()
    
    @staticmethod
    def is_loaded() -> bool:
        """Check if model is loaded."""
        return is_loaded()