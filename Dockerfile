# Cloud Run용 Dockerfile - Playwright + Chromium 포함
FROM python:3.11-slim

# 시스템 의존성 설치 (Playwright/Chromium용)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright 브라우저 설치
RUN playwright install chromium
RUN playwright install-deps chromium

# 소스 코드 복사
COPY src/ ./src/
COPY main.py .
COPY server.py .

# 데이터 디렉토리 생성
RUN mkdir -p /app/data

# 환경 변수 기본값
ENV STORAGE_TYPE=supabase
ENV SCRAPE_DELAY_SECONDS=2.0
ENV PORT=8080

# Cloud Run 진입점
CMD ["python", "server.py"]
