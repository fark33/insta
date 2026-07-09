FROM python:3.11-slim

WORKDIR /app

# ابزارهای لازم برای build کردن tgcrypto
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# پورتی که health check روش انجام می‌شه
EXPOSE 8000

ENV PORT=8000

CMD ["python", "bot.py"]
