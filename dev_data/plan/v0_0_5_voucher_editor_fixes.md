# 憑證黏貼編輯器 — Beta 0.0.5 (修復 V0.0.4 的嚴重破壞)

**日期**: 2026-03-07
**狀態**: 規劃中

## 🎯 失敗原因回顧 (Post-Mortem of V0.0.4)
前一個版本的修正產生了嚴重的副作用，原因如下：

1. **「123頁全部串一起」與「刪除選取刪除了整頁」**：
   - 在上個版本中，我移除了 `canvasLoading` 和非同步載入保護機制 (`pendingImageLoads`)，同時在 `syncActivePageFromCanvas` 中使用了錯誤的物件對應，導致 Vue 響應式狀態混亂。切換頁面時舊的物件被保存到了所有頁面上，導致頁面狀態全部串連在一起。
   - `removeSelectedOnCanvas` 的修改可能破壞了 Fabric.js 的層級關係，導致整個頁面資料被清空。
2. **「編號高了、金額不在格子裡、日期寫到用途裡」**：
   - 這是因為我錯誤使用了 `fitz.search_for()` 抓取**「標題文字」**(如「憑證編號」四個字) 的座標，並直接把使用者輸入的內容對齊在這個「標題」上。結果當然是字疊在標題上，而不是填寫在標題底下的「空白格子」內。

## 🛠️ 正確的修正計畫 (版本 0.0.5)

### 目標一：精準找出真正的「輸入格」座標 (而不是標題)
新版的 PDF 確切只有 **6 碼金額 (十萬到元)**。
透過 Python + PyMuPDF 的直觀圖形測量，精準的基準線 (Baseline) 座標如下：
- `憑證編號`：`(90, 310)`
- `預算科目`：`(210, 310)`
- `金額` (6碼)：`x=[316, 335, 355, 373, 393, 412]`, `y=310`
- `用途說明`：TextBox 左上角 `(435, 230)` 寬度 `113`
- `日期`：`(460, 365)`
- `發票張數`：`(482, 115)`

### 目標二：安全地修復按鈕「失焦 (Blur) 導致選取失效」問題
**目標文件**: `frontend/src/views/VoucherEditorView.vue`
1. 絕不去碰原有的 `canvasLoading`、非同步載入等保護機制。
2. 僅將 Header 中的 `<button class="save-btn" @click="removeSelectedOnCanvas">刪除選取</button>` 改為 `@mousedown.prevent="removeSelectedOnCanvas"`。
   - 為什麼是 `mousedown.prevent`？因為 `click` 會在滑鼠放開時觸發，並轉移焦點。`mousedown.prevent` 能阻止瀏覽器將 Focus 從 Canvas 拿走，讓 Fabric.js 保持 `getActiveObjects()`，就能正確刪除。

### 目標三：保護已填寫的內容 (防止亂清空)
**目標文件**: `frontend/src/views/VoucherEditorView.vue`
確保 `onlyFillEmpty` 的邏輯只在**完全空白**時填入。如果陣列空了，不要執行 `page.fields.xxx = ''`。

### 目標四：後端字元遺失防護 (Missing Font)
**目標文件**: `backend/engine/voucher_generator.py`
只在初始化生成器時加上 `font_path` 的絕對路徑檢查與回退，不改動任何其他的 PDF 產出行李，確保穩定性。

---
## 執行步驟
1. 透過 Python 或 Browser Subagent 量測 PDF 空白格的準確像素座標。
2. 小心翼翼地套用 `@mousedown.prevent`，絕不改動 Vue 的狀態管理或 `loadActivePageToCanvas` 機制。
3. 更新 `VoucherEditorView.vue` 的 `drawTextFieldsOnCanvas`。
4. 更新 `voucher_generator.py` 的文字寫入點。
