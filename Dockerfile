# استفاده از نسخه‌ی دقیق پایتون ۳.۱۱.۹ (پایدار و کاملاً سازگار با Pyrogram)
FROM python:3.11.9-slim

# تنظیم مسیر کاری داخل کانتینر
WORKDIR /app

# نصب ابزارهای مورد نیاز برای کامپایل کتابخانه‌های C (مثل tgcrypto)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# کپی فایل requirements.txt و نصب وابستگی‌ها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی کل کد پروژه به داخل کانتینر
COPY . .

# اعلام پورتی که health check روی آن اجرا می‌شود
EXPOSE 8000

# متغیرهای محیطی پیش‌فرض (قابل بازنویسی در Render)
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

# دستور اجرای ربات (بدون -u برای جلوگیری از مشکلات احتمالی)
CMD ["python", "bot.py"]
