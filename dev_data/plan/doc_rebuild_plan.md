# 文檔重構計畫 (Documentation Rebuild Plan)

> **狀態**: 規劃中
> **目標**: 依據 VLM-First 架構全面重寫專案文檔，清除過時資訊。

---

## 1. 核心文檔重構 (Core Documents)

以下文檔將被**完全重寫**或**大幅更新**，以反映目前的系統狀態。

| 目標檔案 | 說明 | 來源/依據 |
|---|---|---|
| **`docs/quickstart.md`** | 快速開始指南 | 更新安裝步驟，強調 OpenAI API Key 配置與 Ollama 設置。 |
| **`docs/api.md`** | API 介面規格 | 整合並更新 `api_reference.md`，新增 Suggestions 與 Config 端點。 |
| **`docs/database.md`** | 資料庫 Schema | 更新 `database_schema.md`，包含 Global DB 與 Project DB (VLM Schema)。 |
| **`docs/json_structure.md`** | JSON 資料結構 | 更新 `json_schema.md`，定義 VLM 輸出的結構化資料與 Metadata。 |
| **`docs/pipeline.md`** | 處理流程說明 | 更新 `processing_pipeline.md`，描述 VLM -> QR -> Validator 流程。 |

## 2. 現有文檔處置 (Existing Docs Disposition)

針對 `docs/` 目錄下現有檔案的處置建議：

| 檔案名稱 | 處置方式 | 理由 |
|---|---|---|
| `api_reference.md` | **重命名/更新** | 重命名為 `api.md`，移除舊 OCR 相關端點描述。 |
| `backend_architecture.md` | **覆蓋 (Overwrite)** | 使用 `dev_data/plan/backend_architecture_v2.md` 的內容覆蓋。 |
| `database_schema.md` | **重命名/更新** | 重命名為 `database.md`，移除過時欄位。 |
| `developer_guide.md` | **更新** | 保留開發流程與環境設定，更新為現代化工具鏈說明。 |
| `empty_receipt_template.json` | **保留** | 作為測試或範例資料仍有用。 |
| `json_schema.md` | **重命名/更新** | 重命名為 `json_structure.md`。 |
| `processing_pipeline.md` | **更新** | 移除 RapidOCR/PaddleOCR 詳細流程，改為 VLM 為主。 |
| `quickstart.md` | **更新** | 簡化步驟，移除舊依賴安裝說明。 |
| `refactoring_plan.md` | **刪除/歸檔** | 已完成階段性任務，內容已過時。 |
| `testing_plan.md` | **保留/更新** | 測試策略仍適用，需更新針對 VLM 的測試項目。 |
| `testing_todo.md` | **保留** | 仍有待辦測試項目。 |
| `README.md` (Root) | **更新** | 作為入口文件，需摘要上述所有變更。 |

## 3. 執行順序

1.  **建立/更新核心文檔**：優先建立 API, DB, JSON, Pipeline 文檔。
2.  **更新架構文檔**：將 V2 架構圖寫入 `docs/backend_architecture.md`。
3.  **更新指南**：更新 Quickstart 與 Developer Guide。
4.  **清理**：刪除或歸檔不再需要的舊計畫文件。
5.  **Root README**：最後更新根目錄 README，索引所有新文檔。

## 4. 詳細內容規劃

### `docs/quickstart.md`
- [ ] 前置需求：Python 3.10+, Node.js, Ollama (Optional)
- [ ] 環境變數設置：`GOOGLE_API_KEY`, `OLLAMA_HOST`
- [ ] 安裝指令：Poetry 或 pip requirements
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
