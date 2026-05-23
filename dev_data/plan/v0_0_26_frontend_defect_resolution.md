# v0.0.26 前端缺陷修復計畫

**狀態**: 規劃中 (待套用)

---

## 核心目標

針對使用者回報的四項 frontend/UX 缺陷進行修正：
1. **返回按鈕定位與對齊修復**：修正 `VoucherEditorView.vue` 與 `ProjectDetailView.vue` 返回按鈕的對齊與樣式，消除因瀏覽器預設 margin 造成的版面扭曲。
2. **圖片旋轉按鈕失效修復**：修正 API 呼叫路徑中的 `filename` 參數編碼，對含有中文或特殊字元的檔名進行 URL 編碼以避免路由解析失敗。
3. **「核對資料」導向錯誤修復**：將 path-based 的 `router.push` 統一改為 standard named routing 寫法，確保專案 ID 參數與編輯 job 參數正確帶入。
4. **手動二切功能失效修復**：修正 `ResplitModal.vue` 因圖片載入與偵測 API 解析的先後順序（Race Condition）而造成預設切割區域被初始化為 100x100 的繪圖漂移問題，並移除 hardcoded 的後端主機連接埠。

---

## 預期改動與修復方向

### 1. 返回按鈕定位與對齊 (DEF-1)
- **問題分析**：
  - `VoucherEditorView.vue` 的 `<h2>` 標題因為沒有重設 default margin 0，在 flex 佈局下將標題與 `.back-btn` 拉開並拉高了 header 區塊，造成返回按鈕偏下且不對齊。
  - 專案細節頁 `ProjectDetailView.vue` 的 `.back-btn` 樣式缺乏 border-radius 與滑鼠懸停效果。
  - `VoucherEditorView.vue` 中，專案為空時的 `empty-state-overlay` 內 button 同時繼承 `.back-btn` 與 `.empty-state-content button`，引發樣式覆蓋混亂。
- **修復方案**：
  - 在 `VoucherEditorView.vue` 中加入 `.header-left h2 { margin: 0; font-size: 1.25rem; }` 以精準對齊。
  - 將專案為空時的按鈕 class 從 `back-btn` 改為獨立的 `empty-back-btn`。
  - 為 `ProjectDetailView.vue` 的 `.back-btn` 加上圓角、轉場 hover 動態效果，使其符合系統 UI 一致性。

### 2. 旋轉與刪除按鈕中文檔名路徑編碼 (DEF-2)
- **問題分析**：
  - `api.js` 中，`rotateImage`、`deleteRawFile`、`runSplitSingle` 連接埠路徑直接使用 `${filename}`。當檔名包含中文（如 `114-2燕巢小宏遠一.jpg`）或特定符號時，FastAPI 路由解析出錯並回傳 404 或 400。
- **修復方案**：
  - 修改 `api.js` 中相關路徑，將 `${filename}` 替換為 `${encodeURIComponent(filename)}`。

### 3. 核對資料按鈕命名路由修復 (DEF-3)
- **問題分析**：
  - 在 `ProjectDetailView.vue` 中，核對資料按鈕綁定的 `editJob` 方法與開啟憑證編輯器方法使用 path-based `router.push({ path: ... })`。這在處理帶有參數的路徑時較為脆弱。
- **修復方案**：
  - 統一改用 named routing 寫法：
    - `router.push({ name: 'voucher-editor', params: { id: projectId }, query: { editJobId: job.job_id } })`

### 4. 手動二切 Modal 畫布座標漂移與 Race Condition 修復 (DEF-4)
- **問題分析**：
  - 在 `ResplitModal.vue` 中，當 Modal 開啟時會觸發 `fetchDetectedRects` 偵測 API。如果 API 呼叫速度比圖片載入觸發 `@load="onImageLoad"` 的速度快，此時 `naturalSize.width` 為 0 且 `fullImageSize` 也尚未取得，`createDefaultRect()` 會 fallback 到 `100x100` 像素。
  - 當圖片載入完成後，SVG viewBox 雖然伸展至 full 尺寸，但預設 rects 已經被初始化為 `100x100` 的微小方塊並被固定在左上角，導致使用者無法看到與拖曳，形同功能損壞。
- **修復方案**：
  - 修改 `ResplitModal.vue` 的 API 邏輯：在 `fetchDetectedRects` 偵測完或 catch error 時，若 `naturalSize.width === 0` (代表圖片尚未載入)，將 `rects.value` 設為空陣列 `[]`，直到 `@load="onImageLoad"` 執行時，若偵測到 `rects.value.length === 0`，再動態生成尺寸與 viewBox 一致的預設區域。
  - 將 modal 內 hardcoded 的 `http://localhost:8000` 圖片前綴，替換為 Axios 的 `api.toAbsoluteUrl` 解析方法。

---

## 相關修改檔案

### Frontend
- [api.js](../../frontend/src/services/api.js)
- [ProjectDetailView.vue](../../frontend/src/views/ProjectDetailView.vue)
- [VoucherEditorView.vue](../../frontend/src/views/VoucherEditorView.vue)
- [ResplitModal.vue](../../frontend/src/components/ResplitModal.vue)

---

## 驗證計畫

1. **返回按鈕對齊**：開啟憑證編輯器，確認「← 返回活動」與「憑證黏貼編輯器」標題在同一水平線上，且高度無異常拉伸。
2. **中文檔名旋轉**：點擊中文檔名原始圖分割出來的發票卡片上的旋轉按鈕（↻ / ↺），確認預覽圖即時更新且無 404/500 錯誤。
3. **核對資料跳轉**：點擊「核對資料」，確認順利跳轉至憑證編輯器，且自動彈出對應的 metadata 修改 sidebar。
4. **手動二切**：點擊手動二切，確認在大圖上會出現可拖曳的點與藍色半透明區域，並能成功保存套用二切結果。
