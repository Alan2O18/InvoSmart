# 快速開始 (Quickstart)

> **版本**: VLM-First V2
> **狀態**: 已更新 (Zero Ollama)
> **日期**: 2026-02-17

本指南將協助您快速建立 AI Agent Lab 的開發環境。本專案目前採用 VLM-First 架構，完全依賴 OpenAI 相容介面（如 Google Gemini 或 OpenRouter）進行視覺處理，**無需本地安裝 Ollama 或重型 OCR 引擎**。

## 1. 系統需求 (Prerequisites)

- **Python**: 3.10 或更高版本
- **Node.js**: v16 或更高版本 (前端開發用)
- **API Key**: 必須擁有一個支援 OpenAI 介面的 VLM 服務金鑰（推薦 Google Gemini Flash Lite）。

## 2. 後端設置 (Backend Setup)

目前我們使用 micromamba 進行虛擬環境管理。
環境名稱為 OCR_GA


### 安裝依賴

```bash
pip install -r requirements.txt
```

> **注意**: 專案已移除 PaddleOCR 與 Local LLM 依賴，安裝過程應相當快速。

### 設定環境變數

在專案根目錄建立 `.env` 檔案（或直接修改 `config.json`），設定您的 API Key：

```bash
# .env 範例
GOOGLE_API_KEY=your_gemini_api_key_here
# 若使用其他 OpenAI 相容服務：
# OPENAI_BASE_URL=https://openrouter.ai/api/v1
# OPENAI_API_KEY=your_openrouter_key
```

或者，您可以直接編輯 `config.json` 中的 `vision_settings`：

```json
{
    "vision_settings": {
        "api_key": "your_key",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model_name": "gemini-2.5-flash-lite"
    }
}
```

## 4. 啟動後端服務
```bash
# 啟動開發伺服器
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

服務啟動後可訪問：
- **API 文檔**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 5. 前端設置 (Frontend Setup)

開啟新的終端機視窗：

```bash
cd frontend
npm install
npm run dev
```

前端介面預設運行於 `http://localhost:5173`。

## 6. 驗證安裝

1. 打開瀏覽器訪問 `http://localhost:5173`。
2. 進入「專案管理」，建立一個新專案。
3. 上傳一張收據圖片。
4. 觀察後端 Log，確認 `VisionHandler` 成功調用遠端 API 並返回結果。
5. 若能看到識別出的收據內容，即代表安裝成功。

---

## 常見問題

**Q: 我需要安裝 CUDA 嗎？**
A: **不需要**。VLM 運算在雲端進行，RapidOCR (用於輔助驗證) 使用 ONNX Runtime CPU 版本即可流暢運行。

**Q: 為什麼找不到 Ollama 設定？**
A: 本專案已棄用 Ollama。所有圖文理解與邏輯判斷皆由 VLM (Gemini Flash Lite) 一次完成。
