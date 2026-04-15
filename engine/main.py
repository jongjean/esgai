from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, validator
import os
import uuid
import json
import traceback
import sqlite3
import re
from datetime import datetime
import shutil
from urllib.parse import quote
from dotenv import load_dotenv
import asyncio
import hashlib

from generator import ESGGenerator
from rules import ESGRuleEngine
from infra.redis_mgr import RedisManager
from infra.report_engine import ESGReportEngine

load_dotenv()

app = FastAPI(title="ESG AI SaaS Production Engine")

# [PHASE 1] DB 및 경로 초기화
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DOWNLOAD_DIR = "/app/downloads"
DB_PATH = "/app/leads.db"

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

redis_mgr = RedisManager(REDIS_URL)
generator = ESGGenerator()
rule_engine = ESGRuleEngine()
report_engine = ESGReportEngine(TEMPLATE_DIR)

@app.on_event("startup")
async def startup_event():
    # [Resilience] Redis 준비 대기
    await redis_mgr.ensure_connection()
    
    # [PHASE 1] Lead DB 스키마 초기화
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                company TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT NOT NULL,
                job_id TEXT,
                consent_required INTEGER DEFAULT 1,
                consent_marketing INTEGER DEFAULT 0,
                source TEXT,
                stage3_data TEXT,
                report_content TEXT,
                created_at TEXT
            )
        """)
        conn.commit()
        conn.close()
        print(f"[DB] Leads database initialized at {DB_PATH}", flush=True)
    except Exception as e:
        print(f"[DB] Error initializing leads database: {e}", flush=True)

# --- Models ---

class AnalyzeRequest(BaseModel):
    company_name: str
    industry: str
    size: Optional[str] = None

class TranslateRequest(BaseModel):
    text: str
    company_name: str = "기업"
    industry: str = ""
    size: str = ""
    job_id: Optional[str] = None

class LeadRequest(BaseModel):
    name: str
    company: str
    phone: str
    email: str
    job_id: Optional[str] = None
    consent_required: bool = True
    consent_marketing: bool = False
    source: str = "download"
    stage3_data: Optional[str] = None

    @validator('email')
    def validate_email(cls, v):
        if not re.match(r"^[a-zA-Z0-9._+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", v):
            raise ValueError('올바른 이메일 형식이 아닙니다.')
        return v

    @validator('phone')
    def validate_phone(cls, v):
        clean_phone = re.sub(r'[^0-9]', '', v)
        if len(clean_phone) < 9:
            raise ValueError('전화번호가 너무 짧습니다.')
        return v

# --- API Endpoints ---

@app.post("/analyze")
async def analyze_esg(req: AnalyzeRequest):
    # [Milestone 4] Redis Caching (Stage 1)
    is_premium = getattr(req, 'is_premium', False)
    if not is_premium:
        raw_key = f"{req.company_name}_{req.industry}_{req.size}_stage1"
        cache_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
        cached_job_id = await redis_mgr.client.get(f"cache:stage1:{cache_hash}")
        if cached_job_id:
            # 상태가 done인지 확인
            st = await redis_mgr.get_job_status(cached_job_id)
            if st == "done":
                print(f"[CACHE HIT] Stage 1 reused job: {cached_job_id}")
                return {"job_id": cached_job_id, "status": "queued"}

    job_id = str(uuid.uuid4())
    
    if not is_premium:
        raw_key = f"{req.company_name}_{req.industry}_{req.size}_stage1"
        cache_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
        # 24시간 TTL
        await redis_mgr.client.set(f"cache:stage1:{cache_hash}", job_id, ex=86400)

    payload = {
        "company_name": req.company_name,
        "industry": req.industry,
        "size": req.size,
        "stage": 1
    }
    await redis_mgr.enqueue_job(job_id, payload)
    return {"job_id": job_id, "status": "queued"}

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    status = await redis_mgr.get_job_status(job_id)
    if status == "done":
        result = await redis_mgr.client.get(f"result:{job_id}:draft")
        if not result:
            result = await redis_mgr.client.get(f"result:{job_id}")
        return {"status": "done", "report": json.loads(result) if result else {}}
    return {"status": status}

@app.post("/translate")
async def extract_translation(req: Request):
    try:
        data = await req.json()
        target_text = data.get("text", "")
        
        # [Milestone 4] Redis Caching (Stage 2 - Translation)
        cache_hash = hashlib.sha256(target_text.encode('utf-8')).hexdigest()
        cached_trans = await redis_mgr.client.get(f"cache:trans:{cache_hash}")
        if cached_trans:
            print("[CACHE HIT] Translation reused")
            return {"translated_text": cached_trans}

        # Stage 2: Translate the draft strictly (No Markdown)
        translated = await generator.translate_to_korean(target_text)
        
        # Cache the translation for 1 hour
        await redis_mgr.client.set(f"cache:trans:{cache_hash}", translated, ex=3600)
        
        return {"translated_text": translated}
    except Exception as e:
        print(f"❌ Translation API Error: {str(e)}", flush=True)
        return {"translated_text": "현장에서 한국어 렌더링에 실패했습니다. 다음 단계로 넘어가 조회를 계속해 주세요."}

@app.post("/analyze/deep")
async def analyze_deep(req: Request):
    try:
        data = await req.json()
        job_id = data.get("job_id")
        
        if not job_id:
            raise HTTPException(status_code=400, detail="job_id가 누락되었습니다.")

        required_data = data.get("required") or {}
        options_data = data.get("options") or {}
        
        req_data = {
            "required": required_data,
            "options": options_data
        }
        
        base_result_str = await redis_mgr.client.get(f"result:{job_id}:draft")
        if not base_result_str:
            base_result_str = await redis_mgr.client.get(f"result:{job_id}")
            
        if not base_result_str:
            raise HTTPException(status_code=404, detail="기존 1단계 분석 결과를 찾을 수 없습니다.")
        
        base_data = json.loads(base_result_str)
        company = base_data.get("company_name", "기업")
        industry = base_data.get("industry", "산업")
        size = base_data.get("size", "")

        await redis_mgr.client.set(f"{redis_mgr.NS_REQ_DATA}{job_id}", json.dumps(req_data), ex=86400)
        await redis_mgr.set_job_status(job_id, "queued", force=True)
        
        # [Milestone 4] Redis Caching (Stage 2)
        is_premium = data.get("is_premium", False)
        if not is_premium:
            answers_str = json.dumps(req_data, sort_keys=True)
            raw_key = f"{company}_{industry}_{size}_stage2_{answers_str}"
            cache_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
            cached_job_id = await redis_mgr.client.get(f"cache:stage2:{cache_hash}")
            
            if cached_job_id:
                st = await redis_mgr.get_job_status(cached_job_id)
                if st == "done":
                    res = await redis_mgr.client.get(f"{redis_mgr.NS_RESULT}{cached_job_id}")
                    if res:
                        try:
                            # 기존 결과 파일과 데이터를 현재 job_id로 복제 (무료 이용자 중복 방어)
                            shutil.copy(os.path.join(DOWNLOAD_DIR, f"{cached_job_id}.docx"), os.path.join(DOWNLOAD_DIR, f"{job_id}.docx"))
                            shutil.copy(os.path.join(DOWNLOAD_DIR, f"{cached_job_id}.pdf"), os.path.join(DOWNLOAD_DIR, f"{job_id}.pdf"))
                            
                            await redis_mgr.client.set(f"{redis_mgr.NS_RESULT}{job_id}", res)
                            await redis_mgr.client.set(f"file_ready:{job_id}", "true")
                            await redis_mgr.client.set(f"dist_file:{job_id}:docx", await redis_mgr.client.get(f"dist_file:{cached_job_id}:docx") or "")
                            await redis_mgr.client.set(f"dist_file:{job_id}:pdf", await redis_mgr.client.get(f"dist_file:{cached_job_id}:pdf") or "")
                            await redis_mgr.set_job_status(job_id, "done")
                            print(f"[CACHE HIT] Stage 2 reused job: {cached_job_id} for {job_id}")
                            return {"status": "queued", "job_id": job_id}
                        except Exception as ce:
                            print(f"[CACHE ERROR] Restore failed: {ce}")
                            # fallback to queue
            
            # 캐시가 없으면 현재 job_id 등록해두고 생성
            await redis_mgr.client.set(f"cache:stage2:{cache_hash}", job_id, ex=86400)

        payload = {
            "stage": 2,
            "company_name": company,
            "industry": industry,
            "size": size,
            "step2_data": req_data,
            "raw_report": base_data.get("raw_report", "")
        }
        await redis_mgr.enqueue_job(job_id, payload)
        print(f"[API] Deep Analysis Queued for Job: {job_id}", flush=True)
        return {"status": "queued", "job_id": job_id}
    except Exception as e:
        print(f"[API] Deep Analysis Error: {e}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/deep/{job_id}")
async def get_deep_status(job_id: str):
    status = await redis_mgr.get_job_status(job_id)
    if status == "done":
        raw_preview = await redis_mgr.client.get(f"{redis_mgr.NS_RESULT}{job_id}")
        is_ready = await redis_mgr.client.get(f"file_ready:{job_id}")
        
        if not raw_preview:
             return {"status": "processing", "stage": 1}
             
        file_path = os.path.join(DOWNLOAD_DIR, f"{job_id}.docx")
        if not os.path.exists(file_path):
             return {"status": "processing", "stage": 2, "info": "Finalizing file..."}
        
        try:
            parsed = json.loads(raw_preview)
            if isinstance(parsed, dict) and "raw_report" in parsed:
                clean_preview = parsed["raw_report"]
            else:
                clean_preview = raw_preview
        except:
            clean_preview = raw_preview

        dist_docx = await redis_mgr.client.get(f"dist_file:{job_id}:docx")
        dist_pdf  = await redis_mgr.client.get(f"dist_file:{job_id}:pdf")

        return {
            "status": "done", 
            "preview": clean_preview, 
            "stage": 2,
            "file_ready": is_ready == "true",
            "dist_docx": dist_docx,
            "dist_pdf": dist_pdf
        }
    elif status == "failed":
        return {"status": "failed"}
    return {"status": status if status != "not_found" else "queued"}

@app.get("/download/{job_id}/{fmt}")
async def download_report(job_id: str, fmt: str):
    if fmt not in ["docx", "pdf"]:
        raise HTTPException(status_code=400, detail="지원하지 않는 포맷입니다.")
    
    file_path = os.path.join(DOWNLOAD_DIR, f"{job_id}.{fmt}")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="리포트 파일이 아직 생성되지 않았습니다.")

    size1 = os.path.getsize(file_path)
    if size1 < 1024:
        raise HTTPException(status_code=500, detail="리포트 파일이 생성 중이거나 손상되었습니다.")
    
    await asyncio.sleep(0.05)
    size2 = os.path.getsize(file_path)
    
    if size1 != size2:
        raise HTTPException(status_code=503, detail="파일이 아직 동기화 중입니다. 잠시 후 다시 시도해주세요.")
        
    download_filename = await redis_mgr.client.get(f"dist_file:{job_id}:{fmt}")
    
    if not download_filename:
        company_name = "ESG"
        try:
            draft_str = await redis_mgr.client.get(f"{redis_mgr.NS_RESULT}{job_id}:draft")
            if draft_str:
                draft_data = json.loads(draft_str)
                company_name = draft_data.get("company_name", "ESG")
        except: pass
        download_filename = f"ESG_{company_name}.{fmt}"
    
    if fmt == "docx":
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        media_type = "application/pdf"
    
    encoded_filename = quote(download_filename)
    print(f"[DOWNLOAD] Serving Balanced File: {file_path} as {download_filename}", flush=True)
    
    return FileResponse(
        file_path, 
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "Cache-Control": "no-cache, no-store, must-revalidate"
        }
    )

# [PHASE 2] 리드 수집 API
@app.post("/api/leads")
async def save_lead(req: LeadRequest):
    try:
        # 1. Redis에서 Stage 3 데이터 (사용자 자가진단 답변) 추출 시도
        user_input = None
        if req.job_id:
            try:
                # req_data:{job_id} 키에 저장된 정보를 가져옴
                raw_input = await redis_mgr.client.get(f"{redis_mgr.NS_REQ_DATA}{req.job_id}")
                if raw_input:
                    user_input = raw_input
                    print(f"[API] Stage 3 data found for {req.job_id}", flush=True)
            except Exception as re:
                print(f"[API] Redis fetch error: {re}", flush=True)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO leads (name, company, phone, email, job_id, consent_required, consent_marketing, source, stage3_data, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            req.name,
            req.company,
            req.phone,
            req.email,
            req.job_id,
            1 if req.consent_required else 0,
            1 if req.consent_marketing else 0,
            req.source,
            user_input or req.stage3_data,
            await redis_mgr.client.get(f"{redis_mgr.NS_RESULT}{req.job_id}") if req.job_id else None,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        conn.close()
        print(f"[API] Lead saved: {req.email} (Source: {req.source})", flush=True)
        return {"success": True}
    except Exception as e:
        print(f"[API] Error saving lead: {e}", flush=True)
        raise HTTPException(status_code=500, detail="리드 정보를 저장하는 데 실패했습니다.")

@app.get("/api/admin/leads")
async def get_leads_admin():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads ORDER BY created_at DESC")
        rows = cursor.fetchall()
        leads = [dict(r) for r in rows]
        conn.close()
        return leads
    except Exception as e:
        print(f"[API] Admin error: {e}", flush=True)
        raise HTTPException(status_code=500, detail="리드 목록을 불러오지 못했습니다.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4610)
