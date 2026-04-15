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

# [REDIS] 전역 관리자
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_mgr = RedisManager(REDIS_URL)

# [MASTER-DEPLOY] 아키텍처 경로 설정
MASTER_DIR = "/app/master_downloads"   # /home/ucon/esgai/web/downloads (Persistent Master)
DEPLOY_DIR = "/app/deploy_downloads"   # /var/www/esgai/downloads (Volatile Public)
DB_PATH = "/app/leads.db"              # /home/ucon/esgai/engine/leads.db (Persistent)

@app.on_event("startup")
async def startup_event():
    await redis_mgr.ensure_connection()
    # 경로 보장
    for d in [MASTER_DIR, DEPLOY_DIR]:
        os.makedirs(d, exist_ok=True)
    # DB 초기화
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
        print(f"[DB] Error: {e}", flush=True)

# --- Logic Engines ---
generator = ESGGenerator()
rule_engine = ESGRuleEngine()
report_engine = ESGReportEngine(os.path.join(os.path.dirname(__file__), "templates"))

# --- Models ---
class AnalyzeRequest(BaseModel):
    company_name: str
    industry: str
    size: Optional[str] = None

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
            raise ValueError('Invalid email format')
        return v
    @validator('phone')
    def validate_phone(cls, v):
        if len(re.sub(r'[^0-9]', '', v)) < 9:
            raise ValueError('Phone number too short')
        return v

# --- API Endpoints ---

@app.post("/analyze")
async def analyze_esg(req: AnalyzeRequest):
    job_id = str(uuid.uuid4())
    payload = {"company_name": req.company_name, "industry": req.industry, "size": req.size, "stage": 1}
    await redis_mgr.enqueue_job(job_id, payload)
    return {"job_id": job_id, "status": "queued"}

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    status = await redis_mgr.get_job_status(job_id)
    if status == "done":
        result = await redis_mgr.client.get(f"result:{job_id}:draft") or await redis_mgr.client.get(f"result:{job_id}")
        return {"status": "done", "report": json.loads(result) if result else {}}
    return {"status": status}

@app.post("/analyze/deep")
async def analyze_deep(req: Request):
    data = await req.json()
    job_id = data.get("job_id")
    if not job_id: raise HTTPException(status_code=400, detail="Missing job_id")
    
    req_data = {"required": data.get("required") or {}, "options": data.get("options") or {}}
    base_result_str = await redis_mgr.client.get(f"result:{job_id}:draft") or await redis_mgr.client.get(f"result:{job_id}")
    if not base_result_str: raise HTTPException(status_code=404, detail="Stage 1 not found")
    
    base_data = json.loads(base_result_str)
    await redis_mgr.client.set(f"{redis_mgr.NS_REQ_DATA}{job_id}", json.dumps(req_data), ex=86400)
    await redis_mgr.set_job_status(job_id, "queued", force=True)
    
    payload = {
        "stage": 2, "company_name": base_data["company_name"], "industry": base_data["industry"],
        "size": base_data.get("size", ""), "step2_data": req_data, "raw_report": base_data.get("raw_report", "")
    }
    await redis_mgr.enqueue_job(job_id, payload)
    return {"status": "queued", "job_id": job_id}

@app.get("/status/deep/{job_id}")
async def get_deep_status(job_id: str):
    status = await redis_mgr.get_job_status(job_id)
    if status == "done":
        raw_res = await redis_mgr.client.get(f"{redis_mgr.NS_RESULT}{job_id}")
        if not raw_res: return {"status": "processing", "stage": 1}
        
        # [Single-Naming Mapping]
        friendly_name = await redis_mgr.client.get(f"dist_file:{job_id}:docx")
        if not friendly_name: return {"status": "processing", "stage": 2, "info": "Naming in progress..."}
        
        # 배포 폴더 확인 및 마스터 복구
        deploy_path = os.path.join(DEPLOY_DIR, friendly_name)
        if not os.path.exists(deploy_path):
            master_path = os.path.join(MASTER_DIR, friendly_name)
            if os.path.exists(master_path):
                shutil.copy2(master_path, deploy_path)
            else:
                return {"status": "processing", "stage": 2, "info": "Finalizing files..."}
        
        try:
            parsed = json.loads(raw_res)
            preview = parsed.get("raw_report") if isinstance(parsed, dict) else raw_res
        except: preview = raw_res

        return {
            "status": "done", "preview": preview, "stage": 2, "file_ready": True,
            "dist_docx": friendly_name, "dist_pdf": await redis_mgr.client.get(f"dist_file:{job_id}:pdf")
        }
    return {"status": status}

@app.post("/translate")
async def extract_translation(req: Request):
    try:
        data = await req.json()
        target_text = data.get("text", "")
        # company_name, industry, size 등도 활용 가능
        if not target_text:
            raise HTTPException(status_code=400, detail="Text is required")
            
        translated = await generator.translate_to_korean(target_text)
        return {"translated_text": translated}
    except Exception as e:
        print(f"[TRANSLATE ERROR] {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/download/{job_id}/{fmt}")
async def get_deep_status(job_id: str):
    status = await redis_mgr.get_job_status(job_id)
    if status == "done":
        raw_res = await redis_mgr.client.get(f"{redis_mgr.NS_RESULT}{job_id}")
        if not raw_res: return {"status": "processing", "stage": 1}
        
        # [Single-Naming Mapping]
        friendly_name = await redis_mgr.client.get(f"dist_file:{job_id}:docx")
        if not friendly_name: return {"status": "processing", "stage": 2, "info": "Naming in progress..."}
        
        # 배포 폴더 확인 및 마스터 복구
        deploy_path = os.path.join(DEPLOY_DIR, friendly_name)
        if not os.path.exists(deploy_path):
            master_path = os.path.join(MASTER_DIR, friendly_name)
            if os.path.exists(master_path):
                shutil.copy2(master_path, deploy_path)
            else:
                return {"status": "processing", "stage": 2, "info": "Finalizing files..."}
        
        try:
            parsed = json.loads(raw_res)
            preview = parsed.get("raw_report") if isinstance(parsed, dict) else raw_res
        except: preview = raw_res

        return {
            "status": "done", "preview": preview, "stage": 2, "file_ready": True,
            "dist_docx": friendly_name, "dist_pdf": await redis_mgr.client.get(f"dist_file:{job_id}:pdf")
        }
    return {"status": status}

@app.get("/download/{job_id}/{fmt}")
async def download_report(job_id: str, fmt: str):
    if fmt not in ["docx", "pdf"]: raise HTTPException(status_code=400)
    
    # [Single-Naming Resolution]
    friendly_name = await redis_mgr.client.get(f"dist_file:{job_id}:{fmt}")
    if not friendly_name: raise HTTPException(status_code=404, detail="Mapping not found")
    
    deploy_path = os.path.join(DEPLOY_DIR, friendly_name)
    if not os.path.exists(deploy_path):
        # Master Restore
        master_path = os.path.join(MASTER_DIR, friendly_name)
        if os.path.exists(master_path):
            shutil.copy2(master_path, deploy_path)
        else:
            raise HTTPException(status_code=404, detail="File missing from storage")

    media_type = "application/pdf" if fmt == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(
        deploy_path, media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(friendly_name)}", "Cache-Control": "no-cache"}
    )

@app.post("/api/leads")
async def save_lead(req: LeadRequest):
    try:
        user_input = await redis_mgr.client.get(f"{redis_mgr.NS_REQ_DATA}{req.job_id}") if req.job_id else None
        report_text = None
        if req.job_id:
            raw = await redis_mgr.client.get(f"{redis_mgr.NS_RESULT}{req.job_id}")
            if raw:
                try: report_text = json.loads(raw).get("raw_report") if isinstance(json.loads(raw), dict) else raw
                except: report_text = raw

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO leads (name, company, phone, email, job_id, consent_required, consent_marketing, source, stage3_data, report_content, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            req.name, req.company, req.phone, req.email, req.job_id,
            1 if req.consent_required else 0, 1 if req.consent_marketing else 0,
            req.source, user_input, report_text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit(); conn.close()
        return {"success": True}
    except Exception as e:
        print(f"[ERROR] {e}"); raise HTTPException(status_code=500)

@app.get("/api/admin/leads")
async def get_leads_admin():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    leads = [dict(r) for r in conn.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()]
    conn.close()
    return leads

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4610)
