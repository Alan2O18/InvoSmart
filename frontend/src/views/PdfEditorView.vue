<template>
  <div class="pdf-editor-view">
    <header class="editor-header">
      <div class="header-left">
        <button @click="goBack" class="back-btn">← 返回活動</button>
        <h2>PDF 蓋章與排版工具</h2>
      </div>
      <div class="header-right">
        <span class="job-id">Job: {{ jobId }}</span>
      </div>
    </header>

    <div class="editor-content">
      <PdfWorkbench v-if="job" :job="job" :project-id="projectId" @saved="goBack" />
      <div v-else class="loading">載入 PDF 資料中...</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../services/api'
import PdfWorkbench from '../components/PdfWorkbench.vue'

const route = useRoute()
const router = useRouter()
const projectId = route.params.id
const jobId = route.query.jobId
const job = ref(null)

onMounted(async () => {
  if (!jobId) {
    alert('缺少 jobId 參數')
    goBack()
    return
  }

  try {
    const res = await api.getJobDetails(projectId, jobId)
    job.value = res.data
  } catch (error) {
    console.error('Fetch job error:', error)
    alert('無法載入 PDF 任務資料')
  }
})

const goBack = () => {
  router.push(`/project/${projectId}`)
}
</script>

<style scoped>
.pdf-editor-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #1e1e1e;
  color: #e0e0e0;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  background: #2a2a2a;
  border-bottom: 1px solid #444;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.header-left h2 {
  margin: 0;
  font-size: 1.25rem;
}

.back-btn {
  background: transparent;
  color: #e0e0e0;
  border: 1px solid #666;
  padding: 0.5rem 1rem;
  cursor: pointer;
  border-radius: 4px;
}
.back-btn:hover {
  background: #444;
}

.job-id {
  color: #888;
  font-family: monospace;
}

.editor-content {
  flex: 1;
  overflow: hidden; /* Let the workbench handle scrolling */
  position: relative;
}

.loading {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  font-size: 1.2rem;
  color: #666;
}
</style>
