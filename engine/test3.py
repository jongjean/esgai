import docx
doc = docx.Document('/app/ESG_보고서_템플릿.docx')
for i in range(0, 57, 3):
    try:
        tbl = doc.tables[i]
        if len(tbl.rows) > 0 and len(tbl.rows[0].cells) > 1:
            text = tbl.rows[0].cells[1].text.strip().replace('\n', ' ')
            print(f'Table {i+2} (Input target): {text[:60]}...')
    except Exception as e:
        pass
