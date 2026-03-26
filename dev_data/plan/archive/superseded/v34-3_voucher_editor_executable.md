# Voucher Editor V34.3 - Single-Source Executable Plan

Date: 2026-03-06
Status: Ready for implementation
Scope: Replace mixed V34.2/V34.3 notes with one clean, implementation-first spec.

---

## Deep Review Verdict

This document resolves the previously identified blockers and removes version-mixing ambiguity.

Blocking issues addressed in this V34.3 spec:
1. Submission path now normalizes `payDate` before `generate` API call.
2. Date parsing is strict (invalid calendar dates are rejected, not auto-shifted by JS).
3. `getProjectDetail` failure is non-fatal during editor init.
4. Metadata key usage is corrected to `metadata.budgetExpense?.[0]?.name`.
5. Voucher numbering recalculation call sites are complete (`addPage`, add/remove invoice, keyboard delete, mount, prefix/startIndex watch).

Non-blocking residual risk:
1. Fabric canvas memory lifecycle should still keep `dispose()` in `onBeforeUnmount` (already present in current code).

---

## File Change Map

1. `frontend/src/utils/voucher.js`
2. `frontend/src/views/VoucherEditorView.vue`
3. `frontend/src/services/api.js`
4. `backend/routers/projects.py`

---

## 1) `frontend/src/utils/voucher.js`

### 1.1 Add strict date parser and ISO normalizer

Add these exports near the top-level utility functions:

```javascript
export function parseDateString(value) {
  if (value === null || value === undefined) return NaN
  const raw = String(value).trim()
  if (!raw) return NaN

  let y = 0
  let m = 0
  let d = 0

  // Format A: YYYYMMDD
  if (/^\d{8}$/.test(raw)) {
    y = Number(raw.slice(0, 4))
    m = Number(raw.slice(4, 6))
    d = Number(raw.slice(6, 8))
  } else {
    // Format B: YYYY-MM-DD or YYYY/MM/DD
    const mObj = raw.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/)
    if (!mObj) return NaN
    y = Number(mObj[1])
    m = Number(mObj[2])
    d = Number(mObj[3])
  }

  if (m < 1 || m > 12 || d < 1 || d > 31) return NaN

  const dt = new Date(Date.UTC(y, m - 1, d))
  // Strict calendar validation: reject 2024-02-31 instead of auto-normalizing to 2024-03-02.
  if (
    dt.getUTCFullYear() !== y ||
    dt.getUTCMonth() + 1 !== m ||
    dt.getUTCDate() !== d
  ) {
    return NaN
  }

  return dt.getTime()
}

export function normalizeDateToISO(value) {
  const ts = parseDateString(value)
  if (Number.isNaN(ts)) return ''
  const dt = new Date(ts)
  const yyyy = dt.getUTCFullYear()
  const mm = String(dt.getUTCMonth() + 1).padStart(2, '0')
  const dd = String(dt.getUTCDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}
```

### 1.2 Update `hasInvalidDate` to strict parser

Replace the current implementation:

```javascript
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

### 1.3 Auto-layout overflow guard

In `simulateLayout`, add a hard guard:

```javascript
if (scaledW > maxWidth) return Number.POSITIVE_INFINITY
```

This prevents binary search from accepting impossible single-item widths.

---

## 2) `frontend/src/services/api.js`

Add a dedicated detail endpoint method:

```javascript
getProjectDetail(projectId) {
  return api.get(`/api/projects/${projectId}/detail`)
},
```

---

## 3) `backend/routers/projects.py`

Add route (safe with current route table):

```python
@router.get("/{project_id}/detail")
async def get_project_detail(project_id: str, engine: Engine = Depends(get_engine)):
    """Return full project payload including metadata."""
    project = await engine.project_repo.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
```

---

## 4) `frontend/src/views/VoucherEditorView.vue`

### 4.1 Import utilities

Update imports from `../utils/voucher` to include:

```javascript
parseDateString,
normalizeDateToISO,
```

### 4.2 Date validation computed

Replace `isCurrentPageDateInvalid` check from `Date.parse` to strict parser:

```javascript
return Number.isNaN(parseDateString(payDate))
```

### 4.3 Recalculate amount/date/purpose from invoice data

In `recalculatePageFields(page, options)`:

1. Amount path must support all invoice shapes:

```javascript
let totalAmount = 0
for (const inv of pageInvoices) {
  const r = inv.result || {}
  const raw = r.total_amount ?? r.summary?.total ?? r.total ?? 0
  const amount = parseFloat(String(raw))
  if (!Number.isNaN(amount)) totalAmount += amount
}
const nextAmount = totalAmount ? String(Math.round(totalAmount)) : ''
```

2. Date path must use timestamp sort + ISO writeback:

```javascript
const validDateObjects = pageInvoices
  .map(inv => inv.result?.date || inv.result?.header?.date || '')
  .map(d => ({ raw: d, ts: parseDateString(d) }))
  .filter(obj => !Number.isNaN(obj.ts))
  .sort((a, b) => a.ts - b.ts)

const nextPayDate = validDateObjects.length
  ? normalizeDateToISO(validDateObjects[validDateObjects.length - 1].raw)
  : ''
```

3. Purpose path should keep fallback chain:

```javascript
const desc = item.category || item.description || item.name || ''
```

### 4.4 Add `recalculateVoucherNumbers()` helper

Add helper and use it as the single numbering source:

```javascript
const recalculateVoucherNumbers = () => {
  let runningIndex = startIndex.value
  pages.value.forEach(page => {
    const count = (page.images || []).length
    page.fields.receiptCount = String(count)

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
```

### 4.5 Required call sites for `recalculateVoucherNumbers()`

1. `watch([globalPrefix, startIndex], recalculateVoucherNumbers)`
2. End of `_doAddInvoice`
3. End of `removeImage`
4. End of `removeSelectedOnCanvas`
5. End of `addPage`
6. End of `runAutoLayout`
7. End of initial `onMounted` data-load flow

Note: `switchPage` does not need global renumbering.

### 4.6 `runAutoLayout` consistency call

After applying `layoutResult`, run:

```javascript
recalculatePageFields(activePage.value, { onlyFillEmpty: true })
recalculateVoucherNumbers()
```

### 4.7 Non-blocking project metadata load in `onMounted`

Keep template + layout in primary `Promise.all`, and project detail as degradable:

```javascript
let defaultBudget = ''
try {
  const projectResp = await api.getProjectDetail(projectId)
  const meta = projectResp.data?.metadata || {}
  defaultBudget = meta.budgetExpense?.[0]?.name || ''
} catch (e) {
  console.warn('getProjectDetail failed, budgetItem stays empty', e)
}
```

When merging loaded layout pages, preserve user draft values by default:

```javascript
fields: {
  voucherNo: '',
  budgetItem: defaultBudget,
  amount: '',
  purpose: '',
  receiptCount: '0',
  payDate: '',
  isManuallyEdited: false,
  ...(p.fields || {}),
}
```

### 4.8 `goBack` must save before leaving

```javascript
const goBack = async () => {
  await saveLayout()
  router.push(`/project/${projectId}`)
}
```

### 4.9 `generatePdf` must submit normalized and filtered pages

Do not submit `payload.value` directly.

```javascript
const generatePdf = async () => {
  try {
    syncActivePageFromCanvas()
    ensurePageNumbers()

    const submitPages = pages.value
      .filter(p => (p.images || []).length > 0)
      .map(p => ({
        ...p,
        fields: {
          ...p.fields,
          payDate: normalizeDateToISO(p.fields.payDate),
        },
      }))

    const submitPayload = {
      globalPrefix: globalPrefix.value,
      startIndex: startIndex.value,
      pages: submitPages,
    }

    const response = await api.generateVoucherFromLayout(projectId, submitPayload)
    alert(`PDF 產出成功: ${response.data.filename}`)
  } catch (error) {
    console.error('generate failed', error)
    alert('產出失敗，請檢查欄位格式與發票內容')
  }
}
```

---

## Validation Checklist (Must Pass)

Frontend:
1. `payDate="20240301"` -> accepted and submitted as `2024-03-01`.
2. `payDate="2024/03/01"` -> accepted and submitted as `2024-03-01`.
3. `payDate="2024-02-31"` -> rejected as invalid.
4. Add/remove/delete invoices -> voucher numbers stay continuous.
5. Add empty page -> `receiptCount` becomes `0`, `voucherNo` empty.
6. `getProjectDetail` failure -> editor still loads template/layout.
7. Generate with empty pages present in UI -> only non-empty pages submitted.

Backend:
1. `GET /api/projects/{id}/detail` returns full project with `metadata`.
2. Unknown project id returns 404.
3. Generate payload with ISO `payDate` passes strict validation.

---

## Implementation Notes

1. This file intentionally excludes review-history narratives to stay executable.
2. If preserving prior audit logs is required, keep them in `v34-2_voucher_editor_executable.md` and treat this file as the only implementation source.
