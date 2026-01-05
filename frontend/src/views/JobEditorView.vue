<template>
  <div class="job-editor" v-if="job">
    <header class="editor-header">
      <button @click="goBack" class="back-btn">← Back</button>
      <h1>Edit Job: {{ getFilename(job.image_path) }}</h1>
      <div class="header-actions">
        <button @click="save" :disabled="saving" class="save-btn">
          {{ saving ? 'Saving...' : 'Save' }}
        </button>
      </div>
    </header>

    <!-- 模式切換標籤 -->
    <div class="mode-tabs">
      <button 
        :class="{ active: editMode === 'ocr' }" 
        @click="editMode = 'ocr'"
      >📝 OCR 文字編輯</button>
      <button 
        :class="{ active: editMode === 'json' }" 
        @click="editMode = 'json'"
      >🔧 JSON 結構化編輯</button>
    </div>

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

      <!-- Panel 2: Editor (OCR or JSON) -->
      <div class="panel" :style="{ flex: panelSizes[1] }">
        <div class="panel-header">
          <span class="panel-title">{{ editMode === 'ocr' ? '📝 OCR Text Editor' : '🔧 JSON Structured Editor' }}</span>
          <div class="panel-controls">
            <button @click="togglePanel(1)" class="panel-btn">{{ panelSizes[1] > 0.1 ? '−' : '+' }}</button>
          </div>
        </div>
        <div class="panel-content" v-show="panelSizes[1] > 0.1">
          
          <!-- OCR Editor Mode -->
          <div v-show="editMode === 'ocr'" class="editor-mode-ocr">
            <div class="ocr-toolbar">
              <button @click="regenerateLLM" :disabled="regenerating" class="regen-btn">
                {{ regenerating ? 'Regenerating...' : '🔄 根據此 OCR 重新執行 LLM' }}
              </button>
              <small class="tip">提示: 修正 OCR 文字後，點擊按鈕可重新生成 LLM 結果。</small>
            </div>
            <textarea
              v-model="manualOcrText"
              @keydown="handleKeydown"
              placeholder="Enter corrected OCR text here..."
              class="manual-textarea"
            ></textarea>
            <div class="ocr-source">
              <small>原始 OCR 結果 (唯讀):</small>
              <pre class="ocr-preview">{{ formatOCRText(job.ocr_result) }}</pre>
            </div>
          </div>

          <!-- JSON Editor Mode -->
          <div v-show="editMode === 'json'" class="editor-mode-json">
             <JsonFieldEditor v-model="manualJsonData" />
          </div>

        </div>
        <div class="resize-handle" @mousedown="startResize(1, $event)"></div>
      </div>

      <!-- Panel 3: Result Preview -->
      <div class="panel" :style="{ flex: panelSizes[2] }">
        <div class="panel-header">
          <span class="panel-title">👁️ Result Preview</span>
          <div class="panel-controls">
            <button @click="togglePanel(2)" class="panel-btn">{{ panelSizes[2] > 0.1 ? '−' : '+' }}</button>
          </div>
        </div>
        <div class="panel-content" v-show="panelSizes[2] > 0.1">
          <div v-if="manualJsonData && Object.keys(manualJsonData).length > 0" class="preview-mode">
             <div class="preview-badge">🔧 人工編輯預覽</div>
             <pre class="result-display">{{ JSON.stringify(manualJsonData, null, 2) }}</pre>
          </div>
          <div v-else class="preview-mode">
             <div class="preview-badge">🤖 LLM 原始結果</div>
             <pre class="result-display">{{ formatLLMResult(job.llm_result) }}</pre>
          </div>
        </div>
        <div class="resize-handle" @mousedown="startResize(2, $event)"></div>
      </div>
    </div>
  </div>
  <div v-else class="loading">Loading...</div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../services/api'
import JsonFieldEditor from '../components/JsonFieldEditor.vue'

const route = useRoute()
const router = useRouter()
const projectId = route.params.id
const jobId = route.query.jobId

const job = ref(null)
const editMode = ref('ocr') // 'ocr' | 'json'
const manualOcrText = ref('')
const manualJsonData = ref({})
const undoStack = ref([])
const saving = ref(false)
const regenerating = ref(false)
const panelSizes = ref([1, 1.2, 0.8]) 

const imageUrl = computed(() => {
  if (!job.value?.image_path) return ''
  const filename = getFilename(job.value.image_path)
  return `http://localhost:8000/static/${encodeURIComponent(projectId)}/分割發票/${encodeURIComponent(filename)}`
})

const fetchJobDetails = async () => {
  try {
    const res = await api.getJobDetails(projectId, jobId)
    job.value = res.data
    
    // 初始化 OCR 編輯器
    // 優先順序: manual_ocr_text > ocr_result > empty
    if (res.data.manual_ocr_text) {
      manualOcrText.value = res.data.manual_ocr_text
    } else if (res.data.ocr_result && formatOCRText(res.data.ocr_result).trim()) {
      manualOcrText.value = formatOCRText(res.data.ocr_result)
    } else {
      manualOcrText.value = ''
    }

    // 初始化 JSON 編輯器
    // 優先順序: manual_json_text (parsed) > llm_result > empty object
    if (res.data.manual_json_text) {
        try {
            manualJsonData.value = JSON.parse(res.data.manual_json_text)
            // 如果只有 JSON 編輯，預設切換到 JSON 模式
            if (res.data.edit_mode === 'json') {
                editMode.value = 'json'
            }
        } catch (e) {
            console.error("Failed to parse manual_json_text", e)
             manualJsonData.value = res.data.llm_result || {}
        }
    } else if (res.data.llm_result) {
        manualJsonData.value = res.data.llm_result
    }

    // 恢復上次的編輯模式 (如果後端有存)
    if (res.data.edit_mode) {
        editMode.value = res.data.edit_mode
    }
    
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
  if (ocrResult.text) return ocrResult.text 
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

// Undo support for OCR text
const handleKeydown = (e) => {
  if (e.ctrlKey && e.key === 'z') {
    e.preventDefault()
    if (undoStack.value.length > 0) {
      manualOcrText.value = undoStack.value.pop()
    }
  } else if (!e.ctrlKey && !e.altKey && !e.metaKey) {
    if (undoStack.value.length > 50) undoStack.value.shift()
    undoStack.value.push(manualOcrText.value)
  }
}

const save = async () => {
  saving.value = true
  try {
    // 1. Save OCR Text
    await api.saveManualText(projectId, jobId, manualOcrText.value)
    
    // 2. Save JSON Data
    await api.saveManualJson(projectId, jobId, manualJsonData.value)
    
    alert('Saved both OCR Text and JSON Data!')
  } catch (e) {
    alert('Error saving: ' + e)
  } finally {
    saving.value = false
  }
}

const regenerateLLM = async () => {
  if (!manualOcrText.value.trim()) {
    alert('Please enter some text in OCR Editor first')
    return
  }
  
  // Auto-save OCR text before regenerating
  try {
      await api.saveManualText(projectId, jobId, manualOcrText.value)
  } catch (e) {
      alert('Failed to auto-save before regenerating: ' + e)
      return
  }
  
  regenerating.value = true
  try {
    const res = await api.regenerateFromManual(projectId, jobId)
    job.value.llm_result = res.data.llm_result
    // 更新 JSON 編輯器的數據為最新的 LLM 結果 (如果用戶還沒手動編輯過 JSON，或者確認要覆蓋?)
    // 這裡我們選擇更新，因為用戶剛做完 LLM 重跑，通常期望 JSON 編輯器看到最新結果
    // 但為了安全，我們可以只在 JSON 還是空的時候自動更新，或者直接更新
    // 簡單起見，直接更新
    manualJsonData.value = res.data.llm_result
    
    alert('LLM Regenerated! JSON Editor updated.')
  } catch (e) {
    alert('Error regenerating: ' + e)
  } finally {
    regenerating.value = false
  }
}

// Panel resize logic
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

.mode-tabs {
  display: flex;
  background: #333;
  padding: 0 1rem;
  border-bottom: 1px solid #444;
}

.mode-tabs button {
  background: transparent;
  border: none;
  color: #888;
  padding: 10px 20px;
  cursor: pointer;
  font-weight: bold;
  border-bottom: 3px solid transparent;
}

.mode-tabs button.active {
  color: #fff;
  border-bottom-color: #0ea5e9;
  background: #2a2a2a;
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
  color: #ccc;
}

.manual-textarea {
  width: 100%;
  height: calc(100% - 120px);
  min-height: 300px;
  background: #1a1a1a;
  color: #e0e0e0;
  border: 1px solid #444;
  padding: 0.5rem;
  font-family: monospace;
  font-size: 0.9rem;
  resize: none;
}

.ocr-toolbar {
    margin-bottom: 10px;
    padding-bottom: 10px;
    border-bottom: 1px solid #444;
}

.regen-btn {
  background: #2563eb;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  cursor: pointer;
  border-radius: 4px;
}

.tip {
    display: block;
    margin-top: 5px;
    color: #888;
}

.ocr-source {
  margin-top: 1rem;
  border-top: 1px solid #444;
  padding-top: 0.5rem;
}

.ocr-preview {
  white-space: pre-wrap;
  font-family: monospace;
  font-size: 0.75rem;
  background: #1a1a1a;
  padding: 0.5rem;
  max-height: 150px;
  overflow: auto;
  border-radius: 4px;
  margin: 0.25rem 0 0 0;
  color: #888; 
}

.preview-badge {
    background: #0ea5e9;
    color: white;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.8rem;
    margin-bottom: 5px;
    display: inline-block;
}

.resize-handle {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 5px;
  cursor: col-resize;
  background: transparent;
  z-index: 10;
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
