# V0.0.8 Backend Test Coverage Improvement Plan

## 1. Current State Assessment
經過 `micromamba run -n OCR_GA pytest --cov=backend` 的深度掃描，目前後端整體覆蓋率為 **77%**（368 個測試全數通過）。
雖然表面上綠燈，但核心架構（包含 Worker 佇列處理、Excel 匯出、資料庫連線生命週期等）存在嚴重的覆蓋率盲區 (Coverage Gaps)，這可能導致我們在生產環境遇到未知的 Crash 或 Memory Leak 而無法提早發現。

為確保系統擁有工業級的穩定性，本計畫旨在針對小於 60% 覆蓋率的神經樞紐程式碼進行「邊界條件 (Edge Cases)」與「例外處理 (Exception Handling)」的壓力測試。

---

## 2. 淘汰過時與冗餘測試
目前的 `tests/` 目錄中，存在 8 個「尚未實作」或「已廢棄」的空殼測試檔（大小皆為 23 Bytes，僅包含 `import pytest_asyncio`）。
這批檔案將在 V0.0.8 階段一併移除，以保持測試目錄的整潔度：
1. `test_api.py`
2. `test_api_full.py`
3. `test_archive_handler.py`
4. `test_excel_exporter.py`
5. `test_file_ops.py`
6. `test_integration.py`
7. `test_manual_correction.py`
8. `test_workers.py`

---

## 3. 重點提升目標與詳細測試策略 (Target Coverage: >90%)

### 🔴 優先級別一：核心背景任務系統 (Critical Core)

#### 1. `backend/engine/pdf_worker.py` (目前 13%)
- **痛點分析**：`global_pdf_worker_loop` 與 `_process_pdf_job` 負責處理非同步的 PDF 處理佇列，目前完全沒有測試到這些 Worker 的啟動、重試、任務失敗與例外捕捉。
- **測試策略 (Test Scenarios)**：
  - **Happy Path**：Mock `pdf_task_queue.get()` 回傳正常的專案 ID 與任務 ID，並 Mock `pdf_engine.execute_commands()` 回傳成功，最後 Assert 是否有呼叫 `job_repo.update_job_status()` 將狀態標為已完成。
  - **Exception Branch**：模擬 `pdf_engine.execute_commands()` 拋出 `ValueError("Invalid PDF")`，驗證 Worker 迴圈是否安然無恙（不會中斷跳出），並且 Assert 是否正確將任務狀態標記為 `failed` 並寫入錯誤日誌。
  - **Shutdown Event**：發送 `_shutdown_event.set()`，測試 Worker 是否能優雅地跳出 `while` 迴圈並關閉。

#### 2. `backend/engine/workers.py` (目前 15%)
- **痛點分析**：雖然 V0.0.7 修復了 `test_engine_workers.py` 中 3 個基本的 Mock 測試，但 `global_receipt_worker_loop` 內仍有多個例外捕捉區塊、Fallback 機制以及資料庫處理尚未覆蓋。
- **測試策略 (Test Scenarios)**：
  - **Async/Await Crash**：測試當 `loop.run_until_complete()` 內部拋出 `asyncio.CancelledError` 時的處理。
  - **None Job**：模擬 `task_queue.get()` 取出任務，但資料庫 `job_repo.get_job()` 卻回傳 `None`（任務已被刪除）的防禦性處理。
  - **Job Event Trigger**：驗證任務執行成功或失敗後，是否正確呼叫 `engine.job_repo.emit_event()` 通知 WebSocket。

#### 3. `backend/engine/excel_exporter.py` (目前 12%)
- **痛點分析**：`export_project_to_excel` 與 `generate_excel` 處理了龐大的資料整理與 Excel 格子格式化，但目前缺乏任何資料流的測試。
- **測試策略 (Test Scenarios)**：
  - **Empty Project**：當專案內沒有任何已完成的 Invoice 收據時，測試匯出功能是否優雅回傳空表格或是特定的警告（避免 Pandas 操作空 DataFrame 炸裂）。
  - **Complete Data Formatting**：傳入一個 Mock 的完整收據資料清單（包含統編、日期、科目、多個 Item），透過 `openpyxl` 儲存到記憶體 (`BytesIO`)，再透過 `pandas` 讀出來驗證 Cell 的值是否與 Mock 來源完全吻合（驗證欄位 Mapper 沒有寫錯）。
  - **Missing Optional Fields**：測試某些收據沒有 `tax` 或 `amount` 時，匯出函式是否能補上預設值（`0` 或 `""`）而不報報錯。

#### 4. `backend/database/core.py` (目前 35%)
- **痛點分析**：`get_db` 的 Generator `yield` 與 Session 的 `close()` 機制若有瑕疵，會導致連接池耗盡。
- **測試策略 (Test Scenarios)**：
  - **Session Isolation**：確保呼叫 `get_db()` 能夠正確生出獨立的 `SessionLocal`。
  - **Cleanup on Exception**：寫一個測試函式去依賴 `get_db()`，並在該函式內主動 `raise Exception`，驗證資料庫連線的 `__exit__` 或 `finally` 區塊是否有確實呼叫 `session.close()` 關閉連線。

---

### 🟡 優先級別二：處理與網路邊界 (Edge Cases)

#### 1. `backend/utils/config.py` (目前 50%)
- **測試策略**：
  - 測試在沒有 `.env` 檔案存在時，`resolve_config()` 是否能使用安全的硬編碼預設值。
  - 測試寫入未經授權的路徑時能否正常拋出或記錄錯誤。

#### 2. `backend/processing/contour_validator.py` (目前 52%)
- **測試策略**：
  - 提供極端的無效幾何結構（如邊長為 0 的 bounding box 或交錯不合理的線段），驗證驗證器是否如期回傳 `False` 或提供極地的信心指數，而非產生 Divide by Zero 的例外。

#### 3. `backend/routers/pdf.py` (目前 53%)
- **測試策略**：
  - **Bad Request Validation**：使用 FastAPI `TestClient`，傳遞格式錯誤的 Base64 檔案或不支援的 MimeType (`image/png` 當作 PDF 上傳)，驗證是否回傳正確的 HTTP 400/415 狀態碼，而不是讓後端觸發 500。
  
#### 4. `backend/processing/llm_handler.py` (目前 56%)
- **測試策略**：
  - **Malformed JSON Response**：Mock VLM/OpenAI API 回傳一個破裂的 JSON（如丟掉括號），測試 `repair_json_heuristics` 是否能成功修復，或是至少能正常走到 Fallback / 回傳錯誤而不當機。
  - **Validation Fallback**：即使 LLM 回傳正確的 JSON，但內容違反 Pydantic Schema 時，測試系統能不能漂亮地記錄錯誤並將信心指數歸零。

---

## 4. 執行與交付階段劃分

- 🛠️ **Phase 1: 廢棄檔案清理與資料庫穩定性**
  - 任務：刪除 8 個無用的 `test_*.py` 測試檔。
  - 任務：提升 `database/core.py` 與 `utils/config.py` 的測試。
- 🛠️ **Phase 2: 核心平行 Worker 除錯防護網**
  - 任務：編寫與注入 AsyncMock 以壓力測試 `pdf_worker.py` 與 `workers.py` 的例外處理迴圈，防止背景任務死鎖。
- 🛠️ **Phase 3: Router 與 Parser 的極端邊界檢查**
  - 任務：針對 `llm_handler.py` 與 `pdf.py` 進行惡意/錯誤資料灌入測試 (Fuzzing / Bad inputs)。
- 🛠️ **Phase 4: 報表匯出資料對齊驗證**
  - 任務：使用 in-memory I/O 深度測試 `excel_exporter.py`，確保各種缺漏收據欄位的情境都能正常產出報表。

**驗收標準 (Acceptance Criteria)**：
1. 全系統 `pytest --cov=backend` 需以 Exit Code 0 結束。
2. 後端總覆蓋率提升至 **90% 以上**。
3. `engine/` 資料夾下的平均覆蓋率需超越 85%。
