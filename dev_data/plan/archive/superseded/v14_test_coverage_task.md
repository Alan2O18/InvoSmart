# 測試覆蓋率提升任務 (Test Coverage Improvement Task)

- [x] **Pre-requisites: 環境與 Bug 修復**
  - [x] 修復 `backend/routers/files.py` 的 Sync/Async 錯誤
  - [x] 修復 `backend/routers/websocket.py` 的 `get_jobs` async 調用錯誤
  - [x] 修復 `backend/routers/correction.py` 的 `save_manual_text` async 調用錯誤
  - [x] 修正 `workers.py` 中 `asyncio.run` 事件衝突隱患
  - [x] 清除多餘的 `import sqlite3` (`jobs.py`, `regeneration_handler.py`)
  - [x] 於 `conftest.py` 建立 `mock_app_client` 路由依賴注入測試夾具

- [x] **Phase 1:### 階段一：路由層核心 API (API Routers) [x]**
- [x] 配置 `conftest.py` 以支援 `TestClient` (新增 `mock_app_client`)
- [x] 撰寫與測試 `projects.py` 端點 (新增、查詢、刪除、更新狀態)
- [x] 撰寫與測試 `jobs.py` 端點 (取得工作列表與細節、刪除工作)
- [x] 撰寫與測試 `processing.py` 端點 (觸發分割、VLM 處理、匯出、封存)
- [x] 撰寫與測試 `files.py` 端點 (上傳、刪除原始檔)
- [x] 撰寫與測試 `correction.py` 端點 (儲存人工修正)
- [x] 撰寫與測試 `groups.py` （專案群組管理 API）
- [x] 撰寫與測試 `config.py` （後端設定 API）
- [x] **Phase 2: 引擎後端處理層 (Engine Handlers)**
  - [x] `tests/test_word_exporter.py` (含內部 `_replace` 系列單元測試)
  - [x] `tests/test_archive_handler.py` (7z 與 zip 相容性)
  - [x] `tests/test_regeneration_handler.py` (Excel 與狀態更新)
  - [x] `tests/test_file_ops.py` (檔案分離、儲存與旋轉) 

- [x] **Phase 3: 工作者、WebSocket 與儲存庫 (workers, ws, suggestion_repo)**
  - [x] `tests/test_workers.py` (任務失敗保護)
  - [x] `tests/test_suggestion_repository.py` (RAG Context、知識萃取)
  - [x] WebSocket 推播機制 (`TestClient.websocket_connect`)

- [x] **Phase 4: 全局端點整合 (main, suggestions)**
  - [x] `backend/main.py` lifespan 及 CORS
  - [x] `backend/routers/suggestions.py` (自動完成推薦)

- [x] **Phase 5: 核心處理管線與儲存庫 (Optional)**
  - [x] `vision_handler.py` & `qr_handler.py`
  - [x] `rapidocr_handler.py` & `receipt_splitter.py`
  - [x] `project_repository.py` & `job_repository.py`
  - [x] `engine/core.py` & `receipt_processor.py`
