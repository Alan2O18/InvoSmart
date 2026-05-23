# 模組分類盤點：檔案在做什麼、方法在幹嘛

## 1) 全專案檔案分類

依實際掃描結果，檔案可分為：

- 核心後端程式：`backend/`
- 前端應用程式：`frontend/src/`、`frontend/tests/`
- 前端第三方依賴與建置產物：`frontend/node_modules/`、`frontend/dist/`
- 資料庫與資料檔：`*.db`、`backend/data/`、`dev_data/`
- 開發/遷移腳本：`scripts/`
- 測試：`tests/`、`frontend/tests/`
- 文件：`docs/`
- Migration：`alembic/`
- 設定與專案根檔：`README.md`、`requirements.txt`、`pytest.ini` 等

## 2) Backend 模組與方法用途

### A. API 層 (`backend/routers/`)
用途：接 HTTP 請求，驗證輸入，呼叫 Engine/Repository，回傳 JSON 或檔案。

- `projects.py`: 專案 CRUD、專案資訊
- `files.py`: 原始檔上傳/刪除/旋轉/列舉
- `jobs.py`: job 查詢、手動 JSON、單筆重跑
- `processing.py`: split、處理流程、匯出、封存
- `pdf.py`: PDF 上傳與命令式編輯
- `voucher.py`: 憑證模板、草稿、產生 PDF
- `groups.py`: 群組與主管章管理
- `config.py`: 模型設定、供應商推斷與更新
- `suggestions.py`: 建議詞查詢/新增
- `websocket.py`: 即時狀態推播

常見方法類型：
- `list_*`, `get_*`, `create_*`, `update_*`, `delete_*`：典型 REST 端點
- `_parse_*`, `_normalize_*`, `_resolve_*`：在 router 內做 payload 前置整理

### B. Engine 層 (`backend/engine/`)
用途：跨模組協調、背景任務、輸出與憑證生成。

- `core.py` / `Engine`: 全系統中樞，持有 repository 與 processor，提供排程與任務管理
- `workers.py`, `pdf_worker.py`: 背景 worker loop
- `export.py`, `excel_exporter.py`, `word_exporter.py`: 匯出報表
- `archive_handler.py`, `regeneration_handler.py`: 封存/重生相關流程
- `file_ops.py`: 檔案操作共用能力
- `voucher_generator.py`: 使用 PyMuPDF 生成憑證 PDF
- `voucher_text_config.py`: 憑證文字欄位配置

常見方法類型：
- `*_worker_loop(...)`: 持續消化 queue 的工作迴圈
- `generate_*`, `run_*`, `enqueue_*`: 執行型工作流方法
- `get_*_layout`, `get_*_config`: 版面與配置提供

### C. Processing 層 (`backend/processing/`)
用途：VLM/QR/驗算與影像處理核心。

- `receipt_processor.py` / `ReceiptProcessor`: 串接視覺辨識、QR、驗算
- `vision_handler.py` / `VisionHandler`: VLM API 呼叫與結果解析
- `qr_handler.py` / `QRHandler`: QR 解碼與覆寫
- `python_validator.py` / `PythonValidator`: 邏輯驗算與信心度
- `image_preprocessor.py`, `perspective_transform.py`, `contour_validator.py`: 影像前處理與幾何修正
- `pdf_engine.py`: PDF 命令執行（壓縮、重排、蓋章、文字層）
- `flattening.py`: Job 結果扁平化聚合
- `jxl_encoder_backend.py`, `image_codec_adapter.py`: 影像編碼能力

常見方法類型：
- `process(...)`: 單一入口
- `validate(...)`, `detect_and_decode(...)`: 驗證與解碼
- `compress_pdf(...)`, `execute_commands(...)`: PDF 指令流程

### D. Repository / Database (`backend/repositories/`, `backend/database/`)
用途：資料持久化與 DB 操作隔離。

- `project_repository.py`: 全域專案資料管理
- `job_repository.py`: 專案 job 查詢/更新
- `suggestion_repository.py`: 建議詞存取
- `voucher_layout_repo.py`: 憑證草稿 JSON 存取
- `database/models.py`: ORM 模型 (`Project`, `Job`, `InvoiceItem`, `Event`, `Group`, `Suggestion`)
- `database/core.py`: DB 路徑與 SQLite pragma

常見方法類型：
- `list_*`, `get_*`, `save_*`, `update_*`
- DB 初始化與連線設定方法

### E. Utils / Dependency (`backend/utils/`, `backend/dependencies.py`)
用途：設定、logger、解析器、影像 IO、依賴注入。

- `load_config`, `save_config`
- `setup_logging`, `get_logger`
- `extract_structured_data`
- `cv_imread_chinese`, `cv_imwrite_chinese`
- `get_engine`, `get_sync_db`

## 3) Frontend 模組與方法用途

### A. API Service (`frontend/src/services/api.js`)
用途：集中封裝後端 API 呼叫（47 個方法）。

方法群組：
- 專案：`getProjects`, `createProject`, `getProjectDetail`, `updateProject`
- 檔案/任務：`addFiles`, `getProjectJobs`, `deleteJob`
- 處理流程：`runSplit`, `runProcessing`
- 匯出：`runExport`, `runWordExport`
- 憑證：`getVoucherTemplate`, `saveVoucherLayout`, `generateVoucherFromLayout`
- 設定/建議詞：`getConfig`, `updateConfig`, `getSuggestions`, `addSuggestion`

### B. Views (`frontend/src/views/`)
用途：頁面級業務流程與 UI 狀態管理。

- `ProjectDetailView.vue`、`JobEditorView.vue`：任務主操作頁
- `VoucherEditorView.vue`：憑證編輯主流程（方法最多，73）
- `VoucherTemplateConfigView.vue`：模板配置頁（58）
- `SettingsView.vue`：系統設定
- `KanbanView.vue`：看板與狀態視覺化

常見方法類型：
- `load*`, `refresh*`, `handle*`, `save*`, `submit*`

### C. Components (`frontend/src/components/`)
用途：可重用操作元件。

- `ImageViewer.vue`: 縮放/拖曳/定位
- `PdfWorkbench.vue`: PDF 頁面操作與命令輸出
- `JsonFieldEditor.vue`, `SmartJsonEditor.vue`: JSON 欄位編輯

### D. Utils (`frontend/src/utils/voucher.js`)
用途：憑證頁面布局計算、欄位切分、文字配置與碰撞控制。

關鍵函式類型：
- 布局模擬：`simulateLayout(...)`
- 欄位推入：`pushPointEntry(...)`, `pushMultilineEntry(...)`
- 幾何計算與頁面安排邏輯

## 4) Scripts / Tests / Docs 在做什麼

- `scripts/`: 資料遷移、除錯、一次性修復、驗證腳本
- `tests/`: backend 單元測試與整合測試
- `frontend/tests/`: voucher 相關契約與工具測試
- `docs/`: API、資料庫、流程、後端架構說明

## 5) 「所有檔案」怎麼對應到這份盤點

- 若要逐檔查看：開 `all_files_inventory.txt`
- 若要看每個 Python 檔的方法密度：開 `python_symbols_count_by_file.md`
- 若要看前端方法密度：開 `frontend_symbols_count_by_file.md`
- 若要看詳細宣告行：開 `python_symbols_inventory.txt`、`frontend_symbols_inventory.txt`
