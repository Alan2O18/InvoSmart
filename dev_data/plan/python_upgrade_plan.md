# Python 3.12 升級與依賴清理計畫

## 目標
將專案環境升級至 **Python 3.12.12**，並移除所有本地 AI 模型依賴 (PaddleOCR, PyTorch, Transformers)，僅保留 VLM-First 架構所需的輕量級套件。

## 1. 核心依賴分析

### 必須保留 (VLM-First Core)
- **FastAPI / Uvicorn**: Web 框架與伺服器。
- **OpenAI**: VLM API 客戶端 (Gemini/OpenRouter)。
- **OpenCV-Python-Headless / NumPy**: 影像前處理 (不需 GUI)。
- **QReader / Pyzbar / Ultralytics**: QR Code 解碼 (QReader 依賴 YOLOv8，但比 full torch 輕量)。
  - *注意*: `qreader` 會自動安裝 `ultralytics`，雖含 torch 但為 inference-only 較輕量。若需極致輕量可考慮僅用 pyzbar，但 QReader 準確度較高。目前保留 QReader。
- **Pydantic**: 資料驗證。
- **Python-Multipart**: 檔案上傳。
- **Python-Dotenv**: 環境變數。

### 必須移除 (Obsolete)
- `paddlepaddle`, `paddleocr`: 舊 OCR 引擎。
- `torch` (完整版 training libs), `torchvision`: 舊 ML 依賴。
- `transformers`, `huggingface-hub`: 本地 LLM 依賴。
- `markdownify`, `beautifulsoup4`: 舊 HTML 轉 Markdown 依賴。
- `opencc-python-reimplemented`: 舊繁簡轉換 (VLM 直接輸出繁體)。

## 2. 新版 requirements.txt 草稿

```text
# Web Framework
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
python-multipart>=0.0.9
python-dotenv>=1.0.1

# AI & Vision
openai>=1.14.0
opencv-python-headless>=4.9.0
numpy>=1.26.0

# QR Code (Optional but recommended)
qreader>=3.12
# Note: qreader installs ultralytics which includes torch (cpu). 
# This is acceptable for "inference only" usage.

# Utilities
httpx>=0.27.0
aiofiles>=23.2.1
pydantic>=2.6.0
pydantic-settings>=2.2.0
```

## 3. 文件更新
- 更新 `docs/quickstart.md`: 強調 Python 3.12+ 與輕量化安裝。
- 更新 `README.md`: 移除 Paddle 相關安裝說明。
- 更新 `docs/developer_guide.md`: 更新開發環境設置。

## 4. 執行步驟
1. 建立 `requirements.txt`。
2. 更新相關文檔。
3. 通知使用者重建環境。
