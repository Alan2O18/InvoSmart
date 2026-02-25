import fitz

doc = fitz.open(r"c:\Users\tange\Desktop\all_project\py for NKNU GA\AI_AGENT_LAB\dev_data\B-19 114學年度上學期宏遠社社烤 預_結算表 (1).pdf")
with open("inspect_pdf_out_utf8.txt", "w", encoding="utf-8") as f:
    for page_num in range(len(doc)):
        page = doc[page_num]
        tabs = page.find_tables()
        if tabs.tables:
            f.write(f"\n--- Page {page_num} Tables ---\n")
            for t_idx, table in enumerate(tabs.tables):
                f.write(f"  Table {t_idx}:\n")
                df = table.to_pandas()
                f.write(df.to_string())
                f.write("\n")
        else:
            f.write(f"\n--- Page {page_num} Text ---\n")
            f.write(page.get_text())
