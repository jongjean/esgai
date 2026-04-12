import os
import re
import json
import traceback
from datetime import datetime
from docx import Document
from docx.shared import Pt
from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader

class ESGReportEngine:
    def __init__(self, template_dir: str):
        self.template_dir = template_dir
        self.docx_template_path = os.path.join(
            os.path.dirname(template_dir),
            "ESG_보고서_템플릿.docx"
        )
        self.html_template_name = "report.html"
        self.jinja_env = Environment(loader=FileSystemLoader(template_dir))
        print(f"[ENGINE] Initialized. Template Path: {self.docx_template_path}", flush=True)

    def generate_docx(self, data: dict, output_path: str):
        try:
            print(f"[ENGINE] Generating DOCX to {output_path}", flush=True)
            company_name = data.get("company_name", "미등록 기업")
            industry     = data.get("industry", "미분류")
            raw_report   = data.get("raw_report", "")
            date_str     = datetime.now().strftime("%Y-%m-%d")

            # JSON 파싱
            try:
                payload = json.loads(raw_report) if isinstance(raw_report, str) else raw_report
                if "structured_data" in payload: payload = payload["structured_data"]
            except:
                payload = {}

            env = payload.get("environment", {})
            soc = payload.get("social", {})
            gov = payload.get("governance", {})

            if not os.path.exists(self.docx_template_path):
                raise FileNotFoundError(f"Template not found at {self.docx_template_path}")

            doc = Document(self.docx_template_path)
            
            # 헤더 정보 채우기
            for para in doc.paragraphs:
                if '회사(기관)명:' in para.text: para.text = f"회사(기관)명: {company_name}"
                elif '보고기간:' in para.text: para.text = f"보고기간: {datetime.now().year}년"
                elif '작성일:' in para.text: para.text = f"작성일: {date_str}"

            # 앵커 맵핑 (기존 템플릿 호환)
            anchor_map = {
                "[environment.activity]": str(env.get("activity", "친환경 공정 도입 및 에너지 효율화 추진")),
                "[environment.plan]": str(env.get("plan", "탄소 중립 달성을 위한 중장기 로드맵 이행")),
                "[environment.kpi]": str(env.get("kpi", "에너지 사용량 및 재생에너지 비중 관리")),
                "[social.policy]": str(soc.get("policy", "전 임직원 대상 공정 성과 체계 및 인권 경영 강화")),
                "[social.safety]": str(soc.get("safety", "사업장 정기 안전 점검 및 사고 제로화 실현")),
                "[social.kpi]": str(soc.get("kpi", "지역 사회 기여도 및 협력사 상생 협력 지수")),
                "[governance.system]": str(gov.get("system", "이사회 독립성 강화 및 책임 경영 체계 구축")),
                "[governance.ethics]": str(gov.get("ethics", "윤리 규범 준수 및 투명한 기업 문화 확산")),
            }

            # 텍스트 치환 루프 (기업명 1회 노출 및 조사 처리)
            company_replaced = False
            company_pattern = re.compile(r'\[회사명\](은|는|이|가|의)?')

            def replace_company(match):
                nonlocal company_replaced
                particle = match.group(1) or ""
                if not company_replaced:
                    company_replaced = True
                    return company_name + particle
                else:
                    return ""

            for paragraph in doc.paragraphs:
                for anchor, text_val in anchor_map.items():
                    if anchor in paragraph.text:
                        paragraph.text = paragraph.text.replace(anchor, str(text_val))
                
                paragraph.text = company_pattern.sub(replace_company, paragraph.text)
                if '[업종]' in paragraph.text:
                    paragraph.text = paragraph.text.replace('[업종]', industry)

            for tbl in doc.tables:
                for row in tbl.rows:
                    for cell in row.cells:
                        for anchor, text_val in anchor_map.items():
                            if anchor in cell.text:
                                cell.text = cell.text.replace(anchor, str(text_val))
                        
                        cell.text = company_pattern.sub(replace_company, cell.text)
                        if '[업종]' in cell.text:
                            cell.text = cell.text.replace('[업종]', industry)

            # 원자적 저장
            temp_path = output_path + ".tmp"
            doc.save(temp_path)
            os.replace(temp_path, output_path)
            print(f"[ENGINE] DOCX Saved: {output_path}", flush=True)

        except Exception as e:
            print(f"❌ [ENGINE] DOCX ERROR: {e}", flush=True)
            traceback.print_exc()
            raise

    def generate_pdf(self, data: dict, output_path: str):
        try:
            print(f"[ENGINE] Generating PDF to {output_path}", flush=True)
            company_name = data.get("company_name", "미등록 기업")
            industry     = data.get("industry", "미분류")
            raw_report   = data.get("raw_report", "")
            date_str     = datetime.now().strftime("%Y-%m-%d %H:%M")

            try:
                # 1. raw_report가 있으면 파싱 시도
                payload = {}
                if raw_report:
                    try:
                        payload = json.loads(raw_report) if isinstance(raw_report, str) else raw_report
                        if "structured_data" in payload: payload = payload["structured_data"]
                    except:
                        payload = {}

                # 2. 파싱 결과가 비어있으면 data 딕셔너리의 구조화된 데이터 직접 참조 (Fallback)
                env = payload.get("environment") or data.get("environment", {})
                soc = payload.get("social") or data.get("social", {})
                gov = payload.get("governance") or data.get("governance", {})

                sections = []
                sections.append(f"<b>[환경 (Environment)]</b><br>"
                              f"• 실천 사항: {env.get('activity', '친환경 원자재 도입 및 에너지 효율화 실천')}<br>"
                              f"• 추진 계획: {env.get('plan', '탄소 중립 달성을 위한 로드맵 수립 및 실행')}<br>"
                              f"• 핵심 지표: {env.get('kpi', '온실가스 배출량 및 폐기물 재활용률 관리')}")
                
                sections.append(f"<b>[사회 (Social)]</b><br>"
                              f"• 인사 정책: {soc.get('policy', '임직원 복리후생 및 인권 정책 강화')}<br>"
                              f"• 안전 보건: {soc.get('safety', '사업장 안전 관리 시스템 구축 및 정기 점검')}<br>"
                              f"• 기여: {soc.get('kpi', '지역 사회 공헌 지수 및 협력사 동반 성장')}")
                
                sections.append(f"<b>[거버넌스 (Governance)]</b><br>"
                              f"• 경영 체계: {gov.get('system', '이사회의 독립성 강화 및 책임 경영 체계 구축')}<br>"
                              f"• 윤리 경영: {gov.get('ethics', '윤리 규정 준수 및 반부패 문화 확산')}")
                
                pretty_report = "<br><br>".join(sections)
                pretty_report += "<br><br><small>※ 본 보고서는 자동 생성된 초안입니다. 세부 분석은 유료 서비스를 통해 제공됩니다.</small>"
            except Exception as e:
                print(f"⚠️ [PDF ENGINE] Pretty report fail: {e}")
                pretty_report = str(raw_report) + "<br><br>※ 데이터 처리 중 내부 오류가 발생했습니다."

            context = {
                "company_name":    company_name,
                "industry":        industry,
                "generation_date": date_str,
                "full_report":     pretty_report
            }

            template = self.jinja_env.get_template(self.html_template_name)
            html_content = template.render(context)
            
            temp_path = output_path + ".tmp"
            HTML(string=html_content).write_pdf(temp_path)
            os.replace(temp_path, output_path)
            print(f"[ENGINE] PDF Saved: {output_path}", flush=True)

        except Exception as e:
            print(f"❌ [ENGINE] PDF ERROR: {e}", flush=True)
            traceback.print_exc()
            raise
