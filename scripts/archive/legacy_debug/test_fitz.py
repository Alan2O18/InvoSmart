import fitz
from pprint import pprint

def test():
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    font_path = "backend/assets/fonts/kaiu.ttf"
    page.insert_text((100, 100), "測試文字 Test 123", fontname="F0", fontfile=font_path, fontsize=20, color=(1,0,0))
    page.insert_text((100, 200), "VoucherNo: D-16-01", fontname="F0", fontfile=font_path, fontsize=20, color=(1,0,0))
    doc.save("test_font.pdf")
    doc.close()
    print("Success")

if __name__ == "__main__":
    test()
