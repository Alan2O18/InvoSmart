<template>
  <div class="voucher-editor-view">
    <header class="editor-header">
      <div class="header-left">
        <button class="back-btn" @click="goBack">← 返回活動</button>
        <h2>憑證黏貼編輯器</h2>
      </div>
      <div class="header-right">
        <button class="save-btn" @click="removeSelectedOnCanvas">刪除選取</button>
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
            {{ invoice.jobId }}
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
          <input v-model="activePage.fields.amount" />
          <label>日期</label>
          <input v-model="activePage.fields.payDate" placeholder="YYYY-MM-DD" />
          <label>用途</label>
          <textarea v-model="activePage.fields.purpose" rows="2" />
        </div>

        <div class="canvas-wrap">
          <canvas ref="canvasRef"></canvas>
        </div>

        <div class="images">
          <h4>本頁發票（資料）</h4>
          <ul>
            <li v-for="(image, imageIndex) in activePage.images" :key="`${image.jobId}-${imageIndex}`">
              {{ image.jobId }} ({{ image.x }}, {{ image.y }}, {{ image.w }}, {{ image.h }})
              <button @click="removeImage(imageIndex)">移除</button>
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
import api from '../services/api'
import {
  canGenerateVoucher,
  clampImageRect,
  collectUsedJobIds,
  hasDecimalAmount as hasDecimalAmountUtil,
  hasExcessiveAmount as hasExcessiveAmountUtil,
  hasInvalidDate as hasInvalidDateUtil,
} from '../utils/voucher'

const route = useRoute()
const router = useRouter()

const projectId = route.params.id
const maxPages = 10
const CANVAS_WIDTH = 595
const CANVAS_HEIGHT = 842
const SAFE_ZONE = { x0: 30, y0: 394, x1: 565, y1: 730 }

const ready = ref(false)
const isSaving = ref(false)
const templatePng = ref('')
const invoices = ref([])
const activePageIndex = ref(0)
const renderToken = ref(0)
const globalPrefix = ref('D-16')
const startIndex = ref(1)
const canvasRef = ref(null)
let fabricCanvas = null
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

const statusText = computed(() => {
  if (hasInvalidDate.value) return '日期格式異常，請修正'
  if (hasDecimalAmount.value) return '金額不可有小數'
  if (hasExcessiveAmount.value) return '金額不可超過 9,999,999'
  return '可產出'
})

let autosaveTimer = null
let keyboardHandler = null

const templateDataUrl = computed(() => (templatePng.value ? `data:image/png;base64,${templatePng.value}` : ''))

const ensurePageNumbers = () => {
  pages.value.forEach((page, index) => {
    page.pageIndex = index
  })
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
}

const switchPage = async (index) => {
  await saveLayout()
  activePageIndex.value = index
  await nextTick()
  await loadActivePageToCanvas()
}

const addInvoiceToActivePage = (invoice) => {
  if (!activePage.value || invoiceUsageMap.value[invoice.jobId]) return
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
  
  addInvoiceObjectToCanvas(newRect, activePageIndex.value, renderToken.value)
}

const removeImage = (index) => {
  const removed = activePage.value.images.splice(index, 1)[0]
  activePage.value.fields.receiptCount = String(activePage.value.images.length)
  
  if (fabricCanvas && removed) {
    const target = fabricCanvas.getObjects().find(o => o.data?.kind === 'invoice' && o.data.jobId === removed.jobId)
    if (target) {
      fabricCanvas.remove(target)
      fabricCanvas.requestRenderAll()
    }
  }
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
    const response = await api.generateVoucherFromLayout(projectId, payload.value)
    alert(`PDF 產出成功: ${response.data.filename}`)
  } catch (error) {
    console.error('generate failed', error)
    alert('產出失敗，請檢查欄位格式與發票內容')
  }
}

const goBack = () => {
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
  rect.sendToBack()
}

const applyObjectBounds = (obj) => {
  const clamped = clampImageRect({
    x: obj.left,
    y: obj.top,
    w: obj.getScaledWidth(),
    h: obj.getScaledHeight(),
  }, SAFE_ZONE)

  if (obj.width && obj.height) {
    obj.set({
      left: clamped.x,
      top: clamped.y,
      scaleX: clamped.w / obj.width,
      scaleY: clamped.h / obj.height,
    })
  } else {
    obj.set({ left: clamped.x, top: clamped.y })
  }
  obj.setCoords()
}

const syncActivePageFromCanvas = () => {
  if (!fabricCanvas || !activePage.value) return

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
  group.set('data', { kind: 'invoice', jobId: imageData.jobId })
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
    obj.set('data', { kind: 'invoice', jobId: imageData.jobId })
    if (obj.width && obj.height) {
      obj.scaleX = imageData.w / obj.width
      obj.scaleY = imageData.h / obj.height
    }
    applyObjectBounds(obj)
    fabricCanvas.add(obj)
    fabricCanvas.requestRenderAll()
  }

  imageEl.onerror = () => {
    if (!fabricCanvas) return
    if (activePageIndex.value !== targetPageIndex || renderToken.value !== token) return
    const placeholder = makePlaceholderGroup(imageData)
    fabricCanvas.add(placeholder)
    fabricCanvas.requestRenderAll()
  }

  let url = api.getVoucherImageUrl(projectId, imageData.jobId, true)
  if (url.startsWith('/api')) {
    url = (api.defaults?.baseURL || 'http://localhost:8000') + url
  }
  imageEl.src = url
}

const loadActivePageToCanvas = async () => {
  if (!fabricCanvas || !activePage.value) return
  const targetPageIndex = activePageIndex.value
  const token = renderToken.value + 1
  renderToken.value = token

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
      bg.set('data', { kind: 'background' })
      if (bg.width && bg.height) {
        bg.scaleX = CANVAS_WIDTH / bg.width
        bg.scaleY = CANVAS_HEIGHT / bg.height
      }
      fabricCanvas.add(bg)
      bg.sendToBack()
      drawSafeZoneGuides()
      fabricCanvas.requestRenderAll()
    }
    bgImage.src = templateDataUrl.value
  } else {
    drawSafeZoneGuides()
  }

  ;(activePage.value.images || []).forEach(imageData => {
    addInvoiceObjectToCanvas(imageData, targetPageIndex, token)
  })
}

const removeSelectedOnCanvas = () => {
  if (!fabricCanvas) return
  const selected = fabricCanvas.getActiveObjects().filter(obj => obj?.data?.kind === 'invoice')
  if (!selected.length) return
  selected.forEach(obj => fabricCanvas.remove(obj))
  fabricCanvas.discardActiveObject()
  fabricCanvas.requestRenderAll()
  syncActivePageFromCanvas()
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
  })

  fabricCanvas.on('object:scaling', (event) => {
    const obj = event.target
    if (!obj || obj?.data?.kind !== 'invoice') return
    applyObjectBounds(obj)
  })

  fabricCanvas.on('object:modified', () => {
    syncActivePageFromCanvas()
  })

  fabricCanvas.on('object:removed', () => {
    syncActivePageFromCanvas()
  })
}

onMounted(async () => {
  try {
    const [templateResp, layoutResp] = await Promise.all([
      api.getVoucherTemplate(projectId),
      api.getVoucherLayout(projectId),
    ])
    templatePng.value = templateResp.data.templatePng || ''
    invoices.value = templateResp.data.invoices || []
    if (layoutResp.data?.pages?.length) {
      pages.value = layoutResp.data.pages
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

  keyboardHandler = (event) => {
    if (event.key === 'Delete' || event.key === 'Backspace') {
      removeSelectedOnCanvas()
    }
  }
  window.addEventListener('keydown', keyboardHandler)

  autosaveTimer = window.setInterval(saveLayout, 30000)
})

onBeforeUnmount(async () => {
  if (autosaveTimer) {
    window.clearInterval(autosaveTimer)
  }
  if (keyboardHandler) {
    window.removeEventListener('keydown', keyboardHandler)
  }
  if (fabricCanvas) {
    fabricCanvas.dispose()
    fabricCanvas = null
  }
  await saveLayout()
})

watch([globalPrefix, startIndex], () => {
  let runningIndex = startIndex.value
  pages.value.forEach(page => {
    if (page.images.length > 0) {
      const count = page.images.length
      const from = String(runningIndex).padStart(2, '0')
      const to = String(runningIndex + count - 1).padStart(2, '0')
      page.fields.voucherNo = count > 1
        ? `${globalPrefix.value}-${from}~${to}`
        : `${globalPrefix.value}-${from}`
      runningIndex += count
    }
  })
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
</style>
