# 憑證黏貼編輯器 — V34.2 可直接落地實作清單

> [!WARNING]
> 本文件已混入 V34.3 審閱補丁與歷程註記，不再建議作為唯一實作來源。
> 請改用：`dev_data/plan/voucher_editor_plan/v34-3_voucher_editor_executable.md`

**日期**: 2026-03-06
**前置文件**: v34.1 → 審閱回饋 4 點 → 自我審計
**差異**: 僅修改 V34.1 的 4 處錯誤/不完整段落 + 自我審計發現的 2 處遺漏。V33 與 V34 原文保留不改。

---

## 📋 V34.1 ➜ V34.2 變更追蹤

| # | V34.1 問題 | V34.2 修正 |
|:---|:---|:---|
| ① | `nextPayDate` 回存原始字串 `raw`，但後端 `datetime.fromisoformat()` 會拒絕 `YYYY/MM/DD` 和 `YYYYMMDD` | **ISO 正規化**：所有日期在回寫 `page.fields.payDate` 前，一律轉為 `YYYY-MM-DD` 格式 |
| ② | 金額多路徑讀取寫「照舊」，實際 L274 仍只讀 `summary?.total` | **明確列出**必改的三路徑讀取程式碼 |
| ③ | `getProjects()` 全量拉清單讀 metadata，大量專案時造成延遲 | **新增後端端點** `GET /projects/{id}/detail` 回傳含 `metadata` 的完整專案資料 |
| ④ | 文末宣稱「所有風險皆排除」過早 | **刪除**，替換為風險殘餘聲明 |
| ⑤ (自審) | `removeSelectedOnCanvas` (L663) 只呼叫 `recalculatePageFields`，遺漏 `recalculateVoucherNumbers` | **補上呼叫** |
| ⑥ (自審) | 現有 watch (L758) 的空頁面不清 voucherNo | **加 `else { page.fields.voucherNo = '' }`** |

---

## 修正 ①：日期 ISO 正規化回寫

**問題鏈**：  
前端 `parseDateString("20240301")` → 認為合法 → 回存 `"20240301"` → 送往後端 → `datetime.fromisoformat("20240301")` → **422 Error**

**解法**：在 `utils/voucher.js` 新增 `normalizeDateToISO`，在回寫 payDate 前一律正規化。

### [MODIFY] `frontend/src/utils/voucher.js`

```javascript
// 新增兩個公開函式
export function parseDateString(d) {
  if (!d) return NaN
  let clean = String(d).replace(/\//g, '-')
  if (/^\d{8}$/.test(clean))
    return Date.parse(`${clean.slice(0, 4)}-${clean.slice(4, 6)}-${clean.slice(6, 8)}`)
  return Date.parse(clean)
}

/**
 * 將任意合法日期字串正規化為 YYYY-MM-DD (ISO 8601)
 * 目的：確保送往後端的 payDate 能通過 datetime.fromisoformat() 驗證
 * V34.3 修正：使用 UTC 系列函式避免時區偏移
 */
export function normalizeDateToISO(d) {
  const ts = parseDateString(d)
  if (Number.isNaN(ts)) return ''
  const dt = new Date(ts)
  const yyyy = dt.getUTCFullYear()
  const mm = String(dt.getUTCMonth() + 1).padStart(2, '0')
  const dd = String(dt.getUTCDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}
```

### [MODIFY] `frontend/src/utils/voucher.js` — `hasInvalidDate`

```javascript
export function hasInvalidDate(pages = []) {
  return pages.some(page => {
    const payDate = page?.fields?.payDate
    const hasImages = (page.images || []).length > 0
    if (!payDate && hasImages) return true
    if (!payDate) return false
    return Number.isNaN(parseDateString(payDate))  // 取代 Date.parse
  })
}
```

### [MODIFY] `frontend/src/views/VoucherEditorView.vue` — `isCurrentPageDateInvalid`

```javascript
import { ..., parseDateString, normalizeDateToISO } from '../utils/voucher'

const isCurrentPageDateInvalid = computed(() => {
  const p = activePage.value
  if (!p) return false
  const payDate = p.fields?.payDate
  const hasImages = (p.images || []).length > 0
  if (!payDate && hasImages) return true
  if (!payDate) return false
  return Number.isNaN(parseDateString(payDate))  // 取代 Date.parse
})
```

### [MODIFY] `frontend/src/views/VoucherEditorView.vue` — `recalculatePageFields` 日期區塊

```javascript
  // === D.28: 時間戳排序 + ISO 正規化回寫 ===
  const validDateObjects = pageInvoices
    .map(inv => inv.result?.date || inv.result?.header?.date || '')
    .map(d => ({ raw: d, ts: parseDateString(d) }))
    .filter(obj => !Number.isNaN(obj.ts))
    .sort((a, b) => a.ts - b.ts)
  // 🔑 關鍵：用 normalizeDateToISO 而非 raw，確保後端 fromisoformat 通過
  const nextPayDate = validDateObjects.length
    ? normalizeDateToISO(validDateObjects[validDateObjects.length - 1].raw)
    : ''
  if (!onlyFillEmpty || !String(page.fields.payDate || '').trim()) {
    page.fields.payDate = nextPayDate
  }
```

---

## 修正 ②：金額多路徑讀取（明確程式碼）

**必改位置**：`VoucherEditorView.vue` L270-278

**現況** (有 Bug)：
```javascript
  const total = result.summary?.total ?? 0  // ← 僅讀電子發票格式
```

**修改為**：
```javascript
  // === D.25: 金額加總（三路徑相容）===
  let totalAmount = 0
  for (const inv of pageInvoices) {
    const r = inv.result || {}
    // VLM 普通發票: total_amount | 電子發票: summary.total | 手寫收據: total
    const raw = r.total_amount ?? r.summary?.total ?? r.total ?? 0
    const amount = parseFloat(String(raw))
    if (!Number.isNaN(amount)) totalAmount += amount
  }
  // 取整數（台灣憑證不允許小數金額）
  const nextAmount = totalAmount ? String(Math.round(totalAmount)) : ''
```

> [!IMPORTANT]
> 這是 V34.1 中「照舊」被漏掉的程式碼。必須在實作時替換 L270-278。

---

## 修正 ③：後端新增專案詳情端點（替代 getProjects 全量拉）

### [MODIFY] `backend/routers/projects.py` — 新增端點

```python
@router.get("/{project_id}/detail")
async def get_project_detail(project_id: str, engine: Engine = Depends(get_engine)):
    """取得專案完整資料（含 metadata），供 Voucher Editor 等元件讀取。"""
    project = await engine.project_repo.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
```

### [MODIFY] `frontend/src/services/api.js` — 新增 client 方法

```javascript
  getProjectDetail(projectId) {
    return api.get(`/api/projects/${projectId}/detail`)
  },
```

### [MODIFY] `frontend/src/views/VoucherEditorView.vue` — onMounted

```javascript
// V34.3 修正：getProjectDetail 失敗不阻斷、budgetItem → budgetExpense
onMounted(async () => {
  try {
    const [templateResp, layoutResp] = await Promise.all([
      api.getVoucherTemplate(projectId),
      api.getVoucherLayout(projectId),
    ])

    // Fix #4: 取 metadata（可降級，失敗不阻斷編輯器）
    let defaultBudget = ''
    try {
      const projectResp = await api.getProjectDetail(projectId)
      const meta = projectResp.data?.metadata || {}
      defaultBudget = meta.budgetExpense?.[0]?.name || ''  // V34.3: 正確 key
    } catch (e) {
      console.warn('getProjectDetail failed, budgetItem will be empty', e)
    }

    templatePng.value = templateResp.data.templatePng || ''
    invoices.value = templateResp.data.invoices || []

    if (layoutResp.data?.pages?.length) {
      pages.value = layoutResp.data.pages.map(p => ({
        ...p,
        fields: {
          voucherNo: '', budgetItem: defaultBudget, amount: '', purpose: '',
          receiptCount: '0', payDate: '', isManuallyEdited: false,
          ...(p.fields || {})  // 已存欄位優先覆蓋預設值
        }
      }))
      globalPrefix.value = layoutResp.data.globalPrefix || globalPrefix.value
      startIndex.value = layoutResp.data.startIndex || startIndex.value
    } else {
      pages.value[0].fields.budgetItem = defaultBudget
    }
  } catch (error) {
    console.error('voucher init failed', error)
  } finally {
    ready.value = true
  }

  await nextTick()
  initCanvas()
  await loadActivePageToCanvas()
  recalculatePageFields(activePage.value, { onlyFillEmpty: true })
  recalculateVoucherNumbers()  // Fix #3: 初始載入也要跑一次

  autosaveTimer = window.setInterval(saveLayout, 30000)
})
```

---

## 修正 ⑤⑥ (自審)：recalculateVoucherNumbers 呼叫點完整清單

### [NEW] `recalculateVoucherNumbers` 函式

```javascript
const recalculateVoucherNumbers = () => {
  let runningIndex = startIndex.value
  pages.value.forEach(page => {
    const count = (page.images || []).length
    page.fields.receiptCount = String(count)  // Fix #5: 跨頁同步
    if (count > 0) {
      const from = String(runningIndex).padStart(2, '0')
      const to = String(runningIndex + count - 1).padStart(2, '0')
      page.fields.voucherNo = count > 1
        ? `${globalPrefix.value}-${from}~${to}`
        : `${globalPrefix.value}-${from}`
      runningIndex += count
    } else {
      page.fields.voucherNo = ''  // ⑥ 空頁清除編號
    }
  })
}
```

### 7 個完整呼叫點（V34.3 修正：+addPage）

| # | 位置 | 時機 | 現況 |
|:---|:---|:---|:---|
| 1 | `watch([globalPrefix, startIndex], recalculateVoucherNumbers)` | 使用者改 Prefix/StartIndex | 取代原有 watch 匿名函式 |
| 2 | `_doAddInvoice` 末尾 (L351 之後) | 新增發票 | **新增** |
| 3 | `removeImage` 末尾 (L365 之後) | 側邊欄移除發票 | **新增** |
| 4 | `removeSelectedOnCanvas` 末尾 (L665 之後) | 鍵盤 Delete 刪除發票 | **新增** ⑤ |
| 5 | `onMounted` 最末 (recalculatePageFields 之後) | 初始載入 | **新增** |
| 6 | `addPage` 末尾 (L248 之後) | 新增空頁面 | **新增**（V34.3 發現 E） |
| 7 | `switchPage` 之後不需要 | 切頁只切 activePage，不影響全局編號 | 不適用 ✓ |

---

## 用途欄位修正 (Fix #6 D.27)

**現況** (L293-307)：使用 `item.category` — 這部分是對的。

**V34.2 加入的 Fallback**：
```javascript
  if (!page.fields.isManuallyEdited) {
    const descriptions = new Set()
    for (const inv of pageInvoices) {
      const items = (inv.result?.items) || []
      for (const item of items) {
        // category 優先 → description → name
        const desc = item.category || item.description || item.name || ''
        if (desc) descriptions.add(desc)
      }
    }
    const nextPurpose = [...descriptions].join('、')
    if (!onlyFillEmpty || !String(page.fields.purpose || '').trim()) {
      page.fields.purpose = nextPurpose
    }
  }
```

---

## 其餘 Fixes（V34.3 更新）

| Fix | 內容 | 狀態 |
|:---|:---|:---|
| **#9** | `goBack` → `async` + `await saveLayout()` | 與 V34.1 一致 ✓ |
| **#10** | `generatePdf` → `.filter(p => ...)` 空頁過濾 **+ `.map()` 日期正規化**（V34.3 發現 A） | **已更新**，見發現 A |
| **#11** | `simulateLayout` → `if (scaledW > maxWidth) return Infinity` | 與 V34.1 一致 ✓ |

---

## 修改清單總覽

| 檔案 | 修改內容 |
|:---|:---|
| `frontend/src/utils/voucher.js` | 新增 `parseDateString`、`normalizeDateToISO`（UTC 版）；修改 `hasInvalidDate`；修改 `simulateLayout` |
| `frontend/src/views/VoucherEditorView.vue` | 修改 `recalculatePageFields` (金額3路徑 + 日期ISO正規化 + 用途category fallback)；新增 `recalculateVoucherNumbers` + **7呼叫點**（含addPage）；修改 `isCurrentPageDateInvalid`；修改 `onMounted`（getProjectDetail可降級 + budgetExpense）；修改 `goBack`；修改 `generatePdf`（日期正規化 + 空頁過濾）；修改 import |
| `frontend/src/services/api.js` | 新增 `getProjectDetail` |
| `backend/routers/projects.py` | 新增 `GET /{project_id}/detail` 端點 |

---

## ⚠️ 風險殘餘聲明（V34.3 更新）

1. ~~**`budgetItem` key 名稱**~~ → **已修正**（V34.3 發現 D）：直接使用 `meta.budgetExpense?.[0]?.name`。
2. ~~**`datetime.fromisoformat` 的時區**~~ → **已修正**（V34.3 發現 B）：`normalizeDateToISO` 改用 `getUTCFullYear/getUTCMonth/getUTCDate`。
3. **Canvas 記憶體回收**：Fabric.js v7 的 `dispose()` 行為尚未確認。建議 `onBeforeUnmount` 加 `canvas.dispose()`，但非本次修正範圍。

---

## 🔴 V34.2 深度審閱發現（V34.3 補丁）

以下 8 項問題由逐行交叉比對原始碼後發現，必須在實作時一併處理。

### 發現 A：`generatePdf` 送出前缺少日期正規化

**嚴重度**：🔴 高  
**問題**：修正 ① 只在 `recalculatePageFields` 自動回填路徑使用 `normalizeDateToISO`，但使用者可直接在 `<input>` 手打 `2024/03/01` 或 `20240301`。`hasInvalidDate` 改用 `parseDateString` 後會認為合法（不亮紅字、可按「產出 PDF」），但送往後端的 `payDate` 仍是原始字串 → 後端 `datetime.fromisoformat()` 拒絕 → **422 Error**。  
**修正**：在 `generatePdf` 送出前，對所有頁面的 `payDate` 強制正規化。

```javascript
// [MODIFY] generatePdf (L386-L396)
const generatePdf = async () => {
  try {
    syncActivePageFromCanvas()
    ensurePageNumbers()
    // Fix #10: 過濾空頁 + Fix A: 日期正規化
    const submitPages = pages.value
      .filter(p => (p.images || []).length > 0)
      .map(p => ({
        ...p,
        fields: {
          ...p.fields,
          payDate: normalizeDateToISO(p.fields.payDate)  // 確保後端 fromisoformat 通過
        }
      }))
    const submitPayload = {
      globalPrefix: globalPrefix.value,
      startIndex: startIndex.value,
      pages: submitPages
    }
    const response = await api.generateVoucherFromLayout(projectId, submitPayload)
    alert(`PDF 產出成功: ${response.data.filename}`)
  } catch (error) {
    console.error('generate failed', error)
    alert('產出失敗，請檢查欄位格式與發票內容')
  }
}
```

### 發現 B：`normalizeDateToISO` 時區偏移可能導致日期差一天

**嚴重度**：🟡 中  
**問題**：`Date.parse('2024-03-01')` 在部分瀏覽器回傳 UTC 午夜，`new Date(ts).getDate()` 使用本地時區（UTC+8），若 ts 恰好在 UTC 午夜 → 本地拿到 3/1 沒問題。但 `Date.parse('20240301')` 經轉換為 `Date.parse('2024-03-01')` 同理。然而若遇到 UTC-N 時區的使用者，`getDate()` 可能差一天。  
**修正**：改用 `getUTCFullYear / getUTCMonth / getUTCDate`，消除時區依賴。

```javascript
// [MODIFY] normalizeDateToISO
export function normalizeDateToISO(d) {
  const ts = parseDateString(d)
  if (Number.isNaN(ts)) return ''
  const dt = new Date(ts)
  const yyyy = dt.getUTCFullYear()
  const mm = String(dt.getUTCMonth() + 1).padStart(2, '0')
  const dd = String(dt.getUTCDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}
```

### 發現 C：`getProjectDetail` 失敗會阻斷整個編輯器初始化

**嚴重度**：🟡 中  
**問題**：`onMounted` 用 `Promise.all` 綁定 `getVoucherTemplate` + `getVoucherLayout` + `getProjectDetail`（修正 ③）。若新端點 `/detail` 暫時不可用或網路錯誤，會連帶放棄已成功的 template/layout → 整個編輯器白屏。  
**修正**：使用 `Promise.allSettled` 或將 `getProjectDetail` 分離為可降級呼叫。

```javascript
// [MODIFY] onMounted — 改為可降級
onMounted(async () => {
  try {
    const [templateResp, layoutResp] = await Promise.all([
      api.getVoucherTemplate(projectId),
      api.getVoucherLayout(projectId),
    ])
    templatePng.value = templateResp.data.templatePng || ''
    invoices.value = templateResp.data.invoices || []

    // Fix #4: 取 metadata（可降級，失敗不阻斷）
    let defaultBudget = ''
    try {
      const projectResp = await api.getProjectDetail(projectId)
      const meta = projectResp.data?.metadata || {}
      defaultBudget = meta.budgetExpense?.[0]?.name || ''
    } catch (e) {
      console.warn('getProjectDetail failed, budgetItem will be empty', e)
    }

    if (layoutResp.data?.pages?.length) {
      pages.value = layoutResp.data.pages.map(p => ({
        ...p,
        fields: {
          voucherNo: '', budgetItem: defaultBudget, amount: '', purpose: '',
          receiptCount: '0', payDate: '', isManuallyEdited: false,
          ...(p.fields || {})
        }
      }))
      globalPrefix.value = layoutResp.data.globalPrefix || globalPrefix.value
      startIndex.value = layoutResp.data.startIndex || startIndex.value
    } else {
      pages.value[0].fields.budgetItem = defaultBudget
    }
  } catch (error) {
    console.error('voucher init failed', error)
  } finally {
    ready.value = true
  }
  // ... 以下 initCanvas / recalculate 區塊不變
})
```

### 發現 D：`budgetItem` 不存在於 metadata，正確 key 是 `budgetExpense`

**嚴重度**：🟡 中  
**問題**：`EditProjectView.vue` 的 `updateProject` 送出的 metadata 裡只有 `budgetExpense`（陣列，格式 `[{name, qty, price, total, purpose}]`），**沒有** `budgetItem` key。計畫寫 `meta.budgetItem || meta.budgetExpense?.[0]?.name` 雖然有 fallback，但第一個分支 `meta.budgetItem` 永遠是 `undefined`，屬死碼。  
**修正**：直接用 `meta.budgetExpense?.[0]?.name || ''`，刪除 `meta.budgetItem`。

```javascript
// 修正前
const defaultBudget = meta.budgetItem || meta.budgetExpense?.[0]?.name || ''
// 修正後
const defaultBudget = meta.budgetExpense?.[0]?.name || ''
```

### 發現 E：`addPage` 未呼叫 `recalculateVoucherNumbers`

**嚴重度**：🟢 低  
**問題**：`addPage` (L233) 新增空頁面後，不會觸發 watch（因為 `globalPrefix` 和 `startIndex` 都沒變），也沒有呼叫 `recalculateVoucherNumbers`。新頁的 `voucherNo` 會是空字串，這雖然「正確」（空頁不應有編號），但 `receiptCount` 不會被歸零同步。  
**修正**：在 `addPage` 末尾加 `recalculateVoucherNumbers()`。

### 發現 F：`runAutoLayout` 未呼叫任何 recalculate

**嚴重度**：🟢 低  
**問題**：`runAutoLayout` (L568) 重設 `activePage.value.images` 後，不呼叫 `recalculatePageFields` 也不呼叫 `recalculateVoucherNumbers`。images 的位置改了但 `receiptCount` 不會受影響（長度沒變），所以實際影響不大。但若未來加入位置相關計算，會是隱患。  
**修正**：語意上可加 `recalculatePageFields(activePage.value, { onlyFillEmpty: true })`，但目前非必要。列為建議改善。

### 發現 G：呼叫點表格遺漏 `addPage`

**嚴重度**：🟢 低  
**問題**：v34-2 的「6 個完整呼叫點」表格少了 `addPage`（雖然空頁的 voucherNo 應該為空，但呼叫能確保 receiptCount 一致性）。  
**修正**：表格加第 7 行 `addPage`。

| # | 位置 | 時機 | 現況 |
|:---|:---|:---|:---|
| 7 | `addPage` 末尾 (L248 之後) | 新增空頁面 | **新增** |

### 發現 H：後端 `generate_from_layout` 已有空頁跳過機制

**嚴重度**：🟢 資訊  
**問題**：`voucher_generator.py` L135 已有 `if not images: continue`，空頁會被後端跳過不渲染。因此 Fix #10 的前端空頁過濾其實是**雙保險**（前端擋 + 後端擋）。但 `VoucherFieldsStrict` 要求 `voucherNo min_length=1`、`amount min_length=1`、`payDate min_length=1`，空頁面這些欄位都是空字串 → Pydantic 驗證會 422。  
**結論**：Fix #10 的前端過濾仍然**必要**，因為 Strict model 驗證發生在 generator 之前。v34-2 原文正確。

---

## 📝 V34.3 完整呼叫點修正表格

| # | 位置 | 時機 | 動作 |
|:---|:---|:---|:---|
| 1 | `watch([globalPrefix, startIndex], recalculateVoucherNumbers)` | Prefix/StartIndex 變更 | 取代原有 watch |
| 2 | `_doAddInvoice` 末尾 (L351) | 新增發票 | **新增** |
| 3 | `removeImage` 末尾 (L365) | 側邊欄移除發票 | **新增** |
| 4 | `removeSelectedOnCanvas` 末尾 (L666) | 鍵盤 Delete/Backspace | **新增** |
| 5 | `onMounted` 最末 | 初始載入 | **新增** |
| 6 | `addPage` 末尾 (L248) | 新增空頁面 | **新增** |
| 7 | `switchPage` | 切頁 | 不適用（不影響全局編號） |

---

## 🧪 驗證測試清單

### 前端測試矩陣

| # | 測試場景 | 預期結果 |
|:---|:---|:---|
| T1 | 手動輸入 `payDate = "20240301"` → 按產出 PDF | 送出 payload 含 `payDate: "2024-03-01"`，後端不 422 |
| T2 | 手動輸入 `payDate = "2024/03/01"` → 按產出 PDF | 同上正規化為 ISO |
| T3 | 自動回填日期（VLM 回傳 `YYYYMMDD`）→ 欄位顯示 | 顯示 `YYYY-MM-DD` |
| T4 | 空頁面（無發票）→ 按產出 PDF | 空頁被過濾，不送往後端 |
| T5 | 新增發票 → 檢查所有頁面編號 | 編號連續遞增 |
| T6 | 移除發票（側邊欄） → 檢查所有頁面編號 | 編號重算 |
| T7 | 鍵盤 Delete 刪除 → 檢查所有頁面編號 | 編號重算 |
| T8 | `getProjectDetail` 端點掛掉 → 編輯器載入 | 編輯器正常載入，budgetItem 為空 |
| T9 | 切頁再切回 → 原頁面草稿保留 | 日期/金額/用途不被覆蓋 |
| T10 | 金額包含小數 → 自動取整 | 金額欄位顯示整數 |

### 後端測試項目

| # | 測試場景 | 預期結果 |
|:---|:---|:---|
| T11 | `GET /api/projects/{id}/detail` 正常專案 | 回傳含 `metadata` 的完整專案資料 |
| T12 | `GET /api/projects/{id}/detail` 不存在專案 | 回傳 404 |
| T13 | `POST /api/voucher/{id}/generate` 含空頁面 | 前端已過濾，但後端也能 skip 空頁 |
| T14 | `POST /api/voucher/{id}/generate` payDate 為 ISO 格式 | 通過 Pydantic 驗證 |
