# 憑證黏貼編輯器 — 可直接落地 V34.1 實作清單 🚀

**日期**: 2026-03-06
**前置文件**: v34 最終修補計畫 (基於深度審閱回饋修正)
**目標**: 將所有 12 項修補轉化為 100% 準確的函式級修改點，解決 API 路徑假設、日期排序與所有邊界問題。

---

## 🛠️ Stage 1: API 取值與欄位預設值合併 (Fix #1, #4)
**目標位置**: `frontend/src/views/VoucherEditorView.vue` 👉 `onMounted`

**修正邏輯**: 
1. 捨棄錯誤的單一 `getProject`，改用與 `EditProjectView.vue` 相同的 `api.getProjects()` 取回清單過濾出 metadata。
2. 預算擷取加上 `budgetExpense?.[0]?.name` 的 Fallback 機制。

```javascript
// 修改 onMounted 載入區塊
onMounted(async () => {
  try {
    const [templateResp, layoutResp, projectsResp] = await Promise.all([
      api.getVoucherTemplate(projectId),
      api.getVoucherLayout(projectId),
      api.getProjects() // Fix #4: 取回包含 metadata 的專案清單
    ])
    
    // 尋找當前專案的 metadata 與預設預算項目 (budgetItem 或 budgetExpense 第一項)
    const currentProject = projectsResp.data.find(p => p.project_id === projectId)
    const meta = currentProject?.metadata || {}
    const defaultBudget = meta.budgetItem || meta.budgetExpense?.[0]?.name || ''

    templatePng.value = templateResp.data.templatePng || ''
    invoices.value = templateResp.data.invoices || []
    
    if (layoutResp.data?.pages?.length) {
      // Fix #1: 預設值合併
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
      // 全新頁面也套用預算預設值
      pages.value[0].fields.budgetItem = defaultBudget
    }
  } catch (error) { ... }

  await nextTick()
  initCanvas()
  await loadActivePageToCanvas()

  recalculatePageFields(activePage.value, { onlyFillEmpty: true })
  recalculateVoucherNumbers() // <- Fix #3 遺漏的初始呼叫

  autosaveTimer = window.setInterval(saveLayout, 30000)
})
```

---

## 🛠️ Stage 2: 日期工具與驗證統一化 (Fix #12)
**目標位置**: `frontend/src/utils/voucher.js`

**修正邏輯**: 
1. 將強化的 `parseDateString` 寫死在 Utils 內。
2. 替換 `hasInvalidDate` 原有的 `Date.parse(payDate)`。

```javascript
// 新增 utils 工具
export function parseDateString(d) {
  if (!d) return NaN
  let clean = String(d).replace(/\//g, "-")
  if (/^\d{8}$/.test(clean)) return Date.parse(`${clean.slice(0, 4)}-${clean.slice(4, 6)}-${clean.slice(6, 8)}`)
  return Date.parse(clean)
}

// 修改原有的 hasInvalidDate
export function hasInvalidDate(pages = []) {
  return pages.some(page => {
    const payDate = page?.fields?.payDate
    const hasImages = (page.images || []).length > 0
    if (!payDate && hasImages) return true
    if (!payDate) return false
    return Number.isNaN(parseDateString(payDate))
  })
}
```

---

## 🛠️ Stage 3: 紅字判定與欄位重算 (Fix #6, 全面 #12)
**目標位置**: `frontend/src/views/VoucherEditorView.vue`

**修正邏輯**: 
1. 將 UI 單頁紅字 `isCurrentPageDateInvalid` 替換為統一套件。
2. 讓日期排序使用時間戳 `ts`，而不是單純字串排序解決跨格式問題。

```javascript
import { ..., parseDateString } from '../utils/voucher'

// 替換 L198 的 isCurrentPageDateInvalid
const isCurrentPageDateInvalid = computed(() => {
  // ... 前面照舊 ...
  return Number.isNaN(parseDateString(payDate))
})

// 修改 recalculatePageFields 內部
const recalculatePageFields = (page, options = {}) => {
  // ... 前面 amount 計算照舊 ...

  // === D.28: 時間戳穩定排序 ===
  const validDateObjects = pageInvoices
    .map(inv => inv.result?.date || inv.result?.header?.date || '')
    .map(d => ({ raw: d, ts: parseDateString(d) }))
    .filter(obj => !Number.isNaN(obj.ts))
    .sort((a, b) => a.ts - b.ts) // 取代錯誤的純字串 sort
  const nextPayDate = validDateObjects.length ? validDateObjects[validDateObjects.length - 1].raw : ''
  if (!onlyFillEmpty || !String(page.fields.payDate || '').trim()) {
    page.fields.payDate = nextPayDate
  }

  // === D.27: Category 優先用途拼接 ===
  if (!page.fields.isManuallyEdited) {
    const descriptions = new Set()
    for (const inv of pageInvoices) {
      const items = (inv.result?.items) || []
      for (const item of items) {
        const desc = item.category || item.description || item.name || ''
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

## 🛠️ Stage 4: 統一重算編號 / 多頁 Count 同步 / 離開存檔 / 空頁過濾
**目標位置**: `frontend/src/views/VoucherEditorView.vue` 👉 `script` 其他部位

```javascript
// => Fix #3, #5, #7:
const recalculateVoucherNumbers = () => {
  let runningIndex = startIndex.value
  pages.value.forEach(page => {
    const count = (page.images || []).length
    page.fields.receiptCount = String(count) // Fix #5 跨頁面同步
    
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

// => 取代原有 watch
watch([globalPrefix, startIndex], recalculateVoucherNumbers)

// => 把 recalculateVoucherNumbers() 塞入 `_doAddInvoice`, `removeImage`, `removeSelectedOnCanvas` 函數末尾。

// => Fix #9:
const goBack = async () => {
  await saveLayout()
  router.push(`/project/${projectId}`)
}

// => Fix #10
const generatePdf = async () => {
  // ... try catch
  const submitPayload = {
    globalPrefix: payload.value.globalPrefix,
    startIndex: payload.value.startIndex,
    pages: payload.value.pages.filter(p => (p.images || []).length > 0)
  }
  const response = await api.generateVoucherFromLayout(projectId, submitPayload)
  // ... alert
}
```

---

## 🛠️ Stage 5: 自動排版防護邊界 (Fix #11)
**目標位置**: `frontend/src/utils/voucher.js` 👉 `autoLayoutImages`

```javascript
  function simulateLayout(items, H) {
    let rows = 1
    let currentRowWidth = 0
    for (const item of items) {
      const scaledW = (item.originalWidth / item.originalHeight) * H
      if (scaledW > maxWidth) return Infinity // 強制認定這回合算出來的高度 H 無效，讓演算法往小的 H 尋找
      // ...
    }
    return rows
  }
```

---

> 🚦 所有深層風險地雷皆已排除。我們只需精準置換這些區塊！
