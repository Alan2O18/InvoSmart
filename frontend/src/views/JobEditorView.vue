<template>
  <div class="job-editor" v-if="job">
    <header class="editor-header">
      <button @click="goBack" class="back-btn">← Back</button>
      <h1>Edit Job: {{ getFilename(job.image_path) }}</h1>
      <div class="header-actions">
        <button @click="saveManualText" :disabled="saving" class="save-btn">
          {{ saving ? 'Saving...' : 'Save' }}
        </button>
        <button @click="regenerateLLM" :disabled="regenerating" class="regen-btn">
          {{ regenerating ? 'Regenerating...' : 'Regenerate LLM' }}
        </button>
      </div>
    </header>

    <div class="panels-container">
      <!-- Panel 1: Image -->
      <div class="panel" :style="{ flex: panelSizes[0] }">
        <div class="panel-header">
          <span class="panel-title">📷 Invoice Image</span>
          <div class="panel-controls">
            <button @click="togglePanel(0)" class="panel-btn">{{ panelSizes[0] > 0.1 ? '−' : '+' }}</button>
          </div>
        </div>
        <div class="panel-content image-panel" v-show="panelSizes[0] > 0.1">
          <img :src="imageUrl" alt="Invoice" @error="handleImgError" />
        </div>
        <div class="resize-handle" @mousedown="startResize(0, $event)"></div>
      </div>

      <!-- Panel 2: LLM Result -->
      <div class="panel" :style="{ flex: panelSizes[1] }">
        <div class="panel-header">
          <span class="panel-title">🤖 LLM Result</span>
          <div class="panel-controls">
            <button @click="togglePanel(1)" class="panel-btn">{{ panelSizes[1] > 0.1 ? '−' : '+' }}</button>
          </div>
        </div>
        <div class="panel-content" v-show="panelSizes[1] > 0.1">
          <pre class="result-display">{{ formatLLMResult(job.llm_result) }}</pre>
        </div>
        <div class="resize-handle" @mousedown="startResize(1, $event)"></div>
      </div>

      <!-- Panel 3: Manual Correction -->
      <div class="panel" :style="{ flex: panelSizes[2] }">
        <div class="panel-header">
          <span class="panel-title">✏️ Manual Correction</span>
          <div class="panel-controls">
            <button @click="togglePanel(2)" class="panel-btn">{{ panelSizes[2] > 0.1 ? '−' : '+' }}</button>
          </div>
        </div>
        <div class="panel-content" v-show="panelSizes[2] > 0.1">
          <textarea
            v-model="manualText"
            @keydown="handleKeydown"
            placeholder="Enter corrected OCR text here..."
            class="manual-textarea"
          ></textarea>
          <div class="ocr-source">
            <small>OCR Source:</small>
            <pre class="ocr-preview">{{ formatOCRText(job.ocr_result) }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div v-else class="loading">Loading...</div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../services/api'

const route = useRoute()
const router = useRouter()
const projectId = route.params.id
const jobId = route.query.jobId

const job = ref(null)
const manualText = ref('')
const undoStack = ref([])
const saving = ref(false)
const regenerating = ref(false)
const panelSizes = ref([1, 1, 1])  // Equal sizing initially

const imageUrl = computed(() => {
  if (!job.value?.image_path) return ''
  const filename = getFilename(job.value.image_path)
  return `http://localhost:8000/static/${encodeURIComponent(projectId)}/分割發票/${encodeURIComponent(filename)}`
})

const fetchJobDetails = async () => {
  try {
    const res = await api.getJobDetails(projectId, jobId)
    job.value = res.data
    manualText.value = res.data.manual_ocr_text || formatOCRText(res.data.ocr_result)
  } catch (e) {
    alert('Error loading job: ' + e)
  }
}

onMounted(() => {
  if (!jobId) {
    alert('No job ID provided')
    router.push(`/project/${projectId}`)
    return
  }
  fetchJobDetails()
})

const goBack = () => {
  router.push(`/project/${projectId}`)
}

const getFilename = (path) => {
  if (!path) return ''
  return path.split('\\').pop().split('/').pop()
}

const formatOCRText = (ocrResult) => {
  if (!ocrResult) return ''
  if (typeof ocrResult === 'string') return ocrResult
  if (ocrResult.data) return ocrResult.data
  return JSON.stringify(ocrResult, null, 2)
}

const formatLLMResult = (llmResult) => {
  if (!llmResult) return 'No LLM result yet'
  return JSON.stringify(llmResult, null, 2)
}

const handleImgError = (e) => {
  e.target.src = 'https://via.placeholder.com/400x600?text=No+Image'
}

// Undo support
const handleKeydown = (e) => {
  if (e.ctrlKey && e.key === 'z') {
    e.preventDefault()
    if (undoStack.value.length > 0) {
      manualText.value = undoStack.value.pop()
    }
  } else if (!e.ctrlKey && !e.altKey && !e.metaKey) {
    // Save current state for undo
    if (undoStack.value.length > 50) undoStack.value.shift()
    undoStack.value.push(manualText.value)
  }
}

const saveManualText = async () => {
  saving.value = true
  try {
    await api.saveManualText(projectId, jobId, manualText.value)
    alert('Saved!')
  } catch (e) {
    alert('Error saving: ' + e)
  } finally {
    saving.value = false
  }
}

const regenerateLLM = async () => {
  if (!manualText.value.trim()) {
    alert('Please enter some text first')
    return
  }
  
  // Save first
  await saveManualText()
  
  regenerating.value = true
  try {
    const res = await api.regenerateFromManual(projectId, jobId)
    job.value.llm_result = res.data.llm_result
    alert('LLM regenerated!')
  } catch (e) {
    alert('Error regenerating: ' + e)
  } finally {
    regenerating.value = false
  }
}

// Panel resize
let resizingPanel = null
let startX = 0
let startSizes = []

const startResize = (panelIndex, event) => {
  resizingPanel = panelIndex
  startX = event.clientX
  startSizes = [...panelSizes.value]
  document.addEventListener('mousemove', doResize)
  document.addEventListener('mouseup', stopResize)
}

const doResize = (event) => {
  if (resizingPanel === null) return
  const delta = (event.clientX - startX) / 200
  const newSizes = [...startSizes]
  newSizes[resizingPanel] = Math.max(0.1, startSizes[resizingPanel] + delta)
  newSizes[resizingPanel + 1] = Math.max(0.1, startSizes[resizingPanel + 1] - delta)
  panelSizes.value = newSizes
}

const stopResize = () => {
  resizingPanel = null
  document.removeEventListener('mousemove', doResize)
  document.removeEventListener('mouseup', stopResize)
}

const togglePanel = (index) => {
  const sizes = [...panelSizes.value]
  if (sizes[index] > 0.1) {
    sizes[index] = 0.05
  } else {
    sizes[index] = 1
  }
  panelSizes.value = sizes
}
</script>

<style scoped>
.job-editor {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #1a1a1a;
  color: #e0e0e0;
}

.editor-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background: #2a2a2a;
  border-bottom: 1px solid #444;
}

.back-btn {
  background: transparent;
  border: 1px solid #666;
  color: #e0e0e0;
  padding: 0.5rem 1rem;
  cursor: pointer;
}

.header-actions {
  margin-left: auto;
  display: flex;
  gap: 0.5rem;
}

.save-btn {
  background: #059669;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  cursor: pointer;
  border-radius: 4px;
}

.regen-btn {
  background: #2563eb;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  cursor: pointer;
  border-radius: 4px;
}

.panels-container {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.panel {
  display: flex;
  flex-direction: column;
  min-width: 50px;
  position: relative;
  background: #222;
  border-right: 1px solid #444;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem;
  background: #333;
  border-bottom: 1px solid #444;
}

.panel-title {
  font-weight: bold;
  font-size: 0.875rem;
}

.panel-btn {
  background: #444;
  border: none;
  color: white;
  padding: 0.25rem 0.5rem;
  cursor: pointer;
  border-radius: 3px;
}

.panel-content {
  flex: 1;
  overflow: auto;
  padding: 0.5rem;
}

.image-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
}

.image-panel img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.result-display {
  white-space: pre-wrap;
  font-family: monospace;
  font-size: 0.8rem;
  background: #1a1a1a;
  padding: 0.5rem;
  border-radius: 4px;
  margin: 0;
}

.manual-textarea {
  width: 100%;
  height: 60%;
  background: #1a1a1a;
  color: #e0e0e0;
  border: 1px solid #444;
  padding: 0.5rem;
  font-family: monospace;
  font-size: 0.9rem;
  resize: none;
}

.ocr-source {
  margin-top: 0.5rem;
}

.ocr-preview {
  white-space: pre-wrap;
  font-family: monospace;
  font-size: 0.75rem;
  background: #1a1a1a;
  padding: 0.5rem;
  max-height: 200px;
  overflow: auto;
  border-radius: 4px;
  margin: 0.25rem 0 0 0;
}

.resize-handle {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 5px;
  cursor: col-resize;
  background: transparent;
}

.resize-handle:hover {
  background: #0ea5e9;
}

.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  color: #888;
}
</style>
