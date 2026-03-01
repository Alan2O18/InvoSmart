<template>
  <div class="pdf-workbench">
    <div class="toolbar">
      <div class="tools-left">
        <button @click="addStamp('pass')" class="stamp-btn pass">✅ 蓋章 (Pass)</button>
        <button @click="addStamp('fail')" class="stamp-btn fail">❌ 蓋章 (Fail)</button>
        <button @click="addStamp('text')" class="stamp-btn text">📝 加入文字</button>
        <button @click="deleteSelected" class="stamp-btn delete" :disabled="!hasSelection">🗑️ 刪除選取</button>
      </div>
      <div class="tools-center">
        <button @click="prevPage" :disabled="currentPage <= 1">◀</button>
        <span>第 {{ currentPage }} / {{ totalPages }} 頁</span>
        <button @click="nextPage" :disabled="currentPage >= totalPages">▶</button>
      </div>
      <div class="tools-right">
        <button @click="saveAndCompress" :disabled="saving" class="save-btn">
          {{ saving ? '處理中...' : '💾 儲存並壓平 PDF' }}
        </button>
      </div>
    </div>

    <div class="workspace">
      <!-- Left Panel: PDF & Canvas -->
      <div class="canvas-container" ref="containerRef">
        <div class="canvas-wrapper" v-show="!loadingPdf">
          <canvas ref="pdfCanvasRef" class="pdf-layer"></canvas>
          <canvas ref="fabricCanvasRef" class="fabric-layer"></canvas>
        </div>
        <div v-if="loadingPdf" class="loading-overlay">
          載入 PDF 中...
        </div>
      </div>

      <!-- Right Panel: Data Editor -->
      <div class="data-panel">
        <div class="panel-header">
           <span>📝 發票資料核對</span>
        </div>
        <div class="panel-content">
          <JsonFieldEditor 
            :modelValue="formData"
            @update:modelValue="formData = $event"
            :validation="job?.validation"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, shallowRef, watch } from 'vue'
import * as pdfjsLib from 'pdfjs-dist/build/pdf'
import * as fabric from 'fabric' // Correct import for v6 fabric.js
import api from '../services/api'
import JsonFieldEditor from './JsonFieldEditor.vue'

// Set up PDF.js worker using CDN to avoid Vite build complexity for now
pdfjsLib.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.mjs`

const props = defineProps({
  job: { type: Object, required: true },
  projectId: { type: String, required: true }
})
const emit = defineEmits(['saved'])

// State
const containerRef = ref(null)
const pdfCanvasRef = ref(null)
const fabricCanvasRef = ref(null)
const loadingPdf = ref(true)
const saving = ref(false)
const formData = ref({})
const hasSelection = ref(false)

const currentPage = ref(1)
const totalPages = ref(1)

// Refs
const pdfDoc = shallowRef(null)
const fabricCanvas = shallowRef(null)
const pageInstances = ref({}) // Store scale info per page
const pageStamps = ref({})   // Bug 4 fix: persist stamp objects per page (pageNum -> fabric JSON array)

const initData = () => {
    let parsedData = {}
    if (props.job.manual_json_text) {
        try { parsedData = JSON.parse(props.job.manual_json_text) } 
        catch (e) { parsedData = props.job.vlm_result || {} }
    } else if (props.job.vlm_result) {
        parsedData = props.job.vlm_result
    }
    formData.value = parsedData
}

const loadPdf = async () => {
  loadingPdf.value = true
  try {
    const url = `http://localhost:8000/api/pdf/${props.projectId}/${props.job.job_id}/download`
    const loadingTask = pdfjsLib.getDocument(url)
    pdfDoc.value = await loadingTask.promise
    totalPages.value = pdfDoc.value.numPages
    await renderPage(1)
  } catch (error) {
    console.error('Error loading PDF:', error)
    alert('無法載入 PDF')
  } finally {
    loadingPdf.value = false
  }
}

const renderPage = async (pageNumber) => {
  if (!pdfDoc.value) return
  
  // Bug 4 fix: Save current page's stamps before switching
  if (fabricCanvas.value) {
    pageStamps.value[currentPage.value] = fabricCanvas.value.getObjects().map(obj => obj.toObject())
  }

  currentPage.value = pageNumber
  
  const page = await pdfDoc.value.getPage(pageNumber)
  
  // Calculate scale based on container width to fit nicely
  const containerWidth = containerRef.value.clientWidth - 40 // 40px padding
  const unscaledViewport = page.getViewport({ scale: 1.0 })
  const scale = containerWidth / unscaledViewport.width
  const viewport = page.getViewport({ scale })

  // Store scale for coordinate mapping later
  pageInstances.value[pageNumber] = { scale }

  // Prepare PDF Canvas
  const pdfCanvas = pdfCanvasRef.value
  const ctx = pdfCanvas.getContext('2d')
  pdfCanvas.height = viewport.height
  pdfCanvas.width = viewport.width

  // Render PDF
  const renderContext = {
    canvasContext: ctx,
    viewport: viewport
  }
  await page.render(renderContext).promise

  // Prepare Fabric Canvas Layer (will restore saved stamps)
  initFabric(viewport.width, viewport.height, pageNumber)
}

const initFabric = (width, height, pageNumber = currentPage.value) => {
  if (fabricCanvas.value) {
    fabricCanvas.value.dispose()
  }

  // Use the modern v6 initialization signature
  fabricCanvas.value = new fabric.Canvas(fabricCanvasRef.value, {
    width,
    height,
    selection: true
  })

  fabricCanvas.value.on('selection:created', () => hasSelection.value = true)
  fabricCanvas.value.on('selection:cleared', () => hasSelection.value = false)

  // Bug 4 fix: Restore saved stamps for this page
  const saved = pageStamps.value[pageNumber] || []
  saved.forEach(objData => {
    fabric.util.enlivenObjects([objData]).then(([fabricObj]) => {
      if (fabricObj) {
        fabricCanvas.value.add(fabricObj)
        fabricCanvas.value.renderAll()
      }
    })
  })
}

const addStamp = (type) => {
  if (!fabricCanvas.value) return
  
  let stampText = ''
  let color = 'red'
  
  if (type === 'pass') { stampText = '✅ PASS'; color = '#059669' }
  else if (type === 'fail') { stampText = '❌ FAIL'; color = '#dc2626' }
  else if (type === 'text') { stampText = '請再次核對'; color = '#2563eb' }

  // Define object in modern fabric syntax
  const text = new fabric.Textbox(stampText, {
    left: fabricCanvas.value.width / 2 - 50,
    top: 50,
    width: 200,
    fontSize: 24,
    fill: color,
    fontWeight: 'bold',
    fontFamily: 'sans-serif',
    borderColor: '#0ea5e9',
    cornerColor: '#0ea5e9',
    transparentCorners: false,
  })

  fabricCanvas.value.add(text)
  fabricCanvas.value.setActiveObject(text)
  fabricCanvas.value.renderAll()
}

const deleteSelected = () => {
    if (!fabricCanvas.value) return
    const activeObjects = fabricCanvas.value.getActiveObjects()
    if (activeObjects.length) {
        fabricCanvas.value.discardActiveObject()
        activeObjects.forEach((obj) => fabricCanvas.value.remove(obj))
    }
}

const prevPage = () => {
    if (currentPage.value > 1) renderPage(currentPage.value - 1)
}
const nextPage = () => {
    if (currentPage.value < totalPages.value) renderPage(currentPage.value + 1)
}

// Convert fabric pixels to PDF points (1/72 inch)
const exportFabricCommands = () => {
  // Bug 4 fix: First save the current page's stamps
  if (fabricCanvas.value) {
    pageStamps.value[currentPage.value] = fabricCanvas.value.getObjects().map(obj => obj.toObject())
  }

  const stamps = []
  Object.entries(pageInstances.value).forEach(([pageNum, pageInfo]) => {
    const pageNumber = parseInt(pageNum)
    const scale = pageInfo.scale
    const saved = pageStamps.value[pageNumber] || []
    saved.forEach(obj => {
      stamps.push({
        page: pageNumber - 1,         // 0-indexed for backend
        text: obj.text,
        x: (obj.left || 0) / scale,  // Convert to PDF points
        y: (obj.top || 0) / scale,
        color: obj.fill,
        fontsize: (obj.fontSize || 24) / scale
      })
    })
  })
  return stamps
}

const saveAndCompress = async () => {
  if (!confirm("儲存後會壓平面板並把結果存回 Job，確定執行嗎？")) return
  
  saving.value = true
  try {
    // 1. Save JSON Data back to manual_json First
    await api.saveManualJson(props.projectId, props.job.job_id, formData.value)
    
    // 2. Export stamps and tell engine to compress
    const commands = {
      page_order: Array.from({length: totalPages.value}, (_, i) => i),
      stamps: exportFabricCommands()
    }
    
    await api.executePdfCommands(props.projectId, props.job.job_id, commands)
    
    alert('PDF 指令已送出壓縮！後台正在處理中。')
    emit('saved')
  } catch (error) {
    console.error("Save error:", error)
    alert("儲存失敗：" + error.message)
  } finally {
    saving.value = false
  }
}

// Handle window resize elegantly
let resizeTimeout = null
const handleResize = () => {
    if (resizeTimeout) clearTimeout(resizeTimeout)
    resizeTimeout = setTimeout(() => {
        if (!loadingPdf.value && pdfDoc.value) {
            renderPage(currentPage.value) // re-render to fit width
        }
    }, 200)
}

onMounted(() => {
  initData()
  loadPdf()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
    window.removeEventListener('resize', handleResize)
    if (fabricCanvas.value) fabricCanvas.value.dispose()
})
</script>

<style scoped>
.pdf-workbench {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1e1e1e;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: #252525;
  border-bottom: 1px solid #444;
}

.tools-left {
  display: flex;
  gap: 0.5rem;
}

.stamp-btn {
  padding: 0.4rem 0.8rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
  font-size: 0.9rem;
}

.stamp-btn.pass { background: #059669; color: white; }
.stamp-btn.fail { background: #dc2626; color: white; }
.stamp-btn.text { background: #2563eb; color: white; }
.stamp-btn.delete { background: #4b5563; color: white; }
.stamp-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.tools-center {
  display: flex;
  align-items: center;
  gap: 1rem;
  font-weight: bold;
}
.tools-center button {
  background: #333;
  color: white;
  border: 1px solid #555;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
}
.tools-center button:disabled { opacity: 0.3; }

.save-btn {
  background: #f59e0b;
  color: black;
  border: none;
  font-weight: bold;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
}
.save-btn:disabled { opacity: 0.7; }

.workspace {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.canvas-container {
  flex: 2;
  position: relative;
  overflow-y: auto;
  overflow-x: hidden;
  background: #111;
  padding: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.canvas-wrapper {
  position: relative;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.5);
  background: white; /* PDF background */
}

/* 疊加技巧 */
.pdf-layer {
  display: block;
}

.fabric-layer {
  position: absolute !important;
  top: 0;
  left: 0;
  pointer-events: auto;
}

.loading-overlay {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #888;
  font-size: 1.2rem;
}

.data-panel {
  flex: 1;
  min-width: 350px;
  max-width: 500px;
  border-left: 1px solid #444;
  background: #2a2a2a;
  display: flex;
  flex-direction: column;
}

.panel-header {
  padding: 0.75rem 1rem;
  background: #333;
  border-bottom: 1px solid #444;
  font-weight: bold;
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}
</style>
