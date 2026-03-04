# 憑證黏貼編輯器：現實落差與影像管線升級計畫 (v30_UX_and_Pipeline)

**日期**: 2026-03-03
**目標**: 
1. 盤點當前 `VoucherEditorView.vue` 與 `voucher_generator.py` 的實際開發進度，對比 `v27_ultimate_plan` 的 46 項防禦清單，找出現實與理想的落差（Half-implemented / Missing Features）。
2. 定義影像儲存與傳輸管線的最佳化方案 (JXL/AVIF) 及畫布長寬比鎖定 (Aspect Ratio Lock) 的實作細節。

---

## ▍第一部分：Voucher Editor 現狀盤點 (Reality Check)

### 🟢 已經確實實現的核心功能 (Fully Implemented)
目前的系統「基本可用」，也就是主幹流程已經打通，實現了以下 v27 規劃：
1. **前後端徹底解耦**：前端用 Vue + Fabric.js 排版，後端只負責把 `Layout JSON` 轉成 PyMuPDF 精準渲染。
2. **安全區邊界牆 (A.8)**：拖曳發票會精準卡在 `535x336` 的可黏貼區內，不會蓋到簽核欄（打贏了之前亂飄的問題）。
3. **後端高精準 PDF 渲染 (C.16-C.20)**：`voucher_generator.py` 已經完美實踐了：
   - 金額七位數對齊 (`※※※4607`)
   - 包含自動換行與字體縮小防無聲截斷的 `_insert_purpose` 演算法。
   - 300DPI 防畸形膨脹 (`F.43`) 與 PDF 無損壓縮 (`F.44`)。
4. **狀態解耦與防崩潰 (B.9 / D.30)**：刪除發票時，清單隨即釋放灰色狀態；且防幽靈串號演算法能正確繞過空頁給單號。

### 🟡 寫了一半、或體驗打折的功能 (Half-Implemented / UI Downgrades)
程式雖然有寫保護邏輯，但在「操作者體感」上與企劃書有極大落差，導致覺得「不太好用」：
1. **日期/金額的錯誤警報不夠明顯 (B.11, B.13)**：
   - 企劃描述：輸入非法日期時，「支付日期」欄位應該要**爆紅 (#FFE4E1)**；金額有小數時背景要**變黃 🟡**。
   - **現實狀況**：目前 UI 只有在最上面加一行紅字提示，輸入框本身沒有任何變色警示，操作者很難第一時間發現哪格出錯。
2. **重疊警告 (B.12)**：
   - 企劃描述：發票在畫布上互相重疊時，邊框應該變紅色發出警告。
   - **現實狀況**：目前前端沒有計算「物體互相碰撞」的邏輯，只有計算「有沒有撞到 A4 紙邊緣」，所以發票疊在一起毫無反應。
3. **用途說明的字數提醒 (C.21)**：
   - 企劃描述：用途欄位超過 40 字背景變黃，提示建議精簡。
   - **現實狀況**：純粹的 Textarea，沒有字數監聽或是變色警告。

### 🔴 徹底忘記/遺漏的功能 (Completely Missing)
這些是計畫書中明確要求，但目前 codebase 裡「完全找不到蹤影」的東西：
1. **[關鍵] 自動排版功能 (F.45)**：
   - 企劃描述：「點擊『自動排版』按鈕，觸發 O(N log H) 二分搜尋法，讓所有圖片對齊排滿」。
   - **現實狀況**：前端連這顆按鈕都沒有。所有的發票都必須人工一張一張用滑鼠慢慢拉。
2. **手動覆蓋詢問對話框 (A.8)**：
   - 企劃描述：「若手改過用途，再次拖入發票時應彈出詢問：『發現新發票，是否覆蓋您手動編輯的用途以更新？』」。
   - **現實狀況**：沒有實作任何彈跳視窗，加發票時目前也不會智慧覆蓋用途。
3. **全無發票時的防呆遮罩 (D.31)**：
   - 企劃描述：「全無發票時顯示 Empty State 禁用畫布」。
   - **現實狀況**：畫面右邊的畫布依然大剌剌開著，只是左邊清單空空如也，沒有引導性。

---

## ▍第二部分：影像處理管線升級與 Canvas 比例鎖定 (v31)

### 目標
1. **後端統一儲存格式 (JXL)**：將系統原始圖片與分割後的圖片儲存格式全面升格為 JPEG XL (.jxl)，這能大幅節省伺服器硬碟空間並保留高畫質。
2. **前端縮圖傳輸格式 (AVIF)**：當前端向後端請求發票預覽圖時，後端即時將影像壓縮為 AVIF 格式回傳，提升前端載入速度與節省頻寬。
3. **Canvas 物件等比例縮放 (Aspect Ratio Lock)**：修復目前 Voucher Editor 中發票可以被任意壓扁變形的問題。

### Proposed Changes
#### 1. 後端影像編解碼升級 (Dependencies & Utils)
- **[MODIFY] `requirements.txt`**
  - 新增 `imagecodecs` 套件以支援讀寫 `.jxl` 檔案格式。
  - 新增 `pillow-avif-plugin` 套件以支援 Pillow 輸出 `.avif` 格式。

- **[MODIFY] `backend/utils/utils.py`**
  - 修改 `cv_imread_chinese`：引入 `imagecodecs.imread` 攔截 `.jxl` 副檔名的讀取，其餘維持 OpenCV 處理。
  - 修改 `cv_imwrite_chinese`：引入 `imagecodecs.imwrite` 支援寫入 `.jxl`，確保影像維持 RGB 色域。

#### 2. 檔案寫入流程修改 (File Operations)
- **[MODIFY] `backend/engine/file_ops.py`**
  - **接收檔案**：上傳時開放支援 `.jxl` 和 `.avif` 的副檔名過濾。
  - **分割存檔**：在 `run_splitting` 迴圈中，將 `_split_i_ts.jpg` 改為儲存為 `.jxl`。
  - **PDF 轉圖**：將 `_page0_.jpg` 改為儲存為 `.jxl`，並改用 `imagecodecs` 將 PyMuPDF 的 pixmap 轉存。

#### 3. 前端影像傳輸與快取 (Image API)
- **[MODIFY] `backend/routers/voucher.py`**
  - 修改 `_load_image_bytes` 函式：
    - 讀取端：若遇到 `.jxl`，使用 `imagecodecs` 讀取並轉換為 Pillow `Image` 物件。
    - 輸出端：判斷 `thumb=True` 時，將 Pillow 物件輸出為 `format="AVIF"` 取代原本的 `WEBP`，並回傳 MIME type `image/avif`。

#### 4. 前端排版防呆機制 (Frontend Canvas)
- **[MODIFY] `frontend/src/views/VoucherEditorView.vue`**
  - 修改 `addInvoiceObjectToCanvas` 裡的 `fabric.Image` 設定：
    - 加入 `lockUniScaling: true` 屬性，強制只能等比例拉伸。
    - 呼叫 `obj.setControlsVisibility({ mt: false, mb: false, ml: false, mr: false })` 隱藏上下左右的邊界控制點，強制使用者只能拉四個角的控制點進行縮放。

---

## 🚀 結論與下一步

司令的感覺是完全正確的：這套系統目前的狀態是「後端工程師的 MVP」—— 也就是 API 跟底層算分都對了，但 **前端的智慧化輔助（Auto-layout, 欄位高光警示, 防撞框, 覆蓋對話框）全部都沒做**。

在實踐了第二部分的 JXL/AVIF 影像管線升級與長寬比鎖定後，我們接下來應該集中火力補齊第一部分的 UX 缺漏。

**建議行動事項順序**：
- **行動 A**：補齊前端 UX 視覺（日期/金額錯誤變色、重疊警告紅框、字數 40 字背景變黃）
- **行動 B**：實作「自動排版演算法」按鈕（這對擁有數十張發票的大型專案最實用）
- **行動 C**：實作「手動編輯用途的覆蓋與合併邏輯」保護對話框（避免一拉新發票，辛苦打的字被覆蓋）
- **行動 D**：全無發票時的禁用畫布遮罩 (Empty State)
