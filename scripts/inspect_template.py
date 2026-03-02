from docx import Document

doc = Document(r"c:\Users\tange\Desktop\all_project\py for NKNU GA\AI_AGENT_LAB\dev_data\空白 模板 (1).docx")
with open("inspect_template_out_utf8.txt", "w", encoding="utf-8") as f:
    for i, t in enumerate(doc.tables):
        f.write(f"\n--- Table {i} ---\n")
        local_rows = min(len(t.rows), 30)
        for r in range(local_rows):
            cell_texts = [c.text.replace('\n', ' ').strip() for c in t.rows[r].cells]
            f.write(f"Row {r}: {cell_texts}\n")
