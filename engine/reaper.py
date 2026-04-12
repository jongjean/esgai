import asyncio
import os
import json
import time
from infra.redis_mgr import RedisManager

# 환경 변수 및 설정
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REAPER_TIMEOUT = int(os.getenv("REAPER_TIMEOUT", "180"))
REAPER_INTERVAL = int(os.getenv("REAPER_INTERVAL", "30"))

async def reaper_loop():
    print(f"💀 ESG AI Reaper Started (Mode: Logistics & Cleanup)...")
    print(f"   - Timeout: {REAPER_TIMEOUT}s, Interval: {REAPER_INTERVAL}s")
    redis_mgr = RedisManager(REDIS_URL)
    
    while True:
        try:
            # Processing 큐 전수 조사
            processing_jobs = await redis_mgr.client.lrange(redis_mgr.NS_QUEUE_PROCESS, 0, -1)
            now = time.time()
            
            for job_data in processing_jobs:
                try:
                    job_info = json.loads(job_data)
                    job_id = job_info['job_id']
                    ts = job_info.get('ts', now)
                    
                    # [Step 1] 상태 기반 Silent Cleanup
                    # 이미 완료된 상태(done, failed)인데 큐에 남아있는 경우 강제 제거
                    status = await redis_mgr.get_job_status(job_id)
                    if status in redis_mgr.FINAL_STATES:
                        updated_at = int(await redis_mgr.client.get(f"job:updated_at:{job_id}") or 0)
                        # Grace Period (20초) 경과 시에만 제거하여 Race Condition 방지
                        if now - updated_at > 20:
                            print(f"🧹 Cleaning up finished Job [{job_id}] from processing queue (Status: {status})")
                            await redis_mgr.client.lrem(redis_mgr.NS_QUEUE_PROCESS, 1, job_data)
                        continue

                    # [Step 2] 타임아웃 판단
                    if now - ts > REAPER_TIMEOUT:
                        retry_key = f"retry:count:{job_id}"
                        retry_count = int(await redis_mgr.client.get(retry_key) or 0)
                        
                        if retry_count < 3:
                            print(f"♻️  Re-queueing Job [{job_id}] (Retry {retry_count + 1}/3)")
                            job_info['ts'] = now
                            await redis_mgr.client.lpush(redis_mgr.NS_QUEUE_PENDING, json.dumps(job_info))
                            await redis_mgr.client.incr(retry_key)
                            await redis_mgr.client.expire(retry_key, 3600)
                        else:
                            # [Role Change] 실패 선언 대신 DLQ(격리 큐)로 이동
                            print(f"📦 Job [{job_id}] Exceeded Max Retries. Moving to Dead Letter Queue.")
                            await redis_mgr.client.lpush(redis_mgr.NS_QUEUE_DLQ, job_data)
                        
                        # 처리 중인 큐에서는 일단 제거
                        await redis_mgr.client.lrem(redis_mgr.NS_QUEUE_PROCESS, 1, job_data)
                
                except Exception as inner_e:
                    print(f"⚠️ Error processing job data in reaper: {inner_e}")

            await asyncio.sleep(REAPER_INTERVAL) 
            
        except Exception as e:
            print(f"🔥 Reaper Critical Error: {str(e)}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(reaper_loop())
