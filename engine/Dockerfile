FROM python:3.10-slim

WORKDIR /app

# PDF 생성 및 한글 폰트 지원을 위한 시스템 종속성 설치 (WeasyPrint 상용 수준 지원)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-cffi \
    python3-brotli \
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fontconfig \
    fonts-nanum \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 정책 포트 4610 노출
EXPOSE 4610

# 정책 포트 4610으로 uvicorn 구동
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "4610"]
