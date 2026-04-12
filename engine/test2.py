import docx
doc = docx.Document('/app/ESG_보고서_템플릿.docx')
for i in range(0, 57, 3):
    try:
        tbl = doc.tables[i]
        if len(tbl.rows) > 0 and len(tbl.rows[0].cells) > 0:
            text = tbl.rows[0].cells[0].text.strip().replace('\n', ' ')
            print(f'Block {i//3} (Table {i}): {text[:70]}')
    except:
        pass
