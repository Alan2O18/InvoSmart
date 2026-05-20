<template>
  <div class="editor-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">PDF Editor</p>
        <h1>{{ task?.title || 'PDF 編輯工作區' }}</h1>
        <p class="subtitle">先看文件狀態，再進行蓋章、壓縮與頁面操作。</p>
      </div>
      <div class="header-actions">
        <button type="button" class="secondary" @click="reloadAll">重新整理</button>
        <button type="button" class="danger" @click="deleteTask">刪除任務</button>
      </div>
    </header>

    <div v-if="error" class="error-banner">{{ error }}</div>
    <div v-if="loading" class="loading">載入中...</div>

    <div v-else class="editor-layout" v-if="task">
      <section class="preview-panel">
        <div class="panel-card info-card">
          <div><strong>狀態</strong><span>{{ task.status }}</span></div>
          <div><strong>頁數</strong><span>{{ task.page_count || 0 }}</span></div>
          <div><strong>模板</strong><span>{{ task.template_id || '未選擇' }}</span></div>
        </div>

        <iframe v-if="fileUrl" class="pdf-frame" :src="fileUrl"></iframe>
      </section>

      <aside class="control-panel">
        <div class="panel-card">
          <h2>蓋章模板</h2>
          <select v-model="form.templateId">
            <option value="">未選擇</option>
            <option v-for="template in templates" :key="template.id" :value="template.id">
              {{ template.name }}
            </option>
          </select>
        </div>

        <div class="panel-card">
          <h2>蓋章目標</h2>
          <select v-model="form.ownerId">
            <option value="">請選擇人員</option>
            <option v-for="person in persons" :key="person.id" :value="String(person.id)">
              {{ person.name }} ({{ person.role }})
            </option>
          </select>
          <input v-model="form.role" type="text" placeholder="角色選填，例如 handler" />
          <input v-model.number="form.pageIndex" type="number" min="0" :max="Math.max(0, (task.page_count || 1) - 1)" />
        </div>

        <div class="panel-card action-stack">
          <button type="button" class="primary" @click="applySingleStamp">單頁蓋章</button>
          <button type="button" class="primary" @click="applyFullStamp">全頁蓋章</button>
          <button type="button" class="secondary" @click="compressTask">壓縮</button>
          <button type="button" class="secondary" @click="addBlankPage">新增頁面</button>
          <button type="button" class="secondary" @click="deletePage">刪除當前頁</button>
        </div>

        <div class="panel-card">
          <h2>頁序調整</h2>
          <input v-model="form.pageOrder" type="text" placeholder="例如：1,0,2" />
          <button type="button" class="secondary" @click="reorderPages">套用順序</button>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../services/api'

const route = useRoute()
const router = useRouter()

const task = ref(null)
const templates = ref([])
const persons = ref([])
const loading = ref(false)
const error = ref('')

const form = ref({
  templateId: '',
  ownerId: '',
  role: '',
  pageIndex: 0,
  pageOrder: ''
})

const fileUrl = computed(() => task.value ? api.getPdfTaskFileUrl(task.value.id) : '')

const fetchTask = async () => {
  const response = await api.getPdfTask(route.params.id)
  task.value = response.data
  form.value.templateId = task.value.template_id || ''
}

const fetchTemplates = async () => {
  const response = await api.listStampTemplates()
  templates.value = response.data || []
}

const fetchPersons = async () => {
  const response = await api.listPersons()
  persons.value = response.data || []
}

const reloadAll = async () => {
  loading.value = true
  error.value = ''
  try {
    await Promise.all([fetchTask(), fetchTemplates(), fetchPersons()])
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message || '載入失敗'
  } finally {
    loading.value = false
  }
}

const ensureOwner = () => {
  if (!form.value.ownerId) {
    throw new Error('請先選擇蓋章人員')
  }
  return Number(form.value.ownerId)
}

const applySingleStamp = async () => {
  try {
    await api.applyStampToPdfTask(task.value.id, {
      owner_id: ensureOwner(),
      role: form.value.role || null,
      template_id: form.value.templateId || null,
      mode: 'single',
      page_index: Number(form.value.pageIndex || 0)
    })
    await reloadAll()
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message || '單頁蓋章失敗'
  }
}

const applyFullStamp = async () => {
  try {
    await api.applyStampToPdfTask(task.value.id, {
      owner_id: ensureOwner(),
      role: form.value.role || null,
      template_id: form.value.templateId || null,
      mode: 'full',
      page_index: Number(form.value.pageIndex || 0)
    })
    await reloadAll()
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message || '全頁蓋章失敗'
  }
}

const compressTask = async () => {
  try {
    await api.compressPdfTask(task.value.id)
    await reloadAll()
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message || '壓縮失敗'
  }
}

const addBlankPage = async () => {
  try {
    await api.operatePdfTaskPages(task.value.id, { operation: 'add', insert_count: 1 })
    await reloadAll()
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message || '新增頁面失敗'
  }
}

const deletePage = async () => {
  try {
    await api.operatePdfTaskPages(task.value.id, { operation: 'delete', page_indices: [Number(form.value.pageIndex || 0)] })
    await reloadAll()
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message || '刪除頁面失敗'
  }
}

const reorderPages = async () => {
  try {
    const pageOrder = form.value.pageOrder
      .split(',')
      .map((value) => Number(value.trim()))
      .filter((value) => Number.isInteger(value))
    await api.operatePdfTaskPages(task.value.id, { operation: 'reorder', page_order: pageOrder })
    await reloadAll()
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message || '調整頁序失敗'
  }
}

const deleteTask = async () => {
  if (!confirm('確定刪除這份 PDF 任務嗎？')) return
  await api.deletePdfTask(task.value.id)
  router.push('/pdf-tasks')
}

onMounted(reloadAll)
</script>

<style scoped>
.editor-page {
  padding: 2rem;
  color: #e5e7eb;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1.25rem;
}

.eyebrow {
  margin: 0 0 0.35rem;
  color: #7dd3fc;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-size: 0.76rem;
}

h1 { margin: 0; font-size: 2rem; }
.subtitle { margin: 0.5rem 0 0; color: #94a3b8; }

.header-actions {
  display: flex;
  gap: 0.6rem;
  align-items: flex-start;
}

.editor-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(320px, 0.9fr);
  gap: 1rem;
}

.preview-panel,
.control-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.panel-card {
  background: #111827;
  border: 1px solid #334155;
  border-radius: 16px;
  padding: 1rem;
}

.info-card {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
}

.info-card div {
  background: #0b1220;
  border: 1px solid #1e293b;
  border-radius: 10px;
  padding: 0.75rem;
}

.info-card strong,
.info-card span { display: block; }
.info-card strong { color: #94a3b8; font-size: 0.75rem; }

.pdf-frame {
  width: 100%;
  min-height: 76vh;
  border: 1px solid #334155;
  border-radius: 16px;
  background: #020617;
}

.panel-card h2 {
  margin: 0 0 0.75rem;
  font-size: 1rem;
}

input,
select,
button {
  width: 100%;
  border-radius: 10px;
  border: 1px solid #334155;
  background: #0b1220;
  color: #e5e7eb;
  padding: 0.75rem;
  box-sizing: border-box;
}

button {
  border: none;
  cursor: pointer;
  font-weight: 600;
}

button.primary { background: #0f766e; }
button.secondary { background: #334155; }
button.danger { background: #b91c1c; }

.action-stack {
  display: grid;
  gap: 0.6rem;
}

.loading,
.error-banner {
  margin-bottom: 1rem;
  padding: 1rem;
  border-radius: 10px;
}

.loading {
  background: #111827;
  border: 1px dashed #475569;
}

.error-banner {
  background: rgba(185, 28, 28, 0.2);
  border: 1px solid #ef4444;
  color: #fecaca;
}

@media (max-width: 980px) {
  .editor-layout {
    grid-template-columns: 1fr;
  }

  .pdf-frame {
    min-height: 65vh;
  }

  .info-card {
    grid-template-columns: 1fr;
  }
}
</style>