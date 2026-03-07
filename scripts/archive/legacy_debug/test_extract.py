import fitz

def extract():
    doc = fitz.open("test_template.pdf")
    page = doc[0]
    print(page.get_text())

if __name__ == "__main__":
    extract()
