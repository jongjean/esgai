import re

class ESGRuleEngine:
    def __init__(self):
        # 학술점수(Score) 가중치 제거 - 평가 엔진에서 초안 엔진으로 전환
        pass

    def process(self, raw_text: str, size: str) -> dict:
        # Step 1: AI가 생성한 각 섹션 텍스트 추출
        e_text = self._extract(raw_text, "E")
        s_text = self._extract(raw_text, "S")
        g_text = self._extract(raw_text, "G")

        # (기존) 평가 관련 모든 산출 로직(score, level) 파기

        # Step 2: 비즈니스 피벗(Drafting) 지침에 맞춘 순수 초안 JSON 반환
        return {
            "status": "draft_generated",
            "message": "성공적인 ESG 초안을 생성했습니다",
            "policies": {
                "environment": e_text,
                "social": s_text,
                "governance": g_text
            }
        }

    def _extract(self, text: str, symbol: str) -> str:
        # 주어진 텍스트에서 [E], [S], [G] 기호로 묶인 텍스트만 추출
        pattern = rf"\[{symbol}\](.*?)(?=\[|$)"
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else "초안 텍스트 생성에 실패했습니다."
