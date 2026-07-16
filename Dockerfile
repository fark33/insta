FROM python:3.11-slim

# جلوگیری از سوالات تعاملی apt در حین build
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# نصب ffmpeg (برای استخراج/تبدیل صدا) و aria2 (برای دانلود چندکانکشنه)
# این دو مورد روی ایمیج پایه پایتون پیش‌فرض نصب نیستن و علت اصلی
# ارور دادن ربات وقتی از کولب خارج میشه همین هستن.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        aria2 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# کپی و نصب وابستگی‌های پایتون
COPY requirements.txt .

# --upgrade تضمین می‌کنه yt-dlp همیشه آخرین نسخه‌ی موجود در PyPI نصب بشه
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --upgrade -r requirements.txt

# کپی کد اصلی ربات
COPY main.py .

# اجرای ربات
CMD ["python", "main.py"]
