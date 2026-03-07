# 憑證黏貼編輯器 — 關鍵缺陷修正計畫 v33 (Critical Bug Fixes)

**日期**: 2026-03-06
**前置文件**: v32 補完計畫 · 實際操作回報
**目標**: 修復使用者回報的 5 個致命問題 + 自查發現的 3 個連帶問題，讓 Voucher Editor 實際可用。

---

## 0. 問題總覽

| # | 問題 | 嚴重度 | 根因 |
|:---|:---|:---|:---|
| 1 | **存檔沒有用**，退出後重進是空白黏貼單 | 🔴 致命 | 前端 `saveLayout` 傳出的 payload 正確，API 也正確存入了 `voucher_layout.json`。但 `onMounted` 載入 layout 後，auto-numbering watch 沒有觸發（因為 prefix/startIndex 沒改變），且各 page 的 `isManuallyEdited` 可能遺失，導致 `recalculatePageFields` 覆蓋已存的欄位為空值 |
| 2 | **PDF 不會寫日期、金額等欄位**，只有發票圖片 | 🔴 致命 | 後端 `generate_from_layout()` **確實會寫**所有 6 個欄位！但前端從未自動填充 `amount`、`payDate`、`purpose`，因為 `recalculatePageFields` 讀取的 JSON 路徑錯誤（見 #6） |
| 3 | **不會自動給編號** | 🔴 致命 | `watch([globalPrefix, startIndex])` 只在這兩個值變化時觸發。初始載入和新增/移除發票時都不會觸發 |
| 4 | **不會寫預算組別** | 🟡 缺失 | `budgetItem` 從未從任何來源自動填入。需要從專案的 `activity_info` 讀取預算類別 |
| 5 | **不會寫發票張數** | 🟡 缺失 | `recalculatePageFields` 有更新 `receiptCount`，但它只在 add/remove 時觸發。初始載入和 PDF 產出時可能不一致 |
| 6 | **`recalculatePageFields` JSON 路徑全部錯誤** | 🔴 致命 | 當前代碼讀 `result.summary.total` 和 `result.header.date`（電子發票 ELECTRONIC_INVOICE 格式），但 VLM 普通發票的 JSON 結構是 `result.total_amount` 和 `result.date`。`item.category` 也不存在，應為 `item.description \|\| item.name` |
| 7 | **Auto-numbering 不包含新增/移除發票** | 🟡 缺失 | 新增或移除發票後，`voucherNo` 不會即時更新 |
| 8 | **載入 layout 後 `isManuallyEdited` 遺失** | 🟡 邊界 | 被 `recalculatePageFields({ onlyFillEmpty: true })` 覆蓋空值或被初始化邏輯影響 |
| 9 | **點「返回活動」會遺失剛編輯的心血** | 🔴 致命 | `goBack()` 直接跳轉路由，未觸發 `saveLayout`。若退出前未滿 30 秒自動存檔點，內容就會變成「白黏貼單」 |
| 10 | **產出 PDF 可能遇到 `Unprocessable Entity`** | 🔴 致命 | 若某分頁是「空頁面（0 張發票）」，它的金額、編號即為空字串 `""`。送往後端時會觸發 `VoucherFieldsStrict` 的 `min_length=1` 嚴格驗證阻擋整份 PDF 的產生 |
| 11 | **超寬發票自動排版會衝出邊界** | 🔴 致命 | 二分搜尋法在計算面積時，若單張發票寬度超越 `maxWidth`，演算法不會提高懲罰（只算換 1 行），導致最終 H 過大排出版外 |
| 12 | **`YYYYMMDD` 格式的日期被視為無效** | 🟡 邊界 | 傳統收據 OCR 常產生 `20240301`，但 JS 的 `Date.parse("20240301")` 回傳 `NaN`，導致被無視 |

---

## 1. 修正 `recalculatePageFields` 的 JSON 路徑 (Fix #6 + #2 + #5)

### 根因分析
當前代碼 (L260-308)：
```javascript
// 金額: 讀 result.summary.total → 電子發票格式
const total = result.summary?.total ?? 0

// 日期: 讀 result.header?.date → 電子發票格式
.map(inv => (inv.result?.header?.date) || '')

// 用途: 讀 item.category → 不存在的欄位
const cat = item.category || ''
```

但 VLM 的 `EXTRACTION_PROMPT` (prompts_config.py L56-65) 實際輸出的 JSON 結構為：
```json
{
    "supplier": "supplier_name",
    "date": "YYYY-MM-DD",
    "items": [{"description": "product_name", "quantity": 1, "price": 100}],
    "total_amount": 5000
}
```

`get_display_result()` 回傳的是 `_stitch_items_from_db()` 的結果，可能是上述格式或電子發票格式。

### 修正方案

#### [MODIFY] `frontend/src/views/VoucherEditorView.vue` — `recalculatePageFields` (L260-308)

```javascript
const recalculatePageFields = (page, options = {}) => {
  const { onlyFillEmpty = false } = options
  if (!page) return
  const pageImages = page.images || []
  page.fields.receiptCount = String(pageImages.length)

  const pageInvoices = pageImages
    .map(img => invoices.value.find(inv => inv.jobId === img.jobId))
    .filter(Boolean)

  // === D.25: 金額加總 ===
  // 相容多種 JSON 格式：
  //   VLM 普通發票: result.total_amount
  //   電子發票:     result.summary.total
  //   手寫收據:     result.total
  let totalAmount = 0
  for (const inv of pageInvoices) {
    const r = inv.result || {}
    const raw = r.total_amount ?? r.summary?.total ?? r.total ?? 0
    const amount = parseFloat(String(raw))
    if (!Number.isNaN(amount)) totalAmount += amount
  }
  const nextAmount = totalAmount ? String(Math.round(totalAmount)) : ''
  if (!onlyFillEmpty || !String(page.fields.amount || '').trim()) {
    page.fields.amount = nextAmount
  }

  // === D.28: 最晚日期 ===
  const parseDateString = (d) => {
    if (!d) return NaN
    // 支援 YYYYMMDD 格式 (Fix #12)
    if (/^\d{8}$/.test(d)) return Date.parse(`${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`)
    return Date.parse(d)
  }

  const validDates = pageInvoices
    .map(inv => {
      const r = inv.result || {}
      return r.date || r.header?.date || ''
    })
    .filter(d => d && !Number.isNaN(parseDateString(d)))
    .sort()
  const nextPayDate = validDates.length ? validDates[validDates.length - 1] : ''
  if (!onlyFillEmpty || !String(page.fields.payDate || '').trim()) {
    page.fields.payDate = nextPayDate
  }

  // === D.27: 用途去重拼接 ===
  // 相容多種格式：
  //   VLM 普通發票: items[].description
  //   手寫收據:     items[].name
  //   電子發票:     items[].name
  if (!page.fields.isManuallyEdited) {
    const descriptions = new Set()
    for (const inv of pageInvoices) {
      const items = (inv.result?.items) || []
      for (const item of items) {
        const desc = item.description || item.name || ''
        if (desc) descriptions.add(desc)
      }
    }
    const nextPurpose = [...descriptions].join('、')
    if (!onlyFillEmpty || !String(page.fields.purpose || '').trim()) {
      page.fields.purpose = nextPurpose
    }
  }
}
```

---

## 2. 修正自動編號 (Fix #3 + #7)

### 根因分析
當前 `watch([globalPrefix, startIndex])` (L758-771) 只監聽 `globalPrefix` 和 `startIndex` 的變化。問題：
1. **初始載入**時 `globalPrefix` 和 `startIndex` 是從 `layoutResp.data` 恢復的，不會觸發 watch（因為 watch 在設值之後才生效）
2. **新增/移除發票**時 `images.length` 改變了，但 `globalPrefix` 和 `startIndex` 沒變，watch 不觸發

### 修正方案

將 auto-numbering 邏輯抽成獨立函式，在 3 處呼叫：

#### [MODIFY] `frontend/src/views/VoucherEditorView.vue` — Script 區塊

```javascript
// 抽取為獨立函式
const recalculateVoucherNumbers = () => {
  let runningIndex = startIndex.value
  pages.value.forEach(page => {
    const count = (page.images || []).length
    if (count > 0) {
      const from = String(runningIndex).padStart(2, '0')
      const to = String(runningIndex + count - 1).padStart(2, '0')
      page.fields.voucherNo = count > 1
        ? `${globalPrefix.value}-${from}~${to}`
        : `${globalPrefix.value}-${from}`
      runningIndex += count
    } else {
      page.fields.voucherNo = ''
    }
  })
}

// 原有 watch 改為呼叫此函式
watch([globalPrefix, startIndex], recalculateVoucherNumbers)
```

**呼叫時機** (4 處)：
1. `watch([globalPrefix, startIndex])` — 使用者修改前綴/起始號
2. `_doAddInvoice` 末尾 — 新增發票後
3. `removeImage` / `removeSelectedOnCanvas` 末尾 — 移除發票後
4. `onMounted` — 初始載入完成後（在 `recalculatePageFields` 之後）

---

## 3. 修正存檔後重新載入不生效 (Fix #1 + #8)

### 根因分析
`saveLayout` 和 `load_layout` 的 API 層面運作正常。問題在前端：

1. `onMounted` L711-714 正確載入了 `pages`、`globalPrefix`、`startIndex`
2. 但載入後呼叫 `recalculatePageFields(activePage.value, { onlyFillEmpty: true })`
3. 由於 JSON 路徑錯誤 (Fix #6)，`recalculatePageFields` 讀到的金額/日期全是 `0`/`''`
4. `onlyFillEmpty` 模式下，如果已存欄位是空的（因為上次也沒填成功），就會被覆蓋為更空的值

修正 #6 之後，載入問題應自動解決。但還需確保：
- 已儲存的 `pages[].fields` 在載入時完整保留
- `isManuallyEdited` 不被重置

### 修正方案

#### [MODIFY] `frontend/src/views/VoucherEditorView.vue` — `onMounted` 區塊

```javascript
onMounted(async () => {
  try {
    const [templateResp, layoutResp] = await Promise.all([
      api.getVoucherTemplate(projectId),
      api.getVoucherLayout(projectId),
    ])
    templatePng.value = templateResp.data.templatePng || ''
    invoices.value = templateResp.data.invoices || []
    if (layoutResp.data?.pages?.length) {
      // 確保每個 page 的 fields 都有完整欄位（防舊版 layout 缺失 isManuallyEdited）
      pages.value = layoutResp.data.pages.map(p => ({
        ...p,
        fields: {
          voucherNo: '',
          budgetItem: '',
          amount: '',
          purpose: '',
          receiptCount: '0',
          payDate: '',
          isManuallyEdited: false,
          ...p.fields,  // 已存欄位覆蓋預設值
        },
      }))
      globalPrefix.value = layoutResp.data.globalPrefix || globalPrefix.value
      startIndex.value = layoutResp.data.startIndex || startIndex.value
    }
  } catch (error) {
    console.error('voucher init failed', error)
  } finally {
    ready.value = true
  }

  await nextTick()
  initCanvas()
  await loadActivePageToCanvas()

  // 僅填空欄位，不覆蓋已存值
  recalculatePageFields(activePage.value, { onlyFillEmpty: true })
  // 初始載入後也要計算編號
  recalculateVoucherNumbers()

  autosaveTimer = window.setInterval(saveLayout, 30000)
})
```

---

## 4. 自動填寫預算組別 (Fix #4)

### 根因分析
`budgetItem` 不屬於發票資料，而是專案級別的設定。目前前端完全沒有讀取這個值。

### 修正方案

在 `onMounted` 中從 `templateResp.data.projectMeta` 或 `GET /project/{id}` API 讀取活動資訊，自動填入空白頁的 `budgetItem`：

#### [MODIFY] `frontend/src/views/VoucherEditorView.vue` — Script 區塊

```javascript
// 在 onMounted 的載入區塊中
const projectResp = await api.getProject(projectId)
const activityInfo = projectResp.data?.activityInfo || projectResp.data?.activity_info || {}
const defaultBudgetItem = activityInfo.budget_item || activityInfo.budgetItem || ''

// 對每頁補上預設預算組別（僅空白時填入）
if (defaultBudgetItem) {
  pages.value.forEach(page => {
    if (!page.fields.budgetItem?.trim()) {
      page.fields.budgetItem = defaultBudgetItem
    }
  })
}
```

> [!WARNING]
> 需要確認 `activity_info` 是否有 `budget_item` 欄位。如果沒有，需要先在後端 `activity_info` 或前端 `EditProjectView.vue` 中增加此欄位。

---

## 5. 確保發票張數始終正確 (Fix #5)

### 根因分析
`receiptCount` 已在 `recalculatePageFields` 中更新。但 `onMounted` 的初始載入只對 `activePage` 呼叫一次。如果有多頁，其他頁面的 `receiptCount` 不會被更新。

### 修正方案

在 `onMounted` 初始化後，對**所有頁面**執行 `receiptCount` 同步：

```javascript
// 在 onMounted 中，recalculatePageFields 之後
pages.value.forEach(p => {
  p.fields.receiptCount = String((p.images || []).length)
})
```

---

## 6. 深層 Bug 修補：存檔、產出與演算法 (Fix #9, #10, #11)

### [MODIFY] `frontend/src/views/VoucherEditorView.vue`

**Fix #9: 離開前強制存檔**
修改 `goBack` 函式：
```javascript
const goBack = async () => {
  await saveLayout() // 返回前強制確保存檔
  router.push(`/project/${projectId}`)
}
```

**Fix #10: 產出前過濾空頁面以通過 strict 驗證**
修改 `generatePdf` 函式：
```javascript
const generatePdf = async () => {
  try {
    syncActivePageFromCanvas()
    ensurePageNumbers()
    // 過濾空分頁，避免空欄位觸發 min_length=1 Pydantic Error
    const submitPayload = {
      globalPrefix: payload.value.globalPrefix,
      startIndex: payload.value.startIndex,
      pages: payload.value.pages.filter(p => p.images && p.images.length > 0)
    }
    const response = await api.generateVoucherFromLayout(projectId, submitPayload)
    alert(`PDF 產出成功: ${response.data.filename}`)
  } catch (error) { ... }
}
```

### [MODIFY] `frontend/src/utils/voucher.js`

**Fix #11: 自動排版超級寬圖超出邊界防護**
修改 `autoLayoutImages.simulateLayout` 內部邏輯：
```javascript
  function simulateLayout(items, H) {
    let rows = 1
    let currentRowWidth = 0
    for (const item of items) {
      const scaledW = (item.originalWidth / item.originalHeight) * H
      // Bug Fix: 單張極寬就直接判為「無效高度」強制縮小 H
      if (scaledW > maxWidth) return Infinity 
      
      if (currentRowWidth > 0 && currentRowWidth + GAP + scaledW > maxWidth) {
        rows++
        currentRowWidth = scaledW
      } else {
        currentRowWidth += (currentRowWidth > 0 ? GAP : 0) + scaledW
      }
    }
    return rows
  }

  // 同理，也要修改 Date.parse 邏輯 (Fix #12)
  export function hasInvalidDate(pages = []) {
    return pages.some(page => {
      const payDate = page?.fields?.payDate
      const hasImages = (page.images || []).length > 0
      if (!payDate && hasImages) return true
      if (!payDate) return false
      
      const parseDateString = (d) => {
        if (/^\d{8}$/.test(d)) return Date.parse(`${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`)
        return Date.parse(d)
      }
      return Number.isNaN(parseDateString(payDate))
    })
  }
```

---

## 實作順序

| 步驟 | 任務 | 預估 |
|:---|:---|:---|
| **1** | Fix #6/#12: 修正 `recalculatePageFields` JSON 路徑與 `YYYYMMDD` 日期解析 | 10 min |
| **2** | Fix #3/#7: 抽取 `recalculateVoucherNumbers` + 4 處呼叫 | 10 min |
| **3** | Fix #1/#8: 修正 `onMounted` 載入邏輯 + fields 預設值合併 | 10 min |
| **4** | Fix #5: 所有頁面 receiptCount 同步 | 5 min |
| **5** | Fix #4: 自動填寫 budgetItem（視 API 結構） | 10-20 min |
| **6** | Fix #9/#10/#11: 離開強存、過濾空頁面、自動排版寬度防護 | 10 min |

**預計總工時: ~55-65 分鐘**

---

## 驗證計畫

- [ ] **存讀一致**: 修改欄位 → 存檔 → 切換到其他頁面 → 返回 Voucher Editor → 確認所有欄位（包括 voucherNo、budgetItem、amount、payDate、purpose、receiptCount）完整保留
- [ ] **自動域計算**: 拖入發票後，立即確認金額、日期、用途自動填入（不再是空白）
- [ ] **自動編號**: 拖入第一張發票，確認 voucherNo 立即生成（如 `D-16-01`）；再拖入一張，確認變為 `D-16-01~02`
- [ ] **PDF 產出完整**: 點擊「產出 PDF」，確認產出的 PDF 上有日期、金額（七位右對齊）、用途、憑證號碼、發票張數
- [ ] **預算組別**: 開啟 Voucher Editor，確認 budgetItem 自動從專案活動資訊填入
- [ ] **多頁一致**: 建立 3 頁，每頁各加不同數量的發票，確認所有頁的編號不衝突、receiptCount 正確
