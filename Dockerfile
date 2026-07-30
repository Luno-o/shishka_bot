FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# --- ИНИЦИАЛИЗАЦИЯ ---
# Копируем безопасный скрипт и entrypoint
COPY db_init_safe.py .
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
# ----------------------

# Create non-root user
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Используем entrypoint
ENTRYPOINT ["/entrypoint.sh"]