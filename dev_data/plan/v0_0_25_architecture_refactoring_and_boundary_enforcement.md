# v0.0.25 架構重構與邊界強制執行計畫

**狀態**: ✅ 已完成

---

## 核心目標

為了解決核心模組職責不清、PDF 與影像處理邏輯散布在多個層次的問題，本版本將執行全面的架構重構：
1. **嚴格執行 3 層架構邊界限制**：禁止 Router 層直接引用 `numpy`、`cv2`、`fitz` (PyMuPDF) 等科學運算與 PDF 渲染套件。
2. **服務解耦與重構**：
   - 封裝 `PdfTaskService` 集中管理 PDF 的頁面分割、渲染與印章嵌入。
   - 封裝 `ResplitService` 處理圖片自動分割、手動二切邏輯。
   - 移除 `file_ops.py` 等過時或職責混亂的元件，使 `core.py` 扮演乾淨的注入與協調角色。
3. **前端視圖整合與精簡**：
   - 將舊的 5 個獨立視圖或對話框整合進主檢視或 Modal 中，精簡前端路由，消除向後相容的轉址定義。
4. **資料庫正規化**：
   - 移除已廢棄的 `flattened_data` 與 `flattening_status` 欄位（以 SQLite 安全 migration 進行）。

---

## 預期改動與模組分工

### 1. 後端架構重構 (Backend Redesign)

- **PdfTaskService**: 
  - 新增 `backend/engine/pdf_task_service.py`。
  - 將原本散佈在 router 或 `cache_service` 中的 PDF 第一頁渲染、分頁提取與合併等底層 fitz 運算集中管理。
  - 確保 router 層完全不接觸 `fitz`。
- **ResplitService**:
  - 新增 `backend/engine/resplit_service.py`。
  - 封裝發票的自動分割與手動二切計算，限制程式碼長度在 500 行以內。
- **ImageCodecAdapter**:
  - 將影像編解碼轉換邏輯移入 `backend/engine/image_codec_adapter.py`。
- **檔案式倉庫 (File-based Repositories)**:
  - 實作 `PdfTaskRepository` (儲存 PDF 分割任務 Meta)。
  - 實作 `StampTemplateRepository` (儲存蓋章模板)。
  - 避免將非關聯性的大型 JSON 結構硬塞進關聯式資料庫。

### 2. 前端視圖精簡與整合 (Frontend Consolidation)

- **視圖移出與 Modal 化**:
  - `EditProjectView` -> 整合為 `ProjectSettingsModal.vue`（可在 `ProjectDetailView` 直接喚起）。
  - `JobEditorView` -> 整合為 `VoucherEditorView.vue` 右側的 Metadata Sidebar。
  - `StampSourceUploadView` / `StampZoneConfigView` -> 整合進 `StampsManagementView.vue` 中的 Dialog 精靈。
  - `VoucherTemplateConfigView` -> 修復並還原 Fabric.js 可視化範本座標編輯器。
- **路由清理**:
  - 移除 `router/index.js` 中對應的 5 個已刪視圖路由。
  - 清理 `/stamps`、`/stamp-zones` 的轉址。

### 3. 資料庫欄位清理与 Migration
- 移除 `models.py` 中的 `flattened_data` 與 `flattening_status` 屬性。
- 使用 Autogenerate 產生 SQLite-safe Alembic 遷移腳本並套用。

---

## 預期修改檔案

### Backend
- `backend/engine/pdf_task_service.py`
- `backend/engine/resplit_service.py`
- `backend/engine/image_codec_adapter.py`
- `backend/repositories/pdf_task_repo.py`
- `backend/repositories/stamp_template_repo.py`
- `backend/database/models.py`
- `backend/repositories/job_repository.py`

### Frontend
- `frontend/src/components/ProjectSettingsModal.vue`
- `frontend/src/views/VoucherEditorView.vue`
- `frontend/src/views/StampsManagementView.vue`
- `frontend/src/views/VoucherTemplateConfigView.vue`
- `frontend/src/router/index.js`

---

## 驗證與測試計畫

- 完整執行並通過 `pytest` 測試套件，確保重構後 600+ 單元與整合測試均無迴歸。
- 編譯 frontend 專案，確保無 typescript / lint / 模組缺失錯誤。
