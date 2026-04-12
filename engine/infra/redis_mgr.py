import redis.asyncio as redis
import json
import time
import hashlib
from typing import Optional, Dict, Any

class RedisManager:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.client = redis.from_url(redis_url, decode_responses=True)
        # 네임스페이스 정의
        self.NS_QUEUE_PENDING = "queue:esg:pending"
        self.NS_QUEUE_PROCESS = "queue:esg:processing"
        self.NS_CACHE = "cache:esg:"
        self.NS_HOT_CACHE = "hotcache:esg:"
        self.NS_LOCK = "lock:esg:"
        self.NS_RATE_IP = "rate:ip:"
        self.NS_RATE_FP = "rate:fp:"
        self.NS_COUNT = "count:esg:"
        self.NS_JOB_ST = "job:status:"
        self.NS_QUEUE_DLQ = "queue:esg:dead_letter"
        self.NS_RESULT = "result:"
        self.NS_REQ_DATA = "req_data:"
        self.FINAL_STATES = {"done", "failed"}

    async def ensure_connection(self):
        """[Resilience] Redis 연결이 확립될 때까지 무한 재시도 (컨테이너 부팅 순서 대응)"""
        import asyncio
        while True:
            try:
                print(f"[REDIS] Connecting to {self.redis_url}...", flush=True)
                await self.client.ping()
                print(f"[REDIS] Connection Established Successfully.", flush=True)
                break
            except Exception as e:
                print(f"[REDIS] Connection Failed: {e}. Retrying in 2s...", flush=True)
                await asyncio.sleep(2)


    def normalize(self, text: str) -> str:
        """[Normalization] 공백 및 대소문자 제거로 캐시 효율 극대화"""
        if not text: return ""
        return text.strip().lower().replace(" ", "")

    def generate_key(self, company: str, industry: str) -> str:
        """기업명과 산업군 기반의 고유 키 생성"""
        norm_company = self.normalize(company)
        norm_industry = self.normalize(industry)
        combined = f"{norm_company}:{norm_industry}"
        return hashlib.md5(combined.encode()).hexdigest()

    # --- [Cache & Auto Promotion] ---
    async def get_cached_report(self, company: str, industry: str) -> Optional[str]:
        key = self.generate_key(company, industry)
        # 1순위: Hot Cache
        hot = await self.client.get(f"{self.NS_HOT_CACHE}{key}")
        if hot: return hot
        # 2순위: 일반 Cache
        return await self.client.get(f"{self.NS_CACHE}{key}")

    async def set_cached_report(self, company: str, industry: str, data: str):
        key = self.generate_key(company, industry)
        # 요청 횟수 확인 (Auto Promotion)
        count = await self.client.get(f"{self.NS_COUNT}{key}") or 0
        if int(count) >= 3:
            # 3회 이상 요청 시 Hot Cache 승격 (TTL 24h)
            await self.client.set(f"{self.NS_HOT_CACHE}{key}", data, ex=86400)
        else:
            # 일반 캐시 저장 (TTL 24h)
            await self.client.set(f"{self.NS_CACHE}{key}", data, ex=86400)

    async def increment_request_count(self, company: str, industry: str):
        """요청 횟수 기록 (1시간 TTL)"""
        key = self.generate_key(company, industry)
        full_key = f"{self.NS_COUNT}{key}"
        await self.client.incr(full_key)
        await self.client.expire(full_key, 3600)

    # --- [Lock & Rate Limit] ---
    async def acquire_lock(self, company: str, industry: str, job_id: str) -> bool:
        key = self.generate_key(company, industry)
        # 10초간 동일 요청 락 (비용 누수 방지)
        return await self.client.set(f"{self.NS_LOCK}{key}", job_id, nx=True, ex=10)

    async def check_rate_limit(self, identifier: str, limit: int, period: int) -> bool:
        """IP 또는 Fingerprint 기반 요청 제한"""
        key = f"{self.NS_RATE_FP}{identifier}"
        count = await self.client.incr(key)
        if count == 1:
            await self.client.expire(key, period)
        return count <= limit

    # --- [Reliable Queue Operations] ---
    async def enqueue_job(self, job_id: str, payload: Dict[str, Any]):
        """Pending 큐에 작업 등록 및 상태 설정"""
        data = json.dumps({"job_id": job_id, "payload": payload, "ts": time.time()})
        await self.client.lpush(self.NS_QUEUE_PENDING, data)
        await self.client.set(f"{self.NS_JOB_ST}{job_id}", "queued", ex=3600)

    async def dequeue_job(self) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """[RPOPLPUSH] Pending에서 Processing으로 원자적 이동 (유실 방지)"""
        data = await self.client.rpoplpush(self.NS_QUEUE_PENDING, self.NS_QUEUE_PROCESS)
        if not data: return None, None
        
        job_info = json.loads(data)
        # 처리 중 상태로 업데이트
        await self.set_job_status(job_info['job_id'], "processing", expire=600)
        return job_info, data

    async def set_job_status(self, job_id: str, status: str, expire: int = 3600, force: bool = False):
        """[State Guard] Final State 보호 로직이 포함된 상태 업데이트 (force=True 시 우회 가능)"""
        current_status = await self.get_job_status(job_id)
        
        # 이미 완료된 상태라도 force=True라면 덮어쓰기 허용 (Phase 2 전환용)
        if not force and current_status in self.FINAL_STATES:
            return False
            
        await self.client.set(f"{self.NS_JOB_ST}{job_id}", status, ex=expire)
        # 디버깅 및 Cleanup을 위한 최종 업데이트 시간 기록
        await self.client.set(f"job:updated_at:{job_id}", int(time.time()), ex=expire)
        return True

    async def complete_job(self, job_id: str, result: str, raw_job_data: Optional[str] = None):
        """작업 완료 처리 및 큐 제거"""
        # 1. 결과 데이터 저장 (상수 네임스페이스 사용)
        await self.client.set(f"{self.NS_RESULT}{job_id}", result, ex=86400) # 24시간 보관
        
        # 2. 상태를 'done'으로 확정 (Guarded)
        await self.set_job_status(job_id, "done", expire=86400)
        
        # 3. Processing 큐에서 즉시 제거 (LREM)
        if raw_job_data:
            await self.client.lrem(self.NS_QUEUE_PROCESS, 1, raw_job_data)
        
        return True

    async def get_job_status(self, job_id: str) -> str:
        return await self.client.get(f"{self.NS_JOB_ST}{job_id}") or "not_found"

    async def get_company_gen_count(self, company_name: str) -> int:
        """[Analytics] 기업별 보고서 생성 누적 횟수 관리 (인덱싱 및 일련번호용)"""
        norm_name = self.normalize(company_name)
        key = f"gen_count:company:{norm_name}"
        count = await self.client.incr(key)
        return count
