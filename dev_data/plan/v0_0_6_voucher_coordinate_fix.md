# 憑證黏貼編輯器 — V0.0.6 修補計畫 (座標校準 + Bug 修復)

**日期**: 2026-03-07
**狀態**: 審閱後修正中
**前置版本**: V0.0.4 (使用者退版後的穩定基礎)

---

## 🎯 問題回顧 (V0.0.4 Post-Mortem)

前一版修正產生嚴重副作用：

1. **「123頁全部串一起」+ 刪除選取刪了整頁**
    - 原因：移除了 `canvasLoading` 和非同步載入保護 (`pendingImageLoads`)，並在 `syncActivePageFromCanvas` 中使用錯誤物件對應，導致 Vue 響應式狀態污染。
    - **教訓**：絕不動 `canvasLoading`、`syncActivePageFromCanvas`、`loadActivePageToCanvas` 的核心機制。

2. **「編號高了、金額不在格子裡、日期寫到用途裡」**
    - 原因：錯誤使用 `fitz.search_for()` 抓「標題文字」座標 (如「憑證編號」四個字)，把使用者的資料對齊了標題，而不是底下的空白輸入格。
    - **教訓**：座標不能靠程式猜測。必須透過視覺化工具由人工校準。

3. **「前端預覽看起來對，但 PDF 還是歪」**
    - 原因：前端 Fabric 文字的外框底部不等於 PyMuPDF 的 baseline。若直接把 PDF baseline 座標原封不動搬到 Canvas，預覽與 PDF 仍會有系統性偏移。
    - **教訓**：前端預覽不能假設自己和 PDF 使用同一套 baseline 計算。必須共用同一份欄位設定，但經過前端專用轉換後再渲染。

---

## 🔍 最新除錯解析 (V0.0.6 實作前診斷)

經過檢視 `voucher_1772899099.pdf` 實際產出結果，確認目前系統「與計畫完全對不上」的核心原因包含：

1. **後端座標設定檔未更新 (`backend/engine/voucher_text_config.py`)**：
   雖然 V0.0.6 已經在下方擬定了「使用者親手校準之最終座標」（例如支付日期: 205, 767），但目前伺服器的設定檔裡依舊殘留著 `payDate: [436, 286]` 等錯誤或舊版的預設值，這導致字根本印不在框裡。
   
2. **前端預覽仍採用 Hardcode，未串接後端單一來源**：
   目前前端 `VoucherEditorView.vue` 將預覽座標寫死（例如 `addText(f.voucherNo, 78, 226)`），這個座標不僅與後端 PDF 印出的不同，也與下方表格的最終計畫不同。這表示前端與後端目前處於「兩套座標」分離的狀況，完全沒有落實「單一設定來源 (SSOT)」。

3. **缺漏版面排版機制未升級**：
   後端 `VoucherGenerator` 尚未升級到支援憑證編號「多行換行寫入 (step=20)」，也沒有自動加上支付金額的「元整」後綴。

結論：**必須徹底將下方表格的 `文字座標真理` 寫入後端 configuration，並開放 API 供前端同步取用，才能根治這個問題。**

---

## 🚧 版本邊界 (V0.0.6 In Scope / Out of Scope)

### 本版要做
1. 修正頁面工具列「刪除選取」按鈕的失焦問題，但**不改動**既有 Canvas 狀態同步主幹。
2. 以使用者校準座標為唯一來源，修正後端 `generate_from_layout` 的文字位置。
3. 新增前端 Canvas 文字預覽層，但採用「安全重繪」方案，不污染 `activePage.images`。
4. 明確保留長用途說明的 textbox / 縮字保護，不再退回單點 `insert_text`。
5. 明確規範前後端統一使用標楷體，前端優先使用後端提供的 TTF。
6. 補 pytest，保證後續改版不再把座標、刪除行為與字體路徑弄壞。

### 本版不做
1. **不在 V0.0.6 直接把整個系統的金額政策從 7 碼全面切到 6 碼。**
2. 不變更 `VoucherFieldsStrict.amount <= 9999999` 的既有契約。
3. 不修改 Draft / Strict payload schema。

### 後續單列計畫：V0.0.7 金額六格全面修正

由於實體紙張只有六個金額空格，這是系統最早的設計失誤，必須另外單列一個**全面性修正計畫**，至少涵蓋：

1. `backend/models/voucher_payload.py` 的 strict amount 上限與驗證規則。
2. `frontend/src/utils/voucher.js` 的超額判定與 UI 提示。
3. `backend/engine/voucher_generator.py` 的 `_insert_amount_cells` 位數與座標。
4. `tests/test_voucher_payload.py`、`tests/test_voucher_generator.py`、`tests/test_routers_voucher.py` 的測試基準。
5. 歷史 layout / 舊資料如何處理七碼輸入的相容策略。

---

## 📏 使用者親手校準之最終座標 (唯一真理)

以下座標均由使用者透過互動式校準工具 (`coord_tool.html`) **親手拖拉**確認。
所有 `pdfX`, `pdfY` 為 PyMuPDF `insert_text` 的 baseline 座標。
字體大小 (`fontSize`) 由使用者逐一指定。

```json
{
   "憑證編號": { "pdfX": 78.5, "pdfY": 255, "fontSize": 16 },
   "預算科目": { "pdfX": 149, "pdfY": 270, "fontSize": 18 },
   "金額_十萬": { "pdfX": 208, "pdfY": 270, "fontSize": 16 },
   "金額_萬":  { "pdfX": 228, "pdfY": 270, "fontSize": 16 },
   "金額_千":  { "pdfX": 250.5, "pdfY": 270, "fontSize": 16 },
   "金額_百":  { "pdfX": 271.5, "pdfY": 270, "fontSize": 16 },
   "金額_十":  { "pdfX": 291, "pdfY": 270, "fontSize": 16 },
   "金額_元":  { "pdfX": 312, "pdfY": 270, "fontSize": 16 },
   "用途說明": { "pdfX": 333, "pdfY": 240, "fontSize": 18 },
   "發票張數": { "pdfX": 473.5, "pdfY": 108, "fontSize": 16 },
   "支付日期": { "pdfX": 205, "pdfY": 785, "fontSize": 20 },
   "支付金額": { "pdfX": 314, "pdfY": 785, "fontSize": 20 }
}
```

### 座標摘要表

| 欄位 | X | Y | 字體大小 | 備註 |
|------|-----|-----|---------|------|
| 憑證編號 | 78.5 | 255 | 16 | 多行時向下 step=20 |
| 預算科目 | 149 | 270 | 18 | 最多顯示 3 字 |
| 金額 | 208~312 | 270 | 16 | 本版只把這些視為**校準點**，不在此版改 digit policy |
| 用途說明 | 333 | 240 | 18 | 需保留 textbox / 縮字保護 |
| 發票張數 | 473.5 | 108 | 16 | 填入「黏貼單據 ( ) 張」中間 |
| 支付日期 | 205 | 785 | 20 | 格式：`114/11/28` (對齊底部框線) |
| 支付金額 | 314 | 785 | 20 | 格式：`4,607元整` (對齊底部框線) |

---

## 🛠️ 修改計畫

### 修改一：前端 `VoucherEditorView.vue`

> [!CAUTION]
> 絕不動到 `canvasLoading`、`syncActivePageFromCanvas`、`loadActivePageToCanvas` 等核心狀態管理機制。

#### A. 修復「刪除選取」按鈕失焦 Bug
- **位置**：頁面右上角工具列的「刪除選取」按鈕。
- **改法**：`@click` → `@mousedown.prevent`
- **原理**：`click` 在滑鼠放開時觸發並轉移焦點。`mousedown.prevent` 阻止瀏覽器將 Focus 從 Canvas 拿走，讓 Fabric.js 保持 `getActiveObjects()`。
- **邊界**：
   1. 只修正頁面工具列按鈕事件。
   2. 不改 `removeSelectedOnCanvas()` 目前語義：它仍然只刪除「當前頁 Canvas 上被選中的 invoice 物件」，不刪側邊欄資料、不刪整頁。

#### B. 新增 Canvas 文字疊加函數 `drawTextFieldsOnCanvas`
- **資料來源**：前後端共用同一份 `TEXT_FIELD_CONFIG` 設定，PDF baseline 座標為唯一真理。
- **實作原則**：
   1. 前端預覽不能直接把 PDF baseline 座標當 Fabric 座標使用。
   2. 必須新增前端專用轉換函式，例如 `pdfBaselineToCanvasPoint(config, text)`，把 PDF baseline 轉成 Fabric 可用的 top/left 或 bottom/left 對齊值。
   3. 轉換時要以**已載入的 KaiU 字型實測文字高度**為準，不用 magic number 硬猜。
- **字型要求**：
   1. 前端優先使用後端 `/api/voucher/fonts/kaiu.ttf` 提供的標楷體。
   2. 若字型載入失敗，只能 `console.warn` 並以 fallback font 畫暫時預覽；不得阻斷編輯器。
   3. 只有在 KaiU 可用時，前端預覽才可宣稱與 PDF 接近一致。
- **重繪安全策略**：
   1. 所有預覽文字物件必須帶 `data.kind = 'text_preview'`。
   2. 每次 `drawTextFieldsOnCanvas()` 開始前，先刪除既有 `text_preview` 物件，再重畫，避免重影與「整頁串一起」的假象。
   3. 預覽文字必須設定 `selectable: false`, `evented: false`, `excludeFromExport: true`。
   4. `syncActivePageFromCanvas()` 必須維持只同步 `kind === 'invoice'` 的物件，不得把預覽文字寫回 `activePage.images`。
- **呼叫時機**：
   1. 在 `loadActivePageToCanvas()` 末尾，於背景與 invoice objects 載入完成後呼叫。
   2. 監聽 `activePage.fields` 深層變化與 `activePageIndex` 切換時重繪。
   3. 必須新增「載入完成 barrier」：只有在當前 page token 下，背景完成且所有 invoice 的 onload/onerror 都已 settle，才允許呼叫 `drawTextFieldsOnCanvas()`。
   4. 若 page token 已切換，舊 token 的任何 onload/onerror 回呼都必須直接丟棄，不得觸發重繪。
- **格式規則**：
   1. 憑證編號多行時，以 `y=255` 為起點，每行 `+20`。
   2. 支付金額格式：`4,607元整`。
   3. 日期轉民國年：`114/11/28`。
   4. 文字顏色：`#1e3a8a` (深藍)。

#### C. 憑證編號格式化
- 修改 `recalculateVoucherNumbers`：原本產生 `D-16-01~04`，改為列舉式：

```text
D-16-01
D-16-02
D-16-03
D-16-04
```

- **注意**：此變更僅限 Voucher Editor / Voucher PDF 的 `voucherNo` 顯示與輸出格式，不應順手更動其他匯出流程或資料模型。

#### D. 保護已填寫內容
- 確保 `recalculatePageFields` 的 `onlyFillEmpty` 邏輯只在欄位完全空白時才填入，不會清空使用者已手動編輯的資料。
- **具體要求**：
   1. `budgetItem`、`amount`、`purpose`、`payDate` 都只能在空白時回填。
   2. 若 `isManuallyEdited === true`，不得覆蓋 `purpose`。
   3. 不可因重繪 Canvas 預覽而觸發欄位回算，避免把已填資料洗掉。

### 修改二：後端 `voucher_generator.py`

#### A. 座標全面更新 (`generate_from_layout`)
將 `generate_from_layout` 中的文字寫入邏輯，改為以本次使用者校準座標為主。

```python
# 1. 憑證編號 (多行，step=20)
voucher_no = str(fields.get("voucherNo", ""))
if voucher_no:
      lines = voucher_no.replace('、', '\n').split('\n')
      vy = 255
      for line in lines:
            self._insert_text(page, (78.5, vy), line, fontsize=16)
            vy += 20

# 2. 預算科目
self._insert_text(page, (149, 270), budget[:3], fontsize=18)

# 3. 金額
# 本版只整理座標來源，不在 V0.0.6 直接切換整個 amount digit policy

# 4. 用途說明
self._insert_purpose(page, purpose)

# 5. 發票張數
self._insert_text(page, (473.5, 92), receiptCount, fontsize=16)

# 6. 支付日期
self._insert_text(page, (205, 767), roc_date, fontsize=20)

# 7. 支付金額
self._insert_text(page, (314, 767), f"{amount:,}元整", fontsize=20)
```

#### B. `_insert_amount_cells` 的處理原則
- **本版先不動 `_insert_amount_cells` 的 digit policy。**
- 只允許在不破壞現有 7 碼契約的前提下，整理座標常數與函式結構。
- 真正的 6 碼全面修正，移至 V0.0.7 單獨處理。

#### C. `_insert_purpose` 保留，但更新為校準版
- **審閱後撤回「移除 `_insert_purpose`」這項做法。**
- 長用途說明仍需要 textbox / 自動縮字保護，因此 `_insert_purpose` 不能刪。
- 正確作法是：
   1. 保留 `_insert_purpose`。
   2. 把它的 `Rect` 依本次校準結果重新定義。
   3. 若需要，將預設字級調整為本版校準字級，但保留 overflow 保護與 warning log。

#### D. 字體防護
- 在 `__init__` 中對 `font_path` 做絕對路徑檢查，若 `kaiu.ttf` 不存在則 log warning。
- 若 `font_path` 存在，前後端均以 KaiU / 標楷體為準，不允許 PDF 與 Canvas 使用不同字型基準。

### 修改三：前後端座標校準統一方式

#### A. 單一設定來源
- 建立單一的欄位座標設定物件，例如 `TEXT_FIELD_CONFIG`。
- 後端直接使用其中的 PDF baseline 座標。
- 前端從同一份設定衍生出 preview 配置，避免兩邊手抄兩份魔法數字。
- **落點規範**：
   1. 設定檔放在 `backend/engine/voucher_text_config.py`（後端唯一真實來源）。
   2. 前端透過 Voucher API 取得同一份設定（例如新增 `GET /api/voucher/text-config`），禁止前端硬編第二份常數。
   3. 如暫不新增端點，需在計畫內標註為暫時方案，且後續必須收斂到單一來源。

#### B. 前端預覽不是校準真理
- 真正驗收以 PDF 為準。
- Canvas 預覽只作為接近最終結果的輔助視圖，不反過來主導後端 PDF 座標。
- 若前後端對不齊，先修 preview baseline 轉換，不回頭改使用者已確認的 PDF baseline 座標。

---

## ✅ 驗證計畫

### 自動驗證
1. 前端 `npm run dev` 無編譯錯誤。
2. 後端 `uvicorn` 無啟動錯誤。
3. 後端 `pytest` 新增 / 更新以下保護：
    - `tests/test_voucher_generator.py`
       - 驗證 `generate_from_layout()` 使用新的校準座標寫入憑證編號、科目、用途、張數、日期、支付金額。
       - 驗證 `_insert_purpose` 仍存在且可處理長文字，不會因 V0.0.6 被移除。
       - 驗證字型檔不存在時只 log warning，不直接炸掉建構。
    - `tests/test_routers_voucher.py`
       - 驗證 `/api/voucher/fonts/kaiu.ttf` 仍可提供 TTF，作為前端預覽字型來源。
4. 前端驗證至少補一層（擇一，不得全省略）：
   - `frontend/tests/` 新增最小測試，覆蓋：
     1. `@mousedown.prevent` 事件後 Canvas active selection 仍存在。
     2. `drawTextFieldsOnCanvas()` 連續觸發時，不會累積重複 `text_preview` 物件。
     3. page token 切換時，舊 token 回呼不會覆寫新頁狀態。
   - 若現階段不建前端測試，必須提供手動驗證錄影或可重現步驟證據，並列入 PR 驗收附件。

### 已知限制 (Known Limitation)
1. V0.0.6 仍維持 7 碼金額契約（`amount <= 9999999`），模板實體六格問題尚未在本版處理。
2. 驗收若出現 7 碼金額超位，應標記為「已知限制」，並由 V0.0.7 的六格全面修正計畫解決。

### 手動驗證
1. 開啟瀏覽器 → 進入憑證編輯器 → 拉入發票。
2. 確認 Canvas 預覽上的文字 (編號、科目、金額、用途、日期) 落在正確格子內。
3. 點擊「刪除選取」按鈕 → 確認能刪除單張發票而非整頁。
4. 點擊「產出 PDF」→ 開啟 PDF → 確認所有文字位置與校準工具 (`coord_tool.html`) 中拖拉的結果一致。
5. 關閉 KaiU 字型或模擬字型載入失敗 → 確認編輯器仍能開啟，僅發出 warning，不破壞主流程。

---

## 📎 相關參考檔案
- 校準工具：`dev_data/coord_tool.html`
- 參考成品：`dev_data/燕巢小宏遠_已核章.pdf`
- 空白範本：`dev_data/憑證黏貼用紙.pdf`
- 座標萃取結果：`ref_text_positions.txt`
