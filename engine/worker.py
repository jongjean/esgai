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

# 디렉토리 설정
INTERNAL_TEMP = "/app/temp_gen"
PUBLIC_DIST = "/app/downloads"

for d in [INTERNAL_TEMP, PUBLIC_DIST]:
    os.makedirs(d, exist_ok=True)

class WorkerRedisManager(RedisManager):
    def __init__(self, redis_url: str):
        super().__init__(redis_url)

async def worker_loop():
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    redis_mgr = WorkerRedisManager(redis_url)
    generator = ESGGenerator()
    report_engine = ESGReportEngine(template_dir="/app/templates")

    # [Resilience] Redis 연결이 확립될 때까지 대기 (부팅 시퀀스 안정화)
    await redis_mgr.ensure_connection()
    
    print("🚀 ESG AI Worker Pool Started...", flush=True)


    while True:
        try:
            # 작업 가져오기 (RPOPLPUSH)
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
                "SME": "중소기업",
                "Mid-Market": "중견기업",
                "Enterprise": "대기업",
                "NGO": "비영리기관",
                "Other": "기타(그외)"
            }
            size_label = SIZE_MAP.get(size, size or "미지정")
            header_block = f"기업(기관)명 : {company}\n기업(기관)형태 : {size_label}\n산업분류 : {industry}\n\n"

            print(f"📦 Processing Job [{job_id}] - Stage {stage} - Company: {company}", flush=True)

            try:
                # [Phase 2] 리포트 생성 (DOCX/PDF)
                if stage == 2:
                    step2_data = payload.get("step2_data", {})
                    req_data = step2_data.get("required", {})
                    
                    # AI 본문 생성
                    print(f"[WORKER] Fetching Stage 1 draft for Job [{job_id}]...", flush=True)
                    draft_data_raw = await redis_mgr.client.get(f"{redis_mgr.NS_RESULT}{job_id}:draft")
                    base_report = ""
                    if draft_data_raw:
                        draft_obj = json.loads(draft_data_raw)
                        base_report = draft_obj.get("raw_report", "")

                    # [Phase 2-A] 번역 단계에서 저장된 심층 분석 우선 활용
                    extended_raw = await redis_mgr.client.get(f"extended_report:{job_id}")
                    data_obj = {}

                    if extended_raw:
                        print(f"[WORKER] Extended report found, using directly.", flush=True)
                        ext_data = json.loads(extended_raw)
                        data_obj = ext_data.get("structured", {})
                    else:
                        # [Phase 2-B] extended_report 없으면 AI refine 호출 (타임아웃 위험)
                        print(f"[WORKER] Calling generator.refine_policies...", flush=True)
                        raw_res = await generator.refine_policies(company, industry, base_report, step2_data)
                        data_obj = json.loads(raw_res)

                    env_res = data_obj.get("environment", {})
                    soc_res = data_obj.get("social", {})
                    gov_res = data_obj.get("governance", {})


                    formatted_text = (
                        header_block +
                        "■ 환경 (Environment)\n\n"
                        f" [주요 환경 활동]\n{env_res.get('activity') or '해당 내용 없음'}\n\n"
                        f" [향후 환경 계획]\n{env_res.get('plan') or '해당 내용 없음'}\n\n"
                        f" [환경 관리 지표]\n{env_res.get('kpi') or '해당 내용 없음'}\n\n"
                        "■ 사회 (Social)\n\n"
                        f" [사회적 책임 정책]\n{soc_res.get('policy') or '해당 내용 없음'}\n\n"
                        f" [안전 및 보건 관리]\n{soc_res.get('safety') or '해당 내용 없음'}\n\n"
                        f" [사회 공헌 지표]\n{soc_res.get('kpi') or '해당 내용 없음'}\n\n"
                        "■ 거버넌스 (Governance)\n\n"
                        f" [투명 경영 및 운영 체계]\n{gov_res.get('system') or '해당 내용 없음'}\n\n"
                        f" [윤리 경영 및 준법 기준]\n{gov_res.get('ethics') or '해당 내용 없음'}"
                    )

                    final_payload = {
                        "raw_report": formatted_text,
                        "structured_data": data_obj
                    }
                    refined_report = json.dumps(final_payload, ensure_ascii=False)
                    
                    report_data = {
                        "company_name": company,
                        "industry": industry,
                        "size_label": size_label,
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "raw_report": refined_report,
                        "environment": env_res,
                        "social": soc_res,
                        "governance": gov_res,
                        "company_intro": data_obj.get("company_intro", ""),
                        "key_products": data_obj.get("key_products", ""),
                        "locations": data_obj.get("locations", ""),
                        "esg_direction": data_obj.get("esg_direction", "")
                    }

                    # [Atomic Distribution Logic]
                    docx_filename = f"{job_id}.docx"
                    pdf_filename  = f"{job_id}.pdf"
                    
                    internal_docx = os.path.join(INTERNAL_TEMP, docx_filename)
                    internal_pdf  = os.path.join(INTERNAL_TEMP, pdf_filename)
                    
                    # 1. 문서 생성 (격리 폴더)
                    report_engine.generate_docx(report_data, internal_docx)
                    report_engine.generate_pdf(report_data, internal_pdf)

                    # 2. 공배포 폴더명 결정 (기업별 일련번호 적용, 날짜 제거)
                    current_count = await redis_mgr.get_company_gen_count(company)
                    suffix = f"{current_count:03d}"
                    dist_docx_name = f"ESG_Templet_{company}+{suffix}.docx"
                    dist_pdf_name = f"ESG_report_{company}+{suffix}.pdf"

                    # 3. 원자적 복제 및 이름 변경 (tmp -> replace)
                    for src, dist_name in [(internal_docx, dist_docx_name), (internal_pdf, dist_pdf_name)]:
                        tmp_dist = os.path.join(PUBLIC_DIST, f"{dist_name}.tmp")
                        shutil.copy2(src, tmp_dist)
                        os.replace(tmp_dist, os.path.join(PUBLIC_DIST, dist_name))
                        # Legacy ID 매칭용 (Engine 조회용)
                        shutil.copy2(src, os.path.join(PUBLIC_DIST, f"{job_id}{os.path.splitext(dist_name)[1]}"))

                    print(f"✅ Job [{job_id}] Final Distribution Success: {dist_docx_name}", flush=True)

                    # Redis 상태 업데이트
                    await redis_mgr.client.set(f"dist_file:{job_id}:docx", dist_docx_name, ex=86400)
                    await redis_mgr.client.set(f"dist_file:{job_id}:pdf", dist_pdf_name, ex=86400)
                    await redis_mgr.client.set(f"file_ready:{job_id}", "true", ex=3600)
                    await redis_mgr.complete_job(job_id, refined_report, raw_job_data=raw_job_data)

                # [Unified Analysis Path] 초고속 한글 분석 수행 (10초 속도 복원)
                else:
                    print(f"[WORKER] Starting consolidated generator.generate_policies for Job [{job_id}] (Stage 1)...", flush=True)
                    # 통합 엔진에서 한글 결과물을 즉시 받아옴
                    korean_report = await generator.generate_policies(company, industry)
                    
                    # [None Guard] 결과값 증발 방어 및 무결성 검증
                    if not korean_report:
                        raise Exception("AI 엔진으로부터 유효한 분석 결과를 받지 못했습니다. (Stage 1 Return None)")
                    
                    print(f"[DEBUG] Stage 1 result length: {len(korean_report)} chars", flush=True)

                    # [Single Source of Truth] 결과 저장 규격 단일화 (메인 API와 완벽 호환)
                    final_data = {
                        "raw_report": header_block + korean_report,

                        "company_name": company,
                        "industry": industry,
                        "size": size,
                        "stage": 1
                    }
                    data_json = json.dumps(final_data, ensure_ascii=False)
                    await redis_mgr.client.set(f"{redis_mgr.NS_RESULT}{job_id}", data_json, ex=86400)
                    await redis_mgr.client.set(f"{redis_mgr.NS_RESULT}{job_id}:draft", data_json, ex=86400)
                    
                    print(f"[WORKER] Successfully finalized job [{job_id}] in one-pass", flush=True)
                    await redis_mgr.complete_job(job_id, korean_report, raw_job_data=raw_job_data)
                    print(f"✅ Analysis Complete (Fast Path): {job_id}", flush=True)



            except Exception as e:
                print(f"❌ Job [{job_id}] Processing Error: {e}", flush=True)
                traceback.print_exc()
                await redis_mgr.set_job_status(job_id, "failed")
                if raw_job_data:
                    await redis_mgr.client.lrem(redis_mgr.NS_QUEUE_PROCESS, 1, raw_job_data)

        except Exception as e:
            print(f"🔥 Critical Worker Loop Error: {e}", flush=True)
            traceback.print_exc()
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(worker_loop())
