FROM python:3.11-slim

# تثبيت FFmpeg والأدوات المطلوبة
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libfontconfig1 \
    fonts-arial \
    fonts-noto-core \
    fonts-noto-cjk \
    git \
    && rm -rf /var/lib/apt/lists/*

# تثبيت خطوط عربية
RUN apt-get update && apt-get install -y fonts-arabeyes fonts-sil-scheherazade || true \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

CMD ["python", "bot.py"]
