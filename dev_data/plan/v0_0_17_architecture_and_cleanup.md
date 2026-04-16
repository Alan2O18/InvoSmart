# v0.0.17 實作計畫：架構解耦、Resplit 修正、印章全人工化、PDF 模組拔除

日期：2026-04-13

---

## 1. 背景與目標

v0.0.16 完成了最危險的 Event Loop 阻塞、記憶體外洩與 Dangling Pointer 修復。
v0.0.17 的四大目標：

1. **架構解耦**：將 788 行的 God Object `FileOps` 分拆為 `FileService`、`ImageService`、`CacheService`。
2. **手動二切修正**：前端 ResplitModal 改為載入 RAW 大圖，後端裁切也從 `原始輸入` 讀取，座標統一。
3. **印章全人工化**：印章建檔極少用，自動偵測效果差且維護成本高；廢除 OpenCV 自動偵測，僅保留手動拉框 + 去背。
4. **拔除舊版 PDF 排版功能**：「獨立 PDF 蓋章排版」是過時遺留模組，從前端上傳按鈕、Router、到後端 Worker/Engine 全部移除。

---

## 2. 修改範圍索引

| 區塊 | 涉及檔案 | 動作 |
|------|----------|------|
| PDF 清除 | `backend/routers/pdf.py` | DELETE |
| PDF 清除 | `backend/engine/pdf_worker.py` | DELETE |
| PDF 清除 | `backend/processing/pdf_engine.py` | DELETE |
| PDF 清除 | `backend/engine/core.py` | MODIFY (移除 pdf queue/worker/enqueue) |
| PDF 清除 | `backend/main.py` | MODIFY (移除 L25 import + L137 掛載) |
| PDF 清除 | `frontend/src/views/PdfEditorView.vue` | DELETE |
| PDF 清除 | `frontend/src/components/PdfWorkbench.vue` | DELETE |
| PDF 清除 | `frontend/src/views/ProjectDetailView.vue` | MODIFY (移除 PDF section) |
| PDF 清除 | `frontend/src/views/KanbanView.vue` | MODIFY (移除 pdf-editor 導航) |
| PDF 清除 | `frontend/src/router/index.js` | MODIFY (移除 L43-46 路由) |
| PDF 清除 | `frontend/src/services/api.js` | MODIFY (移除 L68-79 三個方法) |
| 架構 | `backend/engine/file_service.py` | NEW |
| 架構 | `backend/engine/image_service.py` | NEW |
| 架構 | `backend/engine/cache_service.py` | NEW |
| 架構 | `backend/engine/file_ops.py` | DELETE (遷移後) |
| 架構 | `backend/engine/core.py` | MODIFY (持有新 Service) |
| 架構 | 所有 Router | MODIFY (呼叫新 Service) |
| Resplit | `frontend/src/components/ResplitModal.vue` | MODIFY (讀 RAW 圖) |
| Resplit | 後端 image_service (原 file_ops) | MODIFY (從原始輸入切) |
| 印章 | `frontend/src/components/StampAssignDialog.vue` | MODIFY (跳過偵測) |
| 印章 | `frontend/src/store/stamp.js` | MODIFY (刪 detect) |
| 印章 | `frontend/src/services/api.js` | MODIFY (刪 detectStamps) |
| 印章 | `backend/routers/stamps.py` | MODIFY (刪 detect endpoint) |
| 印章 | `backend/engine/stamp_service.py` | MODIFY (刪 preview) |
| 印章 | `backend/processing/stamp_processor.py` | MODIFY (刪偵測邏輯) |

---

## 3. 具體修改計畫

### 3.1 [Cleanup] 徹底移除獨立 PDF 蓋章排版功能

使用者確認「上傳 PDF 蓋章排版」是不同產品線的舊版功能，當前專案只需處理發票憑證 (Voucher)。

#### 3.1.1 後端刪除

**[DELETE] `backend/routers/pdf.py`**
- 含三個 endpoint：`POST /{project_id}/pdf` (上傳)、`POST /{project_id}/{job_id}/commands` (蓋章排版)、`GET /{project_id}/{job_id}/download`。
- 唯一呼叫端，刪檔即可。

**[DELETE] `backend/engine/pdf_worker.py`**
- 獨立執行緒，用 `asyncio.new_event_loop()` 跑獨立 Event Loop，從 `pdf_task_queue` 取任務。
- 只被 `core.py` L28 import + L145-151 啟動。

**[DELETE] `backend/processing/pdf_engine.py`**
- 封裝 PyMuPDF 的 `execute_commands`、`compress_pdf`、`reorder_pages`、`stamp_image`、`inject_text_layer`。
- 只被 `pdf_worker.py` L10 import + L67 呼叫。

**[MODIFY] `backend/engine/core.py`**
需移除的精確位置：
- L28：`from .pdf_worker import pdf_worker_loop`
- L81：`self.pdf_task_queue: queue.Queue = queue.Queue()`
- L86：`self._pdf_worker_thread: Optional[threading.Thread] = None`
- L144-152：啟動 PDF Worker Thread 的整段程式碼
- L247-260：`enqueue_pdf_job` 方法
- L374-376：`add_pdf_files` wrapper 方法

**[MODIFY] `backend/main.py`**
- L25：移除 `from backend.routers.pdf import router as pdf_router`
- L137：移除 `app.include_router(pdf_router, prefix="/api/pdf", tags=["pdf"])`

**[MODIFY] `backend/engine/file_ops.py`**
- L730+ 的 `add_pdf_files` 方法：在架構拆分前先刪除（唯一呼叫端 `pdf.py` 已被整檔刪除）。

#### 3.1.2 前端刪除

**[DELETE] `frontend/src/views/PdfEditorView.vue`** (119 行)
**[DELETE] `frontend/src/components/PdfWorkbench.vue`** (12831 bytes)
- `PdfWorkbench` 只被 `PdfEditorView` 引用。

**[MODIFY] `frontend/src/router/index.js`**
- 移除 L43-46 的 `{ path: '/project/:id/pdf-editor', name: 'pdf-editor', ... }` 路由。

**[MODIFY] `frontend/src/views/ProjectDetailView.vue`**
- 移除 L57-60 的「上傳 PDF 檔案」input 區塊。
- 移除 L167-211 的「獨立 PDF 文件 (PDF Files)」整個 Table section。
- 移除 L236 的 `pdfJobs` computed。
- 移除 L351-357 的 `getPdfStatusBadgeClass` 函式。
- 移除 L463-490 的 `handlePdfUpload` 函式。
- 移除 L520-522 的 `editPdfJob` 函式。

**[MODIFY] `frontend/src/views/KanbanView.vue`**
- 移除 L164 附近導向 `pdf-editor` 的 `router.push` 邏輯。

**[MODIFY] `frontend/src/services/api.js`**
- 移除 L66-79 的「PDF Processing」區塊（`uploadPdf`、`executePdfCommands`、`downloadPdf`）。

---

### 3.2 [Architecture] FileOps → Service 拆分

> **風險控管**：`file_ops.py` 788 行的巨型物件，需分批遷移。
> 建議執行順序：先搬 Cache → File → Image，每搬一組跑一次 pytest。

#### [NEW] `backend/engine/file_service.py`
純檔案 I/O，不依賴 Semaphore 或 Codec：
- `_resolve_project_path(root, raw_path, preferred_dir)` → 路徑解析
- `_is_within_root(root, target)` → 安全檢查
- `_safe_delete_file(root, target, ...)` → 安全刪除
- `get_raw_files(project_id)` → 列出原始檔
- `delete_raw_file(project_id, filename)` → 刪除原始檔
- `delete_job_files(project_id, job_id)` → 含 GC 佇列

#### [NEW] `backend/engine/image_service.py`
需要 Semaphore / Codec / OpenCV：
- `add_project_files(project_id, files, file_type)` → 含 JXL 寫入
- `apply_job_resplit(project_id, job_id, sub_rects)` → 手動二切
- `detect_job_sub_rects(project_id, job_id)` → 建議框線偵測
- `optimize_jxl_storage(...)` → 背景 JXL 最佳化
- `_warp_by_points(image, points)` → 透視變換裁切
- `_optional_semaphore()` → 並行控制
- `_codec_adapter()` → 取得 ImageCodecAdapter

#### [NEW] `backend/engine/cache_service.py`
從 `CacheMixin` 晉升：
- `ensure_preview_cache(project_id, image_path, max_width)` → 縮圖快取
- `cleanup_preview_cache(max_age_hours)` → 過期清理
- `_thumb_max_width()` → 取得設定值

#### [MODIFY] `backend/engine/core.py`
- 改為持有 `self.file_service`、`self.image_service`、`self.cache_service`。
- 刪除所有「純轉發 wrapper」方法。

#### [MODIFY] 所有 Router
- `files.py`：`engine.file_ops.xxx` → `engine.file_service.xxx` / `engine.cache_service.xxx`
- `jobs.py`：`engine.apply_job_resplit` → `engine.image_service.apply_job_resplit`
- `projects.py`：`engine.file_ops.add_project_files` → `engine.image_service.add_project_files`
- `voucher.py`：`engine.file_ops.ensure_preview_cache` → `engine.cache_service.ensure_preview_cache`
- `processing.py`：相關呼叫更新

#### [DELETE] `backend/engine/file_ops.py`
- 所有方法遷移完成後刪除整個檔案。

---

### 3.3 [Feature] 手動二切 (Resplit) 邏輯修正

**痛點**：使用者要恢復「機器切壞的發票」，但目前只顯示切壞的殘片，無法看到完整的原始圖來重新定位。

**原則**：
- 座標系統統一：前端顯示 RAW 大圖，後端偵測和裁切也用 RAW 大圖。
- 免改 DB Schema：完全靠字串推導（`_split_` 前面的 stem → RAW 檔名）。

#### [MODIFY] `frontend/src/components/ResplitModal.vue`

1. **影像來源** (L99-101)：
   ```javascript
   // 之前：preview/split/${filename}
   // 之後：preview/raw/${rawFilename}
   ```
   新增 `rawFilename` computed：從 `props.job.image_path` 提取 `_split_` 前面的 stem 拼出 RAW 檔名。

2. **後端 API 不動**：仍呼叫 `detectJobSubRects`/`applyJobResplit`，差異在後端內部改讀來源。

#### [MODIFY] 後端 `detect_job_sub_rects` (file_ops.py L628-643 / 拆分後 image_service)

```python
# 之前：preferred_dir="分割發票"   → 讀切壞的小圖做偵測
# 之後：preferred_dir="原始輸入"   → 讀完整大圖做偵測
```
需加入「從 split 檔名推導 raw 檔名」的邏輯。

#### [MODIFY] 後端 `apply_job_resplit` (file_ops.py L645-728 / 拆分後 image_service)

```python
# 之前：source 讀 分割發票 目錄
# 之後：source 讀 原始輸入 目錄（RAW 圖）
```
裁切 `_warp_by_points(raw_image, points)` 後建立新 Job，刪除舊 Job。

---

### 3.4 [Feature] 印章識別改為「全人工極簡化」

**決策依據**：印章建檔極少使用，自動偵測寫死 HSV 閾值效果差。拉框歪一點，去背後放到 PDF 上反而更像人類蓋印。

#### [MODIFY] `frontend/src/components/StampAssignDialog.vue`
1. **拔除自動偵測**：在 Step 1 上傳圖片後，略過 `detectAndGoNext`，直接 `step = 2` 進入拉框畫布。
2. **精簡步驟**：Step indicator 從三步改為兩步。
3. 手動拉框、checkbox 啟用/停用等既有 UX 全部保留。

#### [MODIFY] `frontend/src/store/stamp.js`
- 刪除 L8 `detecting` ref。
- 刪除 L27-38 `detectStamps` action。
- 刪除 export 中對應的引用。

#### [MODIFY] `frontend/src/services/api.js`
- 刪除 L197-203 的 `detectStamps()` 方法。

#### [MODIFY] `backend/routers/stamps.py`
- 刪除 L64-89 的 `POST /stamps/detect` endpoint。

#### [MODIFY] `backend/engine/stamp_service.py`
- 刪除 L63-71 的 `build_preview_base64` 靜態方法（唯一呼叫端是被刪除的 detect endpoint）。

#### [MODIFY] `backend/processing/stamp_processor.py`
- 刪除 `detect_stamps` 及其內部呼叫的 `_build_edge_mask`、`_suppress_overlaps`、`_iou` 等輔助方法。
- **保留**去背核心：`extract_stamps`、`crop_and_remove_background`、`_build_red_mask`、`_build_binary_foreground_mask`。

---

## 4. 執行順序建議

1. **Phase 1 - 先清後建**：拔除 PDF 模組 (3.1)，降低整體複雜度。
2. **Phase 2 - 架構拆分**：FileOps 分拆 (3.2)。每遷移一個 Service 跑一次 pytest。
3. **Phase 3 - 功能修正**：Resplit 對齊 RAW (3.3) + 印章全人工化 (3.4)。
4. **Phase 4 - 驗證**：全面測試。

---

## 5. 驗證計畫

### 自動測試
- `ruff check backend` — 零 lint 錯誤，確認刪除後無殘留引用。
- `pytest` — 全部通過，架構遷移無回歸。
- `npm run build` — 前端編譯零錯誤，確認刪除 PDF 組件後無遺漏。

### 手動測試
1. **Resplit**：點開 ResplitModal → 背景圖必須是完整原始大圖（非殘片）。
2. **印章**：上傳印章圖紙 → 不出現轉圈等待，直接進入拉框畫布。
3. **PDF 移除**：`ProjectDetailView` 中不再出現「獨立 PDF 文件」表格及上傳按鈕，原本的按鈕不會導致白螢幕。
