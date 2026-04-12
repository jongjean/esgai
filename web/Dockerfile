FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 정책 포트 4600 노출
EXPOSE 4600

# 정책 포트 4600으로 uvicorn 구동
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "4600"]
