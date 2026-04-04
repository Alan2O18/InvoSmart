import json
import logging
from backend.utils.parser import extract_structured_data
from backend.engine.excel_exporter import ExcelExporter

logging.basicConfig(level=logging.INFO)

test_json = '''
{
  "receipt_type": "電子發票證明聯",
  "header": {
      "supplier": "測試商家", 
      "buyer": "99999999", 
      "invoice_id": "AB12345678", 
      "date": "2024-01-15"
  }, 
  "items": [
      {"name": "拿鐵", "qty": 1, "price": 50, "total": 50, "category": "茶水"},
      {"name": "蛋糕", "qty": 2, "price": 100, "total": 200, "category": "餐食"}
  ], 
  "summary": {
      "subtotal": 250,
      "tax": 0,
      "total": 250
  }
}
'''

def run_test():
    print("=== Testing extract_structured_data ===")
    parsed = extract_structured_data(test_json)
    
    assert "items" in parsed
    items = parsed["items"]
    assert len(items) == 2
    
    # Check that category parsed successfully
    assert items[0]["description"] == "拿鐵"
    assert items[0]["category"] == "茶水"
    assert items[1]["description"] == "蛋糕"
    assert items[1]["category"] == "餐食"
    
    print("Parser extraction SUCCESS!\n")

    print("=== Testing Excel Exporter Markdown _generate_text_from_vlm_result ===")
    
    # Need a mock repo to init
    class MockRepo:
        pass

    exporter = ExcelExporter(MockRepo())
    markdown_result = exporter._generate_text_from_vlm_result(json.loads(test_json))
    print(markdown_result)

    assert "| 名目 | 單價 | 數量 | 小計 | 品名 |" in markdown_result
    assert "| 茶水 | 50 | 1 | 50 | 拿鐵 |" in markdown_result
    assert "| 餐食 | 100 | 2 | 200 | 蛋糕 |" in markdown_result

    print("Excel Markdown builder SUCCESS!")

if __name__ == "__main__":
    run_test()
