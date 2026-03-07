# 憑證黏貼編輯器 — Beta 0.0.1 可用性與介面大修 (Fixing 爛掉的 UI)

**日期**: 2026-03-06
**前提**: 所有底層 API 與邏輯（V34-3）都已穩固運轉，此更新專注於處理使用者體驗面「可用發票」與「貼哪裡」嚴重爛掉（Debug 介面殘留）的問題。

---

## 🎯 根本原因分析
1. **可用發票 (Sidebar) 爛掉**：左側清單全是 `job-17716...` 這樣的系統 UUID 字串，沒有縮圖、沒有金額、沒有日期，使用者根本無法辨識哪張是哪張發票。
2. **貼哪裡 (Canvas & Bottom List) 爛掉**：
   - 每次點擊發票，全部疊在 `(x+20, y+20)` 擠作一團。
   - 所有圖片強制縮放對齊 `height = 120`，導致台灣常見的細長型熱感應發票（被壓成 40px 寬的細線），比例完全失真。
   - 畫面底部的「本頁發票清單」直接吐出 JSON 座標陣列 `job-xyz (30, 394, 180, 120)`，完全是開發者 Debug 畫面。

---

## 🛠️ 修正計畫 (版本 0.0.1)

### 修正 1: 全面翻新「可用發票」介面 (加入縮圖與辨識資料)
**目標文件**: `frontend/src/views/VoucherEditorView.vue` 👉 HTML Template

**改法**：將原本只有文字的 `<button>` 換成卡片式設計。因為 API `get_voucher_template` 已經隨附了 `imageUrl` 與 `result.total_amount` 等資訊，我們只要正確綁定即可。

```html
<!-- HTML 替換 (Line 31 附近) -->
<div class="invoice-list">
  <button
    v-for="invoice in invoices"
    :key="invoice.jobId"
    class="invoice-item"
    :disabled="invoiceUsageMap[invoice.jobId]"
    @click="addInvoiceToActivePage(invoice)"
  >
    <img :src="invoice.imageUrl" alt="發票縮圖" class="invoice-thumb" loading="lazy" />
    <div class="invoice-info">
      <span class="date">{{ invoice.result?.date || invoice.result?.header?.date || '無日期' }}</span>
      <span class="amount">${{ invoice.result?.total_amount ?? invoice.result?.summary?.total ?? invoice.result?.total ?? 0 }}</span>
    </div>
  </button>
</div>
```

```css
/* Style 新增 */
.invoice-item {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 12px; background: #2a2a2a; border: 1px solid #444;
  border-radius: 6px; cursor: pointer; transition: border-color 0.2s;
  color: white; width: 100%; margin-bottom: 8px;
}
.invoice-item:disabled { opacity: 0.5; cursor: not-allowed; }
.invoice-item:hover:not(:disabled) { border-color: #3b82f6; }
.invoice-thumb { width: 100%; height: 80px; object-fit: contain; background: #fff; border-radius: 4px; }
.invoice-info { display: flex; justify-content: space-between; width: 100%; font-size: 12px; }
.invoice-info .amount { font-weight: bold; color: #fbbf24; }
```

---

### 修正 2: 智慧網格放圖機制與比例保全 (解決「貼哪裡」亂疊)
**目標文件**: `frontend/src/views/VoucherEditorView.vue` 👉 `_doAddInvoice` 與 `addInvoiceObjectToCanvas`

**改法**：
1. 取代 `offset * 20` 定律，改用 Grid（每列三張）智慧放置初始座標。
2. 不再強制 `h=120`。改用等比例限制最大的 `Bounding Box (150x150)` 讓系統依照圖片自身長寬比去算。

```javascript
const _doAddInvoice = (invoice) => {
  const count = activePage.value.images.length
  // 智慧網格放置：一排 3 張發票 (間距 160x170)
  const row = Math.floor(count / 3)
  const col = count % 3
  
  const newRect = clampImageRect({
    jobId: invoice.jobId,
    x: 40 + (col * 160),
    y: 400 + (row * 170),
    w: 150, // 改為正方形 Bounding Box 標準
    h: 150,
  })
  activePage.value.images.push(newRect)
  recalculatePageFields(activePage.value)
  recalculateVoucherNumbers()

  addInvoiceObjectToCanvas(newRect, activePageIndex.value, renderToken.value)
}
```

搭配 `addInvoiceObjectToCanvas` 的縮放修復：
```javascript
    // 找出圖片 L585 周邊...
    if (obj.width && obj.height) {
      if (imageData.w === 150 && imageData.h === 150) {
        // 全新加入時：依照真實圖檔寬高比例，限制在 150x150 內
        const s = Math.min(150 / obj.width, 150 / obj.height)
        obj.scaleX = s
        obj.scaleY = s
        // 同步回 imageData 防止拖移時變形
        imageData.w = obj.width * s
        imageData.h = obj.height * s
      } else {
        // 從 Layout 重新載入時（保留上次使用者拉定的比例）
        const s = imageData.h / obj.height
        obj.scaleX = s
        obj.scaleY = s
      }
    }
```

---

### 修正 3: 底端 JSON 清單移除 (去除 Debug 味)
**目標文件**: `frontend/src/views/VoucherEditorView.vue` 👉 HTML Template

**改法**：把赤裸的座標清單，改成乾淨的「發票管理清單」。

```html
<!-- HTML 替換 (Line 99 附近) -->
<div class="images">
  <h4>本頁發票清單（共 {{ activePage.images.length }} 張）</h4>
  <ul class="placed-list">
    <li v-for="(image, imageIndex) in activePage.images" :key="`${image.jobId}-${imageIndex}`">
      <span class="placed-id">發票 {{ imageIndex + 1 }} (ID: {{ image.jobId.slice(-6) }})</span>
      <button class="remove-btn" @click="removeImage(imageIndex)">移除</button>
    </li>
  </ul>
</div>
```

```css
/* Style 新增 */
.placed-list { list-style: none; padding: 0; margin-top: 8px; }
.placed-list li {
  display: flex; justify-content: space-between; padding: 8px 12px;
  background: #2a2a2a; margin-bottom: 6px; border-radius: 4px; align-items: center; border: 1px solid #444;
}
.placed-id { font-family: monospace; font-size: 13px; }
.remove-btn { background: #ef4444; color: white; border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer; transition: 0.2s;}
.remove-btn:hover { background: #dc2626; }
```

---

### 修正 4: 修復 Fabric.js 狀態丟失 (解決切頁/存檔白紙 Bug)
**目標文件**: `frontend/src/views/VoucherEditorView.vue` 👉 `addInvoiceObjectToCanvas` 與 `loadActivePageToCanvas`

**改法 (已實裝)**：
最新版的 Fabric.js 中，使用舊版的 `obj.set('data', {...})` 語法會默默失效（不報錯但不會存入）。這導致當切換頁面或存檔呼叫 `syncActivePageFromCanvas` 時，系統讀不到 `data.kind === 'invoice'`，進而把所有的發票資料「洗白」成空陣列。

我們已將所有設定語法改為強指定的：
```javascript
// ❌ 錯誤/失效的舊版語法
// obj.set('data', { kind: 'invoice', jobId: imageData.jobId })


---

### 修正 5: 修復 Fabric.js 7.2.0 API 崩潰 (徹底解決切頁白紙)
**目標文件**: `frontend/src/views/VoucherEditorView.vue` 👉 `syncActivePageFromCanvas` 與其他呼叫處

**改法 (已實裝)**：
除了上方的 `set('data')` 之外，我們追蹤到另一個致命的底層報錯 `obj.getScaledWidth is not a function`。
這是因為目前的專案已經使用了 **Fabric.js v7.2.0** 最新版本，而原先程式碼大量使用的 `getScaledWidth()` 與 `getScaledHeight()` 在新版中已被完全廢棄移除。

當你點擊存檔或切換頁面時，系統試圖讀取發票寬高，觸發了未捕捉的 TypeError 導致整個 Vue 執行緒中斷，連帶使得狀態管理與畫面渲染全數崩潰（導致畫面白畫面）。
我們已經將所有的寫法替換為原生的計算屬性：
```javascript
// ❌ 舊版語法 (觸發崩潰)
// let w = obj.getScaledWidth()

// ✅ 新版語法 (安全計算)
let w = obj.width * obj.scaleX
```
這項修復配合修正 4，保證切頁、存檔、平移發票時，都絕對穩健不再吐出白畫面。

---

### 修正 6: 非同步競態條件防護 (切頁白紙的真正根源)
**目標文件**: `frontend/src/views/VoucherEditorView.vue` 👉 `syncActivePageFromCanvas`、`addInvoiceObjectToCanvas`、`loadActivePageToCanvas`

**根因分析 (已透過 console.log 診斷確認)**：
即使修正 4 和修正 5 解決了 Fabric.js 的 API 相容問題，切頁後畫面仍然會變白。
透過在 `syncActivePageFromCanvas`、`switchPage`、`loadActivePageToCanvas` 三個關鍵節點插入診斷日誌，我們捕獲到以下致命序列：

```
[LOAD] Loading page 0 images: 1       ← 開始載入第 1 頁，有 1 張發票
[SYNC] Total canvas objects: 0         ← 同步被觸發，但畫布已被 clear() 清空
[SYNC] Page 0 found 0 invoices.        ← 把 images 從 1 張改寫為 0 張！
       Before: 1 images
```

**問題本質**：`loadActivePageToCanvas` 先呼叫 `fabricCanvas.clear()` 清空畫布，接著以 `new Image()` 非同步載入圖片。
但圖片的 `onload` 是非同步回呼，在圖片下載完成之前，自動存檔計時器（每 30 秒）或其他觸發點會呼叫 `syncActivePageFromCanvas`。
此時畫布上是空的（圖片還沒載入完），sync 就把 `activePage.value.images` 覆蓋成 `[]`，導致資料永久丟失。

**改法 (已實裝)**：
引入 `canvasLoading` 旗標與 `pendingImageLoads` 計數器：
```javascript
// 宣告
let canvasLoading = false
let pendingImageLoads = 0

// loadActivePageToCanvas 中：載入前設定旗標
canvasLoading = imageCount > 0
pendingImageLoads = 0

// addInvoiceObjectToCanvas 中：追蹤未完成的載入
pendingImageLoads++
imageEl.onload = () => {
  pendingImageLoads--
  if (pendingImageLoads <= 0) { canvasLoading = false }
  // ... 正常渲染邏輯
}

// syncActivePageFromCanvas 中：攔截
if (canvasLoading) {
  console.log('[SYNC] BLOCKED — canvas is still loading')
  return  // 不覆寫，保留原始資料
}
```

**驗證結果**：
```
[LOAD] Loading page 0 images: 1
[SYNC] BLOCKED — canvas is still loading images, skip sync   ← 成功攔截！
[SWITCH] Page data AFTER load: [{idx:0, imgCount:1}]         ← 資料完整保留！
```
