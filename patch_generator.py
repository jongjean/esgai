#!/usr/bin/env python3
"""
generator.py 패치 스크립트:
1. translate_to_korean → ESG 심층 구조화 분석 엔진으로 전환
2. refine_policies 타임아웃 → 120초로 연장
"""
import re

with open('/home/ucon/esgai/engine/generator.py', 'r', encoding='utf-8') as f:
    src = f.read()

# ───────────────────────────────────────────────────────────
# 패치 1: translate_to_korean 함수 전면 교체
# ───────────────────────────────────────────────────────────
old_translate = '''    async def translate_to_korean(self, text: str, company_name: str) -> str:'''
new_translate_sig = '''    async def translate_to_korean(self, text: str, company_name: str) -> dict:'''

# 함수 전체를 찾아서 교체
pattern = r'    async def translate_to_korean\(.*?\n    async def refine_policies'
match = re.search(pattern, src, re.DOTALL)
if not match:
    print("ERROR: translate_to_korean 함수를 찾을 수 없습니다.")
    exit(1)

new_translate_func = '''    async def translate_to_korean(self, text: str, company_name: str) -> dict:
        """
        [ESG 심층 강화 분석 엔진]
        1단계 영문 초안 기반으로 풍부한 한국어 ESG 심층 분석 보고서 생성.
        반환: { \'translated_text\': 표시용 전체 텍스트, \'structured\': {env, social, gov} }
        """
        terms_guide = ""
        try:
            with open("/home/ucon/esgai/engine/esg_vocabulary.txt", "r", encoding="utf-8") as f:
                terms_guide = f.read()
        except Exception:
            terms_guide = "기본 ESG 전문 용어 위주로 작성하시오."

        system_prompt = (
            "당신은 국내 상위 1% ESG 평가기관 수석 컨설턴트입니다.\\n"
            f"제공된 영문 ESG 초안을 \'{company_name}\'에 특화된 심층 한국어 ESG 경영 보고서로 재작성하십시오.\\n\\n"
            "[절대 규칙]\\n"
            "1. 모든 출력은 반드시 한국어로만 작성. 영문 병기 금지.\\n"
            "2. 영어 직역 금지. 능동적 한국어 비즈니스 문어체 사용 (~합니다, ~체계를 구축합니다).\\n"
            "3. \'지배구조\' 금지 → 반드시 \'거버넌스\' 사용.\\n"
            f"4. 주어는 반드시 \'{company_name}\' 직접 사용. \'귀사\', \'당사\' 금지.\\n"
            "5. 마크다운 기호(*, #, -, `, _) 절대 미사용.\\n"
            "6. 반드시 JSON 형식으로만 응답하며 아래 스키마를 100% 준수.\\n"
            "7. 각 항목은 최소 200자 이상, 3~5단락으로 풍부하게 서술.\\n\\n"
            "[응답 JSON 스키마]\\n"
            "{\\n"
            \'  \\"environment\\": {\\n\'
            \'    \\"summary\\": \\"환경 영역 종합 헤드라인 (1문장)\\",\\n\'
            \'    \\"activity\\": \\"주요 환경 활동 및 실천 체계 (상세, 5단락 이상)\\",\\n\'
            \'    \\"plan\\": \\"향후 환경 개선 계획 및 로드맵 (상세, 5단락 이상)\\",\\n\'
            \'    \\"kpi\\": \\"환경 관리 지표 및 성과 측정 방향 (상세, 5단락 이상)\\"\\n\'
            "  },\\n"
            \'  \\"social\\": {\\n\'
            \'    \\"summary\\": \\"사회 영역 종합 헤드라인 (1문장)\\",\\n\'
            \'    \\"policy\\": \\"인사 복지 및 사회적 책임 정책 (상세, 5단락 이상)\\",\\n\'
            \'    \\"safety\\": \\"안전 보건 관리 체계 (상세, 5단락 이상)\\",\\n\'
            \'    \\"kpi\\": \\"사회 공헌 전략 및 KPI (상세, 5단락 이상)\\"\\n\'
            "  },\\n"
            \'  \\"governance\\": {\\n\'
            \'    \\"summary\\": \\"거버넌스 영역 종합 헤드라인 (1문장)\\",\\n\'
            \'    \\"system\\": \\"투명 경영 및 거버넌스 체계 (상세, 5단락 이상)\\",\\n\'
            \'    \\"ethics\\": \\"윤리 경영 및 준법 기준 (상세, 5단락 이상)\\"\\n\'
            "  }\\n"
            "}\\n\\n"
            f"<ESG 전문 용어 150+ 지침서>\\n{terms_guide}"
        )

        user_prompt = (
            f"아래 영문 초안을 바탕으로 \'{company_name}\'만의 ESG 심층 분석 보고서를 완성하십시오.\\n\\n"
            f"[1단계 영문 초안]\\n{text}\\n\\n"
            "모든 내용은 반드시 한국어로 100% 작성."
        )

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

                content = response.choices[0].message.content.strip()
                content = re.sub(r\'```json\', \'\', content)
                content = re.sub(r\'```\', \'\', content).strip()
                structured = json.loads(content)

                env = structured.get("environment", {})
                soc = structured.get("social", {})
                gov = structured.get("governance", {})

                display_text = (
                    "[환경 (Environment)]\\n"
                    + env.get("summary", "") + "\\n\\n"
                    + env.get("activity", "") + "\\n\\n"
                    + env.get("plan", "") + "\\n\\n"
                    + env.get("kpi", "") + "\\n\\n"
                    + "[사회 (Social)]\\n"
                    + soc.get("summary", "") + "\\n\\n"
                    + soc.get("policy", "") + "\\n\\n"
                    + soc.get("safety", "") + "\\n\\n"
                    + soc.get("kpi", "") + "\\n\\n"
                    + "[거버넌스 (Governance)]\\n"
                    + gov.get("summary", "") + "\\n\\n"
                    + gov.get("system", "") + "\\n\\n"
                    + gov.get("ethics", "")
                )

                print(f"[DEEP ANALYSIS] 완료 ({len(display_text)} chars)", flush=True)
                return {"translated_text": display_text, "structured": structured}

            except Exception as e:
                if attempt < max_retries:
                    print(f"[심층분석] Retry {attempt+1}: {e}", flush=True)
                    await asyncio.sleep((attempt + 1) * 3)
                else:
                    print(f"[심층분석] 최종 실패: {e}", flush=True)
                    return {"translated_text": f"심층 분석 엔진 장애: {str(e)}", "structured": {}}

    async def refine_policies'''

src = re.sub(pattern, new_translate_func, src, flags=re.DOTALL)

# ───────────────────────────────────────────────────────────
# 패치 2: refine_policies 타임아웃 60 → 120초
# ───────────────────────────────────────────────────────────
src = src.replace('timeout=60.0', 'timeout=120.0')

with open('/home/ucon/esgai/engine/generator.py', 'w', encoding='utf-8') as f:
    f.write(src)

print("✅ generator.py 패치 완료")
print(f"파일 크기: {len(src)} bytes")
