# 文檔重構計畫 (Documentation Rebuild Plan)

> **狀態**: 規劃中 (已通過深度審閱)
> **目標**: 依據 VLM-First V2 架構全面重寫專案文檔，清理 Ollama 與 舊 OCR 的殘留資訊，建立現代化視覺處理管線文檔。

---

## 0. 規劃核心原則 (Design Principles)
- **VLM-First**: 將視覺模型識別作為第一等公民，不再視為 OCR 的補充。
- **Zero Ollama**: 完全移除本機 LLM 依賴，轉向高效能 SaaS VLM。
- **Security First**: 文件中必須明確說明 API Key 的安全處理流程（設定、遮罩、環境變數）。
- **Data Segregation**: 明確區分「全域配置」與「專案資料」的資料庫邊界。

---

## 1. 核心文檔重構 (Core Documents)

以下文檔將被**完全重寫**或**大幅更新**，以反映目前的系統狀態。

| 目標檔案 | 說明 | 來源/依據 |
|---|---|---|
| **`docs/quickstart.md`** | 快速開始指南 | 更新安裝步驟，移除 Ollama 與舊 OCR 依賴，僅保留 VLM 相關設定。 |
| **`docs/api.md`** | API 介面規格 | 整合並更新 `api_reference.md`，新增 Suggestions 與 Config 端點。 |
| **`docs/database.md`** | 資料庫 Schema | 更新 `database_schema.md`，包含 Global DB 與 Project DB (VLM Schema)。 |
| **`docs/json_structure.md`** | JSON 資料結構 | 更新 `json_schema.md`，定義 VLM 輸出的結構化資料與 Metadata。 |
| **`docs/pipeline.md`** | 處理流程說明 | 更新 `processing_pipeline.md`，描述 VLM -> QR -> Validator 流程。 |
| **`docs/testing_v2.md`** | 測試策略 (新) | **[NEW]** 取代過時的測試文檔，針對 VLM 架構重新定義測試範圍。 |

## 2. 現有文檔處置 (Existing Docs Disposition)

針對 `docs/` 目錄下現有檔案的處置建議：

| 檔案名稱 | 處置方式 | 理由 |
|---|---|---|
| `api_reference.md` | **重命名/更新** | 重命名為 `api.md`，移除舊 OCR 相關端點描述。 |
| `backend_architecture.md` | **覆蓋 (Overwrite)** | 使用 `dev_data/plan/backend_architecture_v2.md` 的內容覆蓋。 |
| `database_schema.md` | **重命名/更新** | 重命名為 `database.md`，移除過時欄位。 |
| `developer_guide.md` | **更新** | 移除 Ollama 相關內容，專注於 VLM API Key 與環境變數設定。 |
| `empty_receipt_template.json` | **保留** | 作為測試或範例資料仍有用。 |
| `json_schema.md` | **重命名/更新** | 重命名為 `json_structure.md`。 |
| `processing_pipeline.md` | **更新** | 移除 RapidOCR/PaddleOCR 詳細流程，改為 VLM 為主。 |
| `quickstart.md` | **更新** | 簡化步驟，移除 Ollama 及舊依賴。 |
| `refactoring_plan.md` | **刪除/歸檔** | 已完成階段性任務，內容已過時。 |
| `testing_plan.md` | **標記過時 (Deprecated)** | 內容與現況不符，將建立 `testing_v2.md`。 |
| `testing_todo.md` | **標記過時 (Deprecated)** | 內容與現況不符。 |
| `README.md` (Root) | **更新** | 作為入口文件，需摘要上述所有變更。 |

## 3. 執行順序

1.  **建立/更新核心文檔**：優先建立 API, DB, JSON, Pipeline 文檔。
2.  **更新架構文檔**：將 V2 架構圖寫入 `docs/backend_architecture.md`。
3.  **更新指南**：更新 Quickstart 與 Developer Guide。
4.  **清理**：刪除或歸檔不再需要的舊計畫文件。
5.  **Root README**：最後更新根目錄 README，索引所有新文檔。

## 4. 詳細內容規劃

### `docs/quickstart.md`
- [ ] 前置需求：Python 3.10+, Node.js
- [ ] 環境變數設置：`GOOGLE_API_KEY` (或相容的 OpenAI Base URL)
- [ ] 安裝指令：Poetry 或 pip requirements (移除 Ollama)
- [ ] 啟動指令：Backend & Frontend

### `docs/api.md`
- [ ] Projects: CRUD, Status
- [ ] Jobs: List, Query
- [ ] Processing: Run VLM (VLM-First)
- [ ] Suggestions: Search, Add
- [ ] Config: Update Settings

### `docs/database.md`
- [ ] Global DB: `projects`, `groups`, `vocabulary`
- [ ] Job DB: `jobs` (Status, VLM Result), `events`

### `docs/json_structure.md`
- [ ] Root Object
- [ ] Header (Invoice info)
- [ ] Items (Line items)
- [ ] Summary (Amounts)
- [ ] Metadata (Confidence, QR status)

### `docs/pipeline.md`
- [ ] VLM Analysis (Gemini/OpenAI)
- [ ] QR Verification (QReader)
- [ ] Python Validation (Pure Logic)
