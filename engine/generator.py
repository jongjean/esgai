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
Produce extremely concise and structured business-level ESG framework (bullet points) in English based on the user's input.
[Absolute Rules]
- Be action-oriented and highly conceptual.
- Omit the subject (the company name) in every sentence.
- Use precise formal business English.
- Return ONLY a JSON object."""
        
        # [Shield 4] 가변 데이터는 User Prompt로 배치
        user_prompt = f"""Generate a high-level ESG policy framework for:
Company: {company_name}
Industry: {industry}

[Format]
{{
  "english_draft": {{
    "environment": "Plain text sentences without any markdown symbols",
    "social": "Plain text sentences without any markdown symbols",
    "governance": "Plain text sentences without any markdown symbols"
  }}
}}
[Rules]
- NO markdown formatting (No bold, No *, No #).
- Use plain line breaks or numbering (1., 2., 3.) if needed.
"""



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
                        temperature=0.7,
                        max_tokens=500  # [Milestone 3] 상한 강제 축소
                    ),
                    timeout=30.0
                )

                content_body = response.choices[0].message.content
                result = json.loads(content_body)
                
                eng_draft = result.get("english_draft", {})

                def fmt(d):
                    if isinstance(d, dict):
                        return f"[Environment]\n{d.get('environment', '')}\n\n[Social]\n{d.get('social', '')}\n\n[Governance]\n{d.get('governance', '')}"
                    elif isinstance(d, list):
                        return "\n".join([f"- {i}" for i in d])
                    return str(d)

                eng_text = fmt(eng_draft)

                # Stage 1 strictly provides English. Translation happens in Stage 2.
                output_payload = f"""--- [🇺🇸 English Draft] ---\n{eng_text}"""
                
                print(f"✅ 초고속 영어 분석 완료: {int((time.time()-start_time)*1000)}ms", flush=True)
                return output_payload

            except Exception as e:
                if attempt < max_retries:
                    print(f"⚠️ Retrying AI Analysis (Attempt {attempt+1}): {e}", flush=True)
                    await asyncio.sleep((attempt + 1) * 2)
                else:
                    print(f"🚨 API 잔액 부족 등 치명적 오류. Mock 데이터로 Fallback 진행: {str(e)}", flush=True)
                    fallback = f"""--- [🇺🇸 English Draft] ---\n[Environment]\nService delayed."""
                    return fallback


    async def translate_to_korean(self, text: str) -> str:
        """
        [Stage 2] 한국어 비즈니스 번역 (1:1 매핑)
        사용자 요청에 따라 마크다운 기호를 완전히 배제한 순수 텍스트 번역을 수행합니다.
        """
        system_prompt = """당신은 ESG 전문 번역가입니다. 
제시된 영문 ESGDraft를 고품격 한국어 비즈니스 문어체로 번역하십시오.

[지침]
1. 마크다운 기호(별표 *, 샵 #, 볼드 ** 등)를 절대 사용하지 마십시오.
2. 모든 강조는 줄바꿈과 띄어쓰기, 문맥적 강조(예: '중점 추진', '핵심 전략' 등)로만 처리하십시오.
3. 전문 용어는 업계 통용어를 사용하되 가독성을 높이십시오.
4. 'Governance'는 '거버넌스'로 번역하십시오."""

        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"다음 ESG 초안을 한국어로 번역하십시오:\n\n{text}"}
                    ],
                    temperature=0.3,
                    max_tokens=1500
                ),
                timeout=60.0
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ Translation Error: {str(e)}", flush=True)
            return "번역 중 오류가 발생했습니다. 다음 단계로 넘어가 조회를 계속해 주세요."

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

        # [Shield 1] 정밀 분석에 필요한 전체 용어셋 주입 (환경, 사회, 거버넌스, 공시, 실행) - 토큰 소모의 주범이므로 제거
        terms_guide = "반드시 최신 ESG 전문 용어(예: 탄소중립, 온실가스 배출량, 거버넌스, 다양성 및 포용성 등)를 사용하여 전문적인 비즈니스 문어체로 작성하십시오."

        # [Shield 4] 정적 시스템 프롬프트 (가변 데이터 제거로 캐싱 효율 극대화)
        system_prompt = """당신은 글로벌 1등 ESG 평가기관의 수석 전략 컨설턴트입니다.
제시된 실천 데이터와 1단계 초안 뼈대를 융합하여 최종 C-Level 비즈니스 리포트를 고밀도로 압축 작성하십시오.

[지침]
1. 한국어 비즈니스 문어체로 영역별 5~7문장 이내로 초고밀도 압축 서술.
2. '지배구조' 대신 '거버넌스' 사용.
3. 주어(기업명)는 문맥상 필요할 때만 사용하여 가독성 극대화.
4. JSON 형식 100% 준수 (Key는 영문, Value는 한국어).
5. 마크다운 기호(별표 *, 샵 #, 볼드 ** 등)를 절대 사용하지 마십시오. 텍스트로만 강조하십시오.

[응답 JSON 스키마]
{
  "company_intro": "기업(기관)의 개요, 설립 목적 및 미션 (3문장 내외)",
  "key_products": "기업(기관)의 주요 제품, 서비스 또는 핵심 사업 부문 (비즈니스 요약)",
  "locations": "국내외 주요 사업장 위치 또는 운영 거점 현황",
  "esg_direction": "전사적 차원의 핵심 ESG 경영 철학 및 추진 방향 (가장 돋보이게 1문장 압축)",
  "environment": {
    "activity": "환경 보호 및 탄소 감축을 위한 현재 실천 활동 (3~5문장)",
    "plan": "에너지 효율화 및 친환경 인프라 도입 등 향후 추진 계획 (3~5문장)",
    "kpi": "감축 목표치, 도입 일자 등 구체적인 관리 지표"
  },
  "social": {
    "policy": "직원 복지, 인권 보호, 안전 보건 정책 (3~5문장)",
    "safety": "안전 관리 체계 및 지역사회 공헌 활동 (3~5문장)",
    "kpi": "이직률, 재해율, 봉사 시간 등 구체적 관리 지표"
  },
  "governance": {
    "system": "의사결정 구조의 투명성 및 이사회 운영 (3~5문장)",
    "ethics": "준법 경영 및 윤리 강령 내재화 수준 (3~5문장)"
  },
  "core_kpi": "분석 데이터를 관통하는 최우선 달성 핵심 성과 지표(KPI) (글머리 기호 3개)"
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
        
        # [Milestone 4] 동적 토큰 매니지먼트 (1500~2000 가변 확장)
        is_premium = step2_data.get("is_premium", False) if step2_data else False
        total_answers_len = len(details)
        dynamic_max_tokens = 2000 if (is_premium or total_answers_len > 300) else 1500

        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=selected_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.6,
                    max_tokens=dynamic_max_tokens, # [Shield 5] 동적 토큰 상한 제한 반영
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
            fallback_json = {
                "company_intro": "API 한도 초과로 인한 대체 제공 보고서. 신뢰도 높은 ESG 경영 비전을 구축해 나아갑니다.",
                "key_products": "이해관계자를 고려한 전문 서비스/제품 제공",
                "locations": "대한민국 및 글로벌 사업장 등",
                "esg_direction": "환경, 사회, 투명 지배구조 중심의 책임 경영 선도",
                "environment": {
                    "activity": "사업장 내 폐기물 절감 및 에너지 효율 향상 시스템 구축.",
                    "plan": "오는 하반기부터 탄소 배출 저감 로드맵 수립 및 실천.",
                    "kpi": "전력 사용량 감축률(%), 폐기물 재활용률(%)"
                },
                "social": {
                    "policy": "양성평등 채용 및 공정한 성과 보상 체계 유지, 지속적인 지역사회 기부.",
                    "safety": "사업장 내 중대재해 Zero 달성을 위해 정기 안전 보건 교육 확대 시행.",
                    "kpi": "안전보건 교육 이수율(%), 직원 이직률(%) 방어율"
                },
                "governance": {
                    "system": "전문성 및 다양성을 갖춘 이사회 구성, 주요 ESG 안건에 대한 의결 절차 강화.",
                    "ethics": "전사적 반부패 위반행위 제재 및 윤리 규범 실천 서약 100% 준수."
                }
            }
            return json.dumps(fallback_json, ensure_ascii=False)
