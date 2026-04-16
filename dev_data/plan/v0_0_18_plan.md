# v0.0.18 Plan: FileOps Refactoring & Excel Exporter Bugfix

## Goal Description
本計畫涵蓋兩大目標：
1. **修復 Excel 匯出空表問題**：目前因 `JobRepository.list_jobs()` 效能優化，移除了沉重的 JSON 欄位回傳（如 `vlm_result_json`, `manual_json_text`），導致 `ExcelExporter` 讀不到內容而匯出空表。將比照 `WordExporter` 做法，以迴圈逐筆 `get_job()` 讀取完整資料。
2. **完成 FileOps 拆分 (延續 v0.0.17 未完項目)**：將原本包山包海的 `backend/engine/file_ops.py` 完整拆解為職責單一的 `FileService`、`ImageService` 等，以降低系統耦合度。

## Proposed Changes

---

### Phase 1: Excel Exporter Bug Fix (立即修正)
#### [MODIFY] `backend/engine/excel_exporter.py`
- 修改 `archive_to_excel` 方法中取得資料的邏輯。
- 將 `jobs_list = await job_repo.list_jobs()` 後方，補上迴圈逐筆調用 `job_repo.get_job(job['job_id'])` 取得包含 JSON 欄位的完整字典，再投入 `pd.DataFrame` 中，確保資料解析正常。

---

### Phase 2: FileOps Refactoring (架構重構)
#### [NEW] `backend/engine/file_service.py`
- 新增檔案與目錄操作專司服務。
- 轉移檔案驗證、專案初始化目錄建立等通用檔案系統存取功能。

#### [NEW] `backend/engine/image_service.py` (與 / 或 `cache_service.py`)
- 轉移圖片壓縮、縮圖生成、格式轉換（AVIF/JXL），以及快取生命週期管理等功能。

#### [MODIFY] `backend/engine/file_ops.py`
- 逐步將現有函數代理 (delegate) 至上方的新 Service。
- 最終目標為將其退役或轉為純粹的 FACADE。

#### [MODIFY] Router 層級 (`routers/*.py`) 
- 取代原本對 `FileOps` 的直接呼叫，改為透過新的 Services 處理。

## Verification Plan
### Automated Tests
- 執行 `pytest tests/test_engine_excel_exporter.py` 確認 Excel 是否正常包含資料。
- 執行全量 `pytest` 確保 FileOps 拆分未破壞現有功能。

### Manual Verification
- 在系統中實際產出 Excel 報表，確認「主表」與「細項表」皆有資料。
- 確認所有圖片預覽功能不受 FileOps 拆分影響。
