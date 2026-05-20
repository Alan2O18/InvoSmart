# v0.0.18 Plan: FileOps, Export Refinement & Database Refactoring

## Goal Description

1. **修正匯出格式與命名規範**：
   - 檔名規範：改為 `[ProjectID]「[ProjectName]」_預結算表_{timestamp}` (如 `D-04「身」歷其境_預結算表_1775306216`)。遇到不合法的 Windows 檔名字元將自動替換為「底線 `_`」。
   - 活動名稱格式：`{{活動名稱}}` 替換內容改為 `[ProjectID] [活動名稱]`。
   - 資料排序：匯出項目前依照指定順序進行類別 (Category) 排序：`保險` > `膳食(課程會)` > `餐食` > `茶水` > `消耗性教材` > 其他依字元排序，確保同類項目在文件中能夠連續排列並正確合併。
2. **修復 Excel 匯出空表問題**：目前因 `JobRepository.list_jobs()` 效能優化導致 ExcelExporter 讀不到內容而匯出空表。將改採逐筆 `get_job()` 讀取完整資料。
3. **完成 FileOps 拆分 (延續 v0.0.17 項目)**：將 `backend/engine/file_ops.py` 拆解為 `FileService`、`ImageService` 等單一職責服務。
4. **重構並清晰化資料庫結構 (Database Refactoring)**：解決現有 `Job` 資料表過於臃腫及結構不清晰的問題。目前 `Job` 表內存在大量冗餘的 JSON 字串欄位（`vlm_result_json`、`manual_json_text`、`flattened_data` 等），且與關聯式表 `InvoiceItem` 並存，導致雙重事實來源 (Dual Source of Truth) 與複雜的資料縫合 (`_stitch_items_from_db`) 邏輯。將全面以關聯式結構為主體進行整併。


## Proposed Changes

---


### Phase 1: Database Migration & Repository Refactoring (資料庫與資料層重構)

#### [MODIFY] `backend/processing/flattening.py`
- 修改 `aggregate_flattened_jobs` 函數，加入指定的類別排序權重（`保險`、`膳食(課程會)`、`餐食`、`茶水`、`消耗性教材`），回傳前對 `all_flattened_items` 進行排序。

#### [MODIFY] `backend/engine/word_exporter.py`
- 更新 `process_export` 中的 `base_replacements`，將 `{{活動名稱}}` 前方補上 `project_id`。
- 修改輸出的 Word 檔名生成邏輯，加入剔除問題字元與加上戳記，符合 `[ID]「Name (替換非法字元)」_預結算表_{戳記}.docx` 格式。

#### [MODIFY] `backend/engine/excel_exporter.py`
- 修改 `archive_to_excel` 中輸出的 Excel 檔名生成邏輯，對齊與 Word 相同的規範（剔除非法字元並保留戳記）。
- (已部分實施) 使用 `get_job()` 確保資料完整性。

#### [NEW] `scripts/migrate_v0_0_18.py` (一次性搬移腳本)
- 讀取資料庫中所有的 `Job`。
- 解析 `manual_json_text` 或 `vlm_result_json`，將 `voucher_id`、`purpose` 與 `supplier` 等 Header/Summary 資訊抽離出來，回寫至新的關聯欄位。
- 重建所有 `InvoiceItem` 以確保沒有遺漏。

#### [MODIFY] `backend/database/models.py`
- 重構 `Job` Model：
  - 新增單項發票必備欄位：`voucher_id`, `purpose`, `supplier`, `date`, `total_amount`，由 JSON 中抽出成獨立明確的主體欄位。
  - 將 VLM 的原始 JSON 放著不動，但程式未來不再更新它（視為不可變的原始稽核紀錄）。
  - 移除多餘的 `manual_json_text`。
  - 移除冗餘供匯出用的 `flattened_data` 及 `flattening_status`。

- **重構 `Job` Model**：
  - 移除多餘且重複的 JSON 欄位（如 `manual_json_text`、`vlm_result_json`、`flattened_data`）。
  - 將憑證的 Header、Summary (如 `voucher_id`, `purpose`) 直接入表作為 `Job` 的獨立欄位，或建立關聯的 `Invoice` 表。
  - 將 VLM 的原始完整輸出改為單一欄位 `vlm_raw_output` (或將其移出 DB 存至快取/檔案)，僅作備查，不再作為業務邏輯的核心狀態。

#### [MODIFY] `backend/repositories/job_repository.py`
- 移除 `_stitch_items_from_db` 這類將關聯式表與 JSON 字串混淆縫合的 workaround。
- 確立 **Single Source of Truth** 皆為關聯式欄位與表格。`get_display_result` 與 `get_job_details` 改為直接 Query `Job` 與 `InvoiceItem`，再組裝成 API 需要的回傳格式。
- 移除不再需要的 `refresh_flattened_data` 邏輯，改由 Exporter 讀取資料後即時處理 (On-the-fly Flattening)。

- 廢除舊的 `_stitch_items_from_db` 暴力字串縫合邏輯。
- **儲存 API (`save_manual_json`)**：解析前端傳入的 JSON，將 Header 拆解寫入 `Job` 欄位，明細寫入 `InvoiceItem`，不再把完整的 修改後 JSON 當字串存起來。
- **讀取 API (`get_job_details`, `get_display_result`)**：直接 Query `Job` 與 `InvoiceItem` 表，在 Python 內部動態產出前端能吃的樹狀 Dict 格式，實現完全的前端相容（前端不動）。
- 廢除 `refresh_flattened_data` 邏輯。

---

### Phase 2: Export Refinement & On-the-Fly Flattening (匯出邏輯與即時扁平化)

#### [MODIFY] `backend/processing/flattening.py`
- 提供 `build_export_payload_from_db(jobs, items)`：直接讀取 DB 結構，不依賴緩存的字串，即時 (On-the-fly) 重組為 Excel 和 Word 需要使用的扁平化資料結構。
- 在產生前納入排序權重：`保險` > `膳食(課程會)` > `餐食` > `茶水` > `消耗性教材` > 其他依字元。確保同一類別的項目排在一起。

#### [MODIFY] `backend/engine/word_exporter.py` & `backend/engine/excel_exporter.py`
- 抽換資料來源邏輯為新的 `build_export_payload_from_db`。
- 修正檔名：統一改為 `[ProjectID]「[ProjectName]」_預結算表_{timestamp}`，剔除 Windows 非法符號。
- Word 內建替換：將 `{{活動名稱}}` 改為 `[ProjectID] [活動名稱]`。

---

### Phase 3: FileOps Complete Decoupling (檔案服務徹底解耦)
#### [NEW] `backend/engine/file_service.py`
- 抽取：目錄創建與安全路徑驗證函數。

#### [NEW] `backend/engine/image_service.py`
- 抽取：依賴於 ImageCodecAdapter 的 JXL, AVIF 轉換邏輯。

#### [NEW] `backend/engine/cache_service.py`
- 抽取：與預覽小圖生成與排程清理的任務。

#### [MODIFY] `backend/routers/*.py`, `backend/engine/core.py`, 等
- 全面尋找並更換舊有 `FileOps` 的使用端，將之對應更新到新的 Service instance。徹底消滅 `file_ops.py` (「不建立過渡代理」策略)。

## Verification Plan
### Automated Tests
- 新增/修復與 `test_engine_excel_exporter.py` 和 `test_engine_word_exporter.py` 關聯的涵蓋率。
- 撰寫單元測試以驗證 Repository 重裝 JSON 資料的能力是否 100% 和舊版格式一致。

### Manual Verification
1. **執行遷移指令**：跑完腳本，確保原有 DB 正確遷移且能夠順利開機。
2. **前後端整合測試**：在瀏覽器中開啟任一專案發票進行編輯與存檔，再 F5 刷新頁面，確認畫面維持既有功能且資料能夠被正常的保留與重現。
3. **匯出測試**：點擊 Excel/Word 匯出，確認特定類別（保險等）排序生效、沒有空檔案問題，檔名遵守要求。
