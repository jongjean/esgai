import os
import json
import time
import asyncio
import httpx
import re
from openai import AsyncOpenAI
from typing import Dict, Any

class ESGGenerator:
    def __init__(self):
        # 환경 변수에서 API 키 로드 (보안 정책 준수)
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

        # 비동기 OpenAI 클라이언트 초기화 (타임아웃 60초 강제 설정)
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=120.0
        )
        self.model = "deepseek-chat" # DeepSeek-V3 상용 모델
        print(f"🏛️ ESGGenerator Initialized with model: {self.model}")

    async def generate_policies(self, company_name: str, industry: str) -> str:
        """
        [Ultra-Fast One-Pass Engine] 고품질 분석과 한국어 리라이팅을 단 한 번의 호출로 끝내 10초대 속도 구현.
        """
        print(f"🚀 초고속 분석 시작: {company_name} ({industry})")
        start_time = time.time()
        
        # 용어 사전 로드 (최상위 품질 보증)
        terms_guide = ""
        try:
            with open("/app/esg_vocabulary.txt", "r", encoding="utf-8") as f:
                terms_guide = f.read()
        except:
            terms_guide = "기본 ESG 전문 용어 위주로 작성하시오."

        system_prompt = f"""You are a senior ESG consultant at a top-tier global ESG rating agency.
Analyze the given company name and industry, and produce a professional English ESG management guideline ready for immediate insertion into a C-Level report.

[Absolute Quality Rules]
1. Complete both analysis and writing in a single pass to deliver the response within 10 seconds.
2. Use precise, formal business English with active voice (e.g., '...establishes a framework', '...manages...').
3. Always use the term 'Governance' — never 'Corporate Governance Structure'.
4. [CRITICAL] Use the company name '{company_name}' ONLY ONCE in the very beginning. For all other sentences, STRICTLY OMIT the subject (the company name). Write focused, action-oriented content without repeating the company name as the subject.

[Response Format (JSON)]
{{
  "esg_policy": {{
    "environment": "Environmental domain analysis and specific guidelines (3-5 sentences)",
    "social": "Social domain analysis and specific guidelines (3-5 sentences)",
    "governance": "Governance domain analysis and specific guidelines (3-5 sentences)"
  }}
}}"""
        
        user_prompt = f"Company: {company_name}, Industry: {industry}. Write a highly optimized English ESG policy draft for this company."

        max_retries = 1
        for attempt in range(max_retries + 1):
            try:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.7
                    ),
                    timeout=30.0
                )

                content = response.choices[0].message.content
                result = json.loads(content)
                policy = result.get("esg_policy", {})

                # [One-Pass] Return English report for Stage 1 display
                formatted_english = f"""[Environment]
{policy.get('environment', 'Analysis failed')}

[Social]
{policy.get('social', 'Analysis failed')}

[Governance]
{policy.get('governance', 'Analysis failed')}"""

                print(f"✅ 초고속 분석 완료: {int((time.time()-start_time)*1000)}ms", flush=True)
                return formatted_english

            except Exception as e:
                if attempt < max_retries:
                    print(f"⚠️ Retrying AI Analysis (Attempt {attempt+1}): {e}", flush=True)
                    await asyncio.sleep((attempt + 1) * 2)
                else:
                    raise Exception(f"AI 엔진 통합 추론 최종 실패: {str(e)}")


    async def translate_to_korean(self, text: str, company_name: str) -> dict:
        """
        [ESG 심층 강화 분석 엔진]
        1단계 영문 초안 기반으로 풍부한 한국어 ESG 심층 분석 보고서 생성.
        반환: { 'translated_text': 표시용 전체 텍스트, 'structured': {env, social, gov} }
        """
        terms_guide = ""
        try:
            with open("/app/esg_vocabulary.txt", "r", encoding="utf-8") as f:
                terms_guide = f.read()
        except Exception:
            terms_guide = "기본 ESG 전문 용어 위주로 작성하시오."

        system_prompt = f"""당신은 국내 상위 1% ESG 평가기관 수석 컨설턴트입니다.
제공된 영문 ESG 초안을 '{company_name}'에 특화된 심층 한국어 ESG 경영 보고서로 재작성하십시오.

[절대 규칙]
1. 모든 출력은 반드시 한국어로만 작성. 영문 병기 금지.
2. 영어 직역 금지. 능동적 한국어 비즈니스 문어체 사용 (~합니다, ~체계를 구축합니다).
3. '지배구조' 금지 → 반드시 '거버넌스' 사용.
4. [절대 규칙] 기업 명칭('{company_name}')은 보고서 도입부에서 '단 한 번'만 사용하십시오. 이후 나타나는 모든 문장에서는 주어(기업명)를 반드시 생략하십시오. 매 문장을 기업명으로 시작하는 것은 가독성을 심각하게 해칩니다. 주어 없이 실천 방안과 핵심 내용 위주로만 간결하게 작성하십시오. '귀사', '당사' 표현도 사용하지 마십시오.
5. 마크다운 기호(*, #, -, `, _) 절대 미사용.
6. 반드시 JSON 형식으로만 응답하며 아래 스키마를 100% 준수.
7. 각 항목은 최소 200자 이상, 3~5단락으로 풍부하게 서술.

[응답 JSON 스키마]
{{
  "environment": {{
    "summary": "환경 영역 종합 헤드라인 (1문장)",
    "activity": "주요 환경 활동 및 실천 체계 (상세, 5단락 이상)",
    "plan": "향후 환경 계획 및 로드맵 (상세, 5단락 이상)",
    "kpi": "환경 관리 지표 및 성과 측정 방향 (상세, 5단락 이상)"
  }},
  "social": {{
    "summary": "사회 영역 종합 헤드라인 (1문장)",
    "policy": "인사 복지 및 사회적 책임 정책 (상세, 5단락 이상)",
    "safety": "안전 보건 관리 체계 (상세, 5단락 이상)",
    "kpi": "사회 공헌 전략 및 KPI (상세, 5단락 이상)"
  }},
  "governance": {{
    "summary": "거버넌스 영역 종합 헤드라인 (1문장)",
    "system": "투명 경영 및 거버넌스 체계 (상세, 5단락 이상)",
    "ethics": "윤리 경영 및 준법 기준 (상세, 5단락 이상)"
  }}
}}

<ESG 전문 용어 150+ 지침서>
{terms_guide}
"""

        user_prompt = f"""아래 영문 초안을 바탕으로 '{company_name}'만의 ESG 심층 분석 보고서를 완성하십시오.

[1단계 영문 초안]
{text}

모든 내용은 반드시 한국어로 100% 작성."""

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.5
                    ),
                    timeout=90.0
                )

                res_content = response.choices[0].message.content.strip()
                import json
                structured = json.loads(res_content)

                env = structured.get("environment", {})
                soc = structured.get("social", {})
                gov = structured.get("governance", {})

                # Use triple quotes for display_text to avoid unterminated string literal
                display_text = f"""[환경 (Environment)]
{env.get('summary', '')}

{env.get('activity', '')}

{env.get('plan', '')}

{env.get('kpi', '')}

[사회 (Social)]
{soc.get('summary', '')}

{soc.get('policy', '')}

{soc.get('safety', '')}

{soc.get('kpi', '')}

[거버넌스 (Governance)]
{gov.get('summary', '')}

{gov.get('system', '')}

{gov.get('ethics', '')}"""

                print(f"[DEEP ANALYSIS] 완료 ({len(display_text)} chars)", flush=True)
                return {"translated_text": display_text, "structured": structured}

            except Exception as e:
                if attempt < max_retries:
                    print(f"[심층분석] Retry {attempt+1}: {e}", flush=True)
                    await asyncio.sleep((attempt + 1) * 3)
                else:
                    print(f"[심층분석] 최종 실패: {e}", flush=True)
                    return {"translated_text": f"심층 분석 엔진 장애: {str(e)}", "structured": {}}


    async def refine_policies(self, company_name: str, industry: str, base_report: str, step2_data: dict) -> str:
        """
        [Phase 2] 1단계 초안과 2단계 필수/옵션 상세 정보를 합성하여
        DeepSeek 엔진이 Docx 인쇄에 적합한 프리미엄 정밀 보고서를 작성하는 핵심 로직.
        """
        print(f"🔬 정밀 심층 맵핑 시작: {company_name}")
        
        # [Safety] step2_data가 None일 경우 방어 로직
        if not step2_data:
            step2_data = {}
            
        req_answers = step2_data.get("required") or {}
        opt_answers = step2_data.get("options") or {}
        
        details = "\n[고객사 실제 현황 정보 (필수)]\n"
        details += "\n".join([f"- {k}: {v}" for k, v in req_answers.items()])
        
        if opt_answers:
            details += "\n\n[고객사 실제 현황 정보 (선택 포함)]\n"
            details += "\n".join([f"- {k}: {v}" for k, v in opt_answers.items()])

        terms_guide = ""
        try:
            with open("/home/ucon/esgai/engine/esg_vocabulary.txt", "r", encoding="utf-8") as f:
                terms_guide = f.read()
        except:
            terms_guide = "기본 ESG 전문 용어 위주로 번역하시오."

        system_prompt = f"""당신은 글로벌 1등 ESG 평가기관의 수석 전략 컨설턴트입니다.
사용자 기업 '{company_name}'가 제공한 실천 사항 데이터를 바탕으로, 최종 C-Level 보고서에 들어갈 프리미엄 ESG 본문을 작성하십시오.

[출력 언어 절대 규칙: 한국어]
1. 모든 응답은 반드시 '한국어'로만 작성하십시오. 기초 데이터가 영어일지라도 반드시 한국어로 번석/번역하여 출력해야 합니다.
2. 전문적인 한국어 비즈니스 문체를 사용하십시오. (~입니다, ~합니다)

[핵심 작성 지침]
1. 반드시 JSON 형식으로만 응답하며, 마크다운 기호(예: ```)를 절대 포함하지 마십시오.
2. 각 항목은 최소 10~15문장 이상의 풍부한 분량으로 전문적이고 격조 있는 문체로 작성하십시오. 단순한 사실 나열을 넘어, 해당 활동의 추진 배경, 기대 효과, 장기적 가치 창출 관점을 포함하여 논리적이고 풍성한 3개 이상의 단락으로 구성하십시오.
3. 단순한 '초안'을 넘어, 국내외 유수 기업의 공시 보고서 수준의 세련되고 밀도 높은 비즈니스 어휘를 사용하십시오.
4. 절대 항목을 생략하지 마며, 사용자가 입력한 구체적인 실천 데이터를 본문에 자연스럽게 녹여내십시오.
5. '지배구조'라는 단어는 금지하며, 반드시 '거버넌스'로 통일하여 전문성을 높이십시오.
6. [중요] 사용자가 제공한 실천 사항이 있다면, 해당 데이터를 바탕으로 전략적인 시사점을 도출하여 풍성하게 서술하십시오.
7. [주어 절대 규칙] '귀사'라는 단어를 본문에 절대 사용하지 마십시오. 모든 문장에서 주어로 반드시 '{company_name}'을 사용하십시오.

[출력 강제 구조 (필수)]
반드시 아래 JSON 스키마를 100% 준수하여 응답해야 합니다. Key 이름은 영문을 유지하되 Value는 한국어로 작성하세요.
{{
  "environment": {{
    "activity": "환경 관련 활동 내용",
    "plan": "환경 계획 내용",
    "kpi": "환경 KPI 측정 방향"
  }},
  "social": {{
    "policy": "인사 및 복지 정책",
    "safety": "안전 활동 현황",
    "kpi": "사회 부문 KPI 방향"
  }},
  "governance": {{
    "system": "거버넌스 체계 방향",
    "ethics": "윤리 경영 기준"
  }}
}}

<ESG 전문용어 150+ 및 프리미엄 번역 지침서>
{terms_guide}
"""
        user_prompt = f"""[분석 대상 데이터]
기업명: {company_name}
산업분야: {industry}

<1단계 생성 초안>
{base_report}

<2단계 실천 사항 및 의지 데이터>
{details}

위 데이터를 융합하여, "{company_name}"만의 독보적인 ESG 경영 전략 보고서 본문을 완성하십시오.
"""
        
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.6,
                    response_format={"type": "json_object"}
                ),
                timeout=120.0
            )
            content = response.choices[0].message.content.strip()

            
            # JSON 외의 불필요한 마크다운 백틱 등이 있다면 정제
            import re
            content = re.sub(r'```json', '', content)
            content = re.sub(r'```', '', content).strip()
            
            return content
        except Exception as e:
            import traceback
            err_msg = traceback.format_exc()
            print(f"[REFINE ERROR] Traceback: {err_msg}", flush=True)
            return f"{{\"error\": \"2단계 심층 정밀 분석 중 오류가 발생했습니다. (장애: {str(e) or repr(e)})\"}}"
