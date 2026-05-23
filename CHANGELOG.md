# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [V0.0.25] - 2026-05-23

### 🏗️ 大型架構重構：3 層邊界強制 + 前端視圖整合 (Breaking Architecture Redesign)

**V0.0.25 Focus**: 消除所有 Router 層對 `cv2`/`numpy`/`fitz` 的直接引用；建立 `ResplitService`、`PdfTaskService`、`ImageCodecAdapter` 三個新服務類別；刪除 5 個孤立前端視圖並將其功能整合進主視圖；以及資料庫 Phase 1 正規化（移除 `flattened_data`）。

### Added

#### Backend — 新服務與倉庫
- **`backend/engine/resplit_service.py`** — `ResplitService`：單一職責分割服務，含自動分割 & 手動二切邏輯（≤500 行）
- **`backend/engine/pdf_task_service.py`** — `PdfTaskService`：封裝所有 PyMuPDF 操作（頁面刪除/重排/新增、蓋章、壓縮、模板預覽），讓 Router 零 `fitz` 引用
- **`backend/engine/image_codec_adapter.py`**（移位）— 從 `processing/` 遷移至 `engine/`，file write 行為歸屬正確層次
- **`backend/repositories/pdf_task_repo.py`** — `PdfTaskRepository`：JSON + PDF 檔案式倉庫，管理 `backend/data/pdf_tasks/`
- **`backend/repositories/stamp_template_repo.py`** — `StampTemplateRepository`：JSON 檔案式倉庫，管理 `backend/data/stamp_templates/`
- **`tests/test_resplit_service.py`** — ResplitService 單元測試（自動分割 & 手動二切）

#### Frontend — 新元件
- **`frontend/src/components/ProjectSettingsModal.vue`** — 專案設定 Modal，含活動資訊、財務預算、Word 匯出功能（從 `EditProjectView` 拆出）
- **`VoucherEditorView.vue`** — 右側 Metadata 修改 Sidebar（從 `JobEditorView` 整合進來）；含 `editJobId` 查詢參數自動展開功能

### Removed

#### Backend — 刪除過時元件
- **`backend/engine/file_ops.py`** — 完全刪除，無任何 shim 或兼容包裝
- **`backend/processing/image_codec_adapter.py`** — 移位至 `engine/`（非刪除）
- **`scripts/migrate_db_flatten_jobs.py`** — `flattened_data` 欄位已正規化，遷移腳本無存在意義

#### Backend — 刪除舊測試
- **`tests/test_engine_file_ops.py`** — 對應 `file_ops.py` 的測試；測試內容重新分配至 `test_engine_image_service.py` 和 `test_resplit_service.py`
- **`tests/test_migrate_flatten_jobs_script.py`** — 對應已刪除遷移腳本

#### Frontend — 刪除孤立視圖
- `frontend/src/views/StampSourceUploadView.vue` → 整合進 `StampsManagementView`
- `frontend/src/views/StampZoneConfigView.vue` → 整合進 `StampsManagementView`
- `frontend/src/views/EditProjectView.vue` → 整合進 `ProjectDetailView` + `ProjectSettingsModal`
- `frontend/src/views/VoucherTemplateConfigView.vue` → 整合進 `SettingsView`
- `frontend/src/views/JobEditorView.vue` → 整合進 `VoucherEditorView` Sidebar

### Changed

#### Backend — 層邊界修正
- **`backend/routers/pdf_tasks.py`** — 移除所有 `import fitz`；改透過 `PdfTaskService` 呼叫
- **`backend/routers/voucher.py`** — 移除 `import fitz`；頁面擷取邏輯下移至 `PdfTaskService`
- **`backend/engine/core.py`** — 注入 `ResplitService`、`PdfTaskService`、`PdfTaskRepository`、`StampTemplateRepository`；移除 `self.file_ops` 兼容引用
- **`backend/engine/image_service.py`** — 移除分割相關方法（已移至 `ResplitService`）；維持旋轉、快取、預覽 warm-up 職責
- **`backend/engine/excel_exporter.py`** — 完全改用 `openpyxl`（移除 `pandas` 和 `xlsxwriter`）
- **`backend/engine/regeneration_handler.py`** — 改用 `openpyxl.load_workbook(read_only=True)` 取代 pandas Excel 讀取
- **`backend/processing/jxl_encoder_backend.py`** — `encode_image_to_jxl` 改回傳 raw `bytes`（移除 file write 副作用）
- **`backend/database/models.py`** — 移除 `flattened_data` 和 `flattening_status` 欄位
- **`backend/repositories/job_repository.py`** — 移除 ~28 個 `flattened_data` 相關方法與 ORM 查詢（含 `refresh_flattened_data`）
- **`requirements.txt`** — 移除 `pandas`、`xlsxwriter`、`requests`
- **`.gitignore`** — 新增 DB 檔、workspace、patch 腳本、coverage 產物的忽略規則

#### Frontend — 路由整合
- **`frontend/src/router/index.js`** — 移除 5 個已刪除視圖的路由與 import
- **`frontend/src/views/ProjectDetailView.vue`** — `editJob()` 改導向 `/voucher-editor?editJobId=xxx`；整合 `ProjectSettingsModal`
- **`frontend/src/views/VoucherEditorView.vue`** — `onMounted` 檢查 `editJobId` query 參數，自動展開右側 Sidebar 並切換對應頁面
- **`frontend/src/views/StampsManagementView.vue`** — 整合 `StampAssignDialog` 為內嵌精靈 Modal
- **`frontend/src/views/HomeView.vue`** — 點擊「編輯」導向 `/project/:id?edit=true` 觸發設定 Modal
- **`frontend/package.json`** — 移除 `pdfjs-dist`

### Fixed
- **`tests/test_routers_voucher.py`** — `pdf_task_service.get_template_preview_payload` mock 改用同步 `MagicMock`（原用 `AsyncMock` 導致 `to_thread` 收到 coroutine 物件而非結果）

### Test Metrics
- **Total Tests:** 618 passed, 0 failed
- **Execution Time:** ~75.5s

---

## [V0.0.12] - 2026-03-29

### 🎯 JXL 管線修正與預覽影像全鏈路修復

**V0.0.12 Focus**: 解決 JXL 編碼管線 DLL 相容問題、43 倍效能優化、預覽影像從後端快取到前端顯示的全鏈路修復。

### Changed
- **JXL 編碼器切換**：由 `pyvips`（Windows DLL 衝突）改為 `imagecodecs`（自帶 libjxl binding，零外部依賴）。
- **JXL 編碼加速 43x**：`jpegxl_encode(effort=1)` 將每張圖從 ~23 秒降至 ~0.5 秒，檔案大小僅增加 18%。
- **前端取圖路徑**：由直接 `/static/` 路徑改走 `/api/projects/{id}/preview/{type}/{filename}` API 代理端點。

### Added
- **Preview 代理端點**（`backend/routers/files.py`）：
  - `GET /{project_id}/preview/split/{filename}` — 分割發票預覽
  - `GET /{project_id}/preview/raw/{filename}` — 原始輸入預覽
- **JXL-aware 圖片讀取**：`file_ops._render_preview()` 與 `voucher._load_image_bytes()` 可透過 `imagecodecs.jpegxl_decode()` 讀取 JXL 源檔。

### Fixed
- **預覽圖全面空白**：PIL 無法開啟 JXL + 瀏覽器不支援 JXL 渲染 → 改用 imagecodecs 解碼 + AVIF/WebP 快取。
- **JXL 轉檔極慢**：預設 effort=5（~23s/張）→ effort=1（~0.5s/張）。
- **測試斷言過期**：`voucherNo.point`、`paymentAmount.point` 座標值對齊最新設定。
- **測試 mock 路徑錯誤**：`test_jxl_encoder_backend.py` mock 對齊 lazy import 結構。

### Test Metrics
- **Total Tests:** 473 passed, 0 failed

---

## [V0.0.9] - 2026-03-15

### 🎯 V0.0.9 Completion: Bug Fixes & Visual Settings

**V0.0.9 Focus**: Fix critical UI/UX bugs in the Voucher Editor, address PDF generation font overflows, and introduce a visual settings page for voucher coordinates.

### Added
- **Visual Settings Page**: 
  - Added `VoucherTemplateConfigView.vue` for visually adjusting template coordinates, dragging text anchors, and resizing blocked zones (e.g., stamp areas).
  - Configurable `safeZoneConfig` and `blockedZones` variables implemented to calculate boundary limits.
  - Persisted JSON configuration to `backend/data/voucher_template_config.json` via new API endpoints.

### Fixed
- **Invoice Jumping Bug**: Separated events in `VoucherEditorView.vue` and introduced `clampPositionOnly` to prevent images from snapping backwards when dragged.
- **Font Overflow (`voucherNo` & `budgetItem`)**:
  - Implemented `fitSingleLineFontSize` on the frontend and `_insert_autoscale_text` on the backend.
  - Deployed dynamic vertical cascading font-size reduction for `voucherNo` (minus 2 points for every invoice beyond 4) to prevent text spilling into the stamp zone.
  - Widened `maxWidth` of `budgetItem` to 65.
- **Missing Budget Item**: Fixed logic in `backend/routers/voucher.py` to correctly inject `project.metadata.group` as `budgetItem`.

---

## [V0.0.8-Phase3] - 2026-03-09

### 🎯 P3/P4 Completion: Artifact Cleanup + Focused Tests

**Phase 3 Focus**: Finish pending plan items P3 and P4.

### Added
- `tests/test_image_preprocessor.py` - Image preprocessing coverage (4 tests)
  - `preprocess` shape/type validation
  - edge detection non-zero output check
  - contour area sorting verification
  - empty image contour behavior

- `tests/test_engine_export.py` - Export facade delegation coverage (5 tests)
  - `run_excel` delegation
  - `archive_to_excel` delegation with custom filename
  - `run_word` engine requirement validation
  - `run_word` delegation with job repo from engine
  - `seal_project` delegation with flags

### Removed
- Deleted coverage artifact file: `.coverage`

### Test Metrics
- **Total Tests:** 416 → 425 (+9 tests)
- **Test Results:** 425 passed, 0 failed
- **Coverage:** 4061 statements, 630 missed (84%)

### Key Coverage Gains
- `backend/processing/image_preprocessor.py`: **56% → 100%**
- `backend/engine/export.py`: **71% → 100%**

---

## [V0.0.8-Phase2] - 2026-03-09

### 🎯 Coverage Improvement: 82% → 84%

**Phase 2 Focus**: Advanced error handling, geometric validation, and LLM edge cases

### Added

#### New Test Modules
- `tests/test_contour_validator.py` - ContourValidator geometric validation (11 tests)
  - `order_points` - Standard/rotated rectangle vertex ordering (including diamond edge case)
  - `validate_aspect_ratio` - Valid/invalid/boundary value aspect ratio checks
  - **Coverage:** contour_validator.py now at 100%

#### Extended Test Classes
- `tests/test_processing.py::TestLLMHandlerAdvanced` - LLM error handling (8 tests)
  - `call_with_thinking` - Empty content response and exception handling
  - `structure_with_llm` - Empty input and JSON parsing errors
  - `regenerate_from_corrected_text` - Text regeneration flow
  - `clean_receipt` - Success path and no-text branch
  - `init_without_ollama` - SystemError when Ollama service unavailable
  - **Discovery:** LLMHandler raises SystemError (not graceful degradation) on init failure

- `tests/test_routers_projects.py` - Projects router exception paths (6 tests)
  - Metadata parsing error handling
  - Update/delete/status exception propagation
  - Activity info update failures

- `tests/test_routers_processing.py` - Processing router error coverage (9 tests)
  - Processing/splitting/split_single exception paths
  - Excel/archive operation exceptions  
  - Word export template missing and output path errors

### Fixed
- `test_order_points_rotated` - Fixed diamond shape boundary condition using average y-coordinates
- `test_regenerate_excel` - Added missing `from unittest.mock import patch` import
- `test_structure_with_llm_empty_text` - Adjusted to expect error dict instead of empty dict
- `test_clean_receipt_success` - Fixed mock to use non-streaming Ollama API response
- Removed unused imports (pytest, MagicMock) and added PEP 8 blank line spacing

### Test Metrics
- **Total Tests:** 385 → 416 (+31 tests)
- **Test Results:** 416 passed, 0 failed
- **Execution Time:** ~22s (down from ~50s in Phase 1)
- **Coverage:** 4061 statements, 645 missed (84%)

### Module Coverage Snapshot
```
contour_validator.py       100% ⬆ (complete coverage)
perspective_transform.py   100%
prompts_config.py          100%
models.py                  100%
routers/processing.py      98% ⬆
voucher_layout_repo.py     97%
receipt_splitter.py        96%
utils/utils.py             95%
suggestion_repository.py   95%
```

### Remaining Gaps (6% to 90% target)
- **Low-coverage modules:**
  - word_exporter.py (65%) - Complex docx formatting logic
  - image_preprocessor.py (56%) - OpenCV preprocessing edge cases
  - files router (71%) - File upload/download error paths
  - export.py (71%) - Export coordination logic
  - pdf_engine.py (72%) - PDF parsing edge cases

- **Analysis:** Remaining 645 uncovered statements likely require integration tests (multi-component scenarios) rather than isolated unit tests. Diminishing returns observed beyond 84%.

### Next Phase Recommendations
1. **Integration Testing:** Multi-router workflows (upload → process → export)
2. **Image Processing:** OpenCV edge cases with real malformed images
3. **Word Export:** Complex docx template scenarios
4. **Practical Target:** 84% may be optimal for unit test coverage; remaining gaps need E2E tests

---

## [V0.0.8-Phase1] - 2026-03-09

### 🎯 Coverage Improvement: 77% → 82%

**Phase 1 Focus**: Critical backend infrastructure and worker loops

### Added

#### New Test Modules
- `tests/test_database_core.py` - Database initialization and configuration tests
  - Global DB path configuration and fallback logic
  - SQLite PRAGMA execution verification
  - Async session factory creation and basic queries
  
- `tests/test_utils_config.py` - Configuration management tests
  - Missing config file handling
  - Save/load roundtrip validation
  - Write failure error handling

- `tests/test_engine_worker_loops.py` - Background worker loop tests
  - PDF worker success and failure branches  
  - Receipt worker job completion paths
  - Image load error handling
  - Controlled queue testing helper

- `tests/test_engine_excel_exporter.py` - Excel export tests
  - VLM result to markdown text generation
  - Empty job validation
  - Main and detail sheet generation
  - Project status update verification

#### Test Coverage Enhancements
- `tests/test_routers_pdf.py`
  - Invalid PDF upload rejection (HTTP 400)
  - Download fallback to source PDF when processed version missing

### Changed

#### Bug Fixes
- **[backend/routers/pdf.py](backend/routers/pdf.py)** - Fixed invalid upload classification
  - Non-PDF uploads now correctly return HTTP 400 instead of 500
  - Added dedicated `ValueError` exception handling

### Removed

#### Obsolete Test Files
Deleted 8 empty placeholder test files:
- `tests/test_api.py`
- `tests/test_api_full.py`
- `tests/test_archive_handler.py`
- `tests/test_excel_exporter.py`
- `tests/test_file_ops.py`
- `tests/test_integration.py`
- `tests/test_manual_correction.py`
- `tests/test_workers.py`

#### Generated Artifacts
Cleaned up coverage analysis and cache files:
- Root-level coverage reports: `cov.txt`, `cov_utf8.txt`, `coverage_report.txt`, `coverage_report_utf8.txt`
- HTML coverage report: `htmlcov/`
- Annotated source files: all `backend/**/*.py,cover` files (55 files)
- Python cache: all `__pycache__/` directories
- Pytest cache: `.pytest_cache/`

### Coverage Details

#### Module-Level Improvements
| Module | Before | After | Δ |
|--------|--------|-------|---|
| `backend/database/core.py` | 35% | 91% | +56% |
| `backend/engine/excel_exporter.py` | 12% | 73% | +61% |
| `backend/engine/pdf_worker.py` | 13% | 74% | +61% |
| `backend/engine/workers.py` | 15% | 77% | +62% |
| `backend/routers/pdf.py` | 53% | 73% | +20% |
| `backend/utils/config.py` | 50% | 88% | +38% |

#### Test Results
- **Total Tests**: 385 passed
- **Backend Coverage**: 82%
- **Execution Time**: ~50s (full suite)

### Technical Notes

#### Plan Adaptation
The original V0.0.8 plan was adapted to current branch state:
- Database session lifecycle now managed in `backend/dependencies.py` rather than inline generators
- PDF router uses multipart file upload instead of base64 JSON payloads  
- Worker test file naming updated from plan assumptions

#### Repository Memory
Created `/memories/repo/coverage_plan_notes.md` to track plan vs. implementation variance.

### Next Phase

**Remaining Gap to 90% Target**: 8%

Priority modules for Phase 2:
1. `backend/engine/word_exporter.py` (65%)
2. `backend/processing/llm_handler.py` (56%)
3. `backend/processing/contour_validator.py` (52%)
4. `backend/routers/projects.py` (65%)
5. `backend/routers/processing.py` (66%)

---

## Previous Versions

See `dev_data/plan/` for archived version implementation notes.
