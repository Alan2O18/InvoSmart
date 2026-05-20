<template>
  <div class="upload-page">
    <header class="page-header">
      <div>
        <h1>印章圖片 / PDF 上傳與框選</h1>
        <p>上傳包含印章的原始圖檔或掃描 PDF，框選每一顆印章並指定擁有者。</p>
      </div>
      <div>
        <button class="secondary" @click="goBack">返回上層</button>
      </div>
    </header>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <!-- Step 1: File Selection -->
    <div class="upload-section" v-if="!activeImageSrc">
      <div class="upload-box">
        <label for="stamp-file">點擊選擇圖片或 PDF 檔 (.png, .jpg, .pdf)</label>
        <input 
          id="stamp-file" 
          type="file" 
          accept="image/*,application/pdf"
          @change="handleFileChange" 
        />
      </div>
      <p v-if="loading" class="loading-msg">檔案處理中，請稍候...</p>
    </div>

    <!-- Step 2: Editor Interface (Fabric.js) -->
    <div class="editor-section" v-show="activeImageSrc">
      <div class="toolbar">
        <div class="tool-group">
          <strong>1. 框選印章：</strong>
          <button @click="startDrawing" :class="{ active: isDrawingMode }">
            {{ isDrawingMode ? '請在右圖拖曳新增框' : '+ 新增框選' }}
          </button>
        </div>

        <div class="tool-group">
          <strong>2. 設定屬性：</strong>
          <select v-model="selectedOwnerId" :disabled="!activeObject" title="選擇這顆印章是誰的">
            <option disabled value="">（請先點選框）選擇人員</option>
            <option v-for="p in persons" :key="p.id" :value="p.id">
              {{ p.name }} ({{ p.role }})
            </option>
          </select>
          <select v-model="selectedMode" :disabled="!activeObject" title="選擇去背模式">
            <option value="red">紅印章 (red)</option>
            <option value="edge">邊緣保留 (edge)</option>
          </select>
          <button @click="applySelection" :disabled="!activeObject || !selectedOwnerId" class="apply-btn">
            確認此框
          </button>
          <button @click="removeActiveSelection" :disabled="!activeObject" class="danger">
            移除此框
          </button>
        </div>

        <div class="tool-group actions">
          <strong>3. 儲存：</strong>
          <button class="primary" @click="submitAllStamps" :disabled="isSubmitting || mappedBoxes.length === 0">
            {{ isSubmitting ? '上傳中...' : `儲存所有印章 (${mappedBoxes.length} 顆)` }}
          </button>
          <button class="secondary" @click="resetSession">重新上傳</button>
        </div>
      </div>

      <div class="canvas-container" id="editor-container" ref="containerRef">
        <canvas id="stamp-fabric"></canvas>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import * as fabric from 'fabric'
import * as pdfjsLib from 'pdfjs-dist'
import axios from 'axios'
import api from '../services/api'

// Define PDF.js Worker
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/build/pdf.worker.mjs', import.meta.url).toString()

const router = useRouter()
const route = useRoute()

const error = ref('')
const loading = ref(false)
const isSubmitting = ref(false)

const persons = ref([])
const activeImageSrc = ref(null) // Data URL or Object URL of the image to edit
const rawFileObj = ref(null)     // The original file (PDF/Image) to send to backend if possible

// Editor state
let canvas = null
const containerRef = ref(null)
const isDrawingMode = ref(false)
const activeObject = ref(null)
const selectedOwnerId = ref('')
const selectedMode = ref('red')
const mappedBoxes = ref([]) // Visual list of configured objects

// Fabric Draw tracking
let isDragging = false
let startX = 0
let startY = 0
let activeRect = null

const fetchPersons = async () => {
  try {
    const res = await api.listPersons()
    persons.value = res.data || []
    
    // Auto-select if ?owner=XX in query
    if (route.query.owner) {
      selectedOwnerId.value = parseInt(route.query.owner, 10)
    }
  } catch (e) {
    error.value = '無法載入人員名單'
  }
}

const goBack = () => {
  router.push('/stamps')
}

// =======================
// File Handling (Image or PDF)
// =======================
const handleFileChange = async (e) => {
  const file = e.target.files[0]
  if (!file) return
  error.value = ''
  loading.value = true
  rawFileObj.value = file

  try {
    if (file.type === 'application/pdf') {
      await processPdf(file)
    } else if (file.type.startsWith('image/')) {
      const url = URL.createObjectURL(file)
      activeImageSrc.value = url
      await initEditor(url)
    } else {
      throw new Error('不支援的檔案格式，請上傳 PDF 或圖片。')
    }
  } catch (err) {
    error.value = '處理檔案失敗：' + (err.message || err)
    resetSession()
  } finally {
    loading.value = false
  }
}

const processPdf = async (file) => {
  const arrayBuffer = await file.arrayBuffer()
  const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise
  
  // Render Page 1 to canvas (simplified for now to handle most scans)
  const page = await pdf.getPage(1)
  const scale = 2.0 // High resolution for clipping
  const viewport = page.getViewport({ scale })

  const offscreen = document.createElement('canvas')
  const ctx = offscreen.getContext('2d')
  offscreen.width = viewport.width
  offscreen.height = viewport.height

  await page.render({
    canvasContext: ctx,
    viewport: viewport
  }).promise

  // Convert rendered PDF page to data URL image
  const dataUrl = offscreen.toDataURL('image/png')
  activeImageSrc.value = dataUrl
  
  // Update rawFileObj so the backend receives the converted PNG instead of PDF
  // (Because backend registering expects an Image file to cv2.imdecode)
  const blob = await (await fetch(dataUrl)).blob()
  rawFileObj.value = new File([blob], "pdf_page_1.png", { type: "image/png" })
  
  await initEditor(dataUrl)
}

// =======================
// Fabric.js Editor
// =======================
const initEditor = async (url) => {
  await nextTick()
  
  if (canvas) {
    canvas.dispose()
  }
  canvas = new fabric.Canvas('stamp-fabric', { selection: false })
  
  fabric.Image.fromURL(url, (img) => {
    // scale to fit container width
    const containerWidth = document.getElementById('editor-container').offsetWidth || 800
    const scale = containerWidth / img.width
    
    canvas.setWidth(img.width * scale)
    canvas.setHeight(img.height * scale)
    
    img.set({
      originX: 'left',
      originY: 'top',
      scaleX: scale,
      scaleY: scale,
      selectable: false,
      evented: false,
    })
    
    canvas.setBackgroundImage(img, canvas.renderAll.bind(canvas))
    
    setupCanvasEvents()
  })
}

const setupCanvasEvents = () => {
  canvas.on('mouse:down', (o) => {
    if (!isDrawingMode.value) return
    isDragging = true
    const pointer = canvas.getPointer(o.e)
    startX = pointer.x
    startY = pointer.y
    activeRect = new fabric.Rect({
      left: startX,
      top: startY,
      width: 0,
      height: 0,
      fill: 'rgba(255, 0, 0, 0.2)',
      stroke: 'red',
      strokeWidth: 2,
      selectable: true
    })
    canvas.add(activeRect)
  })

  canvas.on('mouse:move', (o) => {
    if (!isDragging) return
    const pointer = canvas.getPointer(o.e)
    
    if (pointer.x < startX) {
      activeRect.set({ left: pointer.x })
    }
    if (pointer.y < startY) {
      activeRect.set({ top: pointer.y })
    }
    activeRect.set({
      width: Math.abs(pointer.x - startX),
      height: Math.abs(pointer.y - startY)
    })
    canvas.renderAll()
  })

  canvas.on('mouse:up', (o) => {
    if (!isDrawingMode.value || !isDragging) return
    isDragging = false
    
    if (activeRect && activeRect.width < 10) {
      canvas.remove(activeRect)
    } else if (activeRect) {
      activeRect.set({
        cornerColor: 'blue',
        cornerSize: 10,
        transparentCorners: false
      })
      canvas.setActiveObject(activeRect)
      onSelectionCreated(activeRect)
    }
    activeRect = null
    isDrawingMode.value = false
    canvas.selection = true
  })

  canvas.on('selection:created', (e) => onSelectionCreated(e.selected[0]))
  canvas.on('selection:updated', (e) => onSelectionCreated(e.selected[0]))
  canvas.on('selection:cleared', () => {
    activeObject.value = null
  })
}

const startDrawing = () => {
  isDrawingMode.value = !isDrawingMode.value
  canvas.selection = !isDrawingMode.value
}

const onSelectionCreated = (obj) => {
  activeObject.value = obj
  // Restore mapped data if it exists
  if (obj.stampData) {
    selectedOwnerId.value = obj.stampData.owner_id
    selectedMode.value = obj.stampData.mode
  }
}

const applySelection = () => {
  if (!activeObject.value) return
  if (!selectedOwnerId.value) {
    alert("請選擇該印章的擁有者。")
    return
  }

  // Store data firmly on the object
  activeObject.value.stampData = {
    owner_id: selectedOwnerId.value,
    mode: selectedMode.value,
    personName: persons.value.find(p => p.id === selectedOwnerId.value)?.name || '未命名'
  }
  
  // Style visually to show it's configured
  activeObject.value.set({
    stroke: 'green',
    fill: 'rgba(0, 255, 0, 0.2)'
  })
  
  // Text label (optional)
  canvas.renderAll()
  
  // Update external array for tracking
  syncMappedBoxes()
}

const removeActiveSelection = () => {
  if (!activeObject.value) return
  canvas.remove(activeObject.value)
  activeObject.value = null
  syncMappedBoxes()
}

const syncMappedBoxes = () => {
  const allObjects = canvas.getObjects('rect')
  mappedBoxes.value = allObjects.filter(obj => obj.stampData).map(obj => obj.stampData)
}

// =======================
// Submission
// =======================
const submitAllStamps = async () => {
  syncMappedBoxes()
  if (mappedBoxes.value.length === 0) {
    error.value = '請新增並確認至少一個印章框選。'
    return
  }

  isSubmitting.value = true
  error.value = ''

  const allObjects = canvas.getObjects('rect')
  const scale = canvas.backgroundImage.scaleX || 1.0

  // Group by owner, because API `POST /api/stamps/register` takes ONLY one `owner_id` per call!
  // Oh, wait! Our backend API schema ONLY allows a single `owner_id` per POST!
  // "mode: str, owner_id: str, selections: str = Form(...)"
  
  const groups = {}
  for (const obj of allObjects) {
    if (!obj.stampData) continue
    
    // Calculate original image coordinates
    // Fabric bounding rect values are scaled against the rendered canvas
    const x = Math.round(obj.left / scale)
    const y = Math.round(obj.top / scale)
    const w = Math.round((obj.width * obj.scaleX) / scale)
    const h = Math.round((obj.height * obj.scaleY) / scale)
    
    const ownerId = obj.stampData.owner_id
    const mode = obj.stampData.mode
    
    const sel = { x, y, w, h, owner_id: ownerId }
    
    const groupKey = `${ownerId}_${mode}`
    if (!groups[groupKey]) {
      groups[groupKey] = {
        owner_id: ownerId,
        mode: mode,
        selections: []
      }
    }
    groups[groupKey].selections.push(sel)
  }

  let successCount = 0
  let errs = []

  // Send sequentially
  for (const key of Object.keys(groups)) {
    const grp = groups[key]
    const formData = new FormData()
    formData.append('file', rawFileObj.value) // The original Image OR PDF-converted PNG
    formData.append('mode', grp.mode)
    formData.append('owner_id', grp.owner_id)
    formData.append('selections', JSON.stringify(grp.selections))

    try {
      // Use axios pointing to the backend
      const baseURL = window.location.origin.replace(/:5173$/, ':8000')
      await axios.post(`${baseURL}/api/stamps/register`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      successCount += grp.selections.length
    } catch (e) {
      errs.push(`人員 ID ${grp.owner_id}: ${e.message || e}`)
    }
  }

  isSubmitting.value = false

  if (errs.length > 0) {
    error.value = `上傳完成，但有部分錯誤：${errs.join(', ')}`
  } else {
    alert(`成功儲存 ${successCount} 顆印章！`)
    router.push('/stamps')
  }
}

const resetSession = () => {
  activeImageSrc.value = null
  rawFileObj.value = null
  if (canvas) {
    canvas.dispose()
    canvas = null
  }
  mappedBoxes.value = []
  error.value = ''
}

onMounted(() => {
  fetchPersons()
})

onBeforeUnmount(() => {
  if (canvas) canvas.dispose()
})
</script>

<style scoped>
.upload-page {
  padding: 1.5rem;
  color: #e5e7eb;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #374151;
  padding-bottom: 1rem;
  margin-bottom: 2rem;
}

.page-header h1 {
  font-size: 1.8rem;
  margin: 0 0 0.5rem 0;
}
.page-header p {
  color: #9cb3af;
  margin: 0;
}

button {
  padding: 0.5rem 1rem;
  border-radius: 4px;
  border: none;
  cursor: pointer;
  background: #374151;
  color: #fff;
}
button:hover:not(:disabled) {
  opacity: 0.8;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.primary { background: #059669; font-weight: bold; }
.secondary { background: #1d4ed8; }
.danger { background: #dc2626; color: #fff; }
.apply-btn { background: #10b981; color: #fff; }
button.active { background: #fbbf24; color: #000; font-weight: bold; }

.error-banner {
  background: rgba(220, 38, 38, 0.2);
  border: 1px solid #ef4444;
  color: #fca5a5;
  padding: 1rem;
  border-radius: 6px;
  margin-bottom: 1.5rem;
}

.upload-section {
  text-align: center;
  padding: 3rem;
  border: 2px dashed #4b5563;
  border-radius: 8px;
  background: #1f2937;
}
.upload-box label {
  display: block;
  font-size: 1.25rem;
  margin-bottom: 1rem;
  cursor: pointer;
  color: #60a5fa;
}

.editor-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  background: #1f2937;
  padding: 1rem;
  border-radius: 8px;
  border: 1px solid #334155;
  align-items: center;
}

.tool-group {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  border-right: 1px solid #4b5563;
  padding-right: 1.5rem;
}
.tool-group.actions {
  border-right: none;
  margin-left: auto;
}

select {
  padding: 0.4rem;
  border-radius: 4px;
  background: #374151;
  color: white;
  border: 1px solid #4b5563;
}

.canvas-container {
  border: 1px solid #4b5563;
  background: #111827;
  min-height: 500px;
  position: relative;
  overflow: auto;
}
</style>