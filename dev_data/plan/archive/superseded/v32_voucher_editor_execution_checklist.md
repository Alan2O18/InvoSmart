# 憑證黏貼編輯器 v32 — 實作/測試執行清單（按檔案拆分）

日期：2026-03-04  
來源：v32_voucher_editor_plan_completion.md

---

## 使用方式

- 勾選順序建議：先做「實作清單」，再做「測試清單」。
- 每完成一小節就執行對應測試，避免一次改太多難回溯。
- 本清單只涵蓋前端（Vue + utils + frontend tests）；後端不需修改。

---

## A. 實作清單（Implementation Checklist）

## 1) frontend/src/views/VoucherEditorView.vue

### A1. 鍵盤事件防衝突（Step 0）
- [ ] 在 `keyboardHandler` 增加輸入焦點 guard：`input/textarea/select` 不觸發刪圖。
- [ ] 增加 IME guard：`event.isComposing === true` 直接 return。
- [ ] （建議）支援 `contenteditable` 元素 guard。

**驗收條件**
- [ ] 在用途 textarea 按 Backspace/Delete 只刪文字，不刪 canvas 發票。

---

### A2. 等比例縮放鎖定（Step 1）
- [ ] 在 `addInvoiceObjectToCanvas` 對 invoice 物件隱藏中間控制點：`mt/mb/ml/mr: false`。
- [ ] 確認 Canvas 使用 Fabric v7 預設 `uniformScaling`（不加舊版 `lockUniScaling`）。
- [ ] `applyObjectBounds` 增加 guard：只處理 `obj?.data?.kind === 'invoice'`。
- [ ] `applyObjectBounds` 以統一比例回寫：`scaleX === scaleY`。

**驗收條件**
- [ ] 只能透過四角縮放，圖片不會被壓扁拉長。

---

### A3. 欄位即時高光（Step 2）
- [ ] 為金額 input 套用動態 class：
  - [ ] 小數 → `field-error-yellow`
  - [ ] 超額（> 9,999,999）→ `field-error-red`
- [ ] 為日期 input 套用動態 class：無效日期/空日期且有圖 → `field-error-red`。
- [ ] 新增 per-page computed：
  - [ ] `isCurrentPageDateInvalid`
  - [ ] `isCurrentPageAmountDecimal`
  - [ ] `isCurrentPageAmountExcessive`
- [ ] 新增 dark theme 相容 CSS：`field-error-red` / `field-error-yellow`。

**驗收條件**
- [ ] 當前頁輸入異常時，欄位本身立即變色（不只頂部紅字）。

---

### A4. 用途字數警告（Step 3）
- [ ] 將用途欄位包在 `.purpose-wrap`。
- [ ] 新增字數顯示 `{{ purposeLength }} / 40 字`。
- [ ] 超過 40 字：textarea 套 `field-error-yellow`，計數器加 `warn` class。
- [ ] 新增 `purposeLength` computed。

**驗收條件**
- [ ] 用途 > 40 字時，背景變黃且計數器轉警示色。

---

### A5. Empty State 遮罩（Step 4）
- [ ] 新增 `isEmptyProject` computed（建議與 loading 分離）。
- [ ] `canvas-wrap` 加上 disabled class 與 overlay。
- [ ] overlay 顯示「尚無可用發票」說明與返回按鈕。
- [ ] 只禁用 `canvas` pointer events，不禁用 overlay 按鈕。

**驗收條件**
- [ ] 無可用發票時畫布不可操作，且有清楚引導。

---

### A6. Per-page 自動域計算（Step 5）
- [ ] 新增 `recalculatePageFields(page)`：
  - [ ] `receiptCount` = 當頁圖片數
  - [ ] `amount` = 當頁發票金額合計（先清理千分位字元後再 parse）
  - [ ] `payDate` = 當頁有效日期最大值
  - [ ] `purpose` = `description || name` 去重拼接（若非手動編輯）
- [ ] 呼叫時機只放在「新增/刪除發票」路徑，不放在純移動同步。

**驗收條件**
- [ ] 拖入/移除發票後，金額/日期/用途即時正確重算。

---

### A7. 碰撞偵測與紅框（Step 6）
- [ ] 引入 `findOverlappingJobIds`。
- [ ] 建立 `updateOverlapHighlight()`：從 canvas live objects 取即時座標。
- [ ] 重疊時套紅框（`#FF0000`），非重疊回綠框（`#22c55e`）。
- [ ] 在 5 個時機呼叫：
  - [ ] `object:moving`
  - [ ] `object:modified`
  - [ ] `addInvoiceObjectToCanvas` 完成新增後
  - [ ] `removeImage` 結尾
  - [ ] `removeSelectedOnCanvas` 結尾
- [ ] （建議）`object:moving` 以 `requestAnimationFrame` 節流。

**驗收條件**
- [ ] 拖曳、新增、刪除都能即時更新重疊紅框。

---

### A8. 用途覆蓋保護對話框（Step 7）
- [ ] 在 `addInvoiceToActivePage` 先檢查：若 `isManuallyEdited === true` 且用途非空，彈 confirm。
- [ ] 按「取消」：加入發票但跳過用途覆蓋。
- [ ] 按「確定」：清除 `isManuallyEdited` 後再重算用途。
- [ ] 新增 `onPurposeManualEdit` 並在 textarea 綁定 `@input`。

**驗收條件**
- [ ] confirm 的兩條分支都符合預期（保留/覆蓋）。

---

### A9. 自動排版按鈕與流程（Step 8）
- [ ] Toolbar 新增 `⚡ 自動排版` 按鈕（無圖時 disabled）。
- [ ] 新增 `runAutoLayout()`：
  - [ ] 從 canvas invoice objects 蒐集 `originalWidth/originalHeight`
  - [ ] 呼叫 `autoLayoutImages(images, SAFE_ZONE)`
  - [ ] 若回傳 null 顯示提示
  - [ ] 套用回 `activePage.images` 與 canvas 物件座標/等比縮放
  - [ ] 結尾呼叫 `updateOverlapHighlight()`

**驗收條件**
- [ ] 3~10 張圖可一鍵排入安全區，且保持等比。

---

## 2) frontend/src/utils/voucher.js

### B1. 幾何碰撞工具
- [ ] 新增 `rectsOverlap(a, b)`（AABB）。
- [ ] 新增 `findOverlappingJobIds(images)` 回傳重疊 jobId 集合。

### B2. 自動排版演算法
- [ ] 新增 `autoLayoutImages(images, safeZone)`。
- [ ] 使用二分搜尋找最大統一高度 H（含 GAP）。
- [ ] 生成最終 `{ jobId, x, y, w, h }`。
- [ ] 無法容納時回傳 `null`。

### B3. 匯出一致性
- [ ] 確認新函式皆為 named export，供 `VoucherEditorView.vue` 匯入。

---

## B. 測試清單（Test Checklist）

## 3) frontend/tests/voucher-utils.test.js

### C1. 碰撞檢測測試
- [ ] `rectsOverlap`：重疊/貼邊不重疊/完全分離。
- [ ] `findOverlappingJobIds`：
  - [ ] 3 張圖其中 2 張重疊
  - [ ] 多對重疊
  - [ ] 無重疊

### C2. 自動排版測試
- [ ] 單張圖：可放置，位置在 safe zone 內。
- [ ] 多張圖：不超出邊界，且 `h` 一致。
- [ ] 很多小圖：能換行排列。
- [ ] 極端案例：無法容納回傳 `null`。

### C3. 既有驗證函式回歸
- [ ] `hasInvalidDate`（空日期+有圖為 invalid）。
- [ ] `hasDecimalAmount`。
- [ ] `hasExcessiveAmount`。
- [ ] `canGenerateVoucher` 在上述條件下的阻擋行為。

---

## 4) frontend/src/views/VoucherEditorView.vue（建議補 component-level 測試）

> 若目前專案尚未有 Vue component test 基礎設施，可先以手動驗證 + utils 單元測試覆蓋，後續再補 Vitest + @vue/test-utils。

### D1. 互動流程測試（可先手動）
- [ ] 用途手動編輯後新增發票：驗證 confirm 的「確定/取消」。
- [ ] input/textarea 內 Backspace/Delete：不刪 canvas 物件。
- [ ] Empty state 顯示與按鈕可點擊。
- [ ] 自動排版後仍可拖曳與重新碰撞高光。

---

## C. 執行命令（建議）

### 前端測試
- [ ] `node --test frontend/tests/voucher-utils.test.js`

### （若有）前端整體測試
- [ ] `cd frontend && npm test`

### 手動驗收路徑
- [ ] 啟動前端，依 v32 checklist #1~#9 逐項驗收。

---

## D. 交付完成定義（Definition of Done）

- [ ] v32 的 9 個缺口全部實作完成。
- [ ] `frontend/tests/voucher-utils.test.js` 全綠。
- [ ] 不影響既有儲存/產出流程（layout JSON 結構不變）。
- [ ] 手動驗收 checklist 全部打勾。
- [ ] 變更記錄補到對應計畫文件（可在 v32 文件尾部附「Implementation Notes」）。
