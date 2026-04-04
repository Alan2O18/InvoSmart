import json
from backend.processing.vision_handler import VisionHandler

handler = VisionHandler({"vision_settings": {}})

# User's actual truncated JSON snippet
test_str = """{
  "receipt_type": "電子發票證明聯",
  "header": {
    "supplier": "FamilyMart",
    "buyer": null,
    "invoice_id": "UF-82006347",
    "date": "2025-11-20"
  },
  "items": [
    {
      "name": "原萃鐵觀音",
      "qty": 1,
      "price": 19,
      "total": 19
    },
    {
      "name": "原萃鐵觀音",
      "qty": 1,
      "price": 19,"""

repaired = handler._repair_json(test_str)
print("--- REPAIRED STRING ---")
print(repaired)

print("\n--- JSON LOAD TEST ---")
try:
    data = json.loads(repaired)
    print("SUCCESS: JSON is valid!")
    import pprint
    pprint.pprint(data)
except Exception as e:
    print(f"FAILED: {e}")
