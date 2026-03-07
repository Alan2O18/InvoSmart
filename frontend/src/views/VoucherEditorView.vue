<template>
  <div class="voucher-editor-view">
    <header class="editor-header">
      <div class="header-left">
        <button class="back-btn" @click="goBack">← 返回活動</button>
        <h2>憑證黏貼編輯器</h2>
      </div>
      <div class="header-right">
        <button class="save-btn" @mousedown.prevent="removeSelectedOnCanvas">刪除選取</button>
        <button class="save-btn" :disabled="isSaving" @click="saveLayout">{{ isSaving ? '儲存中...' : '儲存草稿' }}</button>
        <button class="generate-btn" :disabled="!canGenerate" @click="generatePdf">產出 PDF</button>
      </div>
    </header>

    <section class="toolbar">
      <label>Prefix</label>
      <input v-model="globalPrefix" type="text" />
      <label>Start Index</label>
      <input v-model.number="startIndex" type="number" min="1" />
      <button @click="addPage" :disabled="pages.length >= maxPages">+ 新增頁</button>
      <button @click="runAutoLayout" :disabled="canvasLoading || !activePage?.images?.length">⚡ 自動排版</button>
      <span class="status" :class="{ bad: hasInvalidDate || hasDecimalAmount || hasExcessiveAmount }">
        {{ statusText }}
      </span>
    </section>

    <div class="content" v-if="ready">
      <aside class="left-panel">
        <h3>可用發票</h3>
        <div class="invoice-list">
          <button
            v-for="invoice in invoices"
            :key="invoice.jobId"
            class="invoice-item"
            :disabled="invoiceUsageMap[invoice.jobId]"
            @click="addInvoiceToActivePage(invoice)"
          >
            <img :src="getFullImageUrl(invoice.imageUrl)" alt="發票縮圖" class="invoice-thumb" loading="lazy" />
            <div class="invoice-info">
              <span class="date">{{ invoice.result?.date || invoice.result?.header?.date || '無日期' }}</span>
              <span class="amount">${{ invoice.result?.total_amount ?? invoice.result?.summary?.total ?? invoice.result?.total ?? 0 }}</span>
            </div>
            <div class="invoice-id" style="font-size:10px; color:#aaa; margin-top:2px;">{{ invoice.jobId.slice(-6) }}</div>
          </button>
        </div>
      </aside>

      <main class="center-panel">
        <div class="page-tabs">
          <button
            v-for="(page, index) in pages"
            :key="index"
            :class="['tab', { active: index === activePageIndex }]"
            @click="switchPage(index)"
          >
            第 {{ index + 1 }} 頁
          </button>
        </div>

        <div class="fields">
          <label>憑證號</label>
          <input v-model="activePage.fields.voucherNo" />
          <label>預算別</label>
          <input v-model="activePage.fields.budgetItem" />
          <label>金額</label>
          <input
            v-model="activePage.fields.amount"
            :class="{
              'field-error-yellow': isCurrentPageAmountDecimal,
              'field-error-red': isCurrentPageAmountExcessive,
            }"
          />
          <label>日期</label>
          <input
            v-model="activePage.fields.payDate"
            placeholder="YYYY-MM-DD"
            :class="{ 'field-error-red': isCurrentPageDateInvalid }"
          />
          <label>用途</label>
          <div class="purpose-wrap">
            <textarea
              v-model="activePage.fields.purpose"
              rows="2"
              @input="onPurposeManualEdit"
              :class="{ 'field-error-yellow': purposeLength > 40 }"
            />
            <span class="char-count" :class="{ warn: purposeLength > 40 }">
              {{ purposeLength }} / 40 字
            </span>
          </div>
        </div>

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

        <div class="images">
          <h4>本頁發票清單（共 {{ activePage.images.length }} 張）</h4>
          <ul class="placed-list">
            <li v-for="(image, imageIndex) in activePage.images" :key="`${image.jobId}-${imageIndex}`">
              <span class="placed-id">發票 {{ imageIndex + 1 }} (ID: {{ image.jobId.slice(-6) }})</span>
              <button class="remove-btn" @click="removeImage(imageIndex)">移除</button>
            </li>
          </ul>
        </div>
      </main>
    </div>

    <div v-else class="loading">載入資料中...</div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as fabric from 'fabric'
import { useRoute, useRouter } from 'vue-router'
import { useActiveElement, useEventListener, useThrottleFn } from '@vueuse/core'
import api from '../services/api'
import {
  autoLayoutImages,
  buildVoucherTextPreviewEntries,
  canGenerateVoucher,
  clampImageRect,
  collectUsedJobIds,
  findOverlappingJobIds,
  hasDecimalAmount as hasDecimalAmountUtil,
  hasExcessiveAmount as hasExcessiveAmountUtil,
  hasInvalidDate as hasInvalidDateUtil,
  normalizeDateToISO,
  parseDateString,
} from '../utils/voucher'

const route = useRoute()
const router = useRouter()

const projectId = route.params.id
const maxPages = 10
const CANVAS_WIDTH = 595
const CANVAS_HEIGHT = 842
const SAFE_ZONE = { x0: 30, y0: 394, x1: 565, y1: 730 }
const PREVIEW_TEXT_COLOR = '#1e3a8a'

const ready = ref(false)
const isSaving = ref(false)
const templatePng = ref('')
const invoices = ref([])
const voucherTextConfig = ref(null)
const activePageIndex = ref(0)
const renderToken = ref(0)
const pendingImageLoads = ref(0)
const globalPrefix = ref('D-16')
const startIndex = ref(1)
const canvasRef = ref(null)
let fabricCanvas = null
let previewDrawTimer = null
let previewFontLoadPromise = null
const canvasLoadState = {
  token: 0,
  pending: 0,
}
const pages = ref([
  {
    pageIndex: 0,
    fields: {
      voucherNo: '',
      budgetItem: '',
      amount: '',
      purpose: '',
      receiptCount: '0',
      payDate: '',
      isManuallyEdited: false,
    },
    images: [],
  },
])

const usedJobIds = computed(() => collectUsedJobIds(pages.value))
const invoiceUsageMap = computed(() => {
  const map = {}
  invoices.value.forEach(invoice => {
    map[invoice.jobId] = usedJobIds.value.has(invoice.jobId)
  })
  return map
})

const activePage = computed(() => pages.value[activePageIndex.value])
const hasInvalidDate = computed(() => hasInvalidDateUtil(pages.value))
const hasDecimalAmount = computed(() => hasDecimalAmountUtil(pages.value))
const hasExcessiveAmount = computed(() => hasExcessiveAmountUtil(pages.value))
const canGenerate = computed(() => canGenerateVoucher(pages.value, isSaving.value))
const canvasLoading = computed(() => pendingImageLoads.value > 0)

const statusText = computed(() => {
  if (hasInvalidDate.value) return '日期格式異常，請修正'
  if (hasDecimalAmount.value) return '金額不可有小數'
  if (hasExcessiveAmount.value) return '金額不可超過 9,999,999'
  return '可產出'
})

// ── Per-page field validation computeds (Step 2: highlighting) ──────────────
const isCurrentPageDateInvalid = computed(() => {
  const p = activePage.value
  if (!p) return false
  const payDate = p.fields?.payDate
  const hasImages = (p.images || []).length > 0
  if (!payDate && hasImages) return true
  if (!payDate) return false
  return Number.isNaN(parseDateString(payDate))
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

// ── Step 3: purpose char count ──────────────────────────────────────────────
const purposeLength = computed(() => (activePage.value?.fields?.purpose || '').length)

// ── Step 4: empty state ─────────────────────────────────────────────────────
const isEmptyProject = computed(() => ready.value && invoices.value.length === 0)

// ── VueUse: reactive active element for keyboard guard ──────────────────────
const activeEl = useActiveElement()

let autosaveTimer = null


const getFullImageUrl = (url) => {
  if (!url) return ''
  return api.toAbsoluteUrl(url)
}

const templateDataUrl = computed(() => (templatePng.value ? `data:image/png;base64,${templatePng.value}` : ''))

const clearTextPreviewObjects = () => {
  if (!fabricCanvas) return
  const previewObjects = fabricCanvas.getObjects().filter(obj => obj?.data?.kind === 'text_preview')
  previewObjects.forEach(obj => fabricCanvas.remove(obj))
}

const createPurposePreviewObject = (entry) => {
  const baseOptions = {
    left: entry.left,
    top: entry.top,
    width: entry.width,
    fontSize: entry.fontSize,
    fontFamily: entry.fontFamily,
    lineHeight: entry.lineHeight,
    fill: PREVIEW_TEXT_COLOR,
    selectable: false,
    evented: false,
    splitByGrapheme: true,
    originX: 'left',
    originY: 'top',
    excludeFromExport: true,
  }

  const makeTextbox = (text, fontSize) => new fabric.Textbox(text, {
    ...baseOptions,
    fontSize,
  })

  for (let fontSize = entry.fontSize; fontSize >= entry.minFontSize; fontSize -= 1) {
    const textbox = makeTextbox(entry.text, fontSize)
    if (textbox.calcTextHeight() <= entry.height) {
      return textbox
    }
  }

  let truncated = entry.text.slice(0, entry.truncateAt)
  while (truncated.length > 0) {
    const candidate = `${truncated}${entry.truncateSuffix}`
    const textbox = makeTextbox(candidate, entry.minFontSize)
    if (textbox.calcTextHeight() <= entry.height) {
      return textbox
    }
    truncated = truncated.slice(0, -1)
  }

  return makeTextbox(entry.truncateSuffix, entry.minFontSize)
}

const createPreviewObject = (entry) => {
  if (entry.type === 'textbox') {
    const textbox = createPurposePreviewObject(entry)
    textbox.data = { kind: 'text_preview', fieldKey: entry.key }
    return textbox
  }

  const text = new fabric.Text(entry.text, {
    left: entry.left,
    top: entry.top,
    fontSize: entry.fontSize,
    fontFamily: entry.fontFamily,
    fill: PREVIEW_TEXT_COLOR,
    selectable: false,
    evented: false,
    originX: 'left',
    originY: 'top',
    excludeFromExport: true,
  })
  text.data = { kind: 'text_preview', fieldKey: entry.key }
  return text
}

const drawTextFieldsOnCanvas = (targetPageIndex = activePageIndex.value, token = renderToken.value, attempt = 0) => {
  if (!fabricCanvas || !activePage.value || !voucherTextConfig.value) return
  if (activePageIndex.value !== targetPageIndex || renderToken.value !== token) return

  if (canvasLoadState.token === token && canvasLoadState.pending > 0) {
    if (attempt >= 60) {
      console.warn('voucher preview text draw timed out waiting for image loads to settle')
      return
    }
    previewDrawTimer = window.setTimeout(() => {
      previewDrawTimer = null
      drawTextFieldsOnCanvas(targetPageIndex, token, attempt + 1)
    }, 16)
    return
  }

  clearTextPreviewObjects()

  const entries = buildVoucherTextPreviewEntries(activePage.value.fields, voucherTextConfig.value)
  entries.forEach(entry => {
    const obj = createPreviewObject(entry)
    fabricCanvas.add(obj)
  })
  fabricCanvas.requestRenderAll()
}

const queueTextPreviewDraw = (targetPageIndex = activePageIndex.value, token = renderToken.value) => {
  if (previewDrawTimer) {
    window.clearTimeout(previewDrawTimer)
  }
  previewDrawTimer = window.setTimeout(() => {
    previewDrawTimer = null
    drawTextFieldsOnCanvas(targetPageIndex, token)
  }, 0)
}

const ensurePreviewFontLoaded = async () => {
  if (previewFontLoadPromise || !voucherTextConfig.value?.font?.url || !window.FontFace) {
    return previewFontLoadPromise
  }

  const { family, url } = voucherTextConfig.value.font
  if (document.fonts?.check?.(`12px "${family}"`)) {
    return Promise.resolve()
  }

  previewFontLoadPromise = new window.FontFace(family, `url(${api.toAbsoluteUrl(url)})`)
    .load()
    .then(fontFace => {
      document.fonts.add(fontFace)
      queueTextPreviewDraw()
    })
    .catch(error => {
      console.warn('voucher preview font load failed', error)
    })

  return previewFontLoadPromise
}

const ensurePageNumbers = () => {
  pages.value.forEach((page, index) => {
    page.pageIndex = index
  })
}

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

const addPage = () => {
  if (pages.value.length >= maxPages) return
  pages.value.push({
    pageIndex: pages.value.length,
    fields: {
      voucherNo: '',
      budgetItem: '',
      amount: '',
      purpose: '',
      receiptCount: '0',
      payDate: '',
      isManuallyEdited: false,
    },
    images: [],
  })
  recalculateVoucherNumbers()
}

const switchPage = async (index) => {
  await saveLayout()
  activePageIndex.value = index
  await nextTick()
  await loadActivePageToCanvas()
  // Only backfill missing auto fields when switching pages; keep existing draft edits.
  recalculatePageFields(activePage.value, { onlyFillEmpty: true })
}

const recalculateVoucherNumbers = () => {
  let runningIndex = startIndex.value
  pages.value.forEach(page => {
    const count = (page.images || []).length
    page.fields.receiptCount = String(count)

    if (count > 0) {
      const lines = Array.from({ length: count }, (_, offset) => {
        const currentIndex = String(runningIndex + offset).padStart(2, '0')
        return `${globalPrefix.value}-${currentIndex}`
      })
      page.fields.voucherNo = lines.join('\n')
      runningIndex += count
    } else {
      page.fields.voucherNo = ''
    }
  })
}

// ── Step 5: Per-page auto field recalculation ──────────────────────────────
const recalculatePageFields = (page, options = {}) => {
  const { onlyFillEmpty = false } = options
  if (!page) return
  const pageImages = page.images || []
  page.fields.receiptCount = String(pageImages.length)

  const pageInvoices = pageImages
    .map(img => invoices.value.find(inv => inv.jobId === img.jobId))
    .filter(Boolean)

  // D.25: Amount sum from multi-shape invoice payload
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

  // D.28: Latest valid date by timestamp, normalize to ISO string
  const validDateObjects = pageInvoices
    .map(inv => inv.result?.date || inv.result?.header?.date || '')
    .map(d => ({ raw: d, ts: parseDateString(d) }))
    .filter(obj => !Number.isNaN(obj.ts))
    .sort((a, b) => a.ts - b.ts)
  const nextPayDate = validDateObjects.length
    ? normalizeDateToISO(validDateObjects[validDateObjects.length - 1].raw)
    : ''
  if (!onlyFillEmpty || !String(page.fields.payDate || '').trim()) {
    page.fields.payDate = nextPayDate
  }

  // D.27: Purpose de-dup concat (category preferred)
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

// ── Step 7: Purpose manual edit flag ────────────────────────────────────────
const onPurposeManualEdit = () => {
  if (activePage.value) {
    activePage.value.fields.isManuallyEdited = true
  }
}

// ── Step 5 + Step 7: Add invoice with purpose override protection ───────────
const addInvoiceToActivePage = (invoice) => {
  if (!activePage.value || invoiceUsageMap.value[invoice.jobId]) return

  // Purpose override protection (A.8 附錄第 8 情境)
  if (activePage.value.fields.isManuallyEdited && activePage.value.fields.purpose?.trim()) {
    const confirmed = window.confirm(
      '發現新發票。您已手動編輯過「用途說明」，是否以新的用途覆蓋您的編輯？\n\n' +
      '點選「確定」→ 以系統自動產生的用途覆蓋\n' +
      '點選「取消」→ 保留您手動編輯的內容'
    )
    if (!confirmed) {
      _doAddInvoice(invoice)
      return
    }
    activePage.value.fields.isManuallyEdited = false
  }

  _doAddInvoice(invoice)
}

const _doAddInvoice = (invoice) => {
  const count = activePage.value.images.length
  // 智慧網格放置：一排 3 張發票 (間距 160x170)
  const row = Math.floor(count / 3)
  const col = count % 3

  const newRect = clampImageRect({
    jobId: invoice.jobId,
    x: 40 + (col * 160),
    y: 400 + (row * 170),
    w: 150,
    h: 150,
  })
  activePage.value.images.push(newRect)
  recalculatePageFields(activePage.value)
  recalculateVoucherNumbers()

  canvasLoadState.token = renderToken.value
  canvasLoadState.pending += 1
  pendingImageLoads.value = canvasLoadState.pending
  addInvoiceObjectToCanvas(newRect, activePageIndex.value, renderToken.value)
}

const removeImage = (index) => {
  const removed = activePage.value.images.splice(index, 1)[0]
  recalculatePageFields(activePage.value)
  recalculateVoucherNumbers()
  
  if (fabricCanvas && removed) {
    const target = fabricCanvas.getObjects().find(o => o.data?.kind === 'invoice' && o.data.jobId === removed.jobId)
    if (target) {
      fabricCanvas.remove(target)
      fabricCanvas.requestRenderAll()
    }
  }
  updateOverlapHighlight()
}

const payload = computed(() => ({
  globalPrefix: globalPrefix.value,
  startIndex: startIndex.value,
  pages: pages.value,
}))

const saveLayout = async () => {
  isSaving.value = true
  try {
    syncActivePageFromCanvas()
    ensurePageNumbers()
    await api.saveVoucherLayout(projectId, payload.value)
  } catch (error) {
    console.error('save layout failed', error)
  } finally {
    isSaving.value = false
  }
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

const goBack = async () => {
  await saveLayout()
  router.push(`/project/${projectId}`)
}

const drawSafeZoneGuides = () => {
  if (!fabricCanvas) return
  const rect = new fabric.Rect({
    left: SAFE_ZONE.x0,
    top: SAFE_ZONE.y0,
    width: SAFE_ZONE.x1 - SAFE_ZONE.x0,
    height: SAFE_ZONE.y1 - SAFE_ZONE.y0,
    fill: 'rgba(34,197,94,0.05)',
    stroke: '#22c55e',
    strokeDashArray: [8, 6],
    selectable: false,
    evented: false,
    excludeFromExport: true,
  })
  fabricCanvas.add(rect)
  fabricCanvas.sendObjectToBack(rect)
}

const applyObjectBounds = (obj) => {
  // Guard: only process invoice images, skip background/safeZone/placeholders
  if (obj?.data?.kind !== 'invoice') return

  const aspectRatio = obj.width && obj.height ? obj.width / obj.height : 1
  let w = obj.getScaledWidth()
  let h = obj.getScaledHeight()
  const maxW = SAFE_ZONE.x1 - SAFE_ZONE.x0
  const maxH = SAFE_ZONE.y1 - SAFE_ZONE.y0

  // Clamp to safe zone while preserving aspect ratio
  if (w > maxW) { w = maxW; h = w / aspectRatio }
  if (h > maxH) { h = maxH; w = h * aspectRatio }

  const clamped = clampImageRect({ x: obj.left, y: obj.top, w, h }, SAFE_ZONE)
  const uniformScale = clamped.w / obj.width

  obj.set({
    left: clamped.x,
    top: clamped.y,
    scaleX: uniformScale,
    scaleY: uniformScale,
  })
  obj.setCoords()
}

const syncActivePageFromCanvas = () => {
  if (!fabricCanvas || !activePage.value) return
  if (canvasLoading.value) return

  const nextImages = fabricCanvas
    .getObjects()
    .filter(obj => obj?.data?.kind === 'invoice')
    .map(obj => clampImageRect({
      jobId: obj.data.jobId,
      x: obj.left,
      y: obj.top,
      w: obj.getScaledWidth(),
      h: obj.getScaledHeight(),
    }, SAFE_ZONE))

  activePage.value.images = nextImages
  activePage.value.fields.receiptCount = String(nextImages.length)
}

// ── Step 6: Overlap detection (throttled via VueUse) ────────────────────────
const updateOverlapHighlight = () => {
  if (!fabricCanvas) return

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
const throttledOverlapHighlight = useThrottleFn(updateOverlapHighlight, 32)

const makePlaceholderGroup = (imageData) => {
  const rect = new fabric.Rect({
    left: 0,
    top: 0,
    width: imageData.w,
    height: imageData.h,
    fill: 'rgba(220,38,38,0.25)',
    stroke: '#dc2626',
    strokeWidth: 2,
    originX: 'left',
    originY: 'top',
  })
  const text = new fabric.Text('載入失敗', {
    left: 8,
    top: 8,
    fill: '#dc2626',
    fontSize: 14,
    originX: 'left',
    originY: 'top',
  })
  const group = new fabric.Group([rect, text], {
    left: imageData.x,
    top: imageData.y,
    lockRotation: true,
    originX: 'left',
    originY: 'top',
  })
  group.data = { kind: 'invoice', jobId: imageData.jobId }
  applyObjectBounds(group)
  return group
}

const addInvoiceObjectToCanvas = (imageData, targetPageIndex, token) => {
  const imageEl = new window.Image()
  imageEl.onload = () => {
    if (!fabricCanvas) return
    if (activePageIndex.value !== targetPageIndex || renderToken.value !== token) return

    const obj = new fabric.Image(imageEl, {
      left: imageData.x,
      top: imageData.y,
      originX: 'left',
      originY: 'top',
      lockRotation: true,
      cornerColor: '#2563eb',
      borderColor: '#22c55e',
      transparentCorners: false,
    })
    // Step 1: hide mid-controls → only corner resize (aspect ratio preserved by canvas.uniformScaling)
    obj.setControlsVisibility({ mt: false, mb: false, ml: false, mr: false })
    obj.data = { kind: 'invoice', jobId: imageData.jobId }
    if (obj.width && obj.height) {
      if (imageData.w === 150 && imageData.h === 150) {
        // 全新加入時：依照真實圖檔寬高比例，限制在 150x150 內
        const s = Math.min(150 / obj.width, 150 / obj.height)
        obj.scaleX = s
        obj.scaleY = s
        // 同步回 imageData 防止拖移時還原為正方形
        imageData.w = obj.width * s
        imageData.h = obj.height * s
      } else {
        // 從 Layout 重新載入時
        const s = imageData.h / obj.height
        obj.scaleX = s
        obj.scaleY = s
      }
    }
    applyObjectBounds(obj)
    fabricCanvas.add(obj)
    fabricCanvas.requestRenderAll()
    updateOverlapHighlight()
    if (canvasLoadState.token === token) {
      canvasLoadState.pending = Math.max(0, canvasLoadState.pending - 1)
      pendingImageLoads.value = canvasLoadState.pending
      queueTextPreviewDraw(targetPageIndex, token)
    }
  }

  imageEl.onerror = () => {
    if (!fabricCanvas) return
    if (activePageIndex.value !== targetPageIndex || renderToken.value !== token) return
    const placeholder = makePlaceholderGroup(imageData)
    fabricCanvas.add(placeholder)
    fabricCanvas.requestRenderAll()
    if (canvasLoadState.token === token) {
      canvasLoadState.pending = Math.max(0, canvasLoadState.pending - 1)
      pendingImageLoads.value = canvasLoadState.pending
      queueTextPreviewDraw(targetPageIndex, token)
    }
  }

  imageEl.src = api.toAbsoluteUrl(api.getVoucherImageUrl(projectId, imageData.jobId, true))
}

// ── Step 4: Auto-layout ─────────────────────────────────────────────────────
const runAutoLayout = () => {
  if (!fabricCanvas || !activePage.value?.images?.length) return

  const pageImages = activePage.value.images || []
  const canvasObjs = fabricCanvas.getObjects().filter(o => o?.data?.kind === 'invoice')
  const canvasObjMap = new Map(canvasObjs.map(obj => [obj?.data?.jobId, obj]))

  const hasAllCanvasObjects = pageImages.every(img => canvasObjMap.has(img.jobId))
  if (!hasAllCanvasObjects) {
    window.alert('部分圖片尚未載入完成，請稍後再執行自動排版。')
    return
  }

  const items = pageImages.map(img => {
    const obj = canvasObjMap.get(img.jobId)
    return {
      jobId: img.jobId,
      originalWidth: obj?.width || obj?.getScaledWidth() || img.w,
      originalHeight: obj?.height || obj?.getScaledHeight() || img.h,
    }
  })

  const layoutResult = autoLayoutImages(items, SAFE_ZONE)
  if (!layoutResult) {
    window.alert('發票過多或尺寸過大，自動排版無法在安全區內排下。請手動微調或分頁。')
    return
  }

  // Apply to data model
  activePage.value.images = layoutResult

  // Apply to canvas objects
  const posMap = Object.fromEntries(layoutResult.map(r => [r.jobId, r]))
  canvasObjs.forEach(obj => {
    const pos = posMap[obj.data.jobId]
    if (!pos) return
    const s = pos.h / obj.height
    obj.set({ left: pos.x, top: pos.y, scaleX: s, scaleY: s })
    obj.setCoords()
  })

  fabricCanvas.requestRenderAll()
  recalculatePageFields(activePage.value, { onlyFillEmpty: true })
  recalculateVoucherNumbers()
  updateOverlapHighlight()
}

const loadActivePageToCanvas = async () => {
  if (!fabricCanvas || !activePage.value) return
  const targetPageIndex = activePageIndex.value
  const token = renderToken.value + 1
  renderToken.value = token
  canvasLoadState.token = token
  canvasLoadState.pending = (activePage.value.images || []).length
  pendingImageLoads.value = canvasLoadState.pending

  fabricCanvas.clear()

  if (templateDataUrl.value) {
    const bgImage = new window.Image()
    bgImage.onload = () => {
      if (!fabricCanvas) return
      if (activePageIndex.value !== targetPageIndex || renderToken.value !== token) return
      const bg = new fabric.Image(bgImage, {
        left: 0,
        top: 0,
        originX: 'left',
        originY: 'top',
        selectable: false,
        evented: false,
        excludeFromExport: true,
      })
      bg.data = { kind: 'background' }
      if (bg.width && bg.height) {
        bg.scaleX = CANVAS_WIDTH / bg.width
        bg.scaleY = CANVAS_HEIGHT / bg.height
      }
      fabricCanvas.add(bg)
      bg.sendToBack()
      drawSafeZoneGuides()
      fabricCanvas.requestRenderAll()
      queueTextPreviewDraw(targetPageIndex, token)
    }
    bgImage.src = templateDataUrl.value
  } else {
    drawSafeZoneGuides()
    queueTextPreviewDraw(targetPageIndex, token)
  }

  ;(activePage.value.images || []).forEach(imageData => {
    addInvoiceObjectToCanvas(imageData, targetPageIndex, token)
  })

  if (!(activePage.value.images || []).length) {
    queueTextPreviewDraw(targetPageIndex, token)
  }
}

const removeSelectedOnCanvas = () => {
  if (!fabricCanvas) return
  const selected = fabricCanvas.getActiveObjects().filter(obj => obj?.data?.kind === 'invoice')
  if (!selected.length) return
  selected.forEach(obj => fabricCanvas.remove(obj))
  fabricCanvas.discardActiveObject()
  fabricCanvas.requestRenderAll()
  syncActivePageFromCanvas()
  recalculatePageFields(activePage.value)
  recalculateVoucherNumbers()
  updateOverlapHighlight()
}

const initCanvas = () => {
  if (!canvasRef.value) return
  if (fabricCanvas) {
    fabricCanvas.dispose()
    fabricCanvas = null
  }
  fabricCanvas = new fabric.Canvas(canvasRef.value, {
    width: CANVAS_WIDTH,
    height: CANVAS_HEIGHT,
    backgroundColor: '#ffffff',
    preserveObjectStacking: true,
  })

  fabricCanvas.on('object:moving', (event) => {
    const obj = event.target
    if (!obj || obj?.data?.kind !== 'invoice') return
    applyObjectBounds(obj)
    throttledOverlapHighlight()
  })

  fabricCanvas.on('object:scaling', (event) => {
    const obj = event.target
    if (!obj || obj?.data?.kind !== 'invoice') return
    applyObjectBounds(obj)
  })

  fabricCanvas.on('object:modified', () => {
    syncActivePageFromCanvas()
    updateOverlapHighlight()
  })

  fabricCanvas.on('object:removed', () => {
    syncActivePageFromCanvas()
  })
}

onMounted(async () => {
  try {
    const [textConfigResp, templateResp, layoutResp] = await Promise.all([
      api.getVoucherTextConfig(),
      api.getVoucherTemplate(projectId),
      api.getVoucherLayout(projectId),
    ])

    let defaultBudget = ''
    try {
      const projectResp = await api.getProjectDetail(projectId)
      const meta = projectResp.data?.metadata || {}
      defaultBudget = meta.budgetExpense?.[0]?.name || ''
    } catch (e) {
      console.warn('getProjectDetail failed, budgetItem stays empty', e)
    }

    voucherTextConfig.value = textConfigResp.data
    templatePng.value = templateResp.data.templatePng || ''
    invoices.value = templateResp.data.invoices || []

    if (layoutResp.data?.pages?.length) {
      pages.value = layoutResp.data.pages.map(p => ({
        ...p,
        fields: {
          voucherNo: '',
          budgetItem: defaultBudget,
          amount: '',
          purpose: '',
          receiptCount: '0',
          payDate: '',
          isManuallyEdited: false,
          ...(p.fields || {}),
        },
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
  await ensurePreviewFontLoaded()
  initCanvas()
  await loadActivePageToCanvas()
  // Initial load should not overwrite existing draft values from saved layout.
  recalculatePageFields(activePage.value, { onlyFillEmpty: true })
  recalculateVoucherNumbers()

  autosaveTimer = window.setInterval(saveLayout, 30000)
})

// ── Step 0: Keyboard guard — VueUse useEventListener (auto-cleanup) ─────────
useEventListener(window, 'keydown', (event) => {
  // Guard: don't fire canvas delete when typing in form fields or composing IME
  if (event.isComposing) return
  const tag = activeEl.value?.tagName?.toLowerCase()
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return
  if (activeEl.value?.isContentEditable) return

  if (event.key === 'Delete' || event.key === 'Backspace') {
    removeSelectedOnCanvas()
  }
})

onBeforeUnmount(async () => {
  if (previewDrawTimer) {
    window.clearTimeout(previewDrawTimer)
  }
  if (autosaveTimer) {
    window.clearInterval(autosaveTimer)
  }
  if (fabricCanvas) {
    syncActivePageFromCanvas()
  }
  await saveLayout()
  if (fabricCanvas) {
    fabricCanvas.dispose()
    fabricCanvas = null
  }
})

watch([globalPrefix, startIndex], recalculateVoucherNumbers)
watch(
  () => activePage.value?.fields,
  () => {
    queueTextPreviewDraw()
  },
  { deep: true },
)
watch(voucherTextConfig, () => {
  queueTextPreviewDraw()
})
</script>

<style scoped>
.voucher-editor-view {
  min-height: 100vh;
  background: #1e1e1e;
  color: #f3f4f6;
}

.editor-header {
  padding: 12px 16px;
  border-bottom: 1px solid #333;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left,
.header-right,
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar {
  padding: 10px 16px;
  border-bottom: 1px solid #333;
}

.content {
  display: grid;
  grid-template-columns: 280px 1fr;
  min-height: calc(100vh - 112px);
}

.left-panel {
  border-right: 1px solid #333;
  padding: 12px;
}

.invoice-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.center-panel {
  padding: 12px;
}

.page-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
}

.tab.active {
  background: #2563eb;
  color: white;
}

.fields {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 8px;
  margin-bottom: 12px;
}

.canvas-wrap {
  border: 1px solid #374151;
  background: #0b1220;
  width: fit-content;
  margin: 0 auto;
  padding: 8px;
  margin-bottom: 12px;
}

.canvas-wrap canvas {
  display: block;
}

.status.bad {
  color: #f87171;
  font-weight: 600;
}

input,
textarea,
button {
  background: #111827;
  color: #f3f4f6;
  border: 1px solid #374151;
  border-radius: 6px;
  padding: 6px 8px;
}

button:disabled {
  opacity: 0.45;
}

.loading {
  padding: 24px;
}

/* ── Field validation highlights ──────────────────────────────────────────── */
.field-error-red {
  outline: 2px solid rgba(220, 38, 38, 0.8);
  background: rgba(220, 38, 38, 0.15) !important;
}
.field-error-yellow {
  outline: 2px solid rgba(202, 138, 4, 0.8);
  background: rgba(202, 138, 4, 0.15) !important;
}

/* ── Purpose textarea wrapper ─────────────────────────────────────────────── */
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
  right: 8px;
  bottom: 6px;
  font-size: 11px;
  color: #9ca3af;
  pointer-events: none;
  user-select: none;
}
.char-count.warn {
  color: #ca8a04;
  font-weight: 600;
}

/* ── Canvas disabled / empty-state overlay ────────────────────────────────── */
.canvas-disabled {
  position: relative;
}
.canvas-disabled canvas {
  opacity: 0.35;
  pointer-events: none;
}
.empty-state-overlay {
  position: absolute;
  inset: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(11, 18, 32, 0.75);
  border-radius: 8px;
}
.empty-state-content {
  text-align: center;
  color: #9ca3af;
  max-width: 360px;
}
.empty-icon {
  font-size: 48px;
  display: block;
  margin-bottom: 8px;
}
.empty-state-content h3 {
  color: #f3f4f6;
  margin: 0 0 6px;
}
.empty-state-content p {
  font-size: 13px;
  line-height: 1.5;
  margin: 0 0 12px;
}
.empty-state-content button {
  background: #2563eb;
  border: none;
  color: #fff;
  padding: 8px 20px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}
.empty-state-content button:hover {
  background: #1d4ed8;
}

/* ── UI 改善：Beta 0.0.1 樣式 ── */
.invoice-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: #2a2a2a;
  border: 1px solid #444;
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.2s;
  color: white;
  width: 100%;
  margin-bottom: 8px;
}
.invoice-item:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.invoice-item:hover:not(:disabled) {
  border-color: #3b82f6;
}
.invoice-thumb {
  width: 100%;
  height: 80px;
  object-fit: contain;
  background: #fff;
  border-radius: 4px;
}
.invoice-info {
  display: flex;
  justify-content: space-between;
  width: 100%;
  font-size: 12px;
}
.invoice-info .amount {
  font-weight: bold;
  color: #fbbf24;
}

.placed-list {
  list-style: none;
  padding: 0;
  margin-top: 8px;
}
.placed-list li {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: #2a2a2a;
  margin-bottom: 6px;
  border-radius: 4px;
  align-items: center;
  border: 1px solid #444;
}
.placed-id {
  font-family: monospace;
  font-size: 13px;
}
.remove-btn {
  background: #ef4444;
  color: white;
  border: none;
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: 0.2s;
}
.remove-btn:hover {
  background: #dc2626;
}
</style>
