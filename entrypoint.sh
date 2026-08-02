#!/bin/sh
set -e

echo "🚀 Запуск процесса инициализации Шишка-бота..."

# Проверяем и создаем директорию для данных
mkdir -p /app/data 2>/dev/null || true

echo "📥 Проверка ML-моделей..."
python download_model.py || echo "⚠️ Ошибка при скачивании моделей, но продолжаем..."

echo "🗄️ Проверка и создание таблиц БД..."
python db_init_safe.py

echo "🤖 Запуск Шишка-бота..."
exec python bot.py