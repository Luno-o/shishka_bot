#!/bin/sh
set -e

echo "🚀 Запуск Шишка-бота..."

# Проверяем и создаем директорию для данных
mkdir -p /app/data 2>/dev/null || true

echo "📥 Проверка ML-моделей..."
python download_model.py || echo "⚠️ Ошибка при скачивании моделей, но продолжаем..."

echo "🤖 Запуск Шишка-бота..."
exec python -m bot
