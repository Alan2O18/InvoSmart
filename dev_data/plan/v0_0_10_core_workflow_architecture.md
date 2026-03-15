# AI Agent Lab — 全生命週期工作流核對書

本文件描述一個專案從**建立**到**交付所有行政文件**的完整生命週期。
輔助機制（建議詞迴圈、影像旋轉等）穿插在對應階段中，不再獨立成章。

---

## 全生命週期流程圖

```
建立專案 ──► 上傳原始檔案 ──► 轉檔(JXL) ──► 切分(大圖才需要)
                                                    │
                                                    ▼
                                            AI 辨識 (VLM)
                                                    │
                                          ┌─────────┴─────────┐
                                          ▼                   ▼
                                    辨識成功            辨識失敗/方向錯
                                          │                   │
                                          │            影像旋轉修正 ◄─┐
                                          │                   │       │
                                          │                   ▼       │
                                          │            重新送 VLM ────┘
                                          │
                                          ▼
                              產生前端快取圖 (AVIF/WebP)
                                          │
                                          ▼
                              人工修正 (Job Editor)
                              ├── 前端載入: 小圖 + JSON
                              ├── 使用者校對並修正欄位
                              ├── 儲存 → 回饋迴圈萃取建議詞
                              └── 確認無誤 → 標記 done
                                          │
                                          ▼
                              資料扁平化 (Flattening)
                              巢狀 items → 2D 關聯表
                                          │
                        ┌─────────────────┼─────────────────┐
                        ▼                 ▼                 ▼
                  報表產生             憑證黏貼紙         專案封存
                  (Excel/Word)        (Voucher PDF)     (Archive)
                        │                 │
                        ▼                 ▼
                  下載實體文件        前端排版(AVIF小圖)
                                          │
                                          ▼
                                   排版 JSON → 後端
                                          │
                                          ▼
                                   高清渲染(JXL原圖寫入PDF)
                                          │
                                          ▼
                                   PDF 壓縮
                                          │
                                          ▼
                                   下載憑證 PDF
```

---

## 階段 1：專案建立與前後文注入

| 步驟 | 動作 | 技術細節 |
|------|------|----------|
| 1-1 | 使用者在前端填寫專案資訊 | 活動名稱、起訖日期、**預算科目群組 (group)** |
| 1-2 | 前端呼叫專案建立 | `POST /api/projects` (僅帶入元資料，不含檔案) |
| 1-3 | 前端呼叫檔案上傳 | `POST /api/projects/{project_id}/files` 夾帶原始檔案 |
| 1-4 | 後端將 metadata 寫入 DB | `project.metadata.group` 後續自動映射至憑證的預算科目 |

---

## 階段 2：影像收錄與 AI 辨識

| 步驟 | 動作 | 技術細節 |
|------|------|----------|
| 2-1 | 接收原始圖檔 | JPG / PNG / BMP |
| 2-2 | **轉檔 → JXL** | 壓縮體積但保留 600dpi 細節。**技術點**：Windows 環境下 Pillow 原生不支援，需引入 `pyvips` 或獨立環境編譯的 `libjxl`/`libavif` 取代純 Python OpenCV 處理。 |
| 2-3a | **大圖** → 智慧切分 | `ReceiptSplitter.split()` 切出每張發票獨立存為 JXL |
| 2-3b | **小圖** → 跳過切分 | 單張發票直接存為 JXL |
| 2-4 | 送交 VLM 辨識 | OpenAI / Ollama Vision → 結構化 JSON |
| 2-5 | 建立 Job 進入佇列 | `engine.enqueue_job()` → 狀態 `pending` → `done` |

**輔助機制 — 影像旋轉**：若掃描方向顛倒，使用者可觸發 `POST /api/projects/{project_id}/rotate/{filename}`，覆寫原圖後重新送交 VLM。
> ⚠️ **關鍵約束**：影像旋轉會導致舊有的 VLM 座標 (x,y,w,h) 失效，實作 `rotate` 時必須**強制清除該 Job 舊有 JSON 資料，並重置狀態為 `pending`** 以防座標錯亂。

---

## 階段 3：人工修正與資料壓平

| 步驟 | 動作 | 技術細節 |
|------|------|----------|
| 3-1 | **產生前端快取圖** | 後端額外生成極小的 **AVIF / WebP** 縮圖 |
| 3-2 | 前端載入 Job Editor | 拉取 VLM JSON + AVIF 小圖，秒開不卡頓 |
| 3-3 | 使用者校對、修正欄位 | `amount`, `supplier_name`, `items[]` 等 |
| 3-4 | 儲存修正 | `PUT /jobs/{job_id}/json` → 寫回 DB |
| 3-5 | **建議詞反饋萃取** | 儲存時後端非同步攔截，將店名/品項寫入 `suggestions` 表 |
| 3-6 | 確認完成 → 狀態標記 `done` | |
| 3-7 | **資料扁平化 (Flattening)** | 將巢狀 `items` + `summary` 壓成 2D 關聯表，提早儲存備用。**建議採用背景 Task 非同步執行**，避免使用者按下 Done 時等待過久 Timeout。 |

**輔助機制 — 建議詞迴圈**：步驟 3-5 萃取的資料會在下次前端輸入同欄位時，經由 `GET /suggestions?category=supplier&q=...` 提供自動完成下拉選單。

---

## 階段 4：報表產生

| 步驟 | 動作 | 技術細節 |
|------|------|----------|
| 4-1 | 從 DB 撈出已壓平的資料集 | 不再即時壓平，直接使用階段 3 的產出 |
| 4-2a | 產生 **Excel (XLSX)** | `POST /api/projects/{project_id}/run_export` → 經費核銷清單 |
| 4-2b | 產生 **Word (DOCX)** | `POST /api/projects/{project_id}/run_word_export` → 讀取 `dev_data/空白 模板 (1).docx` (或正規化後新路徑)，透過 `python-docx` 寫入 |
| 4-3 | 交付使用者 | 前端透過 FileResponse 下載 |

---

## 階段 5：憑證黏貼紙 (Voucher PDF)

| 步驟 | 動作 | 技術細節 |
|------|------|----------|
| 5-1 | 前端載入排版編輯器 | 拉取模板 PNG + **AVIF 小圖** (輕量，拖拉順暢) |
| 5-2 | 使用者拖拉排版 | Fabric.js Canvas：拖拉發票位置 (x, y, scale) |
| 5-3 | 打回排版 JSON | `POST /api/voucher/{project_id}/generate` 含每頁 images + 文字欄位 |
| 5-4 | **後端高清渲染** | 從磁碟取出 **JXL 原圖**（非前端的 AVIF），寫入 PDF |
| 5-5 | 文字座標套用 | 讀取 `voucher_template_config.json` 動態配置 + 字體自動縮放 |
| 5-6 | **PDF 壓縮** | 統一採用 `pikepdf` 進行壓縮（基於 QPDF），保留純 Python 相容性，避免依賴外部 Ghostscript 二進位檔案造成部署困難。 |
| 5-7 | 交付使用者 | 壓縮後的 600dpi 高品質 PDF |

---

## 階段 6：專案封存 (Archive)

| 步驟 | 動作 | 技術細節 |
|------|------|----------|
| 6-1 | 使用者觸發封存 | `POST /api/projects/{project_id}/run_archive` |
| 6-2 | 打包專案目錄 | 含原始輸入、分割發票、產出報表、憑證 PDF |
| 6-3 | 標記專案狀態為 `ARCHIVED` | 後續不可再修改 |

---

## ⚠️ 附錄：系統現況盤點與架構落差（啟動時快照）

> 註：本表是啟動時盤點，不做滾動維護；後續是否已完成請以下方各 Phase「啟動增量 / 完成記錄」為準。

| 理想狀態 | 實際現況 | 影響 |
|----------|----------|------|
| 上傳後轉存 JXL | `file_ops.py` 儲存為 `.jpg` (OpenCV) | PDF 品質尚可，但檔案體積未優化 |
| 前端拿 AVIF 小圖 | API 直接吐原始 JPG/PNG | 大圖拖拉卡頓 |
| PDF 壓縮後交付 | 尚未實作壓縮環節 | 憑證 PDF 檔案可能過大 |
| Word 範本在 `backend/assets/templates/` | 目前放在 `dev_data/空白 模板 (1).docx` | 路徑不規範 |
| 扁平化在人工修正後即時完成 | 目前在報表產出時才即時壓平 | 多次報表產出會重複計算 |

---

## 🚀 附錄：系統升級與遷移腳本需求 (Migration Scripts)

為了消弭上述存續的架構落差，並將舊有專案平滑過渡到新的全生命週期工作流，我們在執行 V0.0.10 (或 V0.0.11) 升級時，需配套開發以下獨立腳本來執行歷史資料清洗與轉換：

### 1. 影像格式雙軌升級腳本 (`scripts/migrate_images_to_jxl_avif.py`)（已實作）
- **狀態（2026-03-15）**：已實作，支援 preview cache 生成與 JXL encoder 可用時的 `.jxl` 轉檔。
- **目的**：將舊專案儲存在 `原始輸入/` 與 `分割發票/` 中的 `.jpg` 與 `.png` 檔案，全面轉換為新的 JXL 與 AVIF 架構。
- **步驟**：
  1. 走訪 `backend/data/projects` 下的歷史專案資料夾。
  2. 讀取 `.jpg`，使用高畫質編碼生成對應的 `.jxl`（取代原檔）。
  3. 壓縮並縮放生成對應的 `.avif`（存入快取給前端使用）。
  4. 清理無用的舊 `.jpg` 檔案以釋放空間。

### 2. 資料庫扁平化結構遷移腳本 (`scripts/migrate_db_flatten_jobs.py`)（已實作）
- **狀態（2026-03-15）**：已實作，支援 checkpoint/resume/report。
- **目的**：將資料庫中僅以巢狀 JSON (`items` array) 存在的舊 Job，提前跑一次壓平演算法。
- **步驟**：
  1. 針對 `global.db` 中狀態已為 `done` 的 Job 進行遍歷。
  2. 提取 `summary`、`items` 與 `project.metadata.group` 執行 Flatten 邏輯。
  3. 將結果寫回對應 Job 的新欄位 (如 `flattened_data`)，或寫入獨立的關聯表。

### 3. 資產路徑正規化搬遷腳本 (`scripts/migrate_assets_paths.py`)（已實作）
- **狀態（2026-03-15）**：已實作，支援 dry-run/check-only/report。
- **目的**：解決 Word 報表底稿放在開發用資料夾 (`dev_data`) 的不合規問題。
- **步驟**：
  1. 自動建立 `backend/assets/templates/` 目錄。
  2. 把 `dev_data/空白 模板 (1).docx` 搬動並重新命名為 `backend/assets/templates/報表範本.docx`。
  3. 同步修改 `run_word_export` Router 中硬編碼的路徑指向。

---

## 🛡️ 附錄：高風險實作防禦指南 (High-Risk Defenses)

在實作 V0.0.10 的全新架構時，必須同步導入以下防禦機制，以防止系統在大量併發或邊角操作時崩潰：

### 1. JXL/AVIF 轉檔 OOM (記憶體耗盡) 防護
- **風險**：JXL/AVIF 演算法極度消耗 CPU 與 RAM。若用戶一次上傳大量發票，同時觸發幾十個轉檔任務，伺服器極易 OOM。
- **防禦**：必須在轉檔流程引入 **Concurrency Limiter (併發限制器)**。例如使用 `asyncio.Semaphore` 將並行轉檔任務限制在安全數量內，或交由專屬的 Background Worker Queue 循序處理。

### 2. 資料扁平化 (Flattening) 的 Race Condition 防護
- **風險**：若改用背景 Task 非同步執行 Flatten，當使用者極快速地連續儲存兩次 Job Editor，可能會導致兩支非同步任務同時寫入資料庫，造成舊資料覆寫新資料 (Race Condition)。
- **防禦**：必須實作狀態鎖定機制 (如 `flattening_status`)，或使用 DB 的 Row Lock，確保同一筆 Job 的扁平化運算永遠是**循序且互斥**的。

### 3. 影像旋轉與大圖切割的連動破壞防護
- **風險**：若允許對「原始大圖（尚未切割前）」進行旋轉，則原本 `ReceiptSplitter` 計算出的所有小發票座標將全部失效，導致未來取圖錯亂。
- **防禦**：嚴格限制 `rotate` API：**只能對「已切分且獨立的子發票圖檔」進行旋轉**，絕對禁止對原始大圖旋轉。

### 4. 憑證排版 (Voucher) 的快照失效防護
- **風險**：用戶在排版畫面 (Canvas) 放好發票後，若中途回頭修改了 Job Editor 的金額，排版畫面上帶有的金額快照就會變成舊資料。若後端產 PDF 時直接信任前端傳來的文字，產出的 PDF 金額將是錯誤的舊值。
- **防禦**：後端 `POST /api/voucher/{project_id}/generate` API **絕對禁止盲目信任前端傳來的文字內容**。前端只負責傳遞 (x, y, scale) 排版座標，後端產製 PDF 時，**必須重新從 DB 撈取該 Job 當下最新的真實文字資料**即時印製。

---

## 🧩 附錄：P3 啟動執行包（2026-03-15）

本附錄記錄「Phase 3 - Image Pipeline Upgrade」的啟動批次，採最小可運行路徑先落地，再逐步擴充 JXL 正式編碼管線。

### 已啟動（已落地）

1. **Preview 快取管線接線完成**
       - 在檔案流程新增預覽快取產生器（優先 AVIF，次選 WebP，再退回 JPEG）。
       - 快取檔名採用 `原圖 stem + mtime_ns + size + width` 簽章，避免舊圖誤用。
       - 轉檔流程共用 `image_processing_semaphore`，避免高併發記憶體尖峰。

2. **收檔/切分時預熱快取**
       - `run_splitting` 與 `add_project_files(type=split)` 在 enqueue 前嘗試預熱縮圖快取。
       - 預熱失敗不阻斷主流程（僅警告），確保業務可用性。

3. **旋轉後快取失效與重建**
       - `rotate_image` 旋轉完成後先清掉對應 preview 快取，再立即重建。
       - 避免使用者看到旋轉前舊縮圖。

4. **Voucher 取圖 API 改走快取優先**
       - `GET /api/voucher/{project_id}/image/{job_id}?thumb=true` 先回傳快取圖。
       - 若快取失敗才回退即時縮圖，以維持相容。

### 本批驗收條件（已加入測試）

1. 能建立 preview 快取檔並可重複命中。
2. 圖片旋轉後會觸發快取重建。
3. Voucher thumb API 在有快取時回傳快取內容。

### 下一批（P3-2）

1. 導入正式 **JXL 主檔轉碼 adapter**（可插拔 backend，先 Windows 可用實作）。
2. 將 Job/Asset metadata 顯式化（記錄 source/preview codec 與路徑）。
3. 補 migration script 第一版 `migrate_images_to_jxl_avif.py`（dry-run + checkpoint）。

### P3-2 啟動增量（2026-03-15）

1. **已加入可插拔 Codec Adapter 骨架**
       - 新增 `backend/processing/image_codec_adapter.py`，統一 archival format 選擇。
       - 預設維持 JPG 相容；當設定 `archival_format=jxl` 時，現階段明確 fallback 至 JPG（避免無編碼器環境產生壞檔）。

2. **切分存檔流程已接入 Adapter**
       - `FileOps._prepare_tasks()` 改由 adapter 產生輸出副檔名與落檔，保持舊流程 API/資料表不變。

3. **已交付 migration 腳本初版（可持久化執行）**
       - 新增 `scripts/migrate_images_to_jxl_avif.py`。
       - 具備 `--dry-run`、`--resume`、checkpoint 持久化與批次進度保存。
       - 目前可穩定生成 preview cache（AVIF/WEBP/JPEG）；JXL 轉檔保留為明確 placeholder（待接入實際 encoder）。

---

## 🏁 附錄：P3 完成記錄（2026-03-15）

Phase 3 全部子任務已完成，446 tests passed。

### P3-2 完成批次

1. **JXL Encoder Backend（可插拔探針）**
       - 新增 `backend/processing/jxl_encoder_backend.py`。
       - `is_jxl_available()` 在 process 啟動時一次性探測 pyvips + libjxl 支援，結果模組層級快取。
       - `encode_to_jxl(source_path, output_path, quality=85)` 封裝 pyvips 寫入邏輯，不可用時拋出 `RuntimeError`。
       - `ImageCodecAdapter.resolve_archival_extension()` 升級為探測後再決定格式：pyvips + libjxl 可用 → `.jxl`，否則 fallback `.jpg` 並記錄 warning。
       - `ImageCodecAdapter.write_archival_image()` 升級：`.jxl` 路徑透過臨時 PNG → `encode_to_jxl` 管線；失敗時安全降回 `.jpg`。

2. **Job 資產元資料顯式化**
       - `backend/database/models.py` 的 `Job` ORM 新增 `source_format`（e.g. `"jpg"`, `"jxl"`）和 `preview_cache_path`（最新一次 preview 快取絕對路徑）兩欄。
       - `backend/repositories/job_repository.py` `get_job()` 回傳字典新增上述兩欄位。
       - Alembic migration `b3f7a2c91de0_add_asset_metadata_to_jobs.py` 為既有 DB 補欄。

3. **FileOps 接線資產元資料**
       - `_prepare_tasks()` 與 `add_project_files(type=split)` 在 enqueue 後立即呼叫 `job_repo.update_job(job_id, source_format=..., preview_cache_path=...)`，將格式與快取路徑寫入 Job 記錄。
       - 寫入失敗不阻斷主流程（僅 warning）。

4. **Migration 腳本功能擴充**
       - `scripts/migrate_images_to_jxl_avif.py` 新增 `--canary-limit N`（staged rollout 用，處理 N 張後停止）。
       - 新增 `--report-path FILE`（完成後寫入 JSON summary：migrated/skipped/errors/timestamp）。
       - 每次 checkpoint 時自動輸出 `.rollback.json`（列出本次新生成的快取檔清單，供 rollback 批次刪除使用）。
       - 新增錯誤計數（`errors`）；有錯誤時 exit code = 1。

### 驗收（全部通過）

| 測試 | 檔案 | 描述 |
|------|------|------|
| `test_is_jxl_available_returns_bool` | `test_jxl_encoder_backend.py` | 探針回傳 bool |
| `test_is_jxl_available_result_is_cached` | `test_jxl_encoder_backend.py` | 快取生效 |
| `test_is_jxl_unavailable_when_pyvips_missing` | `test_jxl_encoder_backend.py` | pyvips 缺失 → False |
| `test_encode_to_jxl_raises_when_unavailable` | `test_jxl_encoder_backend.py` | 無 encoder → RuntimeError |
| `test_encode_to_jxl_delegates_to_pyvips` | `test_jxl_encoder_backend.py` | pyvips 可用時呼叫 write_to_file |
| `test_codec_adapter_jxl_falls_back_to_jpg_when_unavailable` | `test_image_codec_adapter.py` | JXL fallback |
| `test_codec_adapter_jxl_resolves_to_jxl_when_available` | `test_image_codec_adapter.py` | JXL 可用時不降級 |
| `test_codec_adapter_write_jxl_invokes_encoder` | `test_image_codec_adapter.py` | write 路由至 encode_to_jxl |
| `test_split_stores_asset_metadata_on_job` | `test_engine_file_ops.py` | split 後 update_job 帶 source_format/preview |
| `test_run_basic_generates_preview` | `test_migrate_images_script.py` | migration 生成快取 |
| `test_canary_limit_stops_early` | `test_migrate_images_script.py` | canary-limit 截止 |
| `test_report_written_with_correct_keys` | `test_migrate_images_script.py` | report JSON 欄位正確 |
| `test_rollback_list_written` | `test_migrate_images_script.py` | rollback.json 輸出 |
| `test_dry_run_writes_no_files` | `test_migrate_images_script.py` | dry-run 不寫出 |
| `test_resume_skips_processed` | `test_migrate_images_script.py` | resume 跳過已處理 |

**全套測試結果：446 passed，0 failed。**

### 附帶修復

- 修復 `backend/engine/file_ops.py` 中因外部工具編碼轉換導致的三處中文目錄名稱毀損：
  - `原始輸入`、`分割發票`、`快取影像/voucher_preview`

---

## 🏁 附錄：P4 完成記錄（2026-03-15）

Phase 4 — **資產路徑正規化 (Asset Normalization) + 匯出路由分離 (API Split)** 全部完成，447 tests passed。

### P4-1：資產路徑正規化

1. **Word 報表範本遷移**
       - `dev_data/空白 模板 (1).docx` 複製至 `backend/assets/templates/報表範本.docx`。
       - `backend/routers/exports.py` 的 `_ASSETS_TEMPLATES` 常量指向正規路徑，不再依賴 `dev_data/`。

2. **憑證模板路徑修正**
       - `backend/engine/core.py` Engine 建構子：`VoucherGenerator` 的模板路徑由
         `dev_data/憑證黏貼用紙.pdf` 改為 `backend/assets/templates/憑證黏貼用紙.pdf`。
       - 對應檔案早已存在 `backend/assets/templates/`，本次修正僅統一程式碼指向。

3. **資產遷移腳本**
       - 新增 `scripts/migrate_assets_paths.py`：
         - 自動複製 `dev_data/` 資產至 `backend/assets/templates/`（跳過已存在的目的地）
         - `--dry-run`：預覽不實際寫出
         - `--check-only`：掃描後端原始碼殘留 dev_data 硬編碼路徑
         - `--report-path`：寫出 JSON 結果摘要

### P4-2：匯出路由分離（API Split）

**拆前（`processing.py` 混合了管線 + 匯出 + 封存，共 95 行）：**

| 端點 | 原位置 |
|------|--------|
| `POST /{project_id}/run_split` | processing.py |
| `POST /{project_id}/split/{filename}` | processing.py |
| `POST /{project_id}/run_processing` | processing.py |
| `POST /{project_id}/run_export` (Excel) | processing.py |
| `POST /{project_id}/run_word_export` | processing.py |
| `POST /{project_id}/run_archive` | processing.py |

**拆後：**

| 端點 | 新位置 | 說明 |
|------|--------|------|
| `POST /{project_id}/run_split` | `processing.py` | 保留：影像切分管線 |
| `POST /{project_id}/split/{filename}` | `processing.py` | 保留：單檔切分 |
| `POST /{project_id}/run_processing` | `processing.py` | 保留：VLM 辨識管線 |
| `POST /{project_id}/run_export` (Excel) | **`exports.py`** | 移至：匯出路由 |
| `POST /{project_id}/run_word_export` | **`exports.py`** | 移至：匯出路由（含正規模板路徑） |
| `POST /{project_id}/run_archive` | **`exports.py`** | 移至：匯出路由 |

- `backend/routers/__init__.py` 新增 `exports` 路由器掛載。

### 驗收（全部通過）

| 測試 | 檔案 | 描述 |
|------|------|------|
| `test_run_excel` | `test_routers_exports.py` | Excel 匯出正常回傳 |
| `test_run_excel_error` | `test_routers_exports.py` | Excel 匯出異常 → 500 |
| `test_archive_project` | `test_routers_exports.py` | 封存正常回傳 |
| `test_archive_project_error` | `test_routers_exports.py` | 封存異常 → 500 |
| `test_run_word_export_success` | `test_routers_exports.py` | Word 匯出正常 |
| `test_run_word_export_template_not_found` | `test_routers_exports.py` | 模板缺失 → 500 |
| `test_run_word_export_output_not_found` | `test_routers_exports.py` | 輸出缺失 → 500 |
| `test_word_template_path_uses_assets_not_dev_data` | `test_routers_exports.py` | 確認路徑不含 dev_data |

**全套測試結果：447 passed，0 failed。**

---

## 🏁 附錄：P5 完成記錄（2026-03-15）

Phase 5 — **Flatten Backfill 與 Cutover 準備** 全部完成，匯出流程已正式切到 persisted flatten payload 優先。

### P5-1：持久化 flatten payload 落地

1. **Job flatten payload 成為正式共用資料源**
       - `backend/database/models.py` 的 `Job` 已持久化 `flattened_data` 與 `flattening_status`。
       - `JobRepository.complete_vlm()`、`save_manual_json()` 與 `refresh_flattened_data()` 全部對齊同一份 flatten 規則。
       - `update_job()` 在狀態回退或 JSON 被清空時，會同步清除舊 flatten payload，避免 stale data。

2. **扁平化規則只保留一套**
       - `backend/processing/flattening.py` 的 `build_job_flatten_payload()` 與 `aggregate_flattened_jobs()` 持續作為唯一 flatten 規則來源。
       - Word exporter、repository 與 backfill script 共用同一份 payload 定義，不再各自維護分岔邏輯。

### P5-2：Backfill 與 Cutover 完成

1. **Word exporter 完成 persisted-first cutover**
       - `backend/engine/word_exporter.py` `ensure_flatten_cache()` 先讀取 Job 既有 `flattened_data`。
       - 若 payload 缺失或損毀，則自動呼叫 `refresh_flattened_data()` 修復。
       - 僅在資料仍無法修復時，才退回 runtime `display_result` fallback，維持匯出可用性。
       - flatten cache payload 新增 `payloadSources` 與 `jobCount`，可追蹤本次匯出使用了多少 persisted / refreshed / runtime fallback 資料。

2. **DB backfill 腳本升級為可續跑版本**
       - `scripts/migrate_db_flatten_jobs.py` 新增 `--checkpoint`、`--resume`、`--checkpoint-interval`。
       - checkpoint 以 `project_id:job_id` 記錄，支援 staged rollout 與中斷後續跑。
       - `--report-path` summary 補齊 `force`、`resume`、`checkpoint`、per-project 統計與 `failed_jobs`，可直接拿來做 cutover 健康檢查。

### 驗收（全部通過）

1. `test_engine_word_exporter.py` 新增 persisted flatten 命中與 refresh repair 用例。
2. `test_migrate_flatten_jobs_script.py` 新增 checkpoint/resume 用例。
3. `test_job_repository.py` 既有 flatten persistence 用例持續通過。

**全套測試結果：455 passed，0 failed。**

