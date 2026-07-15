# استفاده از نسخه سبک پایتون به عنوان ایمیج پایه
FROM python:3.10-slim

# نصب ابزار ffmpeg که برای تبدیل و استخراج صدا توسط yt-dlp حیاتی است
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# تعیین پوشه کاری داخل کانتینر
WORKDIR /app

# کپی کردن لیست نیازمندی‌ها
COPY requirements.txt .

# نصب کتابخانه‌های پایتون
RUN pip install --no-cache-dir -r requirements.txt

# کپی کردن کد اصلی ربات
COPY bot.py .

# دستور اجرای ربات هنگام روشن شدن کانتینر
CMD ["python", "bot.py"]
