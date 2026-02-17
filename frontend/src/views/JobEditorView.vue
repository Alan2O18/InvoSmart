<template>
  <div class="job-editor" v-if="job">
    <header class="editor-header">
      <button @click="goBack" class="back-btn">← Back</button>
      
      <div class="nav-controls">
         <button @click="goToPrev" :disabled="!hasPrev" class="nav-btn" title="Alt + Left">⟨ Prev</button>
         <div class="job-info">
            <h1>{{ getFilename(job.image_path) }}</h1>
            <span class="job-count" v-if="jobList.length">
                {{ currentIndex + 1 }} / {{ jobList.length }}
            </span>
         </div>
         <button @click="goToNext" :disabled="!hasNext" class="nav-btn" title="Alt + Right">Next ⟩</button>
      </div>

      <div class="header-actions">
        <button @click="save" :disabled="saving" class="save-btn" :title="'Ctrl + S' + (isDirty ? ' (Unsaved)' : '')">
          {{ saving ? 'Saving...' : (isDirty ? 'Save *' : 'Save') }}
        </button>
      </div>
    </header>

    <!-- 模式切換標籤 -->
    <div class="mode-tabs">
      <button 
        :class="{ active: editMode === 'json' }" 
        @click="editMode = 'json'"
      >🔧 JSON 結構化編輯</button>
      <button 
        :class="{ active: editMode === 'raw' }" 
        @click="editMode = 'raw'"
      >🔍 Raw VLM Output</button>
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
          <ImageViewer 
            :src="imageUrl" 
            alt="Invoice" 
          />
        </div>
        <div class="resize-handle" @mousedown="startResize(0, $event)"></div>
      </div>

      <!-- Panel 2: Editor (JSON or Raw) -->
      <div class="panel" :style="{ flex: panelSizes[1] }">
        <div class="panel-header">
          <span class="panel-title">{{ editMode === 'json' ? '🔧 JSON Structured Editor' : '🔍 Raw VLM Output' }}</span>
          <div class="panel-controls">
            <button @click="togglePanel(1)" class="panel-btn">{{ panelSizes[1] > 0.1 ? '−' : '+' }}</button>
          </div>
        </div>
        <div class="panel-content" v-show="panelSizes[1] > 0.1">
          
          <!-- JSON Editor Mode -->
          <div v-show="editMode === 'json'" class="editor-mode-json">
             <SmartJsonEditor 
                v-model="manualJsonData" 
                @save="save"
             />
          </div>

          <!-- Raw VLM Output Mode -->
          <div v-show="editMode === 'raw'" class="editor-mode-raw">
            <div class="raw-toolbar">
              <button @click="rerunVLM" :disabled="regenerating" class="regen-btn">
                {{ regenerating ? 'Processing...' : '⚡ Re-run VLM Processing' }}
              </button>
              <small class="tip">提示: 這將使用目前的 VLM 設定重新處理此圖片，並覆蓋當前編輯。</small>
            </div>
            <div class="raw-content">
              <h3>VLM Response:</h3>
              <pre class="raw-display">{{ formatLLMResult(job.llm_result) }}</pre>
            </div>
          </div>

        </div>
        <div class="resize-handle" @mousedown="startResize(1, $event)"></div>
      </div>

      <!-- Panel 3: JSON Preview -->
      <div class="panel" :style="{ flex: panelSizes[2] }">
        <div class="panel-header">
          <span class="panel-title">👁️ Live Preview</span>
          <div class="panel-controls">
            <button @click="togglePanel(2)" class="panel-btn">{{ panelSizes[2] > 0.1 ? '−' : '+' }}</button>
          </div>
        </div>
        <div class="panel-content" v-show="panelSizes[2] > 0.1">
          <div class="preview-mode">
             <div class="preview-badge">🔧 即時預覽</div>
             <pre class="result-display">{{ JSON.stringify(manualJsonData, null, 2) }}</pre>
          </div>
        </div>
        <div class="resize-handle" @mousedown="startResize(2, $event)"></div>
      </div>
    </div>
  </div>
  <div v-else class="loading">Loading... (Check console if stuck)</div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { isEqual } from 'lodash-es'
import api from '../services/api'
import SmartJsonEditor from '../components/SmartJsonEditor.vue'
import ImageViewer from '../components/ImageViewer.vue'

// --- Helpers (Defined first to avoid TDZ) ---
const getFilename = (path) => {
  if (!path) return ''
  return path.split('\\').pop().split('/').pop()
}

const formatLLMResult = (llmResult) => {
  if (!llmResult) return 'No VLM result yet'
  return JSON.stringify(llmResult, null, 2)
}

// --- Setup ---
const route = useRoute()
const router = useRouter()
const projectId = route.params.id
const jobId = route.query.jobId

// --- State ---
const job = ref(null)
const editMode = ref('json') // 'json' | 'raw'
const manualJsonData = ref({})
const initialJsonData = ref({}) // To track original for dirty check
const saving = ref(false)
const regenerating = ref(false)
const panelSizes = ref([1, 1.2, 0.8]) 
const jobList = ref([])

// --- Computed ---
const imageUrl = computed(() => {
  if (!job.value?.image_path) return ''
  const filename = getFilename(job.value.image_path)
  return `http://localhost:8000/static/${encodeURIComponent(projectId)}/分割發票/${encodeURIComponent(filename)}`
})

const currentIndex = computed(() => jobList.value.findIndex(j => j.job_id === route.query.jobId))
const hasPrev = computed(() => currentIndex.value > 0)
const hasNext = computed(() => currentIndex.value < jobList.value.length - 1)
const isDirty = computed(() => {
    return !isEqual(manualJsonData.value, initialJsonData.value)
})

// --- Methods ---
const goBack = () => {
    router.push(`/project/${projectId}`)
}

const fetchJobList = async () => {
    try {
        const res = await api.getProjectJobIds(projectId)
        jobList.value = res.data
        // Preload next image if available
        if (hasNext.value) {
            preloadImage(jobList.value[currentIndex.value + 1])
        }
    } catch (e) {
        console.error("Failed to load job list", e)
    }
}

const fetchJobDetails = async (targetJobId = null) => {
  const finalJobId = targetJobId || route.query.jobId
  if (!finalJobId) return

  try {
    const res = await api.getJobDetails(projectId, finalJobId)
    job.value = res.data
    
    let parsedData = {}
    if (res.data.manual_json_text) {
        try {
            parsedData = JSON.parse(res.data.manual_json_text)
        } catch (e) {
            parsedData = res.data.llm_result || {}
        }
    } else if (res.data.llm_result) {
        parsedData = res.data.llm_result
    }
    
    manualJsonData.value = parsedData
    initialJsonData.value = JSON.parse(JSON.stringify(parsedData)) // Deep Clone
    
  } catch (e) {
    alert('Error loading job: ' + e)
  }
}

const preloadImage = (jobMeta) => {
    if (!jobMeta || !jobMeta.image_path) return
    const filename = getFilename(jobMeta.image_path)
    const url = `http://localhost:8000/static/${encodeURIComponent(projectId)}/分割發票/${encodeURIComponent(filename)}`
    const img = new Image()
    img.src = url
}

const save = async () => {
  saving.value = true
  try {
    await api.saveManualJson(projectId, route.query.jobId, manualJsonData.value)
    alert('Saved JSON Data!')
    initialJsonData.value = JSON.parse(JSON.stringify(manualJsonData.value)) // Reset dirty
  } catch (e) {
    alert('Error saving: ' + e)
  } finally {
    saving.value = false
  }
}

const checkUnsavedChanges = async () => {
    if (isDirty.value) {
        return confirm("您有未儲存的變更。確定要離開嗎？變更將會遺失。")
    }
    return true
}

const navigateToJob = (newJobId) => {
    router.push({ query: { jobId: newJobId } })
}

const goToPrev = async () => {
    if (!hasPrev.value) return
    if (!(await checkUnsavedChanges())) return
    const prevJob = jobList.value[currentIndex.value - 1]
    navigateToJob(prevJob.job_id)
}

const goToNext = async () => {
    if (!hasNext.value) return
    if (!(await checkUnsavedChanges())) return
    const nextJob = jobList.value[currentIndex.value + 1]
    navigateToJob(nextJob.job_id)
}

const rerunVLM = async () => {
  if (!confirm("確定要重新執行 VLM 嗎？這將會覆蓋您目前的編輯內容。")) {
      return
  }
  
  regenerating.value = true
  try {
    const res = await api.runSingleProcessing(projectId, route.query.jobId)
    // 更新 Job 資料
    job.value = res.data.result ? { ...job.value, llm_result: res.data.result } : job.value
    
    // 更新 JSON 編輯器
    if (res.data.result) {
        manualJsonData.value = res.data.result
        alert('VLM Processing Complete! Data updated.')
    } else {
        alert('VLM Finished but no result returned.')
    }
  } catch (e) {
    alert('Error running VLM: ' + e)
  } finally {
    regenerating.value = false
  }
}

// --- Resize Logic ---
let startX = 0
let startSizes = []
let resizingPanel = null

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

const startResize = (panelIndex, event) => {
  resizingPanel = panelIndex
  startX = event.clientX
  startSizes = [...panelSizes.value]
  document.addEventListener('mousemove', doResize)
  document.addEventListener('mouseup', stopResize)
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

// --- Lifecycle & Watches ---

const handleKeydown = (e) => {
    // Alt + Left/Right
    if (e.altKey && e.key === 'ArrowLeft') {
        e.preventDefault()
        goToPrev()
    }
    if (e.altKey && e.key === 'ArrowRight') {
        e.preventDefault()
        goToNext()
    }
}

onMounted(() => {
  if (!route.query.jobId) {
    alert('No job ID provided')
    router.push(`/project/${projectId}`)
    return
  }
  
  fetchJobList()
  fetchJobDetails()
  
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown)
})

onBeforeRouteLeave(async (to, from) => {
    if (isDirty.value) {
        const answer = window.confirm("您有未儲存的變更。確定要離開嗎？變更將會遺失。")
        if (!answer) return false
    }
})

watch(() => route.query.jobId, (newId, oldId) => {
    if (newId && newId !== oldId) {
        manualJsonData.value = {} 
        job.value = null
        fetchJobDetails(newId) 
    }
})

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

.nav-controls {
    display: flex;
    align-items: center;
    gap: 1rem;
    flex: 1;
    justify-content: center;
}

.job-info {
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
}

.job-info h1 {
    font-size: 1.1rem;
    margin: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 400px;
}

.job-count {
    font-size: 0.8rem;
    color: #888;
}

.nav-btn {
    background: #333;
    border: 1px solid #555;
    color: #eee;
    padding: 0.25rem 0.8rem;
    border-radius: 4px;
    cursor: pointer;
}

.nav-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
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
  overflow: hidden; /* Ensure viewer doesn't overflow */
  padding: 0; /* Viewer handles its own layout */
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

.editor-mode-json {
    height: 100%;
}

.raw-display {
  white-space: pre-wrap;
  font-family: monospace;
  font-size: 0.8rem;
  background: #1a1a1a;
  padding: 0.5rem;
  border-radius: 4px;
  margin: 0;
  color: #88ff88; 
}

.raw-toolbar {
    margin-bottom: 10px;
    padding-bottom: 10px;
    border-bottom: 1px solid #444;
}

.regen-btn {
  background: #e11d48;
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
