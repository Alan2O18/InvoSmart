# AI Agent Lab - VLM-First 收據處理系統

> **版本**: V2 (VLM-First Architecture)
> **核心引擎**: Google Gemini 2.5 Flash Lite (OpenAI Compatible)

本專案是一個現代化的收據處理系統，採用 **VLM-First (Vision Language Model)** 策略。我們摒棄了傳統複雜的 OCR + RegEx 流水線，直接利用大型視覺語言模型的圖像理解能力，實現 "High Trust, Verify Later" 的高效處理流程。

![VLM-First Architecture](https://placehold.co/800x200/2c3e50/ffffff?text=VLM+First+Architecture)

---

## 核心特色

- **🚀 VLM-First 架構**: 直接將收據圖片送入 Gemini Flash Lite，一次性完成文字識別、版面分析與結構化提取。
- **🧹 Zero Ollama**: 移除本地 LLM 依賴，大幅降低硬體需求，不再需要高階 GPU。
- **✅ 雙重驗證機制**: 
  - **QR Code**: 針對電子發票，利用 QR Code 作為絕對真理 (Ground Truth)。
  - **Python Validator**: 純程式邏輯驗算金額與日期，確保資料一致性。
- **⚡ 高效能後端**: 基於 FastAPI 與 SQLite WAL 模式，支援高並發非同步處理。
- **🎨 現代化前端**: Vue 3 + Tailwind CSS 提供流暢的操作體驗。

---

## 文件索引

詳細文檔請參考 `docs/` 目錄：

- **[快速開始 (Quickstart)](docs/quickstart.md)**: 安裝依賴、設定 API Key 與啟動系統。
- **[處理流程 (Pipeline)](docs/pipeline.md)**: 了解 VLM -> QR -> Validator 的處理流水線。
- **[API 參考 (API)](docs/api.md)**: 後端 API 規格說明。
- **[資料庫設計 (Database)](docs/database.md)**: SQLite Schema 設計與 WAL 模式說明。
- **[JSON 結構 (JSON)](docs/json_structure.md)**: VLM 輸出與前後端資料交換格式。
- **[開發者指南 (Developer)](docs/developer_guide.md)**: 程式碼架構與開發規範。

---

## 系統架構

### 技術堆疊
| 前端 (Frontend) | 後端 (Backend) | 資料庫 (Database) | AI 模型 (Model) |
|---|---|---|---|
| Vue 3 | FastAPI (Python) | SQLite (WAL Mode) | Gemini 2.5 Flash Lite |
| Vite | OpenAI SDK | (Distributed Files) | QReader (QR Code) |
| Tailwind CSS | NumPy / OpenCV | | |

### 資料流
1. **上傳**: 使用者上傳收據/發票圖片。
2. **VLM 分析**: Backend 直接呼叫 VLM API 取得結構化 JSON。
3. **QR 校正**: 若為電子發票，嘗試解碼 QR Code 並覆蓋 VLM 結果。
4. **邏輯驗算**: Python Validator 檢查金額恆等式 (`Qty * Price == Total`)。
5. **人工確認**: 使用者在前端介面檢視結果 (信心度不足時顯示警告)。

---

## 快速啟動

### 1. 環境設定
請先申請 Google Gemini API Key (或任何 OpenAI 兼容服務)。

```bash
# 複製範例設定
cp config.example.json config.json

# 編輯 config.json 填入 API Key
# "vision_settings": { "api_key": "YOUR_KEY", ... }
```

### 2. 啟動後端
```bash
# 請在專案根目錄執行
micromamba activate OCR_GA
python -m uvicorn backend.main:app --reload
```
> 後端將運行於 `http://localhost:8000` (API Docs: `/docs`)

### 3. 啟動前端
```bash
cd frontend
npm install
npm run dev
```
> 前端將運行於 `http://localhost:5173`

---

## License
MIT License
