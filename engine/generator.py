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
        self.vocab_map = self._load_vocabulary()
        print(f"🏛️ ESGGenerator Initialized with model: {self.model} and structured vocab (Shield 1).")

    def _load_vocabulary(self) -> Dict[str, str]:
        """
        [Shield 1] 용어 사전을 카테고리별로 분할 로드하여 선택적 주입 준비.
        """
        vocab_path = "/app/esg_vocabulary.txt"
        if not os.path.exists(vocab_path):
            # 로컬 개발 환경 호환성
            vocab_path = "/home/ucon/esgai/engine/esg_vocabulary.txt"
            
        try:
            with open(vocab_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 카테고리별 분할 (🌱, 👥, 🏛️, 📊, ⚙️ 키워드 중심)
            vmap = {
                "rules": "", "env": "", "soc": "", "gov": "", "standards": "", "ops": ""
            }
            
            sections = re.split(r'### ', content)
            vmap["rules"] = sections[0] if len(sections) > 0 else ""
            
            for section in sections[1:]:
                if "환경" in section or "🌱" in section: vmap["env"] = "### " + section
                elif "사회" in section or "👥" in section: vmap["soc"] = "### " + section
                elif "거버넌스" in section or "🏛️" in section: vmap["gov"] = "### " + section
                elif "공시" in section or "📊" in section: vmap["standards"] = "### " + section
                elif "실행" in section or "⚙️" in section: vmap["ops"] = "### " + section
            
            return vmap
        except Exception as e:
            print(f"⚠️ [Shield 1] Vocabulary load failed: {e}")
            return {}

    def _get_optimized_vocab(self, categories: list = None) -> str:
        """
        필요한 카테고리만 조합하여 압축된 가이드 생성.
        """
        if not categories: return self.vocab_map.get("rules", "")
        
        selected = [self.vocab_map.get("rules", "")]
        for cat in categories:
            if cat in self.vocab_map:
                selected.append(self.vocab_map[cat])
        return "\n".join(selected)

    async def generate_policies(self, company_name: str, industry: str) -> str:
        """
        [Shield 2] Stage 1 - Ultra-Light 모드. 용어 사전 없이 핵심 ESG 뼈대만 영어로 생성하여 비용과 속도 극대화.
        """
        print(f"🚀 [Shield 2] 초경량 분석 시작: {company_name}")
        start_time = time.time()
        
        # [Shield 4] 정적 시스템 프롬프트 (가변 데이터 제거로 캐싱 히트율 극대화)
        system_prompt = """You are a senior ESG context extractor at a top-tier global ESG agency.
Produce a professional business-level ESG management guideline in English based on the user's input.
[Absolute Rules]
- Be action-oriented and professional.
- Omit the subject (the company name) in every sentence.
- Use precise formal business English.
- Return ONLY a JSON object."""
        
        # [Shield 4] 가변 데이터는 User Prompt로 배치
        user_prompt = f"""Generate a high-level ESG policy draft for:
Company: {company_name}
Industry: {industry}

[Format]
{{
  "esg_policy": {{
    "environment": "3-5 sentences of specific guidelines",
    "social": "3-5 sentences of specific guidelines",
    "governance": "3-5 sentences of specific guidelines"
  }}
}}"""


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


    async def translate_to_korean(self, text: str, company_name: str, industry: str = "", size: str = "") -> dict:
        """
        [ESG 심층 강화 분석 엔진]
        1단계 영문 초안 기반으로 풍부한 한국어 ESG 심층 분석 보고서 생성.
        반환: { 'translated_text': 표시용 전체 텍스트, 'structured': {env, social, gov} }
        """
        # 기관 정보 블록 생성
        SIZE_MAP = {
            "SME": "중소기업",
            "Mid-Market": "중견기업",
            "Enterprise": "대기업",
            "NGO": "비영리기관",
            "Other": "기타(그외)"
        }
        size_label = SIZE_MAP.get(size, size or "미지정")
        header_block = f"기업(기관)명 : {company_name}\n기업(기관)형태 : {size_label}\n산업분류 : {industry or '산업'}\n\n"
        # [Shield 1] 심층 분석에 필요한 핵심 세션만 추출 (환경, 사회, 거버넌스, 공시)
        terms_guide = self._get_optimized_vocab(["env", "soc", "gov", "standards"])

        # [Shield 4] 정적 시스템 프롬프트 (캐싱 효율 극대화)
        system_prompt = """당신은 국내 상위 1% ESG 평가기관 수석 컨설턴트입니다.
제공된 영문 ESG 초안을 기반으로 심층 한국어 ESG 경영 보고서를 재작성하십시오.

[절대 규칙]
1. 한국어 비즈니스 문어체 사용 (~합니다, ~체계를 구축합니다).
2. '지배구조' 금지 → 반드시 '거버넌스' 사용.
3. [주어 생략 규칙] 도입부 외에는 주어(기업명)를 반드시 생략하여 가독성 확보.
4. JSON 형식 100% 준수.

[응답 JSON 스키마]
{
  "environment": {
    "summary": "환경 영역 종합 헤드라인 (1문장)",
    "activity": "주요 환경 활동 및 실천 체계 (상세, 5단락 이상)",
    "plan": "향후 환경 계획 및 로드맵 (상세, 5단락 이상)",
    "kpi": "환경 관리 지표 및 성과 측정 방향 (상세, 5단락 이상)"
  },
  "social": {
    "summary": "사회 영역 종합 헤드라인 (1문장)",
    "policy": "인사 복지 및 사회적 책임 정책 (상세, 5단락 이상)",
    "safety": "안전 보건 관리 체계 (상세, 5단락 이상)",
    "kpi": "사회 공헌 전략 및 KPI (상세, 5단락 이상)"
  },
  "governance": {
    "summary": "거버넌스 영역 종합 헤드라인 (1문장)",
    "system": "투명 경영 및 거버넌스 체계 (상세, 5단락 이상)",
    "ethics": "윤리 경영 및 준법 기준 (상세, 5단락 이상)"
  }
}

<ESG 전문 용어 및 리라이팅 지침 (Shield 1 - Optimized)>
""" + terms_guide

        # [Shield 4] 가변 데이터(기업명, 초안 텍스트)는 User Prompt로 배치
        user_prompt = f"""Generate a detailed Korean ESG report for '{company_name}' based on the following draft:
[Draft]
{text}"""


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
                display_text = f"""{header_block}[환경 (Environment)]
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

        # [Shield 1] 정밀 분석에 필요한 전체 용어셋 주입 (환경, 사회, 거버넌스, 공시, 실행)
        terms_guide = self._get_optimized_vocab(["env", "soc", "gov", "standards", "ops"])

        # [Shield 4] 정적 시스템 프롬프트 (가변 데이터 제거로 캐싱 효율 극대화)
        system_prompt = """당신은 글로벌 1등 ESG 평가기관의 수석 전략 컨설턴트입니다.
제시된 실천 데이터와 초안을 융합하여 최종 C-Level 보고서 본문을 작성하십시오.

[지침]
1. 한국어 비즈니스 문어체로 10~15문장 이상의 풍부한 분량으로 서술.
2. '지배구조' 대신 '거버넌스' 사용.
3. 주어(기업명)는 문맥상 필요할 때만 사용하여 가독성 확보.
4. JSON 형식 100% 준수 (Key는 영문, Value는 한국어).

[응답 JSON 스키마]
{
  "environment": {
    "activity": "주요 환경 활동 및 실천 체계 (상세, 10문장 이상)",
    "plan": "향후 환경 계획 및 로드맵 (상세, 10문장 이상)",
    "kpi": "환경 관리 지표 및 성과 측정 방향 (상세, 10문장 이상)"
  },
  "social": {
    "policy": "인사 복지 및 사회적 책임 정책 (상세, 10문장 이상)",
    "safety": "안전 보건 관리 체계 (상세, 10문장 이상)",
    "kpi": "사회 공헌 전략 및 KPI (상세, 10문장 이상)"
  },
  "governance": {
    "system": "투명 경영 및 거버넌스 운영 체계 (상세, 10문장 이상)",
    "ethics": "윤리 경영 및 준법 기준 (상세, 10문장 이상)"
  }
}

<ESG 전문용어 및 프리미엄 리라이팅 지침 (Shield 1 - Optimized)>
""" + terms_guide

        # [Shield 4] 가변 데이터는 User Prompt로 배치
        req_answers = (step2_data or {}).get("required") or {}
        opt_answers = (step2_data or {}).get("options") or {}
        details = "\n".join([f"- {k}: {v}" for k, v in {**req_answers, **opt_answers}.items()])

        user_prompt = f"""[분석 대상 데이터]
기업명: {company_name} / 산업: {industry}
[1단계 초안]
{base_report}
[2단계 실천 데이터]
{details}

위 데이터를 융합하여 상기 JSON 스킹마에 맞춘 최상위 품질의 보고서를 완성하십시오."""

        # [Shield 3] 지능형 호출 게이트: 복잡한 분석 필요 시 모델 분기 가능 (현재 기본 chat 유지)
        selected_model = self.model
        
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=selected_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.6,
                    max_tokens=4000, # [Shield 5] 토큰 상한 제어
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
