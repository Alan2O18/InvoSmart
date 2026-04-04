<template>
  <div class="kanban-view">
    <header class="kanban-header">
      <div class="header-left">
        <button @click="$router.push('/')" class="back-btn">← 回首頁</button>
        <h2>PDF 處理流程看板</h2>
      </div>
      <div class="header-right">
        <select v-model="selectedProjectId" @change="fetchJobs" class="project-selector">
          <option value="">載入中...</option>
          <option v-for="p in projects" :key="p.project_id" :value="p.project_id">
            {{ p.name || p.project_id }}
          </option>
        </select>
        <button @click="fetchJobs" class="refresh-btn">🔄 更新</button>
      </div>
    </header>

    <div class="kanban-board" v-if="selectedProjectId">
      
      <!-- Column 1: Uploaded (待蓋章) -->
      <div class="kanban-col">
        <div class="col-header uploaded">
          <h3>📥 待蓋章排版</h3>
          <span class="count">{{ columnJobs.uploaded.length }}</span>
        </div>
        <div class="col-body">
          <div class="kanban-card" v-for="job in columnJobs.uploaded" :key="job.job_id">
            <div class="card-img" v-if="job.image_path">
              <img :src="getImageUrl(job.image_path)" alt="preview" />
            </div>
            <div class="card-info">
              <div class="filename">{{ getFilename(job.image_path) }}</div>
              <div class="job-id">{{ job.job_id.split('-').pop() }}</div>
            </div>
            <div class="card-actions">
              <button @click="editPdf(job)" class="action-btn">編輯 PDF</button>
            </div>
          </div>
          <div v-if="!columnJobs.uploaded.length" class="empty-msg">無待處理項目</div>
        </div>
      </div>

      <!-- Column 2: Compressing (壓縮中) -->
      <div class="kanban-col">
        <div class="col-header compressing">
          <h3>⚙️ 壓縮與合併中</h3>
          <span class="count">{{ columnJobs.compressing.length }}</span>
        </div>
        <div class="col-body">
          <div class="kanban-card locked" v-for="job in columnJobs.compressing" :key="job.job_id">
            <div class="card-img" v-if="job.image_path">
              <img :src="getImageUrl(job.image_path)" alt="preview" />
            </div>
            <div class="card-info">
              <div class="filename">{{ getFilename(job.image_path) }}</div>
              <div class="compress-loader">處理中...</div>
            </div>
          </div>
          <div v-if="!columnJobs.compressing.length" class="empty-msg">無執行中項目</div>
        </div>
      </div>

      <!-- Column 3: Completed (已完成) -->
      <div class="kanban-col">
        <div class="col-header completed">
          <h3>✅ 完成</h3>
          <span class="count">{{ columnJobs.completed.length }}</span>
        </div>
        <div class="col-body">
          <div class="kanban-card success" v-for="job in columnJobs.completed" :key="job.job_id">
            <div class="card-img" v-if="job.image_path">
              <img :src="getImageUrl(job.image_path)" alt="preview" />
            </div>
            <div class="card-info">
              <div class="filename">{{ getFilename(job.image_path) }}</div>
              <div class="done-mark">已壓平</div>
            </div>
            <div class="card-actions two-btns">
              <button @click="downloadPdf(job)" class="action-btn dl-btn">📥 下載</button>
              <button @click="editPdf(job)" class="action-btn read-btn">查看</button>
            </div>
          </div>
          <div v-if="!columnJobs.completed.length" class="empty-msg">尚未有完成項目</div>
        </div>
      </div>

    </div>
    
    <div v-else class="select-hint">
        請先在右上方選擇一個活動專案以查看 Kanban
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'

const router = useRouter()
const projects = ref([])
const selectedProjectId = ref('')
const allJobs = ref([])
let pollInterval = null

onMounted(async () => {
  try {
    const res = await api.getProjects()
    projects.value = res.data.filter(p => p.status !== 'SEALED' && p.status !== 'ARCHIVED')
    if (projects.value.length > 0) {
      selectedProjectId.value = projects.value[0].project_id
      await fetchJobs()
    }
    
    // Auto refresh every 5s for the Kanban board
    pollInterval = setInterval(fetchJobs, 5000)
  } catch (e) {
    console.error('Initial fetch failed', e)
  }
})

onUnmounted(() => {
    if (pollInterval) clearInterval(pollInterval)
})

const fetchJobs = async () => {
  if (!selectedProjectId.value) return
  
  try {
    const res = await api.getProjectJobs(selectedProjectId.value)
    allJobs.value = res.data
  } catch (error) {
    console.error('Fetch jobs error', error)
  }
}

// Group jobs by PDF status
const columnJobs = computed(() => {
    const uploaded = []
    const compressing = []
    const completed = []
    
    allJobs.value.forEach(job => {
        if (!job.source_pdf_path) return // 忽略非 PDF 任務
        
        if (job.pdf_status === 'uploaded') uploaded.push(job)
        else if (job.pdf_status === 'pending_compression' || job.pdf_status === 'compressing') compressing.push(job)
        else if (job.pdf_status === 'completed') completed.push(job)
    })
    
    return { uploaded, compressing, completed }
})

const getFilename = (path) => path ? path.split('\\').pop().split('/').pop() : ''

const getImageUrl = (path) => {
  if (!path) return ''
  const filename = getFilename(path)
  return `http://localhost:8000/api/projects/${encodeURIComponent(selectedProjectId.value)}/preview/split/${encodeURIComponent(filename)}`
}

const editPdf = (job) => {
    router.push(`/project/${selectedProjectId.value}/pdf-editor?jobId=${job.job_id}`)
}

const downloadPdf = async (job) => {
    try {
        const res = await api.downloadPdf(selectedProjectId.value, job.job_id)
        // 建立假連結觸發下載
        const url = window.URL.createObjectURL(new Blob([res.data]))
        const link = document.createElement('a')
        link.href = url
        link.setAttribute('download', `${getFilename(job.source_pdf_path)}_compressed.pdf`)
        document.body.appendChild(link)
        link.click()
        link.remove()
    } catch (e) {
        alert("下載失敗")
    }
}
</script>

<style scoped>
.kanban-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #1a1a1a;
  color: #e0e0e0;
}

.kanban-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem 2rem;
  background: #252525;
  border-bottom: 1px solid #444;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.header-left h2 {
  margin: 0;
  font-size: 1.5rem;
  color: #60a5fa;
}

.header-right {
  display: flex;
  gap: 1rem;
}

.back-btn {
  background: transparent;
  color: #e0e0e0;
  border: 1px solid #666;
  padding: 0.5rem 1rem;
  cursor: pointer;
  border-radius: 4px;
}

.project-selector {
  padding: 0.5rem;
  background: #333;
  color: white;
  border: 1px solid #555;
  border-radius: 4px;
  font-size: 1rem;
  min-width: 250px;
}

.refresh-btn {
  background: #4b5563;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
}

.select-hint {
    display: flex;
    justify-content: center;
    align-items: center;
    flex: 1;
    color: #888;
    font-size: 1.2rem;
}

.kanban-board {
  display: flex;
  flex: 1;
  gap: 1.5rem;
  padding: 2rem;
  overflow-x: auto;
}

.kanban-col {
  flex: 1;
  min-width: 300px;
  max-width: 400px;
  display: flex;
  flex-direction: column;
  background: #222;
  border-radius: 8px;
  border: 1px solid #333;
}

.col-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border-bottom: 2px solid #444;
  border-radius: 8px 8px 0 0;
}

.col-header h3 { margin: 0; font-size: 1.1rem; }
.count { background: #444; padding: 0.2rem 0.6rem; border-radius: 99px; font-weight: bold; font-size: 0.9rem; }

.col-header.uploaded { border-bottom-color: #3b82f6; }
.col-header.compressing { border-bottom-color: #f59e0b; }
.col-header.completed { border-bottom-color: #10b981; }

.col-body {
  flex: 1;
  padding: 1rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.kanban-card {
  background: #333;
  border-left: 4px solid #3b82f6;
  border-radius: 6px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  box-shadow: 0 4px 6px rgba(0,0,0,0.3);
  transition: transform 0.2s;
}

.kanban-card:hover {
    transform: translateY(-2px);
}

.kanban-card.locked { border-left-color: #f59e0b; opacity: 0.8; }
.kanban-card.success { border-left-color: #10b981; }

.card-img {
  height: 120px;
  background: #000;
  border-radius: 4px;
  overflow: hidden;
  display: flex;
  justify-content: center;
}
.card-img img { height: 100%; object-fit: contain; }

.card-info {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.filename {
  font-weight: bold;
  font-size: 0.95rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}

.job-id { color: #888; font-size: 0.75rem; font-family: monospace; }
.compress-loader { color: #f59e0b; font-size: 0.85rem; font-weight: bold; animation: pulse 1.5s infinite; }
.done-mark { color: #10b981; font-weight: bold; font-size: 0.85rem; }

.card-actions {
  display: flex;
  gap: 0.5rem;
}

.action-btn {
  flex: 1;
  padding: 0.5rem;
  border: none;
  background: #2563eb;
  color: white;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
  font-size: 0.85rem;
}
.action-btn:hover { background: #1d4ed8; }

.dl-btn { background: #059669; }
.dl-btn:hover { background: #047857; }
.read-btn { background: #4b5563; }
.read-btn:hover { background: #374151; }

.empty-msg {
    text-align: center;
    color: #666;
    margin-top: 2rem;
    font-size: 0.95rem;
}

@keyframes pulse {
    0% { opacity: 0.6; }
    50% { opacity: 1; }
    100% { opacity: 0.6; }
}
</style>
