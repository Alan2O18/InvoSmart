# 憑證黏貼編輯器 — Beta 0.0.2 產出 PDF 數值寫入、下載與文字預覽

**日期**: 2026-03-07
**狀態**: 單一可執行版本
**前提**: V0.0.1 介面與防呆存檔都已穩固。使用者回報：「不會往黏貼單上面寫日期、總價、預算組別、發票張數，目前只有貼發票」。

---

## 🎯 根本原因分析 (Root Cause)

經過完整的端到端程式碼追蹤，我們確認真正的問題不是「後端沒寫字」，而是「使用者下載到錯的檔案，且前端畫面沒有即時預覽」。

1. **後端 `VoucherGenerator` 早已實裝欄位寫入**
   - `backend/engine/voucher_generator.py` 的 `generate_from_layout()` 已經會把 `voucherNo`、`budgetItem`、`amount`、`purpose`、`receiptCount`、`payDate` 寫進 PDF。
   - `kaiu.ttf` 已可被 PyMuPDF 正常使用。

2. **編輯器內「產出 PDF」目前不會真正下載**
   - `frontend/src/views/VoucherEditorView.vue` 呼叫 `/api/voucher/{id}/generate` 後，只顯示成功訊息。
   - 使用者看不到下載行為，會誤以為沒產出成功。

3. **專案頁仍保留舊版「快速產生黏貼紙」入口**
   - `frontend/src/views/ProjectDetailView.vue` 仍呼叫舊 API `/api/projects/{id}/generate-voucher-pdf`。
   - 舊 API 只貼圖片，不寫欄位文字，導致使用者拿到的 PDF 看起來像是「沒寫日期、沒寫金額」。

4. **前端沒有 WYSIWYG 文字預覽層**
   - 使用者在欄位中輸入的 `voucherNo`、`amount`、`payDate` 等資料，畫布上完全看不到最終落點。
   - 使用者無法確認內容是否會被正確輸出到 PDF。

---

## ✅ 本版目標

Beta 0.0.2 一次完成以下三件事：

1. 編輯器內產出的 PDF 直接下載到瀏覽器。
2. 專案頁移除舊版錯誤入口，避免再下載到錯的 PDF。
3. Voucher Editor Canvas 增加即時文字預覽，讓畫面與最終 PDF 對齊。

---

## 🛠️ 修正計畫 (版本 0.0.2)

### 修正 1: 後端 `/generate` 直接回傳 PDF 檔案串流 (FileResponse)
**目標文件**: `backend/routers/voucher.py`

將目前的 JSON 回應改成直接回傳 PDF 二進位檔：

```python
from fastapi.responses import FileResponse

    return FileResponse(
        path=output_path,
        filename=filename,
        media_type="application/pdf"
    )
```

#### 補充要求

1. 不再回傳 `{ "pdfUrl": ..., "filename": ... }` JSON。
2. 產出的檔名沿用現有 `filename` 即可，例如 `voucher_1700000000.pdf`。
3. 例外處理邏輯維持不變，只改成功回應型別。

---

### 修正 2: 後端新增楷體字型路由
**目標文件**: `backend/routers/voucher.py`

新增字型靜態下載路由，提供前端 Canvas 預覽與後端 PDF 同一份字型來源：

```python
@router.get("/fonts/kaiu.ttf")
async def get_kaiu_font():
    settings = get_voucher_settings()
    font_path = settings["font_ttf_path"]
    return FileResponse(path=font_path, media_type="font/ttf")
```

#### 補充要求

1. 路由位置固定為 `/api/voucher/fonts/kaiu.ttf`。
2. 若檔案不存在，沿用既有 router 風格拋出適當錯誤即可。

---

### 修正 3: 前端 API 支援 Blob 下載
**目標文件**: `frontend/src/services/api.js`

為 `generateVoucherFromLayout` 補上 `responseType: 'blob'`：

```javascript
generateVoucherFromLayout(projectId, payload) {
  return api.post(`/api/voucher/${projectId}/generate`, payload, {
    responseType: 'blob'
  })
},
```

#### 補充要求

1. 舊版 `generateVoucherPdf(projectId)` API 方法可以先保留。
2. 本版只移除 UI 入口，不必強制刪掉舊 service method。

---

### 修正 4: 前端編輯器實作「真・下載」觸發機制
**目標文件**: `frontend/src/views/VoucherEditorView.vue`

修改 `generatePdf()`，由 blob response 觸發瀏覽器下載。

#### 4A. 檔名處理原則

後端一旦改成 `FileResponse`，前端不能再依賴 `response.data.filename`。正確做法：

1. 優先讀 `response.headers['content-disposition']`
2. 從 header 解析檔名
3. 若解析失敗，fallback 成 `Voucher_${projectId}.pdf`

#### 4B. 下載邏輯

```javascript
const getDownloadFilename = (headers, fallback) => {
  const disposition = headers?.['content-disposition'] || headers?.['Content-Disposition'] || ''
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1])
    } catch {
      return utf8Match[1]
    }
  }
  const plainMatch = disposition.match(/filename="?([^";]+)"?/i)
  return plainMatch?.[1] || fallback
}

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
    const filename = getDownloadFilename(response.headers, `Voucher_${projectId}.pdf`)
    const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    console.error('generate failed', error)
    alert('產出失敗，請檢查欄位格式與發票內容')
  }
}
```

#### 補充要求

1. 不再保留 `alert(response.data.filename)` 這條舊路徑。
2. 仍然維持空頁過濾與 `payDate` 正規化。

---

### 修正 5: 刪除專案頁舊版「快速產生黏貼紙」按鈕
**目標文件**: `frontend/src/views/ProjectDetailView.vue`

直接刪除該按鈕及其對應的 `generateVoucherPdf` 函數，避免使用者下載到不含欄位數值的舊版 PDF。

#### 補充要求

1. 保留「開啟憑證編輯器」按鈕。
2. 不再從 Project Detail 提供舊版 PDF 下載入口。

---

### 修正 6: 前端 Canvas 即時預覽文字 (WYSIWYG — 所見即所得)
**目標文件**: `frontend/src/views/VoucherEditorView.vue`

本修正讓畫布上直接顯示與後端 PDF 相同位置的文字內容。

#### 6A. 字型載入策略

前端畫布必須優先使用與後端 PDF 完全相同的 `kaiu.ttf`，但字型預載失敗不能阻斷整個編輯器。

```javascript
const previewFontFamily = ref('serif')

const loadKaiuFont = async () => {
  try {
    const fontUrl = `${api.defaults?.baseURL || window.location.origin}/api/voucher/fonts/kaiu.ttf`
    const kaiuFont = new FontFace('KaiU', `url(${fontUrl})`)
    await kaiuFont.load()
    document.fonts.add(kaiuFont)
    previewFontFamily.value = 'KaiU'
  } catch (error) {
    console.warn('KaiU font preload failed, fallback to default preview font', error)
    previewFontFamily.value = 'serif'
  }
}
```

#### 補充要求

1. 不要硬編 `http://localhost:8000`。
2. 字型載入失敗時只 `console.warn`，不要中斷 `onMounted()`。
3. `previewFontFamily` 用於所有 canvas 文字預覽物件。

#### 6B. 前端 `toRocDate()` helper

原計畫中的 `toRocDate()` 目前前端不存在，必須補上，邏輯需與後端 `VoucherGenerator._to_roc_date()` 對齊。

```javascript
const toRocDate = (value) => {
  const iso = normalizeDateToISO(value)
  if (!iso) return ''
  const match = iso.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!match) return ''
  const [, year, month, day] = match
  return `${Number(year) - 1911}/${month}/${day}`
}
```

#### 6C. 座標修正 (PyMuPDF baseline → Fabric.js top-left)

> [!IMPORTANT]
> PyMuPDF `insert_text(point)` 中的 `point` 是文字的左下角基線 (baseline)。
> Fabric.js `Text` 的 `left/top` 是文字左上角。
> 因此普通單行文字要做 `fabric_top = fitz_y - fontSize` 的換算。

後端座標 → 前端座標對應表：

| 欄位 | 後端 fitz 座標 | 前端 fabric 座標 | 說明 |
|------|---------------|-----------------|------|
| `voucherNo` | `(78, 238)` | `left=78, top=226` | `238 - 12` |
| `budgetItem` | `(78, 208)` | `left=78, top=196` | `208 - 12` |
| `amount` cells | `(430~526, 232)` | `left=430~526, top=220` | `232 - 12` |
| `purpose` | `textbox(214,248,411,328)` | `left=214, top=248` | textbox 直接用頂端 |
| `payDate` | `(436, 286)` | `left=436, top=274` | `286 - 12` |
| `receiptCount` | `(534, 286)` | `left=534, top=274` | `286 - 12` |

#### 6D. `drawTextFieldsOnCanvas()` 函數實作

```javascript
const drawTextFieldsOnCanvas = () => {
  if (!fabricCanvas || !activePage.value) return

  fabricCanvas.getObjects()
    .filter(o => o?.data?.kind === 'text_preview')
    .forEach(o => fabricCanvas.remove(o))

  const f = activePage.value.fields || {}
  const textProps = {
    fontFamily: previewFontFamily.value,
    fontSize: 12,
    fill: '#000',
    selectable: false,
    evented: false,
    originX: 'left',
    originY: 'top',
    excludeFromExport: true,
  }

  const addText = (text, x, y, opts = {}) => {
    if (!String(text || '').trim()) return
    const node = new fabric.Text(String(text), {
      ...textProps,
      left: x,
      top: y,
      ...opts,
    })
    node.data = { kind: 'text_preview' }
    fabricCanvas.add(node)
  }

  addText(f.voucherNo, 78, 226)
  addText(f.budgetItem, 78, 196)

  if (f.amount && /^\d+$/.test(String(f.amount))) {
    const padded = String(parseInt(f.amount, 10)).padStart(7, '※')
    const xList = [430, 446, 462, 478, 494, 510, 526]
    for (let i = 0; i < 7; i++) {
      addText(padded[i], xList[i], 220)
    }
  }

  if (String(f.purpose || '').trim()) {
    const purposeBox = new fabric.Textbox(String(f.purpose), {
      ...textProps,
      left: 214,
      top: 248,
      width: 197,
      fontSize: 14,
    })
    purposeBox.data = { kind: 'text_preview' }
    fabricCanvas.add(purposeBox)
  }

  addText(toRocDate(f.payDate), 436, 274)
  addText(f.receiptCount, 534, 274)
  fabricCanvas.requestRenderAll()
}
```

#### 6E. 觸發時機

需要保證文字預覽在切頁、載入、欄位編輯後都會重新出現。

1. `loadActivePageToCanvas()` 結尾
2. `watch(() => activePage.value?.fields, drawTextFieldsOnCanvas, { deep: true })`
3. 字型載入完成後，若畫布已初始化，也應補呼叫一次 `drawTextFieldsOnCanvas()`

#### 6F. 層級與防護

1. `drawTextFieldsOnCanvas()` 必須在背景與 invoice objects 都加入後才執行。
2. `syncActivePageFromCanvas()` 目前只同步 `kind === 'invoice'`，因此 `kind: 'text_preview'` 不會污染存檔資料。
3. 所有預覽文字都應設為：
   - `selectable: false`
   - `evented: false`
   - `excludeFromExport: true`

---

## 建議實作順序

1. `backend/routers/voucher.py`
   - `/generate` 改回 `FileResponse`
   - 新增 `/fonts/kaiu.ttf`
2. `frontend/src/services/api.js`
   - `generateVoucherFromLayout()` 改成 blob response
3. `frontend/src/views/VoucherEditorView.vue`
   - 新增 `getDownloadFilename()`
   - 修改 `generatePdf()` 真正下載
   - 補 `toRocDate()`
   - 補 `loadKaiuFont()`
   - 補 `drawTextFieldsOnCanvas()` 與 watcher
4. `frontend/src/views/ProjectDetailView.vue`
   - 移除舊版快速下載按鈕與 handler
5. `tests`
   - 補 router tests
6. 驗證
   - 後端 pytest
   - 前端 build
   - 手動比對 Canvas 與 PDF 位置

---

## 驗證計畫

### 自動化驗證

#### 後端最小回歸測試

1. `/api/voucher/{project_id}/generate` 成功時回傳 `application/pdf`
2. `/api/voucher/fonts/kaiu.ttf` 成功時回傳字型檔

#### 前端最小驗證

1. `npm run build` 必須成功
2. 不要求本版新增 Vue component tests

### 手動驗證

1. 在編輯器修改 `voucherNo`、`budgetItem`、`amount`、`purpose`、`payDate`、`receiptCount`
2. Canvas 上立即看到對應文字預覽
3. 切換頁面再切回，預覽文字仍存在且位置正確
4. 點「產出 PDF」後，瀏覽器直接下載 PDF
5. 下載的 PDF 內文與 Canvas 預覽位置一致
6. 返回專案頁後，已無舊版「快速產生黏貼紙」按鈕

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

可以直接開工。

本文件已合併審閱補正與文字預覽規格，後續實作請以這份 `v0_0_2_voucher_pdf_text_overlay.md` 為唯一來源。
