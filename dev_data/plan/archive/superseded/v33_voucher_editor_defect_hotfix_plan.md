# 憑證黏貼編輯器 v33 — 缺陷修正計畫（Hotfix Plan）

日期：2026-03-05  
前置：v32_voucher_editor_plan_completion.md、v32_voucher_editor_execution_checklist.md

---

## 0) 驗證結論（v32 是否完工）

### 自動化結果
- 前端 utils 測試：18/18 PASS（`node --test frontend/tests/voucher-utils.test.js`）
- 後端測試：362/362 PASS（`python -m pytest tests/ -v --tb=short`）

### 完工判定
- **程式主體功能已大致完成（9 項大功能皆有落地）**。
- **但尚未達到「100% 完工」**，因為仍有 3 個缺陷/規格落差，且 v32 手動驗收清單尚未逐項勾驗。

---

## 1) 缺陷清單（需修）

| ID | 嚴重度 | 位置 | 現象 | 影響 |
|:--|:--|:--|:--|:--|
| D1 | 🔴 高 | `frontend/src/views/VoucherEditorView.vue` `runAutoLayout()` | `autoLayoutImages()` 回傳 `null` 時直接 `return`，未顯示提示 | 使用者無法理解自動排版失敗原因（違反 v32 規格） |
| D2 | 🔴 高 | `frontend/src/views/VoucherEditorView.vue` `runAutoLayout()` | 排版輸入來源只取 canvas 現存物件，接著 `activePage.images = layoutResult` | 在圖片尚未載入完成/暫缺時，可能造成頁面 image 資料遺失 |
| D3 | 🟡 中 | `frontend/src/views/VoucherEditorView.vue` `onBeforeUnmount()` | 先 `dispose()` canvas，再 `saveLayout()` | 離頁最後一次儲存可能缺少最新 canvas 同步狀態 |
| D4 | 🔴 高 | `frontend/src/views/VoucherEditorView.vue` `recalculatePageFields()` | 日期取值邏輯錯誤，從 `inv.result.date` 改成 `inv.result.header.date` | 前端日期沒有自動抓取 |
| D5 | 🔴 高 | `frontend/src/views/VoucherEditorView.vue` `recalculatePageFields()` | 金額取值邏輯錯誤，從 `inv.result.total_amount \|\| inv.result.amount` 改成 `inv.result.summary.total` | 金額沒有自動加總 |
| D6 | 🔴 高 | `frontend/src/views/VoucherEditorView.vue` `recalculatePageFields()` | 用途取值邏輯錯誤，從 `item.description \|\| item.name` 改成 `item.category` | 用途抓錯欄位，應該取「分類」而不是「詳細描述」；且欄位未被自動填寫 |

---

## 2) 修正方案（Implementation Plan）

### Step 1 — 補齊自動排版失敗提示（修 D1）
**檔案**：`frontend/src/views/VoucherEditorView.vue`

在 `runAutoLayout()` 中：
- 目前：`if (!layoutResult) return`
- 修正：改為顯示 alert 後 return

建議文案：
- `發票過多或尺寸過大，自動排版無法在安全區內排下。請手動微調或分頁。`

**驗收**：構造一組無法排版資料，點 `⚡ 自動排版`，必須看到提示。

---

### Step 2 — 排版前完整性檢查（保守方案，修 D2）
**檔案**：`frontend/src/views/VoucherEditorView.vue`

在 `runAutoLayout()`：
1. 先比對 `activePage.value.images` 與 canvas invoice 物件是否「全量對齊」（每個 jobId 都要在 canvas 找到）。
2. 若未全量載入（例如圖片仍在 onload 或失敗重試中），直接提示並中止排版。
3. 僅在全量對齊時才執行 `autoLayoutImages(items, SAFE_ZONE)`。
4. 排版後再整批回寫 `activePage.value.images` 與 canvas 座標，避免因部分載入導致資料遺失。

**驗收**：
- 在圖片延遲載入場景下執行自動排版，必須出現「尚未載入完成」提示，且 `activePage.images.length` 不可減少。
- 在全量載入後執行排版，資料與畫布均維持一致。

---

### Step 3 — 調整 unmount 儲存順序（修 D3）
**檔案**：`frontend/src/views/VoucherEditorView.vue`

在 `onBeforeUnmount()`：
1. 先 `syncActivePageFromCanvas()`（若 canvas 存在）。
2. 再 `await saveLayout()`。
3. 最後才 `fabricCanvas.dispose()`。

**驗收**：
- 拖曳完圖片後立即離開頁面，重新進入時座標需與離開前一致。

---

### Step 4 — 修正日期自動抓取（修 D4）
**檔案**：`frontend/src/views/VoucherEditorView.vue`

在 `recalculatePageFields(page)` 中：
- 目前：`(inv.result || {}).date`
- 改為：`inv.result?.header?.date`（取用發票 header 中的 date）

**驗收**：
- 添加有日期的發票到頁面，檢驗「日期」欄位是否被自動填寫為最新的發票日期。

---

### Step 5 — 修正金額自動加總（修 D5）
**檔案**：`frontend/src/views/VoucherEditorView.vue`

在 `recalculatePageFields(page)` 中：
- 目前：`String(result.total_amount || result.amount || '0')`
- 改為：`result.summary?.total ?? 0`（取用發票 summary 中的 total）

**驗收**：
- 添加多張有金額的發票到頁面，檢驗「金額」欄位是否自動計算為所有發票金額之和。

---

### Step 6 — 修正用途欄位與自動填寫（修 D6）
**檔案**：`frontend/src/views/VoucherEditorView.vue`

在 `recalculatePageFields(page)` 中：
- 目前：取 `item.description || item.name`（品項的詳細描述或名稱）
- 改為：取 `item.category`（發票中的報帳名目/分類）
- 同時確保在 `switchPage()` 和 `onMounted()` 後自動調用 `recalculatePageFields(activePage.value)`

**驗收**：
- 添加有分類（category）的發票到頁面，檢驗「用途」欄位是否自動填寫為發票的分類，例如「茶水、餐食」等。
- 切換頁面時，若無手動編輯過，用途應重新計算。

---

## 3) 測試計畫（Hotfix 驗證）

### 單元測試（建議新增）
**檔案**：`frontend/tests/voucher-utils.test.js`
- 目前已覆蓋 `autoLayoutImages` 演算法。
- 本次 D1/D2/D3 多屬元件流程，建議新增 component-level 測試或先以手動驗收補足。

### 手動驗收（必做）
1. 自動排版失敗提示：確認 alert 出現。  
2. 部分圖片延遲/失敗載入時執行自動排版：確認頁面資料不掉圖。  
3. 拖曳後立即離頁再回來：確認布局已保存。  

---

## 4) 交付完成定義（DoD）

- [ ] D1~D6 皆完成修正。
- [ ] 前端 utils 測試持續全綠（18/18 或以上）。
- [ ] 後端回歸測試維持全綠（362/362 或以上）。
- [ ] v32 手動驗收 checklist 補勾完畢。
- [ ] 驗證：日期、金額、用途三個欄位自動填寫正常。

---

## 5) 風險與回滾

- 本次變更只觸及前端 `VoucherEditorView.vue`，不改 API schema。
- 若 hotfix 有異常，可先回退 `runAutoLayout` 與 `onBeforeUnmount` 區段，不影響既有後端流程。
