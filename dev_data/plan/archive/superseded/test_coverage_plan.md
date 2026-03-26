# 測試覆蓋率改善計畫

## 現況總覽

| 指標 | 數值 |
|---|---|
| 測試總數 | 167 (161 passed, 6 skipped) |
| 整體覆蓋率 | **54%** (2863 stmts, 1308 miss) |
| 測試檔案數 | 16 |

## 覆蓋率分層

### ✅ 良好 (≥80%) — 不需調整

| 模組 | 覆蓋率 | 備註 |
|---|---|---|
| `main.py` | 96% | |
| `python_validator.py` | 91% | |
| `utils.py` | 90% | |
| `keyword_classifier.py` | 88% | |
| `logger.py` | 88% | |
| `job_repository.py` | 86% | |
| `receipt_processor.py` | 84% | |
| `dependencies.py` | 84% | |
| `prompts_config.py` | 100% | |

### ⚠️ 中等 (50%-79%) — 視情況補強

| 模組 | 覆蓋率 | Miss 行數 | 說明 |
|---|---|---|---|
| `routers/suggestions.py` | 80% | 5 | 建議系統路由 |
| `parser.py` | 75% | 13 | JSON 解析邊界情況 |
| `routers/files.py` | 73% | 14 | 檔案操作路由 |
| `routers/groups.py` | 73% | 9 | 群組管理路由 |
| `engine/core.py` | 69% | 52 | 核心引擎 |
| `rapidocr_handler.py` | 68% | 40 | OCR 處理 |
| `routers/projects.py` | 68% | 26 | 專案路由 |
| `project_repository.py` | 65% | 89 | 專案資料庫 |
| `routers/processing.py` | 62% | 18 | 處理路由 |
| `llm_handler.py` | 56% | 67 | LLM 處理 |
| `image_preprocessor.py` | 56% | 8 | 影像前處理 |
| `routers/jobs.py` | 54% | 32 | 任務路由 |
| `file_ops.py` | 52% | 59 | 檔案操作 |
| `contour_validator.py` | 52% | 12 | 輪廓驗證 |

### ❌ 低覆蓋 (<50%) — 需要改善

| 模組 | 覆蓋率 | Miss 行數 | 說明 |
|---|---|---|---|
| `qr_handler.py` | 49% | 67 | QR 碼處理 |
| `suggestion_repository.py` | 43% | 29 | 建議資料庫 |
| `perspective_transform.py` | **38%** | 32 | crop_by_rect / fix_orientation 未測 |
| `vision_handler.py` | **26%** | 131 | Gemini VLM 呼叫 |
| `engine/export.py` | 80% | 4 | |
| `routers/correction.py` | 52% | 12 | |
| `routers/websocket.py` | **19%** | 35 | WebSocket |
| `archive_handler.py` | **19%** | 55 | 壓縮匯出 |
| `regeneration_handler.py` | **19%** | 51 | 重新生成 |
| `receipt_splitter.py` | **17%** | 110 | 核心分割算法 |
| `workers.py` | **14%** | 50 | 背景 Worker |
| `excel_exporter.py` | **11%** | 137 | Excel 匯出 |
| `hough_corner_detector.py` | **0%** | 83 | ⚠️ 死代碼 |

---

## 改善方案

### Phase 0: 清理死代碼 (立即)

#### 刪除 `hough_corner_detector.py`
- 0% 覆蓋，V10 (重構版) 已不再使用
- 無任何 import 引用
- 刪除後整體覆蓋率自動提升: 83 stmts 移除 → ~56%

---

### Phase 1: 核心影像處理 (高優先)

> 這是最近調優的核心模組，最需要迴歸測試保護。

#### 1.1 `perspective_transform.py` (38% → 目標 90%+)

新增測試檔: `tests/test_perspective_transform.py`

| 測試案例 | 說明 |
|---|---|
| `test_order_points_standard` | 標準矩形頂點排序 |
| `test_order_points_rotated` | 旋轉矩形頂點排序 |
| `test_crop_by_rect_basic` | 基本裁切 (合成白色矩形在黑色背景上) |
| `test_crop_by_rect_rotated` | 旋轉矩形裁切 |
| `test_crop_by_rect_landscape_correction` | 長邊校正 (w > h → 自動轉直) |
| `test_crop_by_rect_invalid_size` | 無效尺寸返回空陣列 |
| `test_fix_orientation_horizontal_text` | 水平文字不旋轉 |
| `test_fix_orientation_vertical_text` | 垂直文字旋轉 90° |
| `test_fix_orientation_empty_image` | 空圖片不崩潰 |

#### 1.2 `receipt_splitter.py` (17% → 目標 70%+)

擴充 `tests/test_processing.py` 或新增 `tests/test_receipt_splitter.py`

| 測試案例 | 說明 |
|---|---|
| `test_split_empty_image` | ✅ 已有 |
| `test_split_synthetic_single` | 合成單張白色矩形 → 1 split |
| `test_split_synthetic_two` | 合成兩張分開的矩形 → 2 splits |
| `test_resize_for_detection_small` | 短邊 < 2000 不縮放 |
| `test_resize_for_detection_large` | 短邊 > 2000 等比縮放 |
| `test_mask_iou_dedupe_no_overlap` | 無重疊候選，全部保留 |
| `test_mask_iou_dedupe_overlap` | 高重疊候選，移除小者 |
| `test_mask_iou_dedupe_single` | 單一候選返回自身 |
| `test_adaptive_kernel_size` | 驗證 k = max(3, short_edge // 90) |

#### 1.3 `image_preprocessor.py` (56% → 目標 90%+)

| 測試案例 | 說明 |
|---|---|
| `test_preprocess_basic` | 基本前處理流程 |
| `test_find_contours` | 合成圖形找輪廓 |

---

### Phase 2: 引擎與匯出 (中優先)

#### 2.1 `workers.py` (14% → 目標 60%+)

| 測試案例 | 說明 |
|---|---|
| `test_load_image_success` | 正常讀取圖片 |
| `test_load_image_not_found` | 檔案不存在 raise |
| `test_load_image_corrupted` | 損壞圖片 raise |
| `test_worker_loop_processes_task` | Mock engine，驗證完整流程 |
| `test_worker_loop_handles_error` | 處理失敗正確報錯 |

#### 2.2 `excel_exporter.py` (11% → 目標 50%+)

| 測試案例 | 說明 |
|---|---|
| `test_export_empty_project` | 空專案匯出空 Excel |
| `test_export_with_jobs` | 有 job 資料匯出 |
| `test_export_format` | 驗證工作表名稱/欄位 |

#### 2.3 `archive_handler.py` (19% → 目標 60%+)

| 測試案例 | 說明 |
|---|---|
| `test_archive_creates_zip` | 建立 zip 檔案 |
| `test_archive_includes_images` | 包含圖片 |

#### 2.4 `regeneration_handler.py` (19% → 目標 60%+)

| 測試案例 | 說明 |
|---|---|
| `test_regenerate_updates_job` | 重新產生更新 job |
| `test_regenerate_nonexistent_job` | 不存在的 job |

---

### Phase 3: API 與外部整合 (低優先)

#### 3.1 `vision_handler.py` (26% → 目標 50%+)

需要 mock `google.genai` SDK。

| 測試案例 | 說明 |
|---|---|
| `test_init_with_api_key` | ✅ 部分已有 |
| `test_prepare_image_part` | 圖片轉 base64 |
| `test_process_image_success` | Mock API 成功回應 |
| `test_process_image_retry` | Mock API 失敗重試 |
| `test_clean_json_response` | ✅ 已有 |

#### 3.2 修復 6 個 Skipped 測試

`test_file_ops.py` 中 5 個 skipped:
- `test_rotate_image_90` / `180` — 需要真實圖片
- `test_add_project_files_raw` / `split` — 需要 mock splitter
- `test_run_splitting_success` — 需要 mock splitter

建議: 使用合成圖片 (`np.zeros`) 替代真實圖片依賴。

---

## 預期效果

| 階段 | 新增測試 | 預估覆蓋率 |
|---|---|---|
| 目前 | 0 | 54% |
| Phase 0 (刪死碼) | 0 | ~56% |
| Phase 1 (核心影像) | ~20 | ~65% |
| Phase 2 (引擎匯出) | ~12 | ~72% |
| Phase 3 (API/修復) | ~8 | ~76% |

## 執行建議

1. **Phase 1 最重要** — 保護正在調優的分割/裁切邏輯
2. 所有測試使用**合成圖片** (`np.zeros`, `np.ones`)，不依賴真實圖片
3. 外部 API (Gemini, Ollama) 一律 **mock**
4. 維持 `pytest --timeout=10` 防止測試卡住
