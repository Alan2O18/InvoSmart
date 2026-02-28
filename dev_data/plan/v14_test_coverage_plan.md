# 後端測試覆蓋率提升計畫 v3（最終修正版）

## 📊 現狀摘要

| 指標 | 數值 |
|---|---|
| 總行數 | 3328 |
| 已覆蓋 | 1692 (51%) |
| 未覆蓋 | 1636 |
| 目標覆蓋率 | **80%+** (需至少新覆蓋 **970** 行) |

---

## 🚨 先導任務：修復與環境準備 (Pre-requisites)

### 1. 潛在 Bug 修復 (Sync/Async Mismatch)
在撰寫測試前，必須先修復在 ORM 重構中遺留的同步/非同步呼叫問題：
- **`files.py` (🔴 高)**：`add_files` 與 `add_project_files` 呼叫了 async 的 engine 方法，需改為 `async def`。但 `get_raw_files` 與 `rotate_image` 為**純同步檔案系統操作**，可保留 `def`。
- **`websocket.py` (🔴 高)**：`get_jobs()` 直接呼叫已轉為 async 的 `job_repo.list_jobs()` 但缺少 `await`，會返回 coroutine。
- **`correction.py` (🔴 高)**：`save_manual_text` 為 `def`，但調用了 async 的 `save_manual_json`。
- **`workers.py` (🟡 中)**：Worker 在同步執行緒內 `asyncio.run()` 呼叫 async 方法，需加上事件迴圈預防與主執行緒衝突。
- **`jobs.py` & `regeneration_handler.py` (🟡 低)**：移除舊版殘留的 `import sqlite3`。

### 2. 測試架構準備 (conftest.py)
> [!IMPORTANT]
> `backend/dependencies.py` 已內建 `set_engine(mock)` 和 `reset_engine()` 函式，**無需** `app.dependency_overrides`。

- **策略**: 在 `conftest.py` 新增一個 `mock_app_client` fixture，內部呼叫 `set_engine(mock_engine)` 注入 Mock，並在 teardown 時呼叫 `reset_engine()` 清理。所有 Phase 1 的 Router 測試共用此 fixture。

---

## 🛠️ 分階段實施計畫

#### Phase 1: 路由層核心 API (API Routers) [DONE]行）
> **定位**: 在現有的 `test_api.py` 與 `test_api_full.py` 基礎上大舉擴充。
- **`projects.py` (33% → 90%)**: 測試建立專案 (上傳檔案)、更新 metadata、獲取列表等所有端點。
- **`jobs.py` (30% → 90%)**: 測試任務發佈 (`/process`)、儲存人工 JSON (`/json`) 及狀態回饋。
- **`processing.py` (36% → 85%)**: 測試觸發分割、VLM 處理、導出等端點的 HTTP 回應。
- **`groups.py` (48% → 95%) & `config.py` (30% → 90%)**: 測試群組 CRUD 與 API Key 遮罩邏輯。
- **`files.py` (35% → 85%) & `correction.py` (0% → 100%)**: 在上述 Bug 修復後補齊端點呼叫。

### Phase 2：引擎後端處理器（預估覆蓋 +420 行）
> **定位**: 覆蓋耗時但極為核心的邏輯，尤其是檔案導出與檔案調度。
- **`word_exporter.py` (8% → 70%)**: (277 行未覆蓋) 優先針對內部輔助方法（`_replace_text_in_paragraph`, `_format_roc_date`, `_fill_budget__*` 等）撰寫獨立單元測試，再測試 `process_export`。
- **`archive_handler.py` (23% → 85%)**: 模擬 7z 成功/失敗退回 ZIP，以及原始檔案排除邏輯 (`include_raw`)。
- **`regeneration_handler.py` (20% → 80%)**: 模擬從 Excel `人工修正` 欄位反向重建 JSON。
- **`file_ops.py` (40% → 80%)**: 模擬圖片分割任務的調度邏輯 (`_prepare_tasks`) 與檔案查詢。
- **`export.py` Facade (未測試)**: 薄層委派，測試 `run_excel`/`run_word`/`seal_project` 是否正確轉發至子 handler。

### Phase 3：工作者、自動完成與 WebSocket 狀態流 [DONE]
> **定位**: 需要較複雜的非同步框架 Mock（事件迴圈切換、WebSocket Client）。
- **`workers.py` (15% → 75%)**: 模擬 `task_queue.get`，測試 Worker 成功/失敗 (`fail_job`) 的邊界狀況，以及 `_load_image` 錯誤抓取。
- **`suggestion_repository.py` (20% → 90%)**: 直接測試 SQLite 邏輯（排序、批量新增、從 manual_json 萃取、RAG Context 構建）。
- **`websocket.py` (22% → 85%)**: 使用 `TestClient.websocket_connect` 或 `httpx.AsyncClient` 實作狀態推播監聽。

### Phase 4：低垂果實 - 主程式與零星端點 [DONE]
- **`main.py` (81% → 90%)**: 測試 App Lifespan 事件 (DB 初始化與 Config 取代)。
- **`suggestions.py` Router (73% → 95%)**: 測試對應的 autocomplete 端點。

### Phase 5：影像處理與外部 AI 串接管道 (Optional / 衝刺 80%)（預估覆蓋 +200 行以上）
> **定位**: 作為達成 80% 大目標後的進階挑戰，或是作為覆蓋率保底防線。
- **`vision_handler.py` & `qr_handler.py` [DONE]**: Mock base64 轉換、重試機制與 QRCode 解析。
- **`rapidocr_handler.py` & `receipt_splitter.py` [DONE]**: OpenCV 裁切邊界處理與 OCR 區塊截取。
- **`project_repository.py` & `job_repository.py` [DONE]**: 測試剩餘的 SQLite 排他性更動與狀態更新。
- **`engine/core.py` & `receipt_processor.py` [DONE]**: 針對大型重構後可能遺漏的新增邊角邏輯進行覆蓋率補強。

---

## 📈 覆蓋率成長預估

| 階段 | 預估新增覆蓋行數 | 累積推估覆蓋率 | 備註 |
|---|---|---|---|
| 本期基礎 | 0 | **51.0%** | (缺漏 1636 行) |
| Phase 1 (Routers) | +300 | **60.0%** | |
| Phase 2 (Handlers)| +420 | **72.6%** | `word_exporter` 佔多數 |
| Phase 3 (WS, Repo)| +150 | **77.1%** | |
| Phase 4 (Main) | + 30 | **78.0%** | |
| Phase 5 (Pipeline)| +200+ | **84.0%+**| (達成 >80% 保底) |
