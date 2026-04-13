from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import os
import uuid
import json
import traceback
from datetime import datetime
import shutil
from urllib.parse import quote
from dotenv import load_dotenv
import asyncio

from generator import ESGGenerator
from rules import ESGRuleEngine
from infra.redis_mgr import RedisManager
from infra.report_engine import ESGReportEngine

load_dotenv()

app = FastAPI(title="ESG AI SaaS Production Engine")

@app.on_event("startup")
async def startup_event():
    # [Resilience] Redis가 준비될 때까지 대기
    await redis_mgr.ensure_connection()


# 인프라 및 경로 초기화
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
# [SSOT] 모든 컴포넌트 간 통일된 배포 경로
DOWNLOAD_DIR = "/app/downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

redis_mgr = RedisManager(REDIS_URL)
generator = ESGGenerator()
rule_engine = ESGRuleEngine()
report_engine = ESGReportEngine(TEMPLATE_DIR)

class AnalyzeRequest(BaseModel):
    company_name: str
    industry: str
    size: Optional[str] = None

class TranslateRequest(BaseModel):
    text: str
    company_name: str = "기업"
    job_id: Optional[str] = None

@app.post("/analyze")
async def analyze_esg(req: AnalyzeRequest):
    job_id = str(uuid.uuid4())
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
        # [Boundary Normalization] 1단계 완료 결과는 draft 키에서 우선 조회
        result = await redis_mgr.client.get(f"result:{job_id}:draft")
        if not result:
            result = await redis_mgr.client.get(f"result:{job_id}")
        return {"status": "done", "report": json.loads(result) if result else {}}
    return {"status": status}

@app.post("/translate")
async def translate_text(req: TranslateRequest):
    try:
        print(f"[API] Deep ESG Analysis Request for: {req.company_name}", flush=True)
        if not req.text:
            raise HTTPException(status_code=400, detail="분석할 텍스트가 없습니다.")

        result = await generator.translate_to_korean(req.text, req.company_name)
        translated_text = result.get("translated_text", "")
        structured = result.get("structured", {})

        print(f"[API] Deep Analysis Success. Length: {len(translated_text)}", flush=True)

        # job_id가 있으면 심층 분석 결과를 Redis에 저장 (Stage 2 문서 생성에 활용)
        if req.job_id and structured:
            ext_data = json.dumps({"structured": structured, "company_name": req.company_name}, ensure_ascii=False)
            await redis_mgr.client.set(f"extended_report:{req.job_id}", ext_data, ex=86400)
            print(f"[API] Extended report stored for job: {req.job_id}", flush=True)

        return {"translated_text": translated_text}
    except Exception as e:
        print(f"[API] Deep Analysis Error: {e}", flush=True)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/deep")
async def analyze_deep(req: Request):
    try:
        data = await req.json()
        job_id = data.get("job_id")
        
        if not job_id:
            raise HTTPException(status_code=400, detail="job_id가 누락되었습니다.")

        # 프런트엔드 데이터 수집 (누락 시 빈 객체 보장)
        required_data = data.get("required") or {}
        options_data = data.get("options") or {}
        
        req_data = {
            "required": required_data,
            "options": options_data
        }
         # 기존 1단계 분석 데이터를 가져와서 기업명, 산업 정보 확보
        # [Boundary Normalization] 1단계 데이터는 draft 키에 우선 저장
        base_result_str = await redis_mgr.client.get(f"result:{job_id}:draft")
        if not base_result_str:
            base_result_str = await redis_mgr.client.get(f"result:{job_id}")
            
        if not base_result_str:
            raise HTTPException(status_code=404, detail="기존 1단계 분석 결과를 찾을 수 없습니다.")
        
        base_data = json.loads(base_result_str)
        company = base_data.get("company_name", "기업")
        industry = base_data.get("industry", "산업")
        size = base_data.get("size", "")

        # [Unified ID] 1단계와 동일한 ID 사용 (경계 정규화)
        # 2단계 요청 데이터 저장 (메타데이터 보관)
        await redis_mgr.client.set(f"{redis_mgr.NS_REQ_DATA}{job_id}", json.dumps(req_data), ex=86400)
        
        # [State Machine] 강제 초기화 (done -> queued 우회 허용)
        await redis_mgr.set_job_status(job_id, "queued", force=True)
        
        # 큐잉 (PayloadSnapshot 전략: Redis 분리 환경 대비용 원본 동봉)
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
    # [Unification] 모든 진행 상태는 job:status:{id} 하나로 관리됨
    status = await redis_mgr.get_job_status(job_id)
    if status == "done":
        raw_preview = await redis_mgr.client.get(f"{redis_mgr.NS_RESULT}{job_id}")
        
        # [SSOT Connection] 물리적 파일 생성 완료 여부 확인
        is_ready = await redis_mgr.client.get(f"file_ready:{job_id}")
        
        if not raw_preview:
             return {"status": "processing", "stage": 1}
             
        # [Absolute SSOT Check] 물리적 파일이 진짜로 있는지 확인 (job_id 기반 고정)
        file_path = os.path.join(DOWNLOAD_DIR, f"{job_id}.docx")
        if not os.path.exists(file_path):
             return {"status": "processing", "stage": 2, "info": "Finalizing file..."}
        
        # [Normalization] 백엔드에서 JSON 껍데기를 직접 벗겨서 전달
        try:
            parsed = json.loads(raw_preview)
            if isinstance(parsed, dict) and "raw_report" in parsed:
                clean_preview = parsed["raw_report"]
            else:
                clean_preview = raw_preview
        except:
            clean_preview = raw_preview

        # [Pretty Distribution Rename] 배포된 실제 파일명 조회 (Static 서빙용)
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
    
    # [SSOT] 물리적 파일 경로 (job_id 기반 고정 및 통일)
    file_path = os.path.join(DOWNLOAD_DIR, f"{job_id}.{fmt}")
    
    # 1. 물리적 존재 및 무결성 확인
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="리포트 파일이 아직 생성되지 않았습니다.")

    # 2. [Stability Guard] 파일 크기 안정성 체크 (OS Write Buffer 이슈 차단)
    size1 = os.path.getsize(file_path)
    if size1 < 1024:
        raise HTTPException(status_code=500, detail="리포트 파일이 생성 중이거나 손상되었습니다.")
    
    await asyncio.sleep(0.05) # 50ms 대기
    size2 = os.path.getsize(file_path)
    
    if size1 != size2:
        # 파일 크기가 변하고 있다면 아직 OS가 쓰고 있는 중임
        raise HTTPException(status_code=503, detail="파일이 아직 동기화 중입니다. 잠시 후 다시 시도해주세요.")
        
    # [Pretty Filename] 저장된 배포 파일명 조회 (Redis 기저)
    download_filename = await redis_mgr.client.get(f"dist_file:{job_id}:{fmt}")
    
    if not download_filename:
        # Fallback (데이터 유실 시 최소 품질 보장)
        company_name = "ESG"
        try:
            draft_str = await redis_mgr.client.get(f"{redis_mgr.NS_RESULT}{job_id}:draft")
            if draft_str:
                draft_data = json.loads(draft_str)
                company_name = draft_data.get("company_name", "ESG")
        except: pass
        download_filename = f"ESG_{company_name}.{fmt}"
    
    # media_type 결정
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4610)
