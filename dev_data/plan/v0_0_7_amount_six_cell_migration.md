# 憑證黏貼編輯器 — V0.0.7 完整計畫 (六格金額制度全面收斂)

**日期**: 2026-03-08
**狀態**: 規劃中
**前置版本**: V0.0.6

---

## 目標

將 Voucher Editor 的金額制度從歷史遺留的七碼契約，完整收斂到實體模板實際存在的六格金額欄位，並在前端 UI、後端驗證、PDF 輸出、歷史資料相容策略與測試基準上同步完成切換。

---

## 背景與問題定義

V0.0.6 已完成文字座標校準與預覽/PDF 同步，但刻意保留了舊有七碼金額契約：

1. `VoucherFieldsStrict.amount` 目前仍允許 `<= 9999999`。
2. 前端 `formatVoucherAmountCells()` / `hasExcessiveAmount()` 仍以七格為假設。
3. `VoucherGenerator._insert_amount_cells()` 仍以七個 cell 寫入 PDF。
4. 歷史 layout 可能已保存七碼金額資料。
5. 實體憑證模板實際只有六格金額欄位，導致「制度允許、版面卻裝不下」的根本矛盾。

結論：V0.0.7 必須做的是制度切換，不只是改幾個座標。

---

## 範圍

### In Scope

1. 將憑證金額上限正式改為六格整數，也就是 `0 ~ 999999`。
2. 統一前端驗證、欄位預覽、PDF 輸出與後端 strict validation 的規則。
3. 定義歷史七碼資料在 UI / 匯入 / 舊 layout 載入時的相容與提示策略。
4. 補齊測試，讓六格制度成為可防回歸的正式契約。
5. 更新文件與版本紀錄，避免未來再把七格當成有效需求。

### Out of Scope

1. 不重做 Voucher Editor 整體 UI 版型。
2. 不改動用途 textbox、voucherNo 多行或 PDF 圖片排版邏輯。
3. 不處理非 Voucher 流程的金額欄位政策。

---

## 成功標準

1. 使用者無法再於 strict generate 流程提交超過六格的整數金額。
2. 前端預覽只畫六格金額字元，不再保留第七格的 legacy padding 行為。
3. 歷史七碼資料載入時，使用者能明確看到錯誤狀態或遷移提示，不會靜默截斷。
4. 後端 PDF、前端預覽、router validation、payload model 與 tests 對六格規則完全一致。
5. 文件、版本紀錄、測試名稱與錯誤訊息全部改為六格語意。

---

## 設計原則

### 1. 不做靜默截斷

七碼金額若直接砍掉左邊或右邊一位，雖然看似「能印出來」，實際上會破壞會計資料正確性。V0.0.7 禁止這種做法。

### 2. Draft 可以容錯，Strict 必須阻擋

- Draft / layout save 可以暫存歷史或錯誤資料，避免編輯器直接炸掉。
- Strict generate 必須攔下超過六格、含小數、含非數字的金額。

### 3. 前端提示要早於後端報錯

使用者在欄位輸入與預覽階段就應看到超額提示，而不是等到按下「產出 PDF」才知道失敗。

### 4. 共享設定仍維持單一來源

金額格的座標、格數與 padding 規則應繼續以 `backend/engine/voucher_text_config.py` 為主，不再回到前後端各寫一套常數。

---

## 需求拆解

### A. Payload 與驗證規則

目標檔案：

- `backend/models/voucher_payload.py`
- `tests/test_voucher_payload.py`
- `tests/test_routers_voucher.py`

修改內容：

1. 將 strict amount 規則改為六格整數上限 `999999`。
2. 明確禁止小數、負數、逗號格式輸入與非數字字符。
3. 保留 Draft 對原始字串的容忍，但要讓 strict path 在 generate 時精準報錯。
4. 錯誤訊息要直接指出「本版憑證金額僅支援六格整數」。

驗證案例：

- `999999` 合法
- `1000000` 非法
- `4607` 合法
- `04607` 是否允許要明確定義

建議：允許前導零存在於儲存字串，但 display / render 時仍顯示在六格內，不改數值語意。

### B. 共享文字設定改版

目標檔案：

- `backend/engine/voucher_text_config.py`
- `backend/routers/voucher.py`
- `frontend/src/services/api.js`

修改內容：

1. 將 `amount` config 的 `padLength` 從 `7` 改為 `6`。
2. 將 `xList` 收斂為六格清單，移除 legacy 第七格相容位。
3. 在 config payload 中顯式標註 `digitPolicy: 6` 或同等語意欄位，讓前端不必靠 array 長度猜規則。
4. 若需要處理 legacy layout，可另外加上 `legacyMaxDigits: 7` 供 UI 提示使用，但生成規則不得再接受七碼。

### C. 後端 PDF 生成

目標檔案：

- `backend/engine/voucher_generator.py`
- `tests/test_voucher_generator.py`

修改內容：

1. `_insert_amount_cells()` 改為六格輸出。
2. 對空字串、非數字仍維持安全 no-op。
3. 對超過六格的字串不得偷偷截斷；應由上游 strict validation 擋住，測試也要覆蓋。
4. `paymentAmount` 底部顯示仍保留完整千分位格式，例如 `123,456元整`。
5. 若 layout save 中殘留七碼資料，而 generate path 直接被呼叫，router/validation 必須先回 422，不讓 generator 在模糊狀態下處理。

### D. 前端欄位預覽與輸入提示

目標檔案：

- `frontend/src/utils/voucher.js`
- `frontend/src/views/VoucherEditorView.vue`
- `frontend/tests/`

修改內容：

1. `formatVoucherAmountCells()` 改為六格 padding。
2. `hasExcessiveAmount()` 門檻改為 `999999`。
3. 任何顯示「七格」語意的提示、註解、測試名稱、錯誤訊息一律更新。
4. 若載入的 page fields amount 超過六格：
   - 編輯器不得自動改值
   - 該頁應維持錯誤提示狀態
   - `canGenerateVoucher()` 必須返回 false
5. 預覽格數必須與 PDF 一致為六格。

### E. 歷史資料遷移策略

V0.0.7 的難點不是改程式，而是避免把舊資料悄悄弄壞。建議策略如下：

1. Layout 載入時若 amount 超過六格，保留原值，但在頁面顯示明確錯誤。
2. 產出按鈕 disabled，直到使用者手動修正為六格內。
3. 不在後端自動幫使用者把七碼轉六碼。
4. 若有批次匯入或腳本依賴舊規則，需在文件中明確標示 V0.0.7 為 breaking change。

可選項：

- 若使用者強烈需要，可另做一次性 migration script，但不應綁在主流程中自動執行。

### F. 文件與版本紀錄

目標檔案：

- `docs/json_structure.md`
- `docs/api.md`
- `docs/testing_v2.md`
- `dev_data/version_history/`

修改內容：

1. 把 Voucher amount 規則從七格改寫為六格。
2. 說明 V0.0.7 是有意識的 breaking change。
3. 補一份版本紀錄，說明為何 V0.0.6 延後、V0.0.7 才正式切換。

---

## 執行步驟

### Phase 1: 規則落地

1. 調整 payload strict validation 與 router 測試。
2. 更新共享 text config 的 amount 格數與 metadata。

### Phase 2: 生成與預覽收斂

1. 更新 generator 六格寫入邏輯。
2. 更新 frontend utils、preview 與按鈕 disable 條件。

### Phase 3: 歷史資料保護

1. 驗證舊 layout 載入時的錯誤提示與不可產出狀態。
2. 確認不會發生 silent truncation。

### Phase 4: 文件與驗收

1. 更新 docs 與 version history。
2. 跑 targeted tests、frontend tests、build。
3. 做一次手動回歸，確認六格顯示、錯誤提示、PDF 產出一致。

---

## 驗證計畫

### 後端

1. `tests/test_voucher_payload.py`
   - 六格合法
   - 七格非法
   - 小數非法
   - 非數字非法
2. `tests/test_routers_voucher.py`
   - strict generate 對七碼回 422
   - `/api/voucher/text-config` 回傳六格設定
3. `tests/test_voucher_generator.py`
   - 六格 amount 正確寫入 PDF
   - generator 不再假設第七格存在

### 前端

1. `frontend/tests/voucher-text-preview.test.js`
   - six-cell padding
   - excessive amount detection
   - 舊資料超額時 `canGenerateVoucher()` 鎖定
2. `npm test`
3. `npm run build`

### 手動驗證

1. 載入正常六格金額資料，確認預覽與 PDF 位置正確。
2. 載入超過六格的舊 layout，確認頁面顯示錯誤且無法產出。
3. 將錯誤金額改回六格內，確認按鈕恢復可用並可正常下載 PDF。

---

## 風險與對策

### 風險 1: 舊資料突然無法產出

對策：

- 明確標示為 breaking change
- 在 UI 顯示可理解的錯誤提示
- 保留 draft save，不阻止使用者回來修正

### 風險 2: 前後端規則不同步

對策：

- 金額格數一律從共享 config 派生
- 測試同時覆蓋 router、generator、frontend utils

### 風險 3: 開發者只改 PDF、忘了改 preview

對策：

- 把 preview tests 納入必跑清單
- 版本計畫明確把 preview 視為正式交付物，不是附屬品

---

## 驗收定義

以下條件全部成立，V0.0.7 才算完成：

1. 任一七碼 amount 在 strict generate path 都被攔下。
2. 前端預覽只顯示六格，且與 PDF 一致。
3. 歷史七碼 layout 不會被靜默截斷，也不會產出錯誤 PDF。
4. 自動測試與 build 全數通過。
5. 文件已更新，版本紀錄已補齊。

---

## 相關檔案

- `backend/models/voucher_payload.py`
- `backend/engine/voucher_text_config.py`
- `backend/engine/voucher_generator.py`
- `backend/routers/voucher.py`
- `frontend/src/utils/voucher.js`
- `frontend/src/views/VoucherEditorView.vue`
- `tests/test_voucher_payload.py`
- `tests/test_voucher_generator.py`
- `tests/test_routers_voucher.py`
- `frontend/tests/voucher-text-preview.test.js`