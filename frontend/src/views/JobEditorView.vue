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
        <button @click="rerunVLM" :disabled="regenerating" class="regen-btn" title="Re-run VLM">
            {{ regenerating ? 'Thinking...' : '⚡ Re-run' }}
        </button>
        <button @click="save" :disabled="saving" class="save-btn" :title="'Ctrl + Enter / Ctrl + S' + (isDirty ? ' (Unsaved)' : '')">
          {{ saving ? 'Saving...' : (isDirty ? 'Save *' : 'Save') }}
        </button>
      </div>
    </header>

    <div class="panels-container">
      <!-- Panel 1: Image -->
      <div class="panel" :style="{ flex: panelSizes[0] }" ref="panel1">
        <div class="panel-header" :class="{ 'focused': focusedPanel === 1 }">
          <span class="panel-title">📷 Reference (Alt+1)</span>
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

      <!-- Panel 2: Form Editor -->
      <div class="panel" :style="{ flex: panelSizes[1] }" ref="panel2">
        <div class="panel-header" :class="{ 'focused': focusedPanel === 2 }">
          <span class="panel-title">📝 Form Editor (Alt+2) <span v-if="isDirty" class="dirty-mark">*</span></span>
          <div class="panel-controls">
            <button @click="togglePanel(1)" class="panel-btn">{{ panelSizes[1] > 0.1 ? '−' : '+' }}</button>
          </div>
        </div>
        <div class="panel-content" v-show="panelSizes[1] > 0.1">
           <JsonFieldEditor 
              :modelValue="debouncedJsonData"
              @update:modelValue="updateFromForm"
              :isJsonInvalid="isJsonInvalid"
              :validation="job?.validation"
           />
        </div>
        <div class="resize-handle" @mousedown="startResize(1, $event)"></div>
      </div>

      <!-- Panel 3: JSON Editor -->
      <div class="panel" :style="{ flex: panelSizes[2] }" ref="panel3">
        <div class="panel-header" :class="{ 'focused': focusedPanel === 3 }">
          <span class="panel-title">🔧 JSON Editor (Alt+3) <span v-if="isDirty" class="dirty-mark">*</span></span>
          <div class="panel-controls">
            <button @click="togglePanel(2)" class="panel-btn">{{ panelSizes[2] > 0.1 ? '−' : '+' }}</button>
          </div>
        </div>
        <div class="panel-content" v-show="panelSizes[2] > 0.1">
             <SmartJsonEditor 
                v-model="manualJsonData" 
                @save="save"
                :showQuickFields="false"
             />
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
import { isEqual, debounce } from 'lodash-es'
import api from '../services/api'
import SmartJsonEditor from '../components/SmartJsonEditor.vue'
import JsonFieldEditor from '../components/JsonFieldEditor.vue'
import ImageViewer from '../components/ImageViewer.vue'

// --- Helpers ---
const getFilename = (path) => {
  if (!path) return ''
  return path.split('\\').pop().split('/').pop()
}

// --- Setup ---
const route = useRoute()
const router = useRouter()
const projectId = route.params.id

// --- State ---
const job = ref(null)
const manualJsonData = ref({}) // Source of Truth
const debouncedJsonData = ref({}) // Delayed for Form View
const initialJsonData = ref({}) // Track original
const saving = ref(false)
const regenerating = ref(false)
const panelSizes = ref([1, 1, 1]) 
const jobList = ref([])
const isJsonInvalid = ref(false) // Track if SmartJsonEditor has massive error
const focusedPanel = ref(2) // Default focus Form

// --- Computed ---
const imageUrl = computed(() => {
  if (!job.value?.image_path) return ''
  const filename = getFilename(job.value.image_path)
  return api.toAbsoluteUrl(`/api/projects/${encodeURIComponent(projectId)}/preview/split/${encodeURIComponent(filename)}`)
})

const currentIndex = computed(() => jobList.value.findIndex(j => j.job_id === route.query.jobId))
const hasPrev = computed(() => currentIndex.value > 0)
const hasNext = computed(() => currentIndex.value < jobList.value.length - 1)
const isDirty = computed(() => !isEqual(manualJsonData.value, initialJsonData.value))

// --- Debounce Logic for Sync ---
// When JSON changes, update debouncedJsonData after 300ms
const updateDebouncedData = debounce((newVal) => {
    debouncedJsonData.value = JSON.parse(JSON.stringify(newVal))
}, 300)

watch(manualJsonData, (newVal) => {
    updateDebouncedData(newVal)
}, { deep: true })

const updateFromForm = (newVal) => {
    // Form updates immediate source of truth
    manualJsonData.value = newVal
}

const goBack = async () => {
    if (isDirty.value) {
        const sure = confirm("您有未儲存的變更。確定要離開嗎？")
        if (sure === false) return
    }
    try {
        await router.push(`/project/${projectId}`)
    } catch (e) {
        window.location.href = `/project/${projectId}`
    }
}

const fetchJobList = async () => {
    try {
    const res = await api.getProjectJobs(projectId)
        jobList.value = res.data
        if (hasNext.value) preloadImage(jobList.value[currentIndex.value + 1])
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
            parsedData = res.data.vlm_result || {}
        }
    } else if (res.data.vlm_result) {
        parsedData = res.data.vlm_result
    }
    
    manualJsonData.value = parsedData
    debouncedJsonData.value = JSON.parse(JSON.stringify(parsedData)) // Init immediately
    initialJsonData.value = JSON.parse(JSON.stringify(parsedData))
    
  } catch (e) {
    alert('Error loading job: ' + e)
  }
}

const preloadImage = (jobMeta) => {
    if (!jobMeta || !jobMeta.image_path) return
    const filename = getFilename(jobMeta.image_path)
    const url = api.toAbsoluteUrl(`/api/projects/${encodeURIComponent(projectId)}/preview/split/${encodeURIComponent(filename)}`)
    const img = new Image()
    img.src = url
}

const save = async () => {
  saving.value = true
  try {
    await api.saveManualJson(projectId, route.query.jobId, manualJsonData.value)
    // alert('Saved JSON Data!') 
    initialJsonData.value = JSON.parse(JSON.stringify(manualJsonData.value))
    return true
  } catch (e) {
    alert('Error saving: ' + e)
    return false
  } finally {
    saving.value = false
  }
}

const rerunVLM = async () => {
  if (!confirm("確定要重新執行 VLM 嗎？這將會覆蓋您目前的編輯內容。")) return
  
  regenerating.value = true
  try {
    const res = await api.runSingleProcessing(projectId, route.query.jobId)
    // 更新 Job 資料
    job.value = res.data.result ? { ...job.value, vlm_result: res.data.result } : job.value
    
    // 更新 JSON 編輯器
    if (res.data.result) {
        manualJsonData.value = res.data.result
        initialJsonData.value = JSON.parse(JSON.stringify(res.data.result))
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


const checkUnsavedChanges = async () => {
    if (isDirty.value) return confirm("您有未儲存的變更。確定要離開嗎？")
    return true
}

const navigateToJob = (newJobId) => router.push({ query: { jobId: newJobId } })

const goToPrev = async () => {
    if (!hasPrev.value) return
    if (!(await checkUnsavedChanges())) return
    navigateToJob(jobList.value[currentIndex.value - 1].job_id)
}

const goToNext = async () => {
    if (!hasNext.value) return
    if (!(await checkUnsavedChanges())) return
    navigateToJob(jobList.value[currentIndex.value + 1].job_id)
}

const handleSaveAndNext = async () => {
    if (await save()) {
         if (hasNext.value) {
             const nextJob = jobList.value[currentIndex.value + 1]
             navigateToJob(nextJob.job_id)
         } else {
             alert("已儲存 (這是最後一張)")
         }
    }
}

// --- Resize Logic ---
let startX = 0, startSizes = [], resizingPanel = null

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
  sizes[index] = sizes[index] > 0.1 ? 0.05 : 1
  panelSizes.value = sizes
}

// --- Lifecycle & Watches ---
const handleKeydown = (e) => {
    // Alt + Left/Right
    if (e.altKey && e.key === 'ArrowLeft') { e.preventDefault(); goToPrev(); }
    if (e.altKey && e.key === 'ArrowRight') { e.preventDefault(); goToNext(); }
    
    // Ctrl + Enter (Save & Next)
    if (e.ctrlKey && e.key === 'Enter') {
        e.preventDefault()
        handleSaveAndNext()
    }
    
    // Alt + 1/2/3 Focus
    if (e.altKey && ['1','2','3'].includes(e.key)) {
        e.preventDefault()
        focusedPanel.value = parseInt(e.key)
    }
}

onMounted(() => {
  if (!route.query.jobId) {
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

onBeforeRouteLeave(async (to, from, next) => {
    if (isDirty.value) {
        const sure = confirm("您有未儲存的變更。確定要離開嗎？")
        if (!sure) {
            next(false)
            return
        }
    }
    next()
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
  padding: 0.5rem 1rem;
  background: #2a2a2a;
  border-bottom: 1px solid #444;
  height: 50px;
}

.back-btn {
  background: transparent;
  border: 1px solid #4b5563;
  color: #d1d5db;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: all 0.2s;
}
.back-btn:hover {
  border-color: #9ca3af;
  color: white;
  background: rgba(255, 255, 255, 0.05);
}

.header-actions { margin-left: auto; display: flex; gap: 0.5rem; }

.nav-controls {
    display: flex; align-items: center; gap: 1rem; flex: 1; justify-content: center;
}

.job-info { text-align: center; }
.job-info h1 { font-size: 1rem; margin: 0; max-width: 400px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.job-count { font-size: 0.75rem; color: #888; }

.nav-btn {
    background: #333; border: 1px solid #555; color: #eee;
    padding: 0.25rem 0.8rem; border-radius: 4px; cursor: pointer;
}
.nav-btn:disabled { opacity: 0.3; cursor: not-allowed; }

.save-btn {
  background: #059669; color: white; border: none;
  padding: 0.25rem 1rem; cursor: pointer; border-radius: 4px; font-weight: bold;
}
.save-btn:disabled { opacity: 0.7; cursor: wait; }

.regen-btn {
    background: #e11d48; color: white; border: none;
    padding: 0.25rem 1rem; cursor: pointer; border-radius: 4px; font-weight: bold;
    margin-right: 10px;
}

.panels-container {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.panel {
  display: flex; flex-direction: column;
  min-width: 50px; position: relative;
  background: #222; border-right: 1px solid #444;
}

.panel-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0.25rem 0.5rem; background: #333; border-bottom: 1px solid #444;
  font-size: 0.8rem; color: #aaa;
}
.panel-header.focused {
    background: #444; color: #fff;
    border-bottom: 2px solid #0ea5e9;
}

.panel-content { flex: 1; overflow: auto; padding: 0.5rem; }

.panel-title { font-weight: bold; }
.dirty-mark { color: #f59e0b; margin-left: 5px; }

.panel-btn {
  background: #444; border: none; color: white;
  padding: 0 5px; cursor: pointer; border-radius: 3px;
}

.image-panel {
  display: flex; align-items: center; justify-content: center;
  background: #000; overflow: hidden; padding: 0;
}

.resize-handle {
  position: absolute; right: 0; top: 0; bottom: 0; width: 5px;
  cursor: col-resize; background: transparent; z-index: 10;
}
.resize-handle:hover { background: #0ea5e9; }

.loading { display: flex; align-items: center; justify-content: center; height: 100vh; color: #888; }
</style>
