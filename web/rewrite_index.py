import re
import os

with open('/home/ucon/esgai/web/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

# We need to replace everything inside <div class="card"> ... </div>
# and the entire <script> ... </script> block.

# First, capture the header and head
head_part = text.split('<div class="card">')[0]

# And the footer part
footer_part_match = re.search(r'(<footer.*?>.*?</footer>)', text, re.DOTALL)
footer_html = footer_part_match.group(1) if footer_part_match else ""

# The new card HTML
card_html = """<div class="card">
            <div style="font-size: 0.85rem; color: #94A3B8; margin-bottom: 20px; text-align: center; width: 100%; opacity: 0.9; word-break: keep-all;">
                아래 3칸만 입력하시고, 한국ESG학회가 제공하는<br>귀사 맞춤형 AI-ESG 평가보고서 템플릿을 받으세요
            </div>

            <!-- 1. 입력 화면 (IDLE / STEP2_FORM) -->
            <div id="input-view">
                <div id="step1-input">
                    <div class="form-group">
                        <label>기업 명칭</label>
                        <input type="text" id="company_name" placeholder="예: ESG미래">
                    </div>
                    <div class="form-group">
                        <label>산업 분야</label>
                        <select id="industry">
                            <option value="제조업">제조업</option>
                            <option value="건설업">건설업</option>
                            <option value="서비스업">서비스업</option>
                            <option value="정보통신업">정보통신업</option>
                            <option value="그외">그외</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>기업 규모</label>
                        <select id="size">
                            <option value="SME">중소기업</option>
                            <option value="Mid-Market">중견기업</option>
                            <option value="Enterprise">대기업</option>
                        </select>
                    </div>
                    <button id="btn_start" onclick="startAnalysis()" style="display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 5px; line-height: 1.2; color: #000000 !important;">
                        <span style="color: #000000 !important;"><span class="kesgai-info" style="color: #000000 !important; border-bottom: 2px solid #000000;">KESGAI</span> AI 엔진 START</span>
                        <span style="font-size: 0.9rem; font-weight: normal; color: #000000 !important;">(실시간 ESG경영 초안 생성)</span>
                    </button>
                </div>
                
                <div id="step2-input" style="display:none; text-align: left;">
                    <h3 style="color: var(--primary); border-bottom: 1px solid var(--glass-border); padding-bottom: 10px; margin-top:0;">[2단계] 맞춤형 정밀 보고서 생성하기</h3>
                    <p style="font-size: 0.85rem; color: #FFFFFF; margin-bottom: 20px;">
                        해당되는 항목을 <span style="color: var(--primary); font-weight: bold;">체크</span>해 주세요. <br>
                        작은 실천도 ESG의 훌륭한 시작이 됩니다. (없을 경우 '도입 예정' 선택)
                    </p>
                    <div id="questions-container"></div>
                    <div style="margin-top: 10px; display: flex; flex-direction: column; gap: 10px;">
                        <button onclick="submitStep2()" style="background: linear-gradient(135deg, var(--primary), var(--secondary)); color: white; border:none; padding: 12px; border-radius: 8px; font-weight: bold; cursor: pointer;">✨ 맞춤형 보고서 템플릿 생성하기</button>
                        <button onclick="restartAnalysis()" style="background: transparent; border: 1px solid #94A3B8; color: #FFFFFF; padding: 12px; border-radius: 8px; cursor: pointer;">처음으로 돌아가기</button>
                    </div>
                </div>
            </div>

            <!-- 2. 로딩 화면 (LOADING) -->
            <div id="loading-view" style="display:none; text-align: center; padding: 40px 20px; overflow: hidden;">
                <h3 id="loading-title" style="color: var(--primary); margin-bottom: 25px;"></h3>
                <div style="width: 100%; background: rgba(255,255,255,0.1); border-radius: 10px; overflow: hidden; margin-bottom: 20px;">
                    <div id="loading-progress" style="width: 0%; height: 8px; background: var(--secondary); transition: width 0.5s ease;"></div>
                </div>
                <span id="loading-desc" style="color: white; font-size: 0.85rem;"></span><br>
                <span style="color: #94A3B8; font-size: 0.85rem;">진행 시간: <span id="loading-timer">0</span>초 / 최대 3분</span>
            </div>

            <!-- 3. 결과 화면 (DONE / ERROR) -->
            <div id="result-view" style="display:none;">
                <div id="error-box" style="display:none; text-align: center; padding: 20px;">
                    <strong style="color: #EF4444; font-size: 1.1rem;">⚠️ 오류가 발생했습니다.</strong><br><br>
                    <p id="error-msg" style="color: white; font-size: 0.85rem;"></p>
                    <div style="margin-top: 20px;">
                        <button onclick="restartAnalysis()" style="background: transparent; border: 1px solid #94A3B8; color: #FFFFFF; padding: 12px; border-radius: 8px; cursor: pointer; width: 100%;">처음으로 돌아가기</button>
                    </div>
                </div>
                
                <div id="step1-result" style="display:none;">
                    <div style="display: flex; justify-content: flex-end; margin-bottom: 5px;">
                        <button id="translateBtn" onclick="toggleTranslation()" style="background: rgba(255,255,255,0.1); border: 1px solid var(--glass-border); color: #fff; padding: 4px 10px; border-radius: 6px; cursor: pointer; font-size: 0.8rem; font-family: 'NanumSquare', sans-serif; transition: all 0.3s; min-width: 100px; margin-top: 0;">🌐 원문 보기(English)</button>
                    </div>
                    <!-- 중요: 결과 렌더링 시 innerText 사용 예정 -->
                    <pre id="draftContent" style="white-space: pre-wrap; text-align: left; font-family: 'Inter', sans-serif; background: rgba(0,0,0,0.2); padding: 15px; border-radius: 8px; margin-top: 5px; border: 1px solid var(--glass-border); line-height: 1.6; font-size: 0.85rem; color: #E2E8F0; transition: opacity 0.3s ease;"></pre>
                    
                    <div style="margin-top: 15px; margin-bottom: 15px; text-align: left;">
                        <strong style="color: var(--primary); font-size: 0.95rem;">✅ "<span id="disp-company1"></span>" ESG경영 1단계 초안이 생성되었습니다.</strong><br>
                        <span style="color: #94A3B8; font-size: 0.8rem;">귀사를 위한 ESG 시작 가이드입니다. 필요에 따라 수정하여 사용하실 수 있습니다.</span>
                    </div>
                    
                    <div style="margin-top: 20px; text-align: center; display: block;">
                        <button onclick="showStep2Form()" style="background: linear-gradient(135deg, #3498DB, #2980B9); color: white; padding: 12px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%; font-size: 0.85rem; white-space: nowrap;">다음 걸음 (맞춤형 보고서 생성 단계로 이동)</button>
                    </div>
                    <div style="margin-top: 15px; text-align: center;">
                        <button onclick="restartAnalysis()" style="background: transparent; border: 1px solid #94A3B8; color: #FFFFFF; padding: 12px; border-radius: 8px; cursor: pointer; width: 100%; font-size: 0.85rem;">진행 초기화 (처음으로 돌아가기)</button>
                    </div>
                </div>

                <div id="step3-result" style="display:none;">
                    <h3 style="color: var(--primary); border-bottom: 1px solid var(--glass-border); padding-bottom: 10px; margin-top:0; text-align:center;"><span id="disp-company2"></span> 맞춤형 리포트</h3>
                    <p style="font-size: 0.85rem; color: #FFFFFF; text-align: center;">입력해주신 2단계 기업 정보가<br>AI 문서에 아래와 같이 매핑 반영되었습니다.</p>
                    
                    <pre id="deepContent" style="text-align: left; white-space: pre-wrap; background: rgba(0,0,0,0.3); padding: 15px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); line-height: 1.6; font-size: 0.85rem; color: #E2E8F0; max-height: 250px; overflow-y: auto;"></pre>
                    
                    <div style="margin-top: 20px; display: flex; flex-direction: column; gap: 10px;">
                        <div style="display: flex; gap: 10px;">
                            <a id="download-docx" href="#" download="ESG_Report.docx" style="flex:1; text-align:center; display:block; text-decoration:none; color:white; padding: 12px 5px; border-radius: 8px; font-weight: bold; background: linear-gradient(135deg, #2B579A 0%, #3B82F6 100%); font-size: 0.75rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">ESG_report.docx</a>
                            <a id="download-pdf" href="#" download="ESG_Report.pdf" style="flex:1; text-align:center; display:block; text-decoration:none; color:white; padding: 12px 5px; border-radius: 8px; font-weight: bold; background: linear-gradient(135deg, #C4302B 0%, #EF4444 100%); font-size: 0.75rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">최종 PDF 파일 다운로드</a>
                        </div>
                        <button onclick="restartAnalysis()" style="background: transparent; border: 1px solid #94A3B8; color: #FFFFFF; padding: 12px; border-radius: 8px; cursor: pointer;">처음으로 돌아가기</button>
                    </div>
                </div>
            </div>
        </div>
    </main>
"""

script_html = """
    <script>
        // ---------------------------------------------------------------------------------
        // [1] State Machine & Master Controllers
        // ---------------------------------------------------------------------------------
        const UI_STATE = {
            IDLE_STEP1: 'idle_1',
            LOADING_STEP1: 'loading_1',
            DONE_STEP1: 'done_1',
            IDLE_STEP2: 'idle_2',
            LOADING_STEP2: 'loading_2',
            DONE_STEP2: 'done_2',
            ERROR: 'error'
        };

        let currentState = UI_STATE.IDLE_STEP1;
        let abortController = null;
        let timerInterval = null;
        let isPolling = false;
        let isCompleted = false;
        let timerSec = 0;
        let msgIdx = 0;
        
        let globalJobId = null;
        let companyGlobal = "기업";

        function setState(nextState, errorMsg = "") {
            currentState = nextState;
            
            const vInput = document.getElementById('input-view');
            const vLoading = document.getElementById('loading-view');
            const vResult = document.getElementById('result-view');
            const boxError = document.getElementById('error-box');
            
            // 모든 뷰 초기화
            vInput.style.display = 'none';
            vLoading.style.display = 'none';
            vResult.style.display = 'none';
            boxError.style.display = 'none';
            document.getElementById('step1-input').style.display = 'none';
            document.getElementById('step2-input').style.display = 'none';
            document.getElementById('step1-result').style.display = 'none';
            document.getElementById('step3-result').style.display = 'none';

            if (nextState === UI_STATE.IDLE_STEP1) {
                vInput.style.display = 'block';
                document.getElementById('step1-input').style.display = 'block';
            } else if (nextState === UI_STATE.LOADING_STEP1) {
                vLoading.style.display = 'block';
            } else if (nextState === UI_STATE.DONE_STEP1) {
                vResult.style.display = 'block';
                document.getElementById('step1-result').style.display = 'block';
            } else if (nextState === UI_STATE.IDLE_STEP2) {
                vInput.style.display = 'block';
                document.getElementById('step2-input').style.display = 'block';
            } else if (nextState === UI_STATE.LOADING_STEP2) {
                vLoading.style.display = 'block';
            } else if (nextState === UI_STATE.DONE_STEP2) {
                vResult.style.display = 'block';
                document.getElementById('step3-result').style.display = 'block';
            } else if (nextState === UI_STATE.ERROR) {
                vResult.style.display = 'block';
                boxError.style.display = 'block';
                const msgEl = document.getElementById('error-msg');
                if(msgEl) msgEl.innerText = errorMsg;
            }
        }

        // ---------------------------------------------------------------------------------
        // [2] Timer Subsystem (완전 분리)
        // ---------------------------------------------------------------------------------
        const M1 = ["기업 정보 확인 중...", "업종 기준 적용 중...", "ESG 항목 구성 중...", "정책 초안 생성 중...", "보고서 정리 중..."];
        
        function startTimer(stage) {
            stopTimer(); // 기존 타이머 강제 정리
            timerSec = 0;
            msgIdx = 0;
            
            const timerEl = document.getElementById('loading-timer');
            const progEl = document.getElementById('loading-progress');
            const titleEl = document.getElementById('loading-title');
            const descEl = document.getElementById('loading-desc');
            
            if(stage === 1) {
                titleEl.innerHTML = M1[0].replace('KESGAI', '<span class="kesgai-info">KESGAI</span>지능');
                descEl.innerText = "온라인 스크랩 정보를 기반으로 초도 작업을 진행합니다.";
            } else {
                titleEl.innerHTML = "맞춤형 보고서 분석 생성 중...";
                descEl.innerText = "귀사가 입력한 상세 현황을 통합 매핑하고 있습니다.";
            }
            
            timerInterval = setInterval(() => {
                timerSec++;
                if(timerEl) timerEl.innerText = timerSec;
                
                let pct = (timerSec / 180) * 100;
                if (pct > 99) pct = 99;
                if(progEl) progEl.style.width = pct + '%';
                
                if (stage === 1 && timerSec % 30 === 0) {
                    msgIdx++;
                    titleEl.innerHTML = M1[msgIdx % M1.length].replace('KESGAI', '<span class="kesgai-info">KESGAI</span>');
                }
            }, 1000);
        }

        function stopTimer() {
            if (timerInterval) {
                clearInterval(timerInterval);
                timerInterval = null;
            }
        }

        // ---------------------------------------------------------------------------------
        // [3] Core Business Logic (Stage 1)
        // ---------------------------------------------------------------------------------
        function generateFingerprint() {
            const nav = window.navigator;
            const screen = window.screen;
            let str = nav.userAgent + nav.language + screen.colorDepth + screen.width + screen.height + new Date().getTimezoneOffset();
            return btoa(str).substring(0, 32);
        }

        async function startAnalysis() {
            const cName = document.getElementById('company_name').value;
            if(!cName) { alert('기업 명칭을 입력해 주세요.'); return; }
            companyGlobal = cName;
            
            const data = {
                company_name: cName,
                industry: document.getElementById('industry').value,
                size: document.getElementById('size').value,
                fingerprint: generateFingerprint()
            };

            // AbortController 강제 적용
            if (abortController) abortController.abort();
            abortController = new AbortController();
            const signal = abortController.signal;

            isCompleted = false;
            
            setState(UI_STATE.LOADING_STEP1);
            startTimer(1);

            try {
                const response = await fetch('./api/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data),
                    signal
                });

                if (!response.ok) throw new Error('서버 통신 오류');
                const initResult = await response.json();
                
                if (initResult.status === 'done' || !initResult.job_id) {
                    handleSuccess1(initResult.report || initResult, data.company_name, null);
                    return;
                }

                globalJobId = initResult.job_id;
                startPolling(1, globalJobId, signal);

            } catch (error) {
                if(error.name === 'AbortError') return;
                stopTimer();
                setState(UI_STATE.ERROR, "통신 오류가 발생했습니다. (" + error.message + ")");
            }
        }

        // ---------------------------------------------------------------------------------
        // [4] Recursion-based Polling System (중복 렌더링 원천 차단)
        // ---------------------------------------------------------------------------------
        let retryCount = 0;
        const MAX_RETRIES = 60; // 3분
        let consecutiveErrors = 0;

        async function startPolling(stage, jobId, signal) {
            if (isPolling) return;
            isPolling = true;
            retryCount = 0;
            consecutiveErrors = 0;
            
            try {
                await doPoll(stage, jobId, signal);
            } finally {
                isPolling = false;
            }
        }

        async function doPoll(stage, jobId, signal) {
            if (signal.aborted) return;
            if (isCompleted) return;

            if (retryCount >= MAX_RETRIES) {
                stopTimer();
                setState(UI_STATE.ERROR, "서버 응답 시간이 초과되었습니다. (Timeout)");
                return;
            }

            retryCount++;
            
            try {
                const url = stage === 1 ? `./api/status/${jobId}` : `./api/status/deep/${jobId}`;
                const res = await fetch(url, { signal });
                
                if (!res.ok) throw new Error('Fetch failed HTTP ' + res.status);
                
                const data = await res.json();
                consecutiveErrors = 0; // 성공 시 리셋

                if (stage === 1) {
                    if (data.status === 'done') {
                        handleSuccess1(data.report, companyGlobal, jobId);
                        return; // 단방향 종료
                    } else if (data.status === 'failed') {
                        stopTimer();
                        setState(UI_STATE.ERROR, "분석 중 데이터 추출에 실패했습니다.");
                        return;
                    }
                } else {
                    if (data.status === 'done' && data.stage === 2) {
                        handleSuccess2(data, companyGlobal, jobId);
                        return;
                    } else if (data.status === 'failed') {
                        stopTimer();
                        setState(UI_STATE.ERROR, "템플릿 문서 조립 중 오류가 발생했습니다.");
                        return;
                    }
                }

                // 진행 중이면 재귀
                setTimeout(() => doPoll(stage, jobId, signal), 2500);

            } catch (e) {
                if (e.name === 'AbortError') return;
                
                // [Fail-Fast] DOM 에러 등 치명적 JS 에러는 재시도 포기
                if (e instanceof TypeError || e instanceof ReferenceError) {
                    console.error("🔥 프론트엔드 치명적 오류 파악됨 (중단):", e);
                    stopTimer();
                    setState(UI_STATE.ERROR, "브라우저 처리 중 치명적 오류가 발생했습니다.");
                    return;
                }

                console.warn("[Polling] Network issue, retrying...", e);
                consecutiveErrors++;
                if (consecutiveErrors >= 10) {
                    stopTimer();
                    setState(UI_STATE.ERROR, "네트워크 연결이 장시간 끊어졌습니다.");
                    return;
                }
                setTimeout(() => doPoll(stage, jobId, signal), 3000);
            }
        }

        // ---------------------------------------------------------------------------------
        // [5] Success Handlers (DOM 보호 & InnerText 렌더링)
        // ---------------------------------------------------------------------------------
        function handleSuccess1(reportData, companyName, jobId) {
            if (isCompleted) return;
            isCompleted = true;
            stopTimer();

            // 데이터 정규화 로직 통합 적용
            let formattedOutput = "";
            if (reportData && typeof reportData.raw_report === 'string') {
                formattedOutput = reportData.raw_report;
            } else if (typeof reportData === 'string') {
                formattedOutput = reportData;
            } else {
                const raw = reportData.raw_report || {};
                const pol = raw.esg_policy || reportData.policies || reportData.esg_policy || {};
                formattedOutput = "[환경]\n" + (pol.environment||'생성 실패') + "\n\n[사회]\n" + (pol.social||'생성 실패') + "\n\n[거버넌스]\n" + (pol.governance||'생성 실패');
            }

            window.esgDraftData = {
                english: null,
                korean: formattedOutput,
                currentMode: 'ko',
                companyName: companyName
            };

            const contentEl = document.getElementById('draftContent');
            if(!contentEl) {
                setState(UI_STATE.ERROR, "결과를 표시할 영역을 찾을 수 없습니다. (UI 파괴됨)");
                return;
            }
            
            // XSS 위험 제거: 반드시 innerText 사용
            contentEl.innerText = formattedOutput;
            
            document.getElementById('disp-company1').innerText = companyName;

            setState(UI_STATE.DONE_STEP1);
        }

        function handleSuccess2(sData, companyName, jobId) {
            if (isCompleted) return;
            isCompleted = true;
            stopTimer();

            let rawPreview = sData.preview || '';
            let displayText = rawPreview;
            try {
                if (typeof rawPreview === 'string' && (rawPreview.startsWith('{') || rawPreview.startsWith('['))) {
                    let parsed = JSON.parse(rawPreview);
                    displayText = parsed.raw_report || JSON.stringify(parsed, null, 2);
                } else if (typeof rawPreview === 'object') {
                    displayText = rawPreview.raw_report || JSON.stringify(rawPreview, null, 2);
                }
            } catch(e) {}

            const contentEl = document.getElementById('deepContent');
            if(!contentEl) return;

            contentEl.innerText = displayText;
            document.getElementById('disp-company2').innerText = companyName;

            const docxUrl = sData.dist_docx ? "./downloads/" + sData.dist_docx : "./api/download/" + jobId + "/docx";
            const pdfUrl = sData.dist_pdf ? "./downloads/" + sData.dist_pdf : "./api/download/" + jobId + "/pdf";

            document.getElementById('download-docx').href = docxUrl;
            document.getElementById('download-docx').innerText = companyName + " ESG_report.docx";
            document.getElementById('download-pdf').href = pdfUrl;

            setState(UI_STATE.DONE_STEP2);
        }

        // ---------------------------------------------------------------------------------
        // [6] Step 2 뷰어 및 데이터 처리
        // ---------------------------------------------------------------------------------
        const Q_DATA = [
            { id: 'env', title: '1. [환경] 생활 속 실천', opts: ['종이 줄이기','재활용 철저','전기 절약','텀블러'] },
            { id: 'ene', title: '2. [에너지] 탄소 절감', opts: ['LED 사용','퇴근 절전','실내 온도','냉난방 관리'] },
            { id: 'wel', title: '3. [복지] 직원 건강', opts: ['식대 제공','자유 휴가','건강검진','간식 제공'] },
            { id: 'soc', title: '4. [사회] 지역 상생', opts: ['기부','지역 업체','인재 채용','행사 참여'] },
            { id: 'gov', title: '5. [거버넌스] 투명 경영', opts: ['정직 거래','투명 운영','의견 반영','청렴 경영'] }
        ];

        function showStep2Form() {
            const container = document.getElementById('questions-container');
            container.innerHTML = Q_DATA.map(q => `
                <div style="margin-bottom: 25px; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 20px;">
                    <label style="color: #FFFFFF; font-size: 0.95rem; font-weight: 700; margin-bottom: 8px; display: block;">${q.title}</label>
                    <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px;">
                        ${q.opts.map(opt => `
                            <label style="display: flex; align-items: center; background: rgba(255,255,255,0.05); padding: 6px 12px; border-radius: 20px; font-size: 0.8rem; cursor: pointer; border: 1px solid rgba(255,255,255,0.1); transition: all 0.2s;">
                                <input type="checkbox" name="q_${q.id}" value="${opt}" style="margin-right: 6px; width: 14px; height: 14px;"> ${opt}
                            </label>`).join('')}
                    </div>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <input type="text" id="q_${q.id}_other" placeholder="기타(직접 입력)" style="flex: 1; background: rgba(0,0,0,0.2); border: 1px solid var(--glass-border); padding: 8px 12px; font-size: 0.8rem; border-radius: 6px; color: white;">
                        <label style="font-size: 0.75rem; color: var(--primary); cursor: pointer;"><input type="checkbox" id="q_${q.id}_planned" style="margin-right: 5px;"> 도입 예정</label>
                    </div>
                </div>
            `).join('');
            
            setState(UI_STATE.IDLE_STEP2);
        }

        async function submitStep2() {
            const reqData = {};
            Q_DATA.forEach(q => {
                let col = Array.from(document.querySelectorAll(`input[name="q_${q.id}"]:checked`)).map(c=>c.value);
                const other = document.getElementById(`q_${q.id}_other`).value;
                if(other) col.push(other);
                const planned = document.getElementById(`q_${q.id}_planned`).checked;
                let txt = col.join(', ');
                if (planned) txt = txt ? txt + " (향후 도입 예정)" : "도입 예정";
                reqData[q.id] = txt || '미기재';
            });

            if (abortController) abortController.abort();
            abortController = new AbortController();
            const signal = abortController.signal;

            isCompleted = false;
            setState(UI_STATE.LOADING_STEP2);
            startTimer(2);

            try {
                const res = await fetch('./api/analyze/deep', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ job_id: globalJobId, required: reqData, options: {} }),
                    signal
                });

                if (!res.ok) throw new Error('매핑 전송 실패');
                startPolling(2, globalJobId, signal);

            } catch (e) {
                if(e.name === 'AbortError') return;
                stopTimer();
                setState(UI_STATE.ERROR, "분석 요청 중 오류가 발생했습니다. (" + e.message + ")");
            }
        }

        function restartAnalysis() {
            if(abortController) abortController.abort();
            stopTimer();
            window.location.reload();
        }

        async function toggleTranslation() {
            const btn = document.getElementById('translateBtn');
            const box = document.getElementById('draftContent');

            if (window.esgDraftData.currentMode === 'en') {
                if (window.esgDraftData.korean) {
                    box.innerText = window.esgDraftData.korean;
                    btn.innerText = '🌐 원문 보기(English)';
                    window.esgDraftData.currentMode = 'ko';
                    return;
                }
            } else {
                box.innerText = window.esgDraftData.english || "원문 데이터가 없습니다.";
                btn.innerText = '🌐 한글 번역';
                window.esgDraftData.currentMode = 'en';
            }
        }

        // 초기화
        document.addEventListener("DOMContentLoaded", () => {
            setState(UI_STATE.IDLE_STEP1);
        });
    </script>
"""

# Now write back
with open('/home/ucon/esgai/web/index_fixed.html', 'w', encoding='utf-8') as f:
    f.write(head_part)
    f.write(card_html)
    f.write(footer_html)
    f.write("\n")
    f.write(script_html)
    f.write("\n</body>\n</html>\n")

print("Done generating index_fixed.html")
