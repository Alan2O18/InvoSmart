import fitz

template_path = r'c:\Users\tange\Desktop\all_project\py for NKNU GA\AI_AGENT_LAB\backend\assets\templates\憑證黏貼用紙.pdf'
out_path = 'test_out.pdf'

with fitz.open(template_path) as template_doc:
    with fitz.open() as out_doc:
        # 測試 generator 裡的寫法
        out_doc.insert_pdf(template_doc, from_page=0, to_page=0)
        page = out_doc[-1]
        page.insert_text((78, 238), "TEST-1234", fontsize=12)
        out_doc.save(out_path)

print("Saved", out_path)
