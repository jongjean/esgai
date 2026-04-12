from docx import Document

doc = Document("/app/ESG_보고서_템플릿.docx")

anchors = {
    26: "[environment.activity]",
    29: "[environment.plan]",
    32: "[environment.kpi]",
    35: "[social.policy]",
    38: "[social.safety]",
    41: "[social.kpi]",
    44: "[governance.system]",
    47: "[governance.ethics]",
}

for idx, anchor in anchors.items():
    tbl = doc.tables[idx]
    if len(tbl.rows) > 0 and len(tbl.rows[0].cells) > 1:
        tbl.rows[0].cells[1].text = anchor

doc.save("/app/ESG_보고서_템플릿.docx")
print("Successfully injected anchor keywords into the template.")
