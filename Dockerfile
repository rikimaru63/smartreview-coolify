FROM python:3.11-slim

WORKDIR /app

# システムパッケージのインストール（PostgreSQL用にlibpq-devを追加）
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Pythonパッケージのインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードのコピー
COPY database.py .
COPY models.py .
COPY main_multi_platform.py .

# 環境変数設定
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# ポート設定
EXPOSE 8080

# アプリケーション起動
CMD ["python", "main_multi_platform.py"]
