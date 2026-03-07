import fitz

def test_on_template():
    template_path = "backend/assets/templates/憑證黏貼用紙.pdf"
    font_path = "backend/assets/fonts/kaiu.ttf"
    
    with fitz.open(template_path) as template_doc:
        with fitz.open() as out_doc:
            out_doc.insert_pdf(template_doc, from_page=0, to_page=0)
            page = out_doc[-1]
            
            # Use "F0"
            page.insert_text((100, 100), "測試文字 (F0)", fontname="F0", fontfile=font_path, fontsize=20, color=(1,0,0))
            # Use a unique name "KaiU_Custom"
            page.insert_text((100, 150), "測試文字 (KaiU_Custom)", fontname="KaiU_Custom", fontfile=font_path, fontsize=20, color=(0,0,1))
            
            out_doc.save("test_template.pdf")

if __name__ == "__main__":
    test_on_template()
