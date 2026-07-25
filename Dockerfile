# استفاده از نسخه سبک پایتون ۳.۱۱
FROM python:3.11-slim

# تنظیم دایرکتوری کاری
WORKDIR /app

# نصب ابزارهای مورد نیاز سیستم (FFmpeg و curl/unzip برای نصب Deno)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# نصب Deno (برای حل چالش JS یوتیوب توسط yt-dlp — حداقل نسخه‌ی موردنیاز یت‌دی‌ال‌پی)
RUN curl -fsSL https://deno.land/install.sh | sh -s -- -y
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

# کپی کردن فایل نیازمندی‌ها و نصب آن‌ها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی کردن تمام فایل‌های پروژه به داخل کانتینر
COPY . .

# اجرای ربات
CMD ["python3", "main.py"]
