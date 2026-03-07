# 憑證黏貼編輯器 — Beta 0.0.2 執行備忘（審閱後）

> [!NOTE]
> 本備忘內容已合併回 `v0_0_2_voucher_pdf_text_overlay.md`。
> 後續請以原始 0.0.2 文件為單一實作來源；本檔僅保留作為審閱紀錄。

日期：2026-03-07  
狀態：可開工，但需先套用以下修正，避免照原計畫實作後返工。

---

## 審閱結論

原計畫抓到的主因是正確的：

1. `backend/engine/voucher_generator.py` 已經會把 `voucherNo`、`budgetItem`、`amount`、`purpose`、`receiptCount`、`payDate` 寫進 PDF。
2. `frontend/src/views/VoucherEditorView.vue` 的 `generatePdf()` 目前只顯示成功訊息，沒有真正下載檔案。
3. `frontend/src/views/ProjectDetailView.vue` 仍保留舊版「快速產生黏貼紙」入口，會讓使用者下載到不含欄位文字的舊版 PDF。

因此 0.0.2 的方向成立，可以直接做。

---

## 施工前必修正

### 1. 下載流程不能再依賴 `response.data.filename`

一旦 `backend/routers/voucher.py` 的 `/generate` 改回 `FileResponse`，前端拿到的就會是 blob，不再是：

```json
{ "filename": "...", "pdfUrl": "..." }
```

所以 `generatePdf()` 必須同步改成：

1. `frontend/src/services/api.js` 對 `generateVoucherFromLayout()` 設定 `responseType: 'blob'`
2. `frontend/src/views/VoucherEditorView.vue` 以 `Blob` 建立下載連結
3. 檔名優先讀 `Content-Disposition`，沒有再 fallback 成 `Voucher_${projectId}.pdf`

不要保留 `alert(response.data.filename)` 這條路徑。

### 2. 前端字型 URL 不要硬編 `http://localhost:8000`

計畫中的 `FontFace('KaiU', 'url(http://localhost:8000/api/voucher/fonts/kaiu.ttf)')` 只適合本機固定環境。這個專案已經把 axios base URL 集中在 `frontend/src/services/api.js`，前端字型載入也應該跟同一來源走。

建議寫法：

```javascript
const fontUrl = `${api.defaults?.baseURL || window.location.origin}/api/voucher/fonts/kaiu.ttf`
```

這樣才不會在改 port、反向代理或部署時失效。

### 3. `toRocDate()` 目前不存在，需補 helper

原計畫的 `drawTextFieldsOnCanvas()` 使用了 `toRocDate(f.payDate)`，但目前前端沒有這個函式。若直接照計畫貼碼，`VoucherEditorView.vue` 會在執行時噴錯。

需要先補一個前端 helper，邏輯應和後端 `VoucherGenerator._to_roc_date()` 對齊：

1. 只接受已正規化的 ISO 日期
2. 轉成 `YYY/MM/DD`
3. 無效日期回空字串

### 4. 預覽字型載入失敗時不能阻斷編輯器

`onMounted()` 現在已經負責載入 template、layout、project detail。字型預載應該是「加值功能」，不是阻塞初始化的硬依賴。

建議：

1. `FontFace.load()` 用 `try/catch`
2. 失敗時只 `console.warn`
3. 仍然畫出文字預覽，先退回預設字型

不然一個字型路由失敗，就會把整個編輯器體驗拖垮。

---

## 建議補強

### 1. 新增最小回歸測試

目前專案有後端 pytest，但沒有現成的 Vue component test 基礎設施。0.0.2 最少要補兩類：

1. `backend` 路由測試：`/api/voucher/{project_id}/generate` 回傳 PDF response
2. `backend` 路由測試：`/api/voucher/fonts/kaiu.ttf` 可回傳字型檔

前端下載與 canvas 預覽先以手動驗證為主即可。

### 2. 舊版 API 可暫留，但 UI 入口必須移除

`frontend/src/views/ProjectDetailView.vue` 的舊按鈕必須移除。至於 `frontend/src/services/api.js` 的 `generateVoucherPdf()` 與 `backend/routers/projects.py` 的舊路由，可以先保留一版，等 0.0.2 驗證完成再決定是否正式下線。

這樣可以降低一次刪太多造成的回歸風險。

### 3. 文字預覽需在載入背景與發票後重畫

`drawTextFieldsOnCanvas()` 的呼叫點除了 watch `activePage.fields`，還要放在 `loadActivePageToCanvas()` 完成後。原因是 `fabricCanvas.clear()` 會把上一頁的預覽字一起清掉。

這點原計畫有提，但實作時要確保順序正確：

1. clear canvas
2. 放背景
3. 放 invoice objects
4. 最後畫 `text_preview`

這樣文字才會在最上層可見。

---

## 建議實作順序

1. `backend/routers/voucher.py`
   - `/generate` 改回 `FileResponse`
   - 新增 `/fonts/kaiu.ttf`
2. `frontend/src/services/api.js`
   - `generateVoucherFromLayout()` 改成 blob response
3. `frontend/src/views/VoucherEditorView.vue`
   - `generatePdf()` 真正下載
   - 補 `toRocDate()`
   - 預載字型
   - 補 `drawTextFieldsOnCanvas()` 與 watcher
4. `frontend/src/views/ProjectDetailView.vue`
   - 移除舊版快速下載按鈕與 handler
5. `tests`
   - 補 router tests
6. 驗證
   - 後端 pytest
   - 前端 build
   - 手動下載與畫面比對

---

## 驗證清單

### 手動驗證

1. 在編輯器修改 `voucherNo`、`budgetItem`、`amount`、`purpose`、`payDate`、`receiptCount`
2. Canvas 上立即看到文字預覽
3. 點「產出 PDF」後，瀏覽器直接下載 PDF
4. 下載的 PDF 內文與 canvas 預覽位置一致
5. 返回專案頁後，已無舊版「快速產生黏貼紙」按鈕

### 建議指令

```powershell
python -m pytest tests -q
```

```powershell
Set-Location frontend
npm run build
```

---

## 開工判定

可以開工。

但施工時應以這份備忘搭配原始 `v0_0_2_voucher_pdf_text_overlay.md` 一起執行，不要直接照原文逐段貼碼。