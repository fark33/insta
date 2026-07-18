# استفاده از نسخه سبک پایتون ۳.۱۱
FROM python:3.11-slim

# تنظیم دایرکتوری کاری
WORKDIR /app

# نصب ابزارهای مورد نیاز سیستم (FFmpeg برای پردازش صدا ضروری است)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# کپی کردن فایل نیازمندی‌ها و نصب آن‌ها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی کردن تمام فایل‌های پروژه (شامل main.py و cookies.txt) به داخل کانتینر
COPY . .

# اجرای ربات
CMD ["python3", "main.py"]
