FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies (tzdata is pinned in requirements.txt)
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Копируем скрипт запуска и делаем entrypoint исполняемым
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Создаем пользователя и все необходимые директории с правильными правами
RUN useradd -m -u 1000 botuser && \
    mkdir -p /app/data && \
    touch /app/data/db.sqlite && \
    chown -R botuser:botuser /app && \
    chmod 755 /app && \
    chmod 755 /app/data && \
    chmod 644 /app/data/db.sqlite

# Переключаемся на пользователя
USER botuser

ENTRYPOINT ["/entrypoint.sh"]
