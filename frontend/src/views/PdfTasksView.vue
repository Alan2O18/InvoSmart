<template>
  <div class="pdf-tasks-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">PDF Tasks</p>
        <h1>獨立 PDF 任務處理</h1>
        <p class="subtitle">先看任務狀態，再進入編輯器進行蓋章、壓縮與頁面操作。</p>
      </div>
      <div class="upload-box">
        <input v-model="newTitle" type="text" placeholder="PDF 標題（可選）" />
        <input ref="fileInput" class="file-input" type="file" accept="application/pdf" @change="handleUpload" />
        <button type="button" class="primary" :disabled="uploading" @click="openFilePicker">{{ uploading ? '上傳中...' : '上傳 PDF' }}</button>
      </div>
    </header>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <div v-if="loading" class="loading">載入中...</div>

    <div v-else class="task-grid">
      <article v-for="task in tasks" :key="task.id" class="task-card" @click="openEditor(task.id)">
        <div class="task-head">
          <div>
            <h2>{{ task.title }}</h2>
            <p class="meta">{{ task.filename }}</p>
          </div>
          <span class="status">{{ task.status }}</span>
        </div>

        <div class="task-stats">
          <div><strong>頁數</strong><span>{{ task.page_count || 0 }}</span></div>
          <div><strong>模板</strong><span>{{ task.template_id || '未選擇' }}</span></div>
          <div><strong>更新</strong><span>{{ formatDate(task.updated_at) }}</span></div>
        </div>

        <div class="task-actions" @click.stop>
          <button type="button" class="secondary" @click="openEditor(task.id)">進入編輯</button>
          <button type="button" class="danger" @click="removeTask(task.id)">刪除</button>
        </div>
      </article>

      <div v-if="tasks.length === 0" class="empty-state">目前尚未上傳任何 PDF。</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'

const router = useRouter()
const tasks = ref([])
const loading = ref(false)
const uploading = ref(false)
const error = ref('')
const newTitle = ref('')
const fileInput = ref(null)

const fetchTasks = async () => {
  loading.value = true
  error.value = ''
  try {
    const response = await api.listPdfTasks()
    tasks.value = response.data || []
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message || '載入失敗'
  } finally {
    loading.value = false
  }
}

const handleUpload = async (event) => {
  const file = event.target.files?.[0]
  if (!file) return
  uploading.value = true
  try {
    await api.createPdfTask(file, newTitle.value)
    newTitle.value = ''
    if (fileInput.value) fileInput.value.value = ''
    await fetchTasks()
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message || '上傳失敗'
  } finally {
    uploading.value = false
  }
}

const openFilePicker = () => {
  fileInput.value?.click()
}

const removeTask = async (taskId) => {
  if (!confirm('確定刪除這份 PDF 任務嗎？')) return
  await api.deletePdfTask(taskId)
  await fetchTasks()
}

const openEditor = (taskId) => {
  router.push(`/pdf-tasks/${taskId}/editor`)
}

const formatDate = (value) => {
  if (!value) return '-'
  return new Date(value * 1000).toLocaleString()
}

onMounted(fetchTasks)
</script>

<style scoped>
.pdf-tasks-page {
  padding: 2rem;
  color: #e5e7eb;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  flex-wrap: wrap;
  margin-bottom: 1.5rem;
}

.eyebrow {
  margin: 0 0 0.35rem;
  color: #7dd3fc;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-size: 0.76rem;
}

h1 {
  margin: 0;
  font-size: 2rem;
}

.subtitle {
  margin: 0.5rem 0 0;
  color: #9ca3af;
}

.upload-box {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  min-width: min(100%, 320px);
  background: #111827;
  border: 1px solid #334155;
  border-radius: 12px;
  padding: 1rem;
}

.upload-box input[type="text"],
.upload-box input[type="file"] {
  width: 100%;
}

.file-input {
  display: none;
}

button {
  border: none;
  border-radius: 8px;
  padding: 0.7rem 1rem;
  cursor: pointer;
  color: white;
  font-weight: 600;
}

button.primary { background: #0f766e; }
button.secondary { background: #334155; }
button.danger { background: #b91c1c; }

.task-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1rem;
}

.task-card {
  background: #111827;
  border: 1px solid #334155;
  border-radius: 16px;
  padding: 1rem;
  cursor: pointer;
  transition: transform 0.16s ease, border-color 0.16s ease;
}

.task-card:hover {
  transform: translateY(-2px);
  border-color: #38bdf8;
}

.task-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: start;
}

.task-head h2 {
  margin: 0 0 0.25rem;
  font-size: 1.1rem;
}

.meta {
  margin: 0;
  color: #94a3b8;
  font-size: 0.9rem;
}

.status {
  background: #1d4ed8;
  color: white;
  border-radius: 999px;
  padding: 0.25rem 0.7rem;
  font-size: 0.75rem;
  white-space: nowrap;
}

.task-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.6rem;
  margin: 1rem 0;
}

.task-stats div {
  background: #0b1220;
  border: 1px solid #1e293b;
  border-radius: 10px;
  padding: 0.65rem;
}

.task-stats strong,
.task-stats span {
  display: block;
}

.task-stats strong { color: #94a3b8; font-size: 0.75rem; }
.task-stats span { margin-top: 0.2rem; }

.task-actions {
  display: flex;
  gap: 0.6rem;
}

.loading,
.empty-state,
.error-banner {
  padding: 1rem;
  border-radius: 10px;
  margin-bottom: 1rem;
}

.loading,
.empty-state {
  background: #111827;
  border: 1px dashed #475569;
  color: #cbd5e1;
}

.error-banner {
  background: rgba(185, 28, 28, 0.2);
  border: 1px solid #ef4444;
  color: #fecaca;
}

@media (max-width: 760px) {
  .task-stats {
    grid-template-columns: 1fr;
  }
}
</style>