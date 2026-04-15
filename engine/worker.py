import os
import re
import json
import time
import shutil
import asyncio
import traceback
from datetime import datetime
import redis.asyncio as redis
from infra.redis_mgr import RedisManager
from infra.report_engine import ESGReportEngine
from generator import ESGGenerator

# [MASTER-DEPLOY] 아키텍처 경로 설정
INTERNAL_TEMP = "/app/temp_gen"
MASTER_DIR = "/app/master_downloads"    # /home/ucon/esgai/web/downloads (Persistent Master)
DEPLOY_DIR = "/app/deploy_downloads"    # /var/www/esgai/downloads (Volatile Public)

for d in [INTERNAL_TEMP, MASTER_DIR, DEPLOY_DIR]:
    os.makedirs(d, exist_ok=True)

class WorkerRedisManager(RedisManager):
    def __init__(self, redis_url: str):
        super().__init__(redis_url)

async def worker_loop():
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    redis_mgr = WorkerRedisManager(redis_url)
    generator = ESGGenerator()
    report_engine = ESGReportEngine(template_dir="/app/templates")

    await redis_mgr.ensure_connection()
    print("🚀 ESG AI Worker Pool Started (Single-Naming Strategy)...", flush=True)

    while True:
        try:
            job_info, raw_job_data = await redis_mgr.dequeue_job()
            if not job_info:
                await asyncio.sleep(2)
                continue

            job_id = job_info.get("job_id")
            payload = job_info.get("payload", {})
            stage = payload.get("stage", 1)
            company = payload.get("company_name", "기업")
            industry = payload.get("industry", "산업")
            size = payload.get("size", "")

            SIZE_MAP = {
                "SME": "중소기업", "Mid-Market": "중견기업", "Enterprise": "대기업",
                "NGO": "비영리기관", "Other": "기타(그외)"
            }
            size_label = SIZE_MAP.get(size, size or "미지정")
            header_block = f"기업(기관)명 : {company}\n기업(기관)형태 : {size_label}\n산업분류 : {industry}\n\n"

            print(f"📦 Processing Job [{job_id}] - Stage {stage} - Company: {company}", flush=True)

            try:
                if stage == 2:
                    step2_data = payload.get("step2_data", {})
                    
                    draft_data_raw = await redis_mgr.client.get(f"{redis_mgr.NS_RESULT}{job_id}:draft")
                    base_report = ""
                    if draft_data_raw:
                        draft_obj = json.loads(draft_data_raw)
                        base_report = draft_obj.get("raw_report", "")

                    extended_raw = await redis_mgr.client.get(f"extended_report:{job_id}")
                    if extended_raw:
                        ext_data = json.loads(extended_raw)
                        data_obj = ext_data.get("structured", {})
                    else:
                        raw_res = await generator.refine_policies(company, industry, base_report, step2_data)
                        data_obj = json.loads(raw_res)

                    env_res = data_obj.get("environment", {})
                    soc_res = data_obj.get("social", {})
                    gov_res = data_obj.get("governance", {})

                    formatted_text = (
                        header_block +
                        "■ 기업 개요 및 미션\n" + f"{data_obj.get('company_intro') or '분석 중...'}\n\n" +
                        "■ 주요 비즈니스 요약\n" + f"{data_obj.get('key_products') or '분석 중...'}\n\n" +
                        "■ ESG 경영 핵심 방향\n" + f"👉 {data_obj.get('esg_direction') or '분석 중...'}\n\n" +
                        "--------------------------------------------------\n\n" +
                        "■ 환경 (Environment)\n\n" +
                        f" [주요 환경 활동]\n{env_res.get('activity') or '해당 내용 없음'}\n\n" +
                        f" [향후 환경 계획]\n{env_res.get('plan') or '해당 내용 없음'}\n\n" +
                        f" [환경 관리 지표]\n{env_res.get('kpi') or '해당 내용 없음'}\n\n" +
                        "■ 사회 (Social)\n\n" +
                        f" [사회적 책임 정책]\n{soc_res.get('policy') or '해당 내용 없음'}\n\n" +
                        f" [안전 및 보건 관리]\n{soc_res.get('safety') or '해당 내용 없음'}\n\n" +
                        f" [사회 공헌 지표]\n{soc_res.get('kpi') or '해당 내용 없음'}\n\n" +
                        "■ 거버넌스 (Governance)\n\n" +
                        f" [투명 경영 및 운영 체계]\n{gov_res.get('system') or '해당 내용 없음'}\n\n" +
                        f" [윤리 경영 및 준법 기준]\n{gov_res.get('ethics') or '해당 내용 없음'}\n\n" +
                        "--------------------------------------------------\n\n" +
                        "■ 핵심 성과 지표 (Core KPIs)\n" + f"{data_obj.get('core_kpi') or '분석 중...'}"
                    )

                    refined_report = json.dumps({"raw_report": formatted_text, "structured_data": data_obj}, ensure_ascii=False)
                    
                    report_data = {
                        "company_name": company, "industry": industry, "size_label": size_label,
                        "date": datetime.now().strftime("%Y-%m-%d"), "raw_report": refined_report,
                        "environment": env_res, "social": soc_res, "governance": gov_res,
                        "company_intro": data_obj.get("company_intro", ""), "key_products": data_obj.get("key_products", ""),
                        "locations": data_obj.get("locations", ""), "esg_direction": data_obj.get("esg_direction", "")
                    }

                    # [Worker Distribution - Single Naming Strategy]
                    current_count = await redis_mgr.get_company_gen_count(company)
                    suffix = f"{current_count:03d}"
                    dist_docx_name = f"ESG_Templet_{company}_{suffix}.docx"
                    dist_pdf_name = f"ESG_Templet_{company}_{suffix}.pdf"

                    temp_docx = os.path.join(INTERNAL_TEMP, f"{job_id}.docx")
                    temp_pdf  = os.path.join(INTERNAL_TEMP, f"{job_id}.pdf")
                    
                    # 1. 문서 생성
                    report_engine.generate_docx(report_data, temp_docx)
                    report_engine.generate_pdf(report_data, temp_pdf)

                    # 2. 마스터 및 배포 전송 (UUID 이름은 사용하지 않음)
                    for src, final_name in [(temp_docx, dist_docx_name), (temp_pdf, dist_pdf_name)]:
                        # A. Master (영구 원본) - 한글 파일명으로 저장
                        shutil.copy2(src, os.path.join(MASTER_DIR, final_name))
                        # B. Deploy (휘발성 배포) - 동일하게 한글 파일명으로 저장
                        shutil.copy2(src, os.path.join(DEPLOY_DIR, final_name))

                    print(f"✅ Job [{job_id}] Saved as {dist_docx_name} (Single-Naming Strategy)", flush=True)

                    await redis_mgr.client.set(f"dist_file:{job_id}:docx", dist_docx_name, ex=86400)
                    await redis_mgr.client.set(f"dist_file:{job_id}:pdf", dist_pdf_name, ex=86400)
                    await redis_mgr.client.set(f"file_ready:{job_id}", "true", ex=3600)
                    await redis_mgr.complete_job(job_id, refined_report, raw_job_data=raw_job_data)

                else:
                    korean_report = await generator.generate_policies(company, industry)
                    if not korean_report: raise Exception("Stage 1 result empty.")
                    
                    final_data = {
                        "raw_report": header_block + korean_report,
                        "company_name": company, "industry": industry, "size": size, "stage": 1
                    }
                    data_json = json.dumps(final_data, ensure_ascii=False)
                    await redis_mgr.client.set(f"{redis_mgr.NS_RESULT}{job_id}", data_json, ex=86400)
                    await redis_mgr.client.set(f"{redis_mgr.NS_RESULT}{job_id}:draft", data_json, ex=86400)
                    await redis_mgr.complete_job(job_id, korean_report, raw_job_data=raw_job_data)
                    print(f"✅ Analysis Complete: {job_id}", flush=True)

            except Exception as e:
                print(f"❌ Processing Error: {e}", flush=True)
                await redis_mgr.set_job_status(job_id, "failed")
                if raw_job_data: await redis_mgr.client.lrem(redis_mgr.NS_QUEUE_PROCESS, 1, raw_job_data)

        except Exception as e:
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(worker_loop())
