# 開發者指南 (Developer Guide)

> **版本**: V2 (VLM-First)
> **日期**: 2026-02-17

本指南協助開發者理解 AI Agent Lab 的後端架構與開發流程。系統已全面轉向 **VLM-First** 架構，移除傳統 OCR 流水線。

---

## 1. 專案架構

```
backend/
├── main.py              # FastAPI 應用程式入口
├── dependencies.py      # 依賴注入 (get_engine)
├── engine/              # 核心協調層
│   ├── core.py          # Engine 類別 (Singleton)
│   └── workers.py       # Global Worker 迴圈
├── processing/          # 業務邏輯層
│   ├── receipt_processor.py  # 主要處理入口
│   ├── vision_handler.py     # VLM (OpenAI SDK)
│   ├── qr_handler.py         # QR Code 解碼
│   └── python_validator.py   # 邏輯驗算
├── repositories/        # 資料存取層
│   ├── project_repository.py # Global DB
│   ├── job_repository.py     # Project DB
│   └── suggestion_repository.py # Suggestion DB
└── routers/             # API路由
    ├── projects.py      # 專案管理
    ├── jobs.py          # 任務操作
    ├── processing.py    # 批次執行
    └── ...
```

---

## 2. 核心開發概念

### 2.1 Engine (單例模式)
系統的核心中樞，負責：
- 管理 `TaskQueue` 與 `GlobalWorker`。
- 持有 `ProjectRepository` 與 `ReceiptProcessor` 實例。
- 協調跨模組操作。

```python
# 取得 Engine 實例
from backend.engine.core import get_engine
engine = get_engine()
```

### 2.2 VLM-First 處理流程
開發新功能時，請遵循 "High Trust, Verify Later" 原則：
1. **相信 VLM**: 優先使用 `VisionHandler` 獲取結構化資料。
2. **驗證**: 使用 `PythonValidator` 或 `QRHandler` 進行檢查。
3. **不要** 引入繁瑣的 OCR 前處理或圖像切割。

### 2.3 資料庫存取
- **Global DB**: 用於專案列表、詞彙庫。(使用 `ProjectRepository`)
- **Job DB**: 每個專案獨立一個 DB，用於儲存任務結果。(使用 `JobRepository`)

---

## 3. 環境設定與 API Key

本專案依賴 OpenAI Compatible API (如 Google Gemini)。

### 設定方式
1. **環境變數**: 在 `.env` 或系統環境變數中設定 `GOOGLE_API_KEY`。
2. **設定檔**: 在 `config.json` 中設定 `vision_settings.api_key`。

```json
// config.json
{
    "vision_settings": {
        "api_key": "YOUR_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model_name": "gemini-2.5-flash-lite",
        "reasoning_effort": "medium"  // 開啟思考模式 (low/medium/high)
    }
}
```

---

## 4. 測試開發

由於架構變更，舊有的測試可能已失效。請遵循 **V2 測試策略**：

### 執行單元測試
(待更新 `tests/` 目錄後)

```bash
micromamba activate OCR_GA
pytest tests/
```

### 手動測試 (API)
啟動後端後，可訪問 Swagger UI 進行測試：
- URL: `http://localhost:8000/docs`

---

## 5. 常見任務指引

### 新增一個 API 端點
1. 在 `backend/routers/` 建立或修改對應的 `.py` 檔。
2. 定義 Pydantic Model (若需要)。
3. 在 `backend/main.py` 中 `include_router`。

### 修改 VLM Prompt
1. 編輯 `backend/processing/vision_handler.py` 中的 `DEFAULT_PROMPT` 常數。
2. 確保 Prompt 的 JSON 範例與 `docs/json_structure.md` 保持一致。

### 新增驗證邏輯
1. 編輯 `backend/processing/python_validator.py`。
2. 在 `validate()` 方法中加入新的檢查規則。
3. 更新 `ValidationResult` 的評分權重。

---

## 6. 相關文檔索引

- [API 參考 (API)](./api.md)
- [資料庫設計 (Database)](./database.md)
- [處理流程 (Pipeline)](./pipeline.md)
- [JSON 結構 (JSON Structure)](./json_structure.md)
