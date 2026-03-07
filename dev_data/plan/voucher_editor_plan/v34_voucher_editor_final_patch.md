# 憑證黏貼編輯器 — 最終修補計畫 v34 (Final Patch)

**日期**: 2026-03-06
**前置文件**: v33 補完計畫 (根據使用者回饋修正)
**目標**: 整合所有 12 項致命缺陷與邊界問題，針對實際 API 結構與回饋調整實施順序與程式邏輯。

---

## 🙋‍♂️ 回覆你的問題

1. **用途欄位來源：到底是 category 還是 description/name？**
   - **我查證錯誤了，抱歉！** 我去翻了 `backend/database/models.py`，你確實有定義 `InvoiceItem.category` 欄位（報帳名目），而且在 `word_exporter.py` 跟 `excel_exporter.py` 裡都有用到它！
   - **結論**：VLM 雖然原始抽出 description，但在寫入 DB 或處理後確實會有 `category` 屬性。所以我會在取用用途時，修改為最穩定的做法：優先抓 `item.category`，若無再抓 `item.description` 或 `name`：`const desc = item.category || item.description || item.name || ''`。

2. **後端 API：GET `/project/{id}` 會不會回傳 activity_info？**
   - 經過追查，**後端不會回傳 `activity_info` 這個 key**。所有透過 `update_activity_info` 或 `update_project` 寫入的活動資訊，都會被**平鋪合併**存放在 `p.meta_data` 裡面！
   - 所以前端從 `GET /api/projects/{id}` 拿到的回應，資料會放在 `projectResp.data.metadata` 中（例如 `metadata.budgetExpense` 等等）。

3. **日期格式：還會有其他格式嗎？**
   - 除了 `YYYY-MM-DD` 以外，舊收據經過辨識最常出現的是連續數字 `YYYYMMDD`。計畫已經針對這兩種做防護。如果還有真的像 `113/03/01` 這種格式，現有 Date API 會回傳 NaN。我們實施時可以順手把 `/` 換成 `-` 再試一次。

4. **是否直接開工？**
   - **是的，看完這份 V34，你可以隨時叫我開工。**

---

## 🛠️ V34 實施計畫總覽 (涵蓋前置 V33 的所有內容)

| # | 項目 | 影響程度 | V34 修正作法 | 狀態 |
|:---|:---|:---|:---|:---|
| **1** | **載入時 fields 預設值合併** | 🟡 中 | 在 `onMounted` 把舊版缺少的 `isManuallyEdited` 等欄位，用展開語法預設補齊。 | 新增實施 |
| **2** | PDF 沒寫欄位 | 🔴 高 | 見缺陷 #6 修正 JSON 路徑 | 包裝在 #6 中 |
| **3/#7** | **不自動給編號 / 增刪不更新編號** | 🔴 高 | 抽出 `recalculateVoucherNumbers()` 函式，並在 4 個時機呼叫 (載入、加、刪、修改 Prefix 時)。 | 新增實施 |
| **4** | **不寫預算組別 (budgetItem)** | 🟡 中 | **已修正方案**：讀取 `projectResp.data?.metadata?.budgetItem`。若專案内沒設定此欄位，則留空讓使用者手填。 | 調整實施 |
| **5** | **receiptCount 多頁不同步** | 🟡 中 | 在載入 layout 或增刪發票時，針對所有 page 跑迴圈更新 `receiptCount = images.length`。 | 新增實施 |
| **6** | **JSON 路徑全部錯誤** | 🔴 高 | `amount` 讀取 `total_amount \|\| summary.total \|\| total`。<br>`purpose` 優先讀取 `category`、再退回 `description \|\| name`。 | 優先實施 |
| **8** | 切頁保留草稿 | 🟢 已解決 | `recalculatePageFields({ onlyFillEmpty: true })` | User 已修 |
| **9** | **點「返回活動」遺失心血** | 🔴 致命 | `goBack` 改為 `async`，路由挑戰前強制 `await saveLayout()`。 | User 自修半套，需補齊 |
| **10** | **空頁面觸發 422 Error** | 🔴 高 | 前端 `generatePdf` 送出 Payload 前，用 `.filter(p => (p.images \|\| []).length > 0)` 濾掉所有空頁面。 | 新增實施 |
| **11** | **極寬圖衝出排版邊界** | 🟡 中 | `simulateLayout` 當算出 `scaledW > maxWidth` 時回傳 `Infinity`，懲罰該高度讓系統自動縮小。 | 新增實施 |
| **12** | **YYYYMMDD 或 / 日期無效** | 🟡 中 | 強化 `parseDateString(d)`，包含正則與斜線替換 `d.replace(/\//g, "-")`。 | 新增實施 |

---

## 💻 具體程式碼變更指引

### Stage 1: 修復資料源 (Fix #6 + #12)
**目標**: `frontend/src/views/VoucherEditorView.vue` -> `recalculatePageFields` 和前端日期判定 Utils。

```javascript
  // D.25 金額加總
  let totalAmount = 0
  for (const inv of pageInvoices) {
    const r = inv.result || {}
    const raw = r.total_amount ?? r.summary?.total ?? r.total ?? 0
    const amount = parseFloat(String(raw))
    if (!Number.isNaN(amount)) totalAmount += amount
  }
  
  // D.28 最晚日期 (兼 Fix #12)
  const parseDateString = (d) => {
    if (!d) return NaN
    let clean = d.replace(/\//g, "-") // 處理 YYYY/MM/DD
    if (/^\d{8}$/.test(clean)) return Date.parse(`${clean.slice(0, 4)}-${clean.slice(4, 6)}-${clean.slice(6, 8)}`)
    return Date.parse(clean)
  }
  const validDates = pageInvoices
    .map(inv => inv.result?.date || inv.result?.header?.date || '')
    .filter(d => d && !Number.isNaN(parseDateString(d)))
    .sort()
  
  // D.27 用途 (支援 Category 與多種退回機制)
  if (!page.fields.isManuallyEdited) {
    const descriptions = new Set()
    for (const inv of pageInvoices) {
      const items = (inv.result?.items) || []
      for (const item of items) {
        const desc = item.category || item.description || item.name || ''
        if (desc) descriptions.add(desc)
      }
    }
    // ... join
  }
```
同時把 `parseDateString` 防護複製到 `frontend/src/utils/voucher.js` 的 `hasInvalidDate`。

---

### Stage 2: 修復自動編號機制 (Fix #3 + #7 + #5)
**目標**: 將 `watch` 邏輯抽出為 `recalculateVoucherNumbers`。

```javascript
const recalculateVoucherNumbers = () => {
  let runningIndex = startIndex.value
  pages.value.forEach(page => {
    // 順手修復 Fix #5
    const count = (page.images || []).length
    page.fields.receiptCount = String(count)
    
    if (count > 0) {
      const from = String(runningIndex).padStart(2, '0')
      const to = String(runningIndex + count - 1).padStart(2, '0')
      page.fields.voucherNo = count > 1 ? `${globalPrefix.value}-${from}~${to}` : `${globalPrefix.value}-${from}`
      runningIndex += count
    } else {
      page.fields.voucherNo = ''
    }
  })
}
// 替換現有的 watch
watch([globalPrefix, startIndex], recalculateVoucherNumbers)
// 並在 addInvoiceToActivePage、removeImage 結尾也呼叫
```

---

### Stage 3: 修復載入時不完整結構與退回心血 (Fix #1 + #4 + #9)
**目標**: 修改 `onMounted` 的 payload 載入，與 `goBack()`。

```javascript
// Fix #1 & #4
onMounted(async () => {
  // ... get APIs
  const projectResp = await api.getProject(projectId)
  const defaultBudget = projectResp.data?.metadata?.budgetItem || ''

  if (layoutResp.data?.pages?.length) {
    pages.value = layoutResp.data.pages.map(p => ({
      ...p,
      fields: {
        voucherNo: '', budgetItem: defaultBudget, amount: '', purpose: '',
        receiptCount: '0', payDate: '', isManuallyEdited: false,
        ...(p.fields || {})
      }
    }))
  }
  // 載入完畢之後，跑一次 recalculateVoucherNumbers() 等等...
})

// Fix #9
const goBack = async () => {
  await saveLayout()
  router.push(`/project/${projectId}`)
}
```

---

### Stage 4: 修復產出驗證與排版邊界 (Fix #10 + #11)
**目標**: `generatePdf` Payload 過濾與 `utils.js` 防護。

```javascript
// Fix #10
const generatePdf = async () => {
  const submitPayload = {
    globalPrefix: payload.value.globalPrefix,
    startIndex: payload.value.startIndex,
    pages: payload.value.pages.filter(p => (p.images || []).length > 0)
  }
  await api.generateVoucherFromLayout(projectId, submitPayload)
}

// Fix #11 in voucher.js
function simulateLayout(items, H) {
  // ...
  const scaledW = (item.originalWidth / item.originalHeight) * H
  if (scaledW > maxWidth) return Infinity // 強制懲罰，逼演算法壓低 H
  // ...
}
```

---

**準備好了！** 如果你覺得 V34 沒問題，請通知我「開工」，我就會一口氣實施這四個階段，徹底解決全部惱人的 Bug！
