# ---- تصویر پایه ----
FROM python:3.11-slim

# جلوگیری از پرامپت‌های تعاملی apt
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ffmpeg برای پردازش صوتی یوتیوب لازمه
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# نصب پکیج‌های پایتون (جدا از کپی کدها، برای کش بهتر لایه‌ها)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی سورس
COPY main.py .

# مسیر داده‌ی پایدار برای session و فایل‌های دانلودی موقت
RUN mkdir -p /app/data
ENV WORKDIR=/app/data

# اجرا با کاربر غیر روت (best practice امنیتی)
RUN useradd --create-home --shell /bin/bash botuser && \
    chown -R botuser:botuser /app
USER botuser

CMD ["python", "main.py"]
