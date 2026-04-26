# v0.0.18 Plan: FileOps Refactoring, Export Refinement & Database Cleanup

## Goal Description

本版本涵蓋四大目標：

1. **修正匯出格式與命名規範**
   - 檔名規範：改為 `[ProjectID]「[ProjectName]」_預結算表_{timestamp}`。遇到不合法的 Windows 檔名字元自動替換為底線 `_`。
   - 活動名稱格式：`{{活動名稱}}` 替換內容改為 `[ProjectID] [活動名稱]`。
   - 資料排序：匯出前依指定權重排序類別：`保險` > `膳食(課程會)` > `餐食` > `茶水` > `消耗性教材` > 其他依字元排序，確保同類項目在文件中連續排列並正確合併。

2. **修復 Excel 匯出空表問題**
   - 目前 `JobRepository.list_jobs()` 效能優化省略了 JSON 欄位，導致 `ExcelExporter` 讀不到內容而匯出空表。已部分修正為逐筆 `get_job()` 讀取。

3. **完成 FileOps 拆分 (延續 v0.0.17)**
   - 將「上帝對象」`file_ops.py`（797 行）徹底解體為 `ImageService`、`CacheService` 等單一職責服務，不使用過渡代理，全面更新所有呼叫端。

4. **重構並清晰化資料庫結構 (Database Refactoring)**
   - 解決 `Job` 表過於臃腫及雙重事實來源 (Dual Source of Truth) 問題。
   - 目前 `Job` 表內同時存在 `vlm_result_json`（Text）、`manual_json_text`（Text）、`flattened_data`（Text）等大型 JSON 字串，又與關聯式表 `InvoiceItem` 並存，導致複雜的資料縫合 (`_stitch_items_from_db`) 邏輯。
   - 確立 `InvoiceItem` 關聯表 + `Job` 上的獨立欄位為唯一主體，VLM 原始 JSON 保留在 DB 中但降級為不可變的唯讀稽核紀錄。
   - 前端不動，後端負責在讀取/回傳時動態組裝成前端預期的 JSON 格式。

## Design Decisions (已確認)

| 議題 | 決策 |
|------|------|
| 資料遷移策略 | 一次性遷移腳本，啟動前執行 |
| API 契約 | 後端重構，API 回傳格式不變，前端不動 |
| VLM 原始 JSON 存放 | 保留在資料庫中（`vlm_raw_json` 欄位），不移至檔案系統 |
| FileOps 拆分策略 | 全面重構，不建立過渡代理 |
| Flattened Data 策略 | 移除預存快取，匯出時即時 (On-the-fly) 從 DB 查詢組裝 |
| `rotate_image` 清除邏輯 | 旋轉後不再 `NULL` 掉 JSON 欄位，改為：① 刪除該 Job 的所有 `InvoiceItem`；② 重置 `voucher_id`/`purpose`/`supplier`/`invoice_date`/`total_amount` 為 `None`；③ 將 `vlm_raw_json` 設為 `None`；④ `status` 改回 `ready` |

---

## Proposed Changes

---

### Phase 1: Export Logic Refinement (匯出修正 — 立即實施，風險最低)

#### [MODIFY] [flattening.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/processing/flattening.py)
- `aggregate_flattened_jobs`：加入類別排序權重（`保險`=0、`膳食(課程會)`=1、`餐食`=2、`茶水`=3、`消耗性教材`=4），回傳前對 `allFlattenedItems` 排序。

#### [MODIFY] [word_exporter.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/engine/word_exporter.py)
- `base_replacements`：`{{活動名稱}}` 替換值改為 `f"{project_id} {meta.get('name', '')}"`。
- `process_export` 結尾：檔名生成改為 `[ID]「Name」_預結算表_{ts}.docx`，加入 `re.sub(r'[<>:"/\\|?*]', '_', name)` 剔除 Windows 非法字元。

#### [MODIFY] [excel_exporter.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/engine/excel_exporter.py)
- `archive_to_excel`：Excel 檔名對齊 Word 規範（`[ID]「Name」_預結算表_{ts}.xlsx`），使用相同的非法字元清理函數。
- 確認逐筆 `get_job()` 讀取已正確實施。

---

### Phase 2: Database Schema & Repository Refactoring (資料庫結構重構)

#### [NEW] [scripts/migrate_v0_0_18.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/scripts/migrate_v0_0_18.py) (一次性遷移腳本)
- 讀取所有 `Job` 記錄。
- 優先解析 `manual_json_text`，其次 `vlm_result_json`，從中抽取 `header.voucher_id`、`summary.purpose`、`header.supplier`、`header.date`、`summary.total` 回寫至新增的 `Job` 獨立欄位。
- 正規化 `vlm_result_json` → `vlm_raw_json`（欄位更名，內容不變）。
- 確認每筆 Job 的 `InvoiceItem` 完整性（若缺漏則從 JSON 重建）。
- 清除已廢棄的 `manual_json_text`、`flattened_data`、`flattening_status` 欄位（設為 NULL 或由 Schema Migration 移除）。

#### [MODIFY] [models.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/database/models.py)
**`Job` 表 — 新增欄位：**
| 欄位 | 型別 | 說明 |
|------|------|------|
| `voucher_id` | `String, nullable` | 憑證/發票號碼 |
| `purpose` | `String, nullable` | 用途說明 |
| `supplier` | `String, nullable` | 供應商名稱 |
| `invoice_date` | `String, nullable` | 發票日期 |
| `total_amount` | `Float, nullable` | 合計金額 |

**`Job` 表 — 欄位變更：**
| 原欄位 | 處理方式 |
|--------|----------|
| `vlm_result_json` | 更名為 `vlm_raw_json`，降級為唯讀稽核備查 |
| `manual_json_text` | **移除** — 不再存完整修改後 JSON |
| `manual_updated_at` | 保留 — 記錄最後人工編輯時間 |
| `flattened_data` | **移除** — 改為即時查詢 |
| `flattening_status` | **移除** |

#### [MODIFY] [job_repository.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/repositories/job_repository.py)

**廢除的方法：**
- `_stitch_items_from_db` — 不再需要 JSON↔關聯表縫合
- `_load_persisted_flatten_payload` (在 word_exporter 中) — 不再讀取預存快取
- `refresh_flattened_data` — 移除預存拍平邏輯

**改寫的方法：**
- `complete_vlm(job_id, vlm_result, ...)`：
  1. 將 `vlm_result` JSON 存入 `vlm_raw_json`（唯讀）。
  2. 從 JSON 抽取 Header/Summary 寫入 `Job` 獨立欄位。
  3. 同步 `items` 到 `InvoiceItem` 表。
  4. 不再寫入 `flattened_data`。

- `save_manual_json(job_id, json_data)`：
  1. 從 `json_data` 抽取 Header/Summary，更新 `Job` 的 `voucher_id`、`purpose`、`supplier` 等欄位。
  2. 同步 `json_data.items` 到 `InvoiceItem` 表。
  3. **不再**將完整 JSON 存為 `manual_json_text`。
  4. 更新 `manual_updated_at`。

- `get_job_details(job_id)` / `get_display_result(job_id)`：
  1. 查詢 `Job` + `InvoiceItem`。
  2. 在 Python 層動態組裝成前端預期的樹狀 Dict（`{header: {}, summary: {}, items: []}`）。
  3. 前端收到的格式與現有完全一致。

- `get_job(job_id)`：
  1. 回傳扁平 dict，將新欄位映射到原有的 key（`vlm_result_json` 改名 → 後端讀取時仍可見舊名）。

**新增的方法：**
- `_extract_header_fields(json_data) -> dict`：從 VLM/手動 JSON 提取 `voucher_id`、`purpose`、`supplier`、`date`、`total` 的共用私有工具。
- `_reconstruct_display_json(job, items) -> dict`：從 DB 欄位 + `InvoiceItem` 列表組裝前端 JSON 格式的共用私有工具。
- `delete_invoice_items(job_id)`：刪除指定 Job 的所有 `InvoiceItem` 記錄（供 `rotate_image` 重置流程使用）。

---

### Phase 3: Export Pipeline Adaptation (匯出管線適配 — 銜接 Phase 2)

#### [MODIFY] [flattening.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/processing/flattening.py)
- 新增 `build_export_payload_from_db(job_dicts, items_by_job_id)`：接收 DB 查詢結果（非 JSON 字串），即時重組為 Exporter 需要的扁平化結構。
- 保留 `build_job_flatten_payload` 與 `aggregate_flattened_jobs` 的 **介面**，但內部改為從新結構讀取。

#### [MODIFY] [word_exporter.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/engine/word_exporter.py)
- `_build_flatten_payload`：不再讀取 `job.flattened_data`，改為從 `job_repo.get_job()` + `InvoiceItem` 查詢即時拍平。
- 移除 `_load_persisted_flatten_payload` 方法。
- 移除 `_flatten_cache_path` 與磁碟快取邏輯（`ensure_flatten_cache` 改為每次即時計算，不寫檔）。

#### [MODIFY] [excel_exporter.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/engine/excel_exporter.py)
- 確認資料來源已改為 `get_job()` 直接讀取（不依賴任何快取）。

#### [MODIFY] [jobs.py (Router)](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/routers/jobs.py)
- `save_manual_json` 端點：移除 `_precompute_flatten_cache` 的 `asyncio.create_task` 呼叫（因為已不再有預存快取）。

#### [MODIFY] [export.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/engine/export.py)
- 移除 `precompute_flatten_cache` 方法。

---

### Phase 4: FileOps Complete Decoupling (檔案服務徹底解耦)

**目標**：將 `file_ops.py`（797 行）解體為 3 個獨立服務，然後刪除 `file_ops.py`。

#### [NEW] [image_service.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/engine/image_service.py)
抽取自 `FileOps`：
- `run_splitting` / `_prepare_tasks` — 圖片分割與 Job 入列
- `add_project_files` — 檔案上傳與格式轉換
- `rotate_image` — 圖片旋轉，**重置邏輯同步更新**（見下）
- `_warp_by_points` — 透視變換
- `_create_resplit_jobs_from_source` — Resplit 裁切
- `apply_job_resplit` / `apply_raw_resplit` — Resplit 應用
- `detect_job_sub_rects` / `detect_raw_sub_rects` — 偵測子區域
- `optimize_jxl_storage` — JXL 格式轉換
- `delete_job_files` — Job 關聯檔案清理
- `flush_deferred_gc` / `_enqueue_deferred_file_gc` — 延遲 GC
- `_codec_adapter` / `_resolve_project_path` / `_is_within_root` / `_safe_delete_file` — 工具函數

**`rotate_image` 重置邏輯（取代舊的 NULL JSON 寫法）：**
```python
# 舊邏輯 (Phase 2 後失效，因 manual_json_text 已移除)
update_job(job_id, vlm_result_json=None, manual_json_text=None, ...)

# 新邏輯
await job_repo.delete_invoice_items(job_id)          # 清除 InvoiceItem
await job_repo.update_job(
    job_id,
    status="ready",
    vlm_raw_json=None,                               # 清除 VLM 原始紀錄
    voucher_id=None, purpose=None, supplier=None,    # 重置 Header 欄位
    invoice_date=None, total_amount=None,
    validation_json=None, vlm_stats=None, qr_verified=0,
)
```
> **Note**：`job_repo.delete_invoice_items(job_id)` 為 Phase 2 新增的 Repository 方法。

#### [NEW] [cache_service.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/engine/cache_service.py)
抽取自 `CacheMixin`（`cache_mixin.py` 193 行）：
- `ensure_preview_cache` — 預覽圖快取
- `invalidate_preview_cache` — 快取失效
- `cleanup_project_cache` / `cleanup_all_projects_cache` — 快取定期清理
- `_render_preview` / `_render_pdf_first_page_to_bgr` — 渲染工具
- `_get_preview_cache_dir` / `_get_preview_format` / `_build_preview_cache_path` — 路徑工具
- `_optional_semaphore` / `_image_semaphore` — 並行控制

#### [MODIFY] [file_service.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/engine/file_service.py) (已存在，擴充)
- 保留現有的 `get_raw_files` / `delete_raw_file`。
- 從 `FileOps` 吸收通用的路徑工具：`_resolve_project_path`、`_is_within_root`（可共用）。

#### [DELETE] [file_ops.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/engine/file_ops.py)
- 所有功能已遷移至上述服務，刪除此檔案。

#### [DELETE] [cache_mixin.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/engine/cache_mixin.py)
- 所有功能已遷移至 `CacheService`，刪除 Mixin。

#### [MODIFY] [core.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/engine/core.py)
- 初始化：`self.file_ops` → 改為 `self.image_service = ImageService(...)` + `self.cache_service = CacheService(...)`。
- 所有 delegate 方法（`run_splitting`、`rotate_image`、`delete_job`、`cleanup_preview_cache`、`optimize_jxl_storage_all_projects`、`detect_*`、`apply_*`）更新引用。

#### [MODIFY] [files.py (Router)](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/routers/files.py)
- L133, L175：`engine.file_ops.ensure_preview_cache` → `engine.cache_service.ensure_preview_cache`

#### [MODIFY] [voucher.py (Router)](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/routers/voucher.py)
- L309：`engine.file_ops.ensure_preview_cache` → `engine.cache_service.ensure_preview_cache`

---

---

## Verification Plan

### Automated Tests
- `pytest tests/test_engine_excel_exporter.py` — 確認 Excel 資料完整與檔名格式。
- `pytest tests/test_engine_word_exporter.py` — 確認 Word 資料與檔名格式。
- 新增 `tests/test_job_repository_v18.py` — 驗證：
  - `save_manual_json` → 寫入獨立欄位 + `InvoiceItem`。
  - `get_job_details` → 輸出格式與舊版 JSON 一致。
  - Round-trip 測試：寫入 → 讀取 → 比對。
- `pytest` 全量 — 確保整體功能未被破壞。

### Manual Verification
1. **執行遷移腳本**：`python scripts/migrate_v0_0_18.py`，確認現有 DB 遷移成功且伺服器能正常啟動。
2. **前端整合測試**：開啟任一專案，進入發票編輯，修改後儲存，F5 刷新確認資料保留。
3. **匯出測試**：
   - Excel/Word 匯出，檔名是否為 `[ID]「Name」_預結算表_{ts}`。
   - Word 文內 `{{活動名稱}}` 是否含 ID。
   - 表格項目是否依類別排序並正確合併。
   - Excel 是否非空表。
