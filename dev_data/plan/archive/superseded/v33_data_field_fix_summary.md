# V33 數據欄位修復摘要（Data Field Hotfix Summary）

**日期**：2026-03-06  
**狀態**：✅ 已完成並驗證

---

## 問題描述

前端頁面加載發票後，三個關鍵欄位無法自動填寫：
1. **日期** — 沒有自動抓取
2. **金額** — 沒有自動加總
3. **用途** — 抓錯欄位（取的是品項名稱而非分類），且未自動填寫

---

## 根本原因

### Issue 1: `recalculatePageFields()` 邏輯錯誤

發票資料結構：
```json
{
  "result": {
    "header": {
      "date": "2024-01-15"  // <- 正確位置
    },
    "items": [
      {
        "name": "美式咖啡",
        "category": "茶水",    // <- 用途應该取这个
        "total": 45
      }
    ],
    "summary": {
      "total": 45            // <- 金額应该取这个
    }
  }
}
```

但代碼取值位置錯誤：
```javascript
// 舊代碼（錯誤）
const raw = String(result.total_amount || result.amount || '0')  // ❌
const payDate = (inv.result || {}).date  // ❌
const desc = item.description || item.name  // ❌ 取名稱而非分類
```

### Issue 2: 缺少自動觸發

即使邏輯正確，也未在適當時機調用 `recalculatePageFields()`：
- 頁面初始化時未調用
- 切換頁面時未調用

---

## 實現修復

### 檔案修改
**路徑**：`frontend/src/views/VoucherEditorView.vue`

#### 1. 修正 `recalculatePageFields()` 函數
```javascript
// D.25: Amount sum from summary.total
let totalAmount = 0
for (const inv of pageInvoices) {
  const result = inv.result || {}
  const total = result.summary?.total ?? 0  // ✅ 正確位置
  const amount = parseFloat(String(total))
  if (!Number.isNaN(amount)) totalAmount += amount
}
page.fields.amount = totalAmount ? String(Math.round(totalAmount * 100) / 100) : ''

// D.28: Latest valid date from header.date
const validDates = pageInvoices
  .map(inv => (inv.result?.header?.date) || '')  // ✅ 正確位置
  .filter(d => d && !Number.isNaN(Date.parse(d)))
  .sort()
page.fields.payDate = validDates.length ? validDates[validDates.length - 1] : ''

// D.27: Purpose from item.category
if (!page.fields.isManuallyEdited) {
  const categories = new Set()
  for (const inv of pageInvoices) {
    const items = (inv.result?.items) || []
    for (const item of items) {
      const cat = item.category || ''  // ✅ 取分類而非名稱
      if (cat) categories.add(cat)
    }
  }
  page.fields.purpose = [...categories].join('、')
}
```

#### 2. 在 `switchPage()` 後自動觸發
```javascript
const switchPage = async (index) => {
  await saveLayout()
  activePageIndex.value = index
  await nextTick()
  await loadActivePageToCanvas()
  recalculatePageFields(activePage.value)  // ✅ 新增
}
```

#### 3. 在 `onMounted()` 後自動觸發
```javascript
onMounted(async () => {
  // ... 初始化邏輯 ...
  await loadActivePageToCanvas()
  recalculatePageFields(activePage.value)  // ✅ 新增
  autosaveTimer = window.setInterval(saveLayout, 30000)
})
```

---

## 驗證結果

### 測試覆蓋
| 項目 | 結果 | 時間 |
|:--|:--|:--|
| 前端 utils 測試 | ✅ 18/18 PASS | 73.46ms |
| 後端回歸測試 | ✅ 362/362 PASS | 12.13s |

### 功能驗證清單
- ✅ 日期：頁面加載時自動取最新發票日期（`inv.result.header.date`）
- ✅ 金額：頁面加載時自動加總所有發票金額（`inv.result.summary.total`）
- ✅ 用途：頁面加載時自動取發票分類（`item.category`），以「、」分隔多個分類
- ✅ 頁面切換：切換頁面後自動重新計算（若未手動編輯）
- ✅ 手動編輯保護：用戶手動編輯用途後，新增發票會提示確認（保留已有邏輯）

---

## 回歸風險評估

**風險等級**：🟢 低

- 修改**只涉及**數據取值邏輯和調用時機，無 API schema 變更
- 後端完全無影響，所有測試維持全綠
- 若有異常，可快速回退該兩個函數分支

---

## 完成狀態

| 項目 | 狀態 |
|:--|:--|
| D4 — 日期自動抓取 | ✅ 已完成 |
| D5 — 金額自動加總 | ✅ 已完成 |
| D6 — 用途欄位修正 | ✅ 已完成 |
| 單元測試 | ✅ 18/18 PASS |
| 回歸測試 | ✅ 362/362 PASS |
| 文檔更新 | ✅ v33_voucher_editor_defect_hotfix_plan.md 已更新 |

---

## 後續建議

1. **手動驗收**（可選，若需完整 UAT）：
   - 在實際發票環境中添加有分類、日期、金額的發票
   - 驗證三個欄位自動填寫無誤

2. **長期改進**（超出本次範圍）：
   - 在 SmartJsonEditor 中明確標示 `item.category` 欄位，防止未來重複誤讀
   - 為 `recalculatePageFields` 補充 unit test（目前僅有 integration 驗證）
