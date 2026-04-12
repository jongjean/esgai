from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader
import os
from datetime import datetime

class ESGReportGenerator:
    def __init__(self, template_dir: str):
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.template_name = "report.html"

    def create_pdf(self, data: dict, output_path: str) -> str:
        # Step 1: 비즈니스 피벗에 맞춘 렌더링 데이터 준비 (Score 파기)
        render_data = {
            "company_name": data.get("company", "알 수 없음"),
            "industry": data.get("industry", "미분류"),
            "generation_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "policies": data.get("report", {}).get("policies", {"environment":"", "social":"", "governance":""})
        }

        # Step 2: Render HTML
        template = self.env.get_template(self.template_name)
        html_out = template.render(render_data)

        # Step 2: Convert to PDF
        HTML(string=html_out).write_pdf(output_path)
        
        return output_path
