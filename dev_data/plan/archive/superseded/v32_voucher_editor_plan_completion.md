# 憑證黏貼編輯器 — 功能補完計畫 v32 (The Completion Sprint)

**日期**: 2026-03-04
**前置文件**: v27 究極計畫 46 項防禦清單 · v30 Reality Check
**目標**: 一次性補齊 v30 盤點出的 3 個🟡半成品 + 3 個🔴遺漏功能 + 1 個新需求（等比例縮放）+ 1 個既有 Bug（鍵盤衝突）+ 1 個遺漏域計算，使 Voucher Editor 達到 v27 規格書 100% 完成度。

---

## 0. 缺失項目總覽 (Gap Summary)

| # | v27 防禦號 | 嚴重度 | 現狀 | 行動 | 歷史來源 |
|:---|:---|:---|:---|:---|:---|
| 1 | B.11/B.13 | 🟡 半成品 | 日期/金額異常時僅頂部紅字提示，輸入框不變色 | 實作即時欄位高光 | resolved.27 Fix 32 |
| 2 | B.12 | 🟡 半成品 | 畫布無碰撞檢測，發票重疊無反應 | 實作 BBox 碰撞偵測 | resolved.33 #12 |
| 3 | C.21 | 🟡 半成品 | 用途 Textarea 無字數監控 | 計數器 + 背景變黃 | resolved.33 #21 |
| 4 | F.45 | 🔴 遺漏 | 自動排版按鈕完全不存在 | 二分搜尋自動排版 | resolved.33 #44 |
| 5 | A.8 附錄 | 🔴 遺漏 | 手改用途後再拖入新發票，無覆蓋詢問 | 對話框確認 | resolved.35 附錄 A #8 |
| 6 | D.31 | 🔴 遺漏 | 發票清單為空時，畫布無任何引導 | Empty State 遮罩 | resolved.33 #31 |
| 7 | v30 新增 | 🔴 新需求 | 發票可被隨意壓扁（寬高不等比） | 隱藏中間控制點 | v30 |
| 8 | D.25-D.28 | 🔴 遺漏 | 拖入/移除發票時不會自動重算金額、日期、用途 | Per-page 自動域計算 | resolved.33 #25-28 |
| 9 | 審核新增 | 🔴 既有Bug | 在 input/textarea 按 Backspace/Delete 會誤刪畫布發票 | 鍵盤事件 guard | 審核發現 |

---

## 1. 欄位即時高光驗證 (Field Validation Highlighting)

### 對應 v27 防禦: B.11 (Source Fix Lock), B.13 (非整數報警), B.15 (金額極限)

### 問題分析
目前 `VoucherEditorView.vue` 的驗證邏輯已存在於 `voucher.js` 的 `hasInvalidDate()`, `hasDecimalAmount()`, `hasExcessiveAmount()` 三個函式中，也有 `computed: statusText` 在工具列顯示紅字警告。但 **輸入框本身沒有任何視覺回饋**（不會爆紅/變黃），操作者常常看不到頂部那行小字提示就繼續亂填。

### 實作細節

#### [MODIFY] `frontend/src/views/VoucherEditorView.vue` — Template 區塊
在 `<div class="fields">` 裡面的 `<input>` 加上動態 CSS class:

```html
<!-- 金額欄位 -->
<input
  v-model="activePage.fields.amount"
  :class="{
    'field-error-yellow': isCurrentPageAmountDecimal,
    'field-error-red': isCurrentPageAmountExcessive
  }"
/>

<!-- 日期欄位 -->
<input
  v-model="activePage.fields.payDate"
  placeholder="YYYY-MM-DD"
  :class="{ 'field-error-red': isCurrentPageDateInvalid }"
/>
```

#### [MODIFY] `frontend/src/views/VoucherEditorView.vue` — Script 區塊
新增三個 per-page computed 屬性（不是全域的 `hasInvalidDate`，而是只看當前頁）：

```javascript
const isCurrentPageDateInvalid = computed(() => {
  const p = activePage.value
  if (!p) return false
  const payDate = p.fields?.payDate
  const hasImages = (p.images || []).length > 0
  if (!payDate && hasImages) return true
  if (!payDate) return false
  return Number.isNaN(Date.parse(payDate))
})

const isCurrentPageAmountDecimal = computed(() => {
  const amount = activePage.value?.fields?.amount
  if (!amount) return false
  return /\./.test(String(amount))
})

const isCurrentPageAmountExcessive = computed(() => {
  const amount = activePage.value?.fields?.amount
  if (!amount) return false
  const num = parseInt(String(amount), 10)
  return !Number.isNaN(num) && num > 9999999
})
```

#### [MODIFY] `frontend/src/views/VoucherEditorView.vue` — Style 區塊
新增兩個 CSS class：

> [!NOTE]
> **審核修正 Fix 6**：配色已調整為暗色主題 (Dark Theme) 相容版本。
> 原版使用 Light Theme 的 `#FFE4E1` 淡紅/`#FEF9C3` 淡黃背景，在 `background: #1e1e1e` 深色介面下對比度不足。

```css
.field-error-red {
  background-color: rgba(220, 38, 38, 0.2) !important; /* 暗色系淡紅 */
  border-color: #dc2626 !important;
  color: #fca5a5 !important;                            /* 亮紅文字 */
}

.field-error-yellow {
  background-color: rgba(202, 138, 4, 0.2) !important;  /* 暗色系淡黃 */
  border-color: #ca8a04 !important;
  color: #fde68a !important;                             /* 亮黃文字 */
}
```

---

## 2. 畫布發票碰撞偵測 (Overlap Detection)

### 對應 v27 防禦: B.12 (物理碰撞警告)

### 問題分析
目前 `applyObjectBounds()` 只檢查發票是否超出 A4 安全區邊界。沒有任何邏輯偵測兩張發票的 BBox 是否交叉重疊。v27 要求：**重疊時邊線變紅 (#FF0000)，但不鎖定產出鈕**（允許刻意堆疊）。

### 實作細節

#### [MODIFY] `frontend/src/utils/voucher.js`
新增 AABB (Axis-Aligned Bounding Box) 碰撞檢測函式：

```javascript
/**
 * 檢測兩個矩形是否重疊 (AABB Collision)
 * @param {Object} a - { x, y, w, h }
 * @param {Object} b - { x, y, w, h }
 * @returns {boolean}
 */
export function rectsOverlap(a, b) {
  return !(
    a.x + a.w <= b.x ||
    b.x + b.w <= a.x ||
    a.y + a.h <= b.y ||
    b.y + b.h <= a.y
  )
}

/**
 * 給定一組發票矩形，回傳有重疊的 jobId Set
 * @param {Array} images - [{ jobId, x, y, w, h }, ...]
 * @returns {Set<string>} 存在重疊的 jobId 集合
 */
export function findOverlappingJobIds(images = []) {
  const overlapping = new Set()
  for (let i = 0; i < images.length; i++) {
    for (let j = i + 1; j < images.length; j++) {
      if (rectsOverlap(images[i], images[j])) {
        overlapping.add(images[i].jobId)
        overlapping.add(images[j].jobId)
      }
    }
  }
  return overlapping
}
```

#### [MODIFY] `frontend/src/views/VoucherEditorView.vue`
在 `fabricCanvas.on('object:modified')` 和 `fabricCanvas.on('object:moving')` 回調中呼叫 `updateOverlapHighlight()`：

> [!NOTE]
> **審核修正 Fix 2**：碰撞偵測必須直接從 Canvas 物件取即時座標，而非讀取 `activePage.value.images`。
> 原因：`object:moving` 事件觸發時 `syncActivePageFromCanvas()` 尚未執行，`activePage.value.images` 中的座標是**舊的**。
> 直接從 `fabricCanvas.getObjects()` 取 `obj.left / obj.top / getScaledWidth()` 才是即時值。

```javascript
import { findOverlappingJobIds } from '../utils/voucher'

const updateOverlapHighlight = () => {
  if (!fabricCanvas) return

  // 直接從 Canvas 取即時座標 (不依賴 activePage.value.images，因為拖動時尚未 sync)
  const liveRects = fabricCanvas.getObjects()
    .filter(o => o?.data?.kind === 'invoice')
    .map(o => ({
      jobId: o.data.jobId,
      x: o.left,
      y: o.top,
      w: o.getScaledWidth(),
      h: o.getScaledHeight(),
    }))
  const overlappingIds = findOverlappingJobIds(liveRects)

  fabricCanvas.getObjects().forEach(obj => {
    if (obj?.data?.kind !== 'invoice') return
    const isOverlapping = overlappingIds.has(obj.data.jobId)
    obj.set('borderColor', isOverlapping ? '#FF0000' : '#22c55e')
    obj.set('stroke', isOverlapping ? '#FF0000' : null)
    obj.set('strokeWidth', isOverlapping ? 2 : 0)
  })
  fabricCanvas.requestRenderAll()
}
```

> [!NOTE]
> **審核修正 Bug 2**：除了 `object:modified` 和 `object:moving` 外，
> `addInvoiceObjectToCanvas` 的 `imageEl.onload` callback 末尾、
> `removeImage` 和 `removeSelectedOnCanvas` 末尾也要呼叫 `updateOverlapHighlight()`。
> 否則新增/刪除發票時碰撞紅框不會即時更新。

在以下 **5 處** 呼叫 `updateOverlapHighlight()`：
1. `fabricCanvas.on('object:moving')` 回調末尾
2. `fabricCanvas.on('object:modified')` 回調末尾
3. `addInvoiceObjectToCanvas` 的 `imageEl.onload` callback 內，`fabricCanvas.add(obj)` 之後
4. `removeImage` 末尾，`fabricCanvas.requestRenderAll()` 之後
5. `removeSelectedOnCanvas` 末尾，`syncActivePageFromCanvas()` 之後

---

## 3. 用途說明字數警告 (Purpose Character Count)

### 對應 v27 防禦: C.21 (用途欄位爆框黃燈)

### 問題分析
目前用途 `<textarea>` 是純文字輸入，沒有字數監聽。v27 要求超過 40 字時背景變黃，提示建議精簡。後端 `_insert_purpose` 會在 14pt→10pt 自動縮字，但前端完全沒有預警。

### 實作細節

#### [MODIFY] `frontend/src/views/VoucherEditorView.vue` — Template
替換用途的 `<textarea>` 以及在下方加入字數提示：

```html
<label>用途</label>
<div class="purpose-wrap">
  <textarea
    v-model="activePage.fields.purpose"
    rows="2"
    :class="{ 'field-error-yellow': purposeLength > 40 }"
  />
  <span class="char-count" :class="{ warn: purposeLength > 40 }">
    {{ purposeLength }} / 40 字
  </span>
</div>
```

#### [MODIFY] Script 區塊
```javascript
const purposeLength = computed(() => (activePage.value?.fields?.purpose || '').length)
```

#### [MODIFY] Style 區塊
```css
.purpose-wrap {
  position: relative;
  grid-column: 2;
}

.purpose-wrap textarea {
  width: 100%;
  box-sizing: border-box;
}

.char-count {
  position: absolute;
  bottom: 4px;
  right: 8px;
  font-size: 11px;
  color: #6b7280;
}

.char-count.warn {
  color: #ca8a04;
  font-weight: 600;
}
```

---

## 4. 自動排版演算法 (Auto-Layout)

### 對應 v27 防禦: F.45 — 二分搜尋 O(N log H) 自動排版

### 問題分析
這是 v30 盤點的**最大遺漏**。目前所有發票必須手動拖曳擺放，操作 10 張以上極度痛苦。v27 要求實作一顆按鈕，觸發後自動計算最佳統一高度，將發票等比壓縮排列進安全區。

### 演算法設計
```
輸入: images[] — 每張發票的原始寬高 (已知)、安全區 535×336 pts
目標: 找到最大的統一高度 H，使得所有發票以等比例縮放至高度 H 後，
      能在 535 pts 寬度內以「左起排列、滿行換行」的方式全部塞進安全區。

方法: Binary Search on H
  lo = 20 pt, hi = 336 pt (安全區全高)
  while hi - lo > 0.5:
    mid = (lo + hi) / 2
    totalRows = simulate_layout(images, H=mid, maxWidth=535)
    if totalRows * mid <= 336:
      lo = mid    // 可以更大
    else:
      hi = mid    // 太大了，會溢出

simulate_layout(images, H, maxWidth):
  currentRowWidth = 0
  rows = 1
  for each image:
    scaledWidth = (image.originalWidth / image.originalHeight) * H
    if currentRowWidth + scaledWidth > maxWidth:
      rows++
      currentRowWidth = scaledWidth
    else:
      currentRowWidth += scaledWidth
  return rows
```

### 實作細節

#### [MODIFY] `frontend/src/utils/voucher.js`
新增自動排版函式：

```javascript
/**
 * O(N log H) 自動排版演算法 — 二分搜尋統一高度
 * @param {Array} images - [{ jobId, originalWidth, originalHeight }]
 * @param {Object} safeZone - { x0, y0, x1, y1 }
 * @returns {Array|null} 排版後的 [{ jobId, x, y, w, h }]，若無法排版回傳 null
 */
export function autoLayoutImages(images, safeZone = { x0: 30, y0: 394, x1: 565, y1: 730 }) {
  if (!images.length) return null
  const maxWidth = safeZone.x1 - safeZone.x0
  const maxHeight = safeZone.y1 - safeZone.y0
  const GAP = 4 // 圖片間距 (pts)

  function simulateLayout(items, H) {
    let rows = 1
    let currentRowWidth = 0
    for (const item of items) {
      const scaledW = (item.originalWidth / item.originalHeight) * H
      if (currentRowWidth > 0 && currentRowWidth + GAP + scaledW > maxWidth) {
        rows++
        currentRowWidth = scaledW
      } else {
        currentRowWidth += (currentRowWidth > 0 ? GAP : 0) + scaledW
      }
    }
    return rows
  }

  // Binary search for maximum H
  let lo = 20, hi = maxHeight
  for (let i = 0; i < 50; i++) {
    const mid = (lo + hi) / 2
    const rows = simulateLayout(images, mid)
    if (rows * mid + (rows - 1) * GAP <= maxHeight) {
      lo = mid
    } else {
      hi = mid
    }
  }

  const H = Math.floor(lo)
  if (H < 20) return null  // 無法塞進去

  // 實際佈建座標
  const result = []
  let curX = safeZone.x0
  let curY = safeZone.y0

  for (const item of images) {
    const scaledW = round2((item.originalWidth / item.originalHeight) * H)
    if (curX > safeZone.x0 && curX + GAP + scaledW > safeZone.x0 + maxWidth) {
      curX = safeZone.x0
      curY += H + GAP
    }

    result.push({
      jobId: item.jobId,
      x: round2(curX),
      y: round2(curY),
      w: scaledW,
      h: H,
    })
    curX += scaledW + GAP
  }

  return result
}
```

#### [MODIFY] `frontend/src/views/VoucherEditorView.vue` — Template
在 Toolbar 區加入按鈕：

```html
<button @click="runAutoLayout" :disabled="!activePage.images.length">⚡ 自動排版</button>
```

#### [MODIFY] Script 區塊
```javascript
import { autoLayoutImages } from '../utils/voucher'

const runAutoLayout = async () => {
  if (!activePage.value || !activePage.value.images.length) return

  // 需要每張發票的原始寬高 — 從 canvas fabric objects 取得
  const canvasObjects = fabricCanvas.getObjects().filter(o => o?.data?.kind === 'invoice')
  const imagesWithDimensions = canvasObjects.map(obj => ({
    jobId: obj.data.jobId,
    originalWidth: obj.width,    // fabric.Image 原始像素寬
    originalHeight: obj.height,  // fabric.Image 原始像素高
  }))

  const layoutResult = autoLayoutImages(imagesWithDimensions, SAFE_ZONE)
  if (!layoutResult) {
    alert('發票過多或尺寸過大，自動排版無法在安全區內排下。請手動微調或分頁。')
    return
  }

  // 套用排版結果
  activePage.value.images = layoutResult

  // 更新 canvas 物件座標
  layoutResult.forEach(rect => {
    const obj = canvasObjects.find(o => o.data.jobId === rect.jobId)
    if (obj) {
      // 審核修正 Fix 5：統一使用高度比作為縮放值，確保等比（消除浮點微差）
      const s = rect.h / obj.height
      obj.set({
        left: rect.x,
        top: rect.y,
        scaleX: s,
        scaleY: s,
      })
      obj.setCoords()
    }
  })
  fabricCanvas.requestRenderAll()
  updateOverlapHighlight()
}
```

---

## 5. 用途手動覆蓋保護對話框 (Purpose Override Confirmation)

### 對應 v27 防禦: A.8 附錄第 8 情境

### 問題分析
目前 `addInvoiceToActivePage()` 在拖入新發票時，不會檢查使用者是否手動修改過用途欄位。若已手動修改，拖入新發票後自動重算用途會蓋掉辛苦打的字。v27 要求彈出確認框。

### 實作細節

#### [MODIFY] `frontend/src/views/VoucherEditorView.vue`
修改 `addInvoiceToActivePage` 函式：

```javascript
const addInvoiceToActivePage = (invoice) => {
  if (!activePage.value || invoiceUsageMap.value[invoice.jobId]) return

  // === 用途覆蓋保護 ===
  if (activePage.value.fields.isManuallyEdited && activePage.value.fields.purpose?.trim()) {
    const confirmed = window.confirm(
      '發現新發票。您已手動編輯過「用途說明」，是否以新的用途覆蓋您的編輯？\n\n' +
      '點選「確定」→ 以系統自動產生的用途覆蓋\n' +
      '點選「取消」→ 保留您手動編輯的內容'
    )
    if (!confirmed) {
      // 保留手動用途，但仍然加入發票到畫布
      _doAddInvoice(invoice, /* skipPurposeUpdate= */ true)
      return
    }
    // 審核修正 Bug 1：使用者按「確定」表示同意覆蓋，必須清除手動旗標
    // 否則後續 recalculatePageFields 會因 isManuallyEdited=true 而跳過用途拼接
    activePage.value.fields.isManuallyEdited = false
  }

  _doAddInvoice(invoice, /* skipPurposeUpdate= */ false)
}

const _doAddInvoice = (invoice, skipPurposeUpdate) => {
  const offset = activePage.value.images.length * 20
  const newRect = clampImageRect({
    jobId: invoice.jobId,
    x: 30 + offset,
    y: 394 + offset,
    w: 180,
    h: 120,
  })
  activePage.value.images.push(newRect)
  activePage.value.fields.receiptCount = String(activePage.value.images.length)

  // 審核修正 Bug 1：recalculatePageFields 已取代此段邏輯
  // 當 skipPurposeUpdate=true 時，isManuallyEdited 仍為 true，recalculatePageFields 會自動跳過用途
  // 當 skipPurposeUpdate=false 時，isManuallyEdited 已被清除，recalculatePageFields 會自動拼接用途
  recalculatePageFields(activePage.value)

  addInvoiceObjectToCanvas(newRect, activePageIndex.value, renderToken.value)
}
```

並在用途 `<textarea>` 上新增 `@input` 事件監聽，標記手動編輯旗標：

```html
<textarea
  v-model="activePage.fields.purpose"
  rows="2"
  @input="onPurposeManualEdit"
  :class="{ 'field-error-yellow': purposeLength > 40 }"
/>
```

```javascript
const onPurposeManualEdit = () => {
  if (activePage.value) {
    activePage.value.fields.isManuallyEdited = true
  }
}
```

---

## 6. 全無發票時的 Empty State 畫布遮罩

### 對應 v27 防禦: D.31 (Empty State 禁用畫布)

### 問題分析
當專案裡完全沒有 `status='done'` 的發票時，左邊清單空空如也，右邊畫布卻照常顯示。沒有任何引導，操作者不知道該做什麼。

### 實作細節

#### [MODIFY] `frontend/src/views/VoucherEditorView.vue` — Template
在 `<div class="canvas-wrap">` 上方或內部新增 Empty State overlay：

```html
<div class="canvas-wrap" :class="{ 'canvas-disabled': isEmptyProject }">
  <div v-if="isEmptyProject" class="empty-state-overlay">
    <div class="empty-state-content">
      <span class="empty-icon">📄</span>
      <h3>尚無可用發票</h3>
      <p>請先回到專案頁面上傳發票，完成 VLM 辨識與人工審核後，<br/>發票才會出現在這裡。</p>
      <button @click="goBack">← 返回專案</button>
    </div>
  </div>
  <canvas ref="canvasRef"></canvas>
</div>
```

#### [MODIFY] Script 區塊
```javascript
const isEmptyProject = computed(() => invoices.value.length === 0)
```

> [!NOTE]
> **審核修正 Fix 4**：`pointer-events: none` 只設在 canvas 元素上，而非整個 `.canvas-disabled` wrap。
> 這樣 overlay 的按鈕不需要額外用 `pointer-events: all` 覆蓋父級，更安全。

#### [MODIFY] Style 區塊
```css
.canvas-disabled {
  position: relative;
  opacity: 0.5;
}

.canvas-disabled canvas {
  pointer-events: none;  /* 只禁用 canvas 本身，不影響 overlay 按鈕 */
}

.empty-state-overlay {
  position: absolute;
  inset: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.6);
  pointer-events: all;
}

.empty-state-content {
  text-align: center;
  color: #f3f4f6;
}

.empty-icon {
  font-size: 48px;
}

.empty-state-content h3 {
  margin: 12px 0 8px;
  font-size: 18px;
}

.empty-state-content p {
  font-size: 13px;
  color: #9ca3af;
  line-height: 1.6;
}

.empty-state-content button {
  margin-top: 16px;
  pointer-events: all;
}
```

---

## 7. 等比例縮放鎖定 (Aspect Ratio Lock)

### 對應: v30 新需求 — 發票不可被壓扁

### 問題分析
目前 `addInvoiceObjectToCanvas` 裡的 `fabric.Image` 沒有限制縮放方式，使用者可以拖動上下左右邊的控制點將發票壓扁或拉長。

> [!CAUTION]
> **審核修正 Bug 4**：Fabric.js v7 已移除 per-object 的 `lockUniScaling` 屬性。
> 等比縮放在 v7 中是 **Canvas 級別** 的設定 `canvas.uniformScaling`（預設 `true`）。
> 因此我們的 Canvas 已經自帶等比縮放！只需隱藏中間控制點 (mt/mb/ml/mr) 即可。

### 實作細節

#### [MODIFY] `frontend/src/views/VoucherEditorView.vue`
修改 `addInvoiceObjectToCanvas` 裡 `new fabric.Image()` 的選項：

```javascript
const obj = new fabric.Image(imageEl, {
  left: imageData.x,
  top: imageData.y,
  originX: 'left',
  originY: 'top',
  lockRotation: true,
  cornerColor: '#2563eb',
  borderColor: '#22c55e',
  transparentCorners: false,
  // Fabric.js v7: uniformScaling 是 Canvas 級別屬性（預設 true），不需 per-object 設定
})
// 隱藏上下左右中間控制點，只留四角 → 物理上防止非等比縮放
obj.setControlsVisibility({ mt: false, mb: false, ml: false, mr: false })
```

同時修改 `applyObjectBounds` 以維持等比性：

> [!NOTE]
> **審核修正 Fix 1**：新增 `kind !== 'invoice'` guard clause。
> 現有代碼中的 `makePlaceholderGroup()` 會建立 `fabric.Group` 類型的物件，
> 這種物件的 `width/height` 語義不同於 `fabric.Image`。
> 不加 guard 的話 `uniformScale = clamped.w / obj.width` 會算出錯誤值。

```javascript
const applyObjectBounds = (obj) => {
  // Guard: 只處理 invoice 類型物件，背景/安全區參考線不動
  if (obj?.data?.kind !== 'invoice') return

  const aspectRatio = obj.width && obj.height ? obj.width / obj.height : 1
  let w = obj.getScaledWidth()
  let h = obj.getScaledHeight()
  const maxW = SAFE_ZONE.x1 - SAFE_ZONE.x0
  const maxH = SAFE_ZONE.y1 - SAFE_ZONE.y0

  // 等比縮放到安全區內
  if (w > maxW) {
    w = maxW
    h = w / aspectRatio
  }
  if (h > maxH) {
    h = maxH
    w = h * aspectRatio
  }

  const clamped = clampImageRect({
    x: obj.left, y: obj.top, w, h,
  }, SAFE_ZONE)

  const uniformScale = clamped.w / obj.width
  obj.set({
    left: clamped.x,
    top: clamped.y,
    scaleX: uniformScale,
    scaleY: uniformScale,
  })
  obj.setCoords()
}
```

---

## 8. Per-Page 欄位自動域計算 (Auto-Recalculate Fields)

### 對應 v27 防禦: D.25 (Per-page 獨立域運算), D.26 (人工修正優先權), D.27 (用途去重拼接), D.28 (最晚日期選取器)

### 問題分析
目前每當使用者拖入或移除發票時，只有 `receiptCount` 會自動更新。但 v27 要求以下欄位也必須自動計算：
- **金額 (amount)**：加總當頁所有發票的金額
- **日期 (payDate)**：取當頁所有發票中最晚的有效日期
- **用途 (purpose)**：去重拼接當頁發票的 `items[].category`（除非使用者已手動修改）

目前代碼的 `GET /template` API 已經回傳每張發票的 `result` 資料（包含 `manualResult` 或 `vlmResult`），但前端完全沒有利用這些資料來自動填充欄位。

### 實作細節

#### [MODIFY] `frontend/src/views/VoucherEditorView.vue` — Script 區塊
新增 `recalculatePageFields` 自動域計算函式：

```javascript
/**
 * 依照當頁 images[] 重新計算金額、日期、用途
 * @param {Object} page - 當前頁面物件
 */
const recalculatePageFields = (page) => {
  if (!page) return
  const pageImages = page.images || []
  page.fields.receiptCount = String(pageImages.length)

  // 從 invoices ref 找出當頁發票的 VLM/Manual 結果
  const pageInvoices = pageImages.map(img =>
    invoices.value.find(inv => inv.jobId === img.jobId)
  ).filter(Boolean)

  // === D.25: 金額加總 ===
  let totalAmount = 0
  for (const inv of pageInvoices) {
    const result = inv.result || {}
    const amount = parseFloat(result.total_amount || result.amount || '0')
    if (!Number.isNaN(amount)) totalAmount += amount
  }
  // D.14: 不做 Math.ceil，保留原始值讓驗證邏輯處理
  page.fields.amount = String(totalAmount || '')

  // === D.28: 最晚日期 ===
  // 審核修正 Fix 3：VLM JSON 只有 `date` 欄位 (YYYY-MM-DD)，沒有 `pay_date`
  const validDates = pageInvoices
    .map(inv => {
      const result = inv.result || {}
      return result.date || ''
    })
    .filter(d => d && !Number.isNaN(Date.parse(d)))
    .sort()
  page.fields.payDate = validDates.length ? validDates[validDates.length - 1] : ''

  // === D.27: 用途去重拼接 (除非手動修改) ===
  // 審核修正 Bug 5：VLM JSON 的 items 結構是 {description, quantity, price}
  // 手寫收據是 {name, qty, price, total}。都沒有 `category` 欄位！
  // 改用 description || name 來拼接用途
  if (!page.fields.isManuallyEdited) {
    const descriptions = new Set()
    for (const inv of pageInvoices) {
      const result = inv.result || {}
      const items = result.items || []
      for (const item of items) {
        const desc = item.description || item.name || ''
        if (desc) descriptions.add(desc)
      }
    }
    page.fields.purpose = [...descriptions].join('、')
  }
}
```

#### 呼叫時機

> [!NOTE]
> **審核修正 Bug 3**：`recalculatePageFields` 只在發票數量增減時呼叫，
> 不再掛在 `syncActivePageFromCanvas` 裡（否則單純拖曳移位也會跑一遍無意義的金額加總循環）。

在以下 **兩處** 呼叫 `recalculatePageFields(activePage.value)`：
1. `_doAddInvoice` 內，`activePage.value.images.push(newRect)` 之後
2. `removeImage` / `removeSelectedOnCanvas` 移除發票後

---

## 9. 鍵盤事件防衝突 (Keyboard Event Guard)

### 對應: 審核新發現的既有 Bug

### 問題分析
現有代碼在 `onMounted` 中註冊了全域 `keydown` 監聽器：
```javascript
keyboardHandler = (event) => {
  if (event.key === 'Delete' || event.key === 'Backspace') {
    removeSelectedOnCanvas()
  }
}
window.addEventListener('keydown', keyboardHandler)
```
當使用者在用途 `<textarea>`、日期 `<input>`、金額 `<input>` 中編輯文字並按 Backspace 或 Delete 時，這個 handler 會放火，僅意地刪除畫布上被選中的發票。

### 實作細節

#### [MODIFY] `frontend/src/views/VoucherEditorView.vue` — Script 區塊
修改 `keyboardHandler` 加上 focus guard：

```javascript
keyboardHandler = (event) => {
  // 審核修正 Bug 6：在 input/textarea 中輸入時不應觸發畫布刪除
  const tag = event.target?.tagName?.toLowerCase()
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return

  if (event.key === 'Delete' || event.key === 'Backspace') {
    removeSelectedOnCanvas()
  }
}
```

---

## 實作順序 (Execution Order)

以依賴關係排序，建議按以下順序實作：

| 步驟 | 任務 | 估計工作量 | 依賴 |
|:---|:---|:---|:---|
| **Step 0** | #9 鍵盤事件防衝突 | ⭐ 簡單 (2 min) | 無 |
| **Step 1** | #7 等比例縮放鎖定 | ⭐ 簡單 (5 min) | 無 |
| **Step 2** | #1 欄位即時高光驗證 | ⭐ 簡單 (10 min) | 無 |
| **Step 3** | #3 用途字數警告 | ⭐ 簡單 (10 min) | 無 |
| **Step 4** | #6 Empty State 遮罩 | ⭐ 簡單 (10 min) | 無 |
| **Step 5** | #8 Per-page 自動域計算 | ⭐⭐ 中等 (20 min) | 需 invoices 的 result 資料 |
| **Step 6** | #2 碰撞偵測 | ⭐⭐ 中等 (20 min) | 需先完成 syncActivePageFromCanvas |
| **Step 7** | #5 用途覆蓋保護對話框 | ⭐⭐ 中等 (15 min) | 需 #8 (自動域計算) |
| **Step 8** | #4 自動排版演算法 | ⭐⭐⭐ 複雜 (30 min) | 需 #7 (等比鎖定) + #2 (碰撞) |

**預計總工時: ~122 分鐘 (純實作)**

---

## 驗證計畫 (Verification Plan)

### 功能驗證 Checklist

- [ ] **#1 高光驗證**: 在日期欄輸入 `abc`，確認欄位背景變暗紅 (`rgba(220,38,38,0.2)`)；金額輸入 `123.45`，確認背景變暗黃 (`rgba(202,138,4,0.2)`)；金額輸入 `10000000`，確認背景變暗紅。
- [ ] **#2 碰撞偵測**: 拖動兩張發票使其完全重疊，確認兩張發票的邊框均變紅色 (#FF0000)；拉開後邊框恢復綠色 (#22c55e)。確認產出按鈕**不被鎖定**。**新增發票到已有發票的位置，確認紅框立即亮起（不需拖曳才觸發）。**
- [ ] **#3 字數警告**: 在用途欄位輸入超過 40 字的文字，確認背景變黃且角落出現計數器 `45 / 40 字`。
- [ ] **#4 自動排版**: 放入 3-5 張不同大小的發票，點擊「⚡ 自動排版」，確認發票被等比排列在安全區內且不超出邊界。
- [ ] **#5 覆蓋對話框**: 先在用途欄手動輸入文字，再拖入新發票，確認彈出確認對話框。選「取消」確認用途不被覆蓋。**選「確定」確認用途被自動覆蓋（驗證 isManuallyEdited 重置）。**
- [ ] **#6 Empty State**: 在無已完成發票的專案中開啟 Voucher Editor，確認畫布被遮罩覆蓋，顯示「尚無可用發票」引導文字。
- [ ] **#7 等比縮放**: 嘗試拖動發票的角點縮放，確認保持寬高比不變；確認只有四個角有控制點，上下左右中間沒有。
- [ ] **#8 自動域計算**: 拖入兩張發票（金額分別為 100 和 200），確認金額欄自動顯示 300、日期欄自動取最晚日期、用途欄自動拼接品名（`description`/`name`）。移除一張後確認所有欄位即時更新。
- [ ] **#9 鍵盤防衝突**: 在用途 textarea 中按 Backspace 刪除文字，確認不會誤觸畫布刪除發票。在日期 input 中按 Delete 鍵，確認不會誤刪畫布物件。

### 後端不受影響確認
本次所有變更均限於前端（`VoucherEditorView.vue` + `voucher.js`），後端無需修改。`POST /generate` 接收到的 Layout JSON 結構不變，PDF 產出流程不受影響。

---

## 附錄：歷史計畫溯源 (Historical Traceability)

> 詳細索引請參閱 [resolved_plans_index.md](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/dev_data/plan/voucher_editor_plan/resolved_plans_index.md)

本計畫的 9 個缺失項目均可追溯至以下歷史計畫文件：

| V32 項目 | 首次出現 | 最終規格定稿 | 現實狀態 |
|:---|:---|:---|:---|
| #1 欄位高光 | resolved.27 Fix 32 (TWD Ceiling + 標黃) | v27 B.11/B.13 | 驗證邏輯存在但視覺回饋缺失 |
| #2 碰撞偵測 | resolved.33 #12 (Anti-Overlap) | v27 B.12 | 完全未實作 |
| #3 字數警告 | resolved.33 #21 (爆框黃燈) | v27 C.21 | 完全未實作 |
| #4 自動排版 | resolved.33 #44 (二分搜尋) | v27 F.45 | 按鈕與算法均未實作 |
| #5 覆蓋保護 | resolved.35 附錄 A 情境 8 | v27 A.8 情境 8 | 完全未實作 |
| #6 Empty State | resolved.33 #31 (清單篩選邊界) | v27 D.31 | 完全未實作 |
| #7 等比鎖定 | v30 Reality Check 新發現 | v30 | 完全未實作 |
| #8 自動域計算 | resolved.33 #25-28 (Per-page 運算) | v27 D.25-D.28 | 僅 receiptCount 有自動更新 |
| #9 鍵盤防衝突 | V32 審核發現 | — | Backspace/Delete 會誤刪畫布物件 |
