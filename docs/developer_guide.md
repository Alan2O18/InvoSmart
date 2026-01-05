# 開發者指南 (Developer Guide)

本指南提供開發者深入了解 Backend 架構和開發流程所需的資訊。

---

## 專案架構

```
backend/
├── main.py              # FastAPI 入口
├── dependencies.py      # 依賴注入
├── engine/              # 核心引擎 (Singleton)
├── managers/            # 專案/任務管理 (Facade)
├── processing/          # OCR/LLM/VLM 處理器
├── routers/             # API 路由
└── utils/               # 工具函數
```

---

## 核心元件

### 1. Engine (引擎單例)

```python
from backend.engine.core import get_engine

engine = get_engine()
engine.create_project("活動名稱")
engine.run_ocr("project_id")
```

**職責**: 協調所有子系統，管理專案生命週期。

### 2. TaskManager (任務管理器)

```python
tm = engine.get_task_manager("project_id")
jobs = tm.list_jobs()
job = tm.get_job("job_id")
```

**狀態機流程**:
```
ready → running → done
         ↓
       failed
```

### 3. Processing 處理器

| 處理器 | 用途 |
|--------|------|
| `ReceiptProcessorV2` | **核心流水線**：協調所有子處理器 |
| `RapidOCRHandler` | 主要 OCR 引擎 (RapidOCR ONNX) |
| `VisionHandler` | VLM 視覺識別 (Qwen VL) |
| `AuditHandler` | 稽核與交叉驗證 (Rule + LLM) |
| `KeywordClassifier` | 收據類型分類器 |
| `QRHandler` | QR Code 偵測與解碼 |
| `GemmaCorrector` | 自動錯誤修正器 |
| `LLMHandler` | (Legacy) 文字校正和結構化 |
| `OCRHandler` | (Legacy) PaddleOCR 處理器 |

---

## 資料流

```
圖片上傳 
  ↓
ReceiptProcessorV2.process()
  ↓
1. RapidOCR → 取得文字與座標
  ↓
2. KeywordClassifier → 判斷類型 (電子/手寫/其他)
  ↓
3. 分流處理:
   ├─ 電子發票: QRHandler 解碼 + VLM 補強
   ├─ 手寫收據: VisionHandler (VLM) 識別
   └─ 其他收據: 純 OCR + LLM 結構化
  ↓
4. AuditHandler → 交叉驗證 (OCR vs QR vs VLM)
  ↓
5. DataValidator → 數學邏輯檢查
  ↓
6. (Optional) GemmaCorrector → 自動修正
  ↓
輸出最終 JSON
```

### 處理流水線

```python
# backend/processing/receipt_processor.py

def process(self, image_array) -> dict:
    # Step 1: 基礎 OCR 與資訊提取
    ocr_result, stats = self.rapidocr.do_ocr(image_array)
    qr_data = self.qr_handler.detect_and_decode(image_array)
    
    # Step 2: 智慧分類
    receipt_type = self.classifier.classify(ocr_result, qr_data)
    
    # Step 3: 策略分發
    if receipt_type == ReceiptType.ELECTRONIC:
         result = self._process_electronic(image_array, ocr_result, qr_data)
    elif receipt_type == ReceiptType.HANDWRITTEN:
         result = self._process_handwritten(image_array)
    else:
         result = self._process_standard(ocr_result)
         
    # Step 4: 稽核與驗證
    audit_result = self.audit_handler.audit(result, qr_data)
    
    # Step 5: 結果組合
    return self._finalize_result(result, audit_result)
```

---

## JSON 資料格式

### LLM 輸出 (新格式)

```json
{
    "receipt_type": "電子發票",
    "header": {
        "supplier": "供應商",
        "invoice_id": "AB12345678",
        "date": "2024-12-19",
        "tax_id": "12345678"
    },
    "items": [
        {"name": "品名", "qty": 1, "price": 100, "total": 100}
    ],
    "summary": {"total": 100},
    "audit": {
        "confidence": 0.95,
        "issues": [],
        "corrections": [
            {"source": "gemma", "timestamp": 1734567890, "description": "自動修正"}
        ]
    }
}
```

### OCR 統計

```json
{
    "engine": "rapidocr",
    "total_time_s": 2.35,
    "text_blocks_count": 15,
    "started_at": 1734567890,
    "completed_at": 1734567893
}
```

---

## 新增處理器

### 步驟 1: 建立處理器類別

```python
# processing/my_handler.py
class MyHandler:
    def __init__(self, config: dict):
        self.config = config
    
    def process(self, data) -> tuple[dict, dict]:
        # 返回 (result, stats)
        return result, stats
```

### 步驟 2: 註冊到引擎

```python
# engine/core.py
self.my_handler = MyHandler(self.config)
```

---

## 測試

### 執行所有測試
```bash
micromamba activate OCR_GA
pytest tests/ -v
```

### 執行特定測試
```bash
pytest tests/test_processing.py::TestLLMHandler -v
```

### 測試覆蓋率
```bash
pytest tests/ --cov=backend --cov-report=html
```

---

## 常用命令

```bash
# 啟動開發伺服器
micromamba activate OCR_GA
python -m uvicorn backend.main:app --reload

# 執行測試
pytest tests/ -v

# 格式化程式碼
black backend/ tests/

# 類型檢查
mypy backend/
```

---

## 相關文檔

- [快速開始](./quickstart.md)
- [API 參考](./api_reference.md)
- [JSON Schema](./json_schema.md)
- [資料庫轉換計畫](./資料庫轉換計畫A.md)
