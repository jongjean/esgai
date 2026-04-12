from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

import httpx
import os
import logging
import asyncio
from urllib.parse import quote

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("esgai_gateway")

app = FastAPI(title="esgai_web_gateway")

ENGINE_URL = os.getenv("ENGINE_URL", "http://engine:4610")
TIMEOUT_CONFIG = httpx.Timeout(180.0, connect=10.0)

# [Static Serving] 배포 폴더를 정적 경로로 마운트 (직접 다운로드 링크 지원)
if not os.path.exists("/app/downloads"):
    os.makedirs("/app/downloads", exist_ok=True)
app.mount("/downloads", StaticFiles(directory="/app/downloads"), name="downloads")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response

@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        resp = Response(content=f.read(), media_type="text/html")
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return resp

@app.post("/analyze")
async def request_analyze(data: dict):
    logger.info(f"Relaying /analyze to {ENGINE_URL}")
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            response = await client.post(f"{ENGINE_URL}/analyze", json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error in /analyze relay: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            response = await client.get(f"{ENGINE_URL}/status/{job_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error in /status relay: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/deep/{job_id}")
async def get_status_deep(job_id: str):
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            response = await client.get(f"{ENGINE_URL}/status/deep/{job_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/deep")
async def request_analyze_deep(data: dict):
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            response = await client.post(f"{ENGINE_URL}/analyze/deep", json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/translate")
async def request_translate(data: dict):
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            response = await client.post(f"{ENGINE_URL}/translate", json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{job_id}/{file_type}")
async def download_file(job_id: str, file_type: str, company: str = "ESG_Report"):
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            target_url = f"{ENGINE_URL}/download/{job_id}/{file_type}"
            # 엔진으로부터 파일을 스트림으로 가져옴
            async with client.stream("GET", target_url) as resp:
                resp.raise_for_status()
                
                # [Transparent Proxy] 엔진의 헤더를 가공 없이 '선택적'으로 전달하여 프로토콜 에러 방지
                headers = {}
                if "content-disposition" in resp.headers:
                    headers["Content-Disposition"] = resp.headers["content-disposition"]
                
                # media_type Fallback (None 방지)
                m_type = resp.headers.get("content-type") or "application/octet-stream"
                
                return StreamingResponse(
                    resp.aiter_bytes(),
                    media_type=m_type,
                    headers=headers
                )
        except Exception as e:
            logger.error(f"Download Error for {job_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"다운로드 중 오류가 발생했습니다: {str(e)}")
