# v0.0.23 嚴重缺陷修復計畫 (Critical Defect Fixes)

經過重新深度分析 v0.0.20~v0.0.22 的實作，我發現了四個導致系統「功能嚴重缺陷」的核心問題。這些缺陷不僅讓系統無法正常初始化，甚至遺漏了當初承諾的關鍵功能（如：印章隨機旋轉）。本計畫將逐一修正這些問題。

## 核心缺陷分析與修復方案

### 1. [Backend] Virtual Persons 初始化靜默失敗 (印章無法管理根本原因)
**原因**：經過實際程式碼比對，`main.py` 的 import 順序本身並無問題。真正的問題是 `ensure_virtual_persons()` 在執行時，底層 SQLite DB 的 `persons` 資料表可能包含舊版 Schema (如缺少 `is_virtual` 欄位)，導致 ORM query 拋出例外，並被 `except` 靜默吞掉，3 個必要的虛擬角色就這樣消失了。Log 中顯示 `Virtual persons initialization failed` 是唯一的錯誤提示。
**這直接導致了「印章根本不能管理」**，因為系統內沒有「與正本相符」、「已稽核」、「社團關防」這三個可以綁定印章的虛擬人物！
**修復方式**：
- 啟動後先確認 `backend.log` 中的具體錯誤訊息。
- 若為 Schema 問題：重新執行資料庫升級腳本，確保 `persons` 資料表含有正確欄位。
- 加強錯誤捕捉，將真實 Exception 內容完整 log 出來，而非靜默吞掉。

### 2. [Backend] PDF 上傳後無法預覽 (瀏覽器強迫下載)
**原因**：在 `backend/routers/pdf_tasks.py` 的 `/pdf-tasks/{task_id}/file` API 中，回傳 `FileResponse` 時帶入了 `filename=task.filename`。這會觸發 FastAPI 自動加上 `Content-Disposition: attachment` 標頭，導致前端的 `<iframe src="...">` 被瀏覽器視為下載要求，而非在網頁內嵌預覽！
**修復方式**：
- 修改 API，加入 `content_disposition_type="inline"` (如果 FastAPI 版本支援)，或是手動設定 Header，確保 PDF 在 Iframe 中正常預覽。

### 3. [Backend] 印章蓋印邏輯「寫了個寂寞」(缺乏真實旋轉與透明度處理)
**原因**：
- `backend/routers/pdf_tasks.py` 只是把圖片原始檔用 `page.insert_image()` 硬塞進去，**完全沒有** 實作 ±10 度隨機旋轉，且缺乏對 PNG 透明通道的防護。
- 更糟的是，即使是 v0.0.20 寫的 `VoucherGenerator._insert_stamp`，原始碼中也只是印出 `logger.debug("旋轉意圖... 目前使用直接插入")`，根本沒有真正執行旋轉！
**修復方式**：
- 建立 `backend/utils/stamp_ops.py` (或整合至現有模組)，使用 `Pillow (PIL)` 讀取印章影像並轉換為 RGBA。
- 使用 `img.rotate(angle, resample=Image.BICUBIC, expand=True)` 進行高畫質旋轉並保留透明通道，再轉為 PNG Byte Stream。
- 將 `VoucherGenerator` 與 `pdf_tasks.py` 的蓋章邏輯全面替換為使用此函數，真正落實隨機旋轉與完美透明背景。

### 4. [Frontend] StampTemplateEditorView 視覺化編輯器缺陷
**原因**：
- 目前的 Canvas 只畫了色塊，並沒有真正載入印章圖片讓使用者預覽，無法達到「所見即所得」的真實感。
- Vue 3 的 Reactivity 處理對於動態增加物件 Key (如 `positions.value[role] = ...`) 如果未正確封裝，可能導致表單輸入時畫面不同步。
- 路由切換 (從編輯跳到新增) 時狀態未能乾淨重置。
**修復方式**：
- 在 Canvas 實作真正的 `Image()` 繪製邏輯，向後端抓取該角色的隨機印章圖片並覆蓋在座標上。
- 使用 `reactive` 重構狀態管理，確保表單綁定 `v-model.number` 時完美連動 Canvas 重繪。
- 強化 UI 的容錯與路由守衛 (watch route)。

## 預期修改檔案 (Proposed Changes)

### Backend Core & API
#### [MODIFY] [backend/main.py]
- 修正 `AsyncSessionLocal` 引用時機，確保 Virtual Persons 正常建立。

#### [NEW] [backend/utils/stamp_ops.py]
- 新增 `rotate_stamp_image(image_path: str, angle: int) -> bytes`，利用 Pillow 真實實作 PNG 旋轉並回傳 bytes。

#### [MODIFY] [backend/engine/voucher_generator.py]
- 引入 `stamp_ops.py`，修正 `_insert_stamp` 方法，刪除「意圖旋轉」的假邏輯，套用真正的旋轉。

#### [MODIFY] [backend/routers/pdf_tasks.py]
- 修正 `apply_stamp_to_pdf_task`，載入模板後，套用 `rotate_stamp_image` 產生旋轉後的影像 Stream，再進行 `insert_image`。
- 修正 `/pdf-tasks/{task_id}/file` 端點，將 `FileResponse` 的 `content_disposition_type` 設為 `"inline"`，解決 PDF 無法預覽的問題。

### Frontend UI
#### [MODIFY] [frontend/src/views/StampTemplateEditorView.vue]
- 加入真實圖片載入邏輯 (`new Image()`)。
- 修正 Vue reactivity 與表單綁定。

## Verification Plan
1. **後端啟動**：檢查 `backend.log` 不再出現 `Virtual persons initialization failed`。
2. **視覺化編輯**：進入「新增視覺化模板」，確認操作順暢且資料正確儲存，應能顯示真實圖片。
3. **PDF 預覽**：進入「獨立 PDF 任務處理」，上傳 PDF，確認 Iframe 能夠順利預覽文件內容而不是直接跳出下載對話框。
4. **蓋章驗證 (關鍵)**：在編輯器執行「全頁蓋章」，下載後確認印章是否**真正被旋轉了 ±10 度** 且 **背景保持透明**。
