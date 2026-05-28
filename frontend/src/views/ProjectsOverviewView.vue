<template>
  <div class="projects-overview-view">
    <header class="overview-header">
      <div class="header-left">
        <button @click="$router.push('/projects')" class="back-btn">← 返回專案列表</button>
        <h1>專案預決算全覽</h1>
      </div>
    </header>

    <!-- Summary Metrics Dashboard -->
    <section class="metrics-grid">
      <div class="metric-card">
        <span class="metric-label">專案總數</span>
        <span class="metric-value">{{ projects.length }}</span>
      </div>
      <div class="metric-card">
        <span class="metric-label">預算總計 (所有專案)</span>
        <span class="metric-value blue">{{ formatCurrency(totalEstimatedExpenses) }}</span>
      </div>
      <div class="metric-card">
        <span class="metric-label">決算總計 (已載入專案)</span>
        <span class="metric-value green">{{ formatCurrency(totalActualExpenses) }}</span>
      </div>
    </section>

    <!-- Project Accordion List -->
    <main class="overview-list" v-if="!initialLoading">
      <div 
        v-for="project in projects" 
        :key="project.project_id" 
        class="project-row-card"
        :class="{ expanded: project.expanded }"
      >
        <!-- Accordion Header -->
        <div class="project-row-header" @click="toggleExpand(project)">
          <div class="row-header-main">
            <span class="expand-arrow">{{ project.expanded ? '▼' : '▶' }}</span>
            <div class="project-info">
              <span class="project-name">{{ project.name || project.project_id }}</span>
              <span class="project-id">{{ project.project_id }}</span>
            </div>
          </div>

          <div class="row-header-metrics" @click.stop>
            <div class="metric-col">
              <span class="col-label">預算總額</span>
              <span class="col-val">{{ formatCurrency(project.budgetTotal) }}</span>
            </div>
            <div class="metric-col">
              <span class="col-label">決算總額</span>
              <span class="col-val" v-if="project.actualTotal !== null">
                {{ formatCurrency(project.actualTotal) }}
              </span>
              <span class="col-val italic gray" v-else>(待展開載入)</span>
            </div>
            <div class="metric-col" v-if="project.actualTotal !== null">
              <span class="col-label">預決算差異</span>
              <span class="col-val font-bold" :class="getVarianceClass(project.budgetTotal - project.actualTotal)">
                {{ formatCurrency(project.budgetTotal - project.actualTotal) }}
              </span>
            </div>
            <div class="actions-col">
              <button 
                @click="$router.push({ name: 'budget-editor', params: { id: project.project_id } })" 
                class="edit-btn"
              >
                預決算編輯器
              </button>
              <button 
                @click="$router.push({ name: 'project-detail', params: { id: project.project_id } })" 
                class="details-btn"
              >
                專案詳情
              </button>
            </div>
          </div>
        </div>

        <!-- Accordion Content (Lazy loaded) -->
        <div class="project-row-content" v-if="project.expanded">
          <!-- Spinner -->
          <div v-if="project.loading" class="spinner-container">
            <div class="spinner-small"></div>
            <span>正在載入憑證與決算資料...</span>
          </div>

          <!-- Content Details -->
          <div v-else class="content-details">
            <!-- Summary stats -->
            <div class="variance-summary-box" :class="getVarianceClass(project.budgetTotal - project.actualTotal)">
              <div class="variance-stat">
                <span>預算金額：<strong>{{ formatCurrency(project.budgetTotal) }}</strong></span>
                <span>決算金額：<strong>{{ formatCurrency(project.actualTotal) }}</strong></span>
                <span>差額：<strong class="large">{{ formatCurrency(project.budgetTotal - project.actualTotal) }}</strong></span>
              </div>
              <p class="variance-explanation">
                {{ getVarianceExplanation(project.budgetTotal - project.actualTotal) }}
              </p>
            </div>

            <!-- Side-by-side sheets -->
            <div class="sheets-grid">
              <!-- Left: Budget details -->
              <div class="sheet-column">
                <div class="sheet-column-header">
                  <h3>📊 預算支出項目 (Budget Estimated)</h3>
                </div>
                <div class="sheet-table-wrapper">
                  <table class="overview-detail-table">
                    <thead>
                      <tr>
                        <th>項目</th>
                        <th style="text-align: right">數量</th>
                        <th style="text-align: right">單價</th>
                        <th style="text-align: right">小計</th>
                        <th>用途</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(item, idx) in getBudgetExpenses(project)" :key="'b-exp-' + idx">
                        <td>{{ item.name }}</td>
                        <td style="text-align: right">{{ item.qty }}</td>
                        <td style="text-align: right">{{ formatCurrency(item.price) }}</td>
                        <td style="text-align: right; color: #60a5fa;">{{ formatCurrency(item.total) }}</td>
                        <td class="dim-text">{{ item.purpose }}</td>
                      </tr>
                      <tr v-if="getBudgetExpenses(project).length === 0">
                        <td colspan="5" class="empty-cell">無預算支出資料</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <!-- Right: Actual details -->
              <div class="sheet-column">
                <div class="sheet-column-header">
                  <h3>💸 決算支出項目 (Actual Expenses)</h3>
                </div>
                <div class="sheet-table-wrapper">
                  <table class="overview-detail-table">
                    <thead>
                      <tr>
                        <th>憑證檔案 / 項目</th>
                        <th style="text-align: right">數量</th>
                        <th style="text-align: right">單價</th>
                        <th style="text-align: right">小計</th>
                        <th>科目類別</th>
                      </tr>
                    </thead>
                    <tbody>
                      <template v-for="(job, jobIdx) in project.jobDetails" :key="'job-' + jobIdx">
                        <!-- Group Header -->
                        <tr class="job-group-row">
                          <td colspan="5">📄 {{ job.voucherId || job.jobId }} (合計: {{ formatCurrency(job.total) }})</td>
                        </tr>
                        <!-- Items -->
                        <tr v-for="(item, idx) in job.items" :key="'item-' + jobIdx + '-' + idx">
                          <td style="padding-left: 1.5rem;">{{ item.name }}</td>
                          <td style="text-align: right">{{ item.qty }}</td>
                          <td style="text-align: right">{{ formatCurrency(item.price) }}</td>
                          <td style="text-align: right; color: #34d399;">{{ formatCurrency(item.total) }}</td>
                          <td class="dim-text">{{ item.category }}</td>
                        </tr>
                        <tr v-if="job.items.length === 0">
                          <td colspan="5" class="empty-cell" style="padding-left: 1.5rem;">無明細項目</td>
                        </tr>
                      </template>
                      <tr v-if="!project.jobDetails || project.jobDetails.length === 0">
                        <td colspan="5" class="empty-cell">無決算明細資料</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <div v-else class="loading-overlay">
      <div class="spinner"></div>
      <p>正在載入專案清單...</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../services/api'

const projects = ref([])
const initialLoading = ref(false)

// Aggregated values
const totalEstimatedExpenses = computed(() => {
  return projects.value.reduce((sum, p) => sum + (p.budgetTotal || 0), 0)
})

const totalActualExpenses = computed(() => {
  return projects.value.reduce((sum, p) => sum + (p.actualTotal || 0), 0)
})

// Currency formatting helper
const formatCurrency = (val) => {
  if (val === null || val === undefined) return '$0'
  return new Intl.NumberFormat('zh-TW', { style: 'currency', currency: 'TWD', maximumFractionDigits: 0 }).format(val)
}

// Budget expenses extractor
const getBudgetExpenses = (project) => {
  return project.metadata?.budgetExpense || []
}

// Style selector for variance
const getVarianceClass = (diff) => {
  if (diff > 0) return 'text-success' // Under budget (saving money)
  if (diff < 0) return 'text-danger'  // Over budget (overdraft)
  return 'text-neutral'
}

const getVarianceExplanation = (diff) => {
  if (diff > 0) return `🎉 預算控制良好！目前低於預估支出共 ${formatCurrency(diff)}。`
  if (diff < 0) return `⚠️ 注意：已超出預估支出共 ${formatCurrency(Math.abs(diff))}，請檢查帳目是否有誤。`
  return '🤝 實際支出與預算完全一致。'
}

// Lazy expand loading
const toggleExpand = async (project) => {
  project.expanded = !project.expanded
  
  if (project.expanded && !project.loaded) {
    project.loading = true
    try {
      // 1. Fetch latest detail just in case
      const detailRes = await api.getProjectDetail(project.project_id)
      const detail = detailRes.data
      project.metadata = detail.metadata || {}
      
      const budgetExpense = project.metadata.budgetExpense || []
      project.budgetTotal = budgetExpense.reduce((sum, item) => sum + (Number(item.total) || 0), 0)
      
      // 2. Fetch Jobs
      const jobsRes = await api.getProjectJobs(project.project_id)
      const jobs = jobsRes.data || []
      
      const doneJobs = jobs.filter(j => j.status === 'done')
      if (doneJobs.length > 0) {
        // Fetch detailed job json
        const detailsRes = await Promise.all(doneJobs.map(j => api.getJobDetails(project.project_id, j.job_id)))
        
        let actualSum = 0
        const parsedJobs = detailsRes.map((res, index) => {
          const detailData = res.data
          let parsedData = {}
          if (detailData.manual_json_text) {
            try {
              parsedData = JSON.parse(detailData.manual_json_text)
            } catch (e) {
              parsedData = detailData.vlm_result || {}
            }
          } else if (detailData.vlm_result) {
            parsedData = detailData.vlm_result
          }
          
          const items = parsedData.items || []
          const jobSum = items.reduce((sum, item) => sum + (Number(item.total) || 0), 0)
          actualSum += jobSum
          
          return {
            jobId: doneJobs[index].job_id,
            voucherId: detailData.voucher_id || parsedData.voucher_id || getFilename(detailData.image_path) || doneJobs[index].job_id,
            items: items,
            total: jobSum
          }
        })
        
        project.jobDetails = parsedJobs
        project.actualTotal = actualSum
      } else {
        project.jobDetails = []
        project.actualTotal = 0
      }
      
      project.loaded = true
    } catch (e) {
      console.error('Failed to load project details for ' + project.project_id, e)
    } finally {
      project.loading = false
    }
  }
}

const getFilename = (path) => {
  if (!path) return ''
  return path.split('\\').pop().split('/').pop()
}

// Ingestion
const loadProjects = async () => {
  initialLoading.value = true
  try {
    const res = await api.getProjects()
    projects.value = res.data.map(p => {
      const meta = p.metadata || {}
      const budgetExpense = meta.budgetExpense || []
      const budgetTotal = budgetExpense.reduce((sum, item) => sum + (Number(item.total) || 0), 0)
      
      return {
        ...p,
        budgetTotal,
        actualTotal: null,
        expanded: false,
        loading: false,
        loaded: false,
        jobDetails: []
      }
    })
  } catch (e) {
    console.error('Failed to load projects list:', e)
    alert('載入專案清單失敗：' + e)
  } finally {
    initialLoading.value = false
  }
}

onMounted(() => {
  loadProjects()
})
</script>

<style scoped>
.projects-overview-view {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: #0f0f12;
  color: #f3f4f6;
  padding: 1.5rem;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

.overview-header {
  margin-bottom: 2rem;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.header-left h1 {
  font-size: 1.8rem;
  font-weight: 700;
  margin: 0;
  background: linear-gradient(135deg, #60a5fa, #3b82f6);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.back-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #e5e7eb;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  transition: all 0.2s ease;
}

.back-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.4);
}

/* Metrics row */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}

.metric-card {
  background: rgba(28, 28, 35, 0.45);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
}

.metric-label {
  font-size: 0.85rem;
  color: #9ca3af;
  font-weight: 500;
}

.metric-value {
  font-size: 1.8rem;
  font-weight: 700;
  color: #fff;
}

.metric-value.blue {
  color: #60a5fa;
}

.metric-value.green {
  color: #34d399;
}

/* Accordion list cards */
.overview-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.project-row-card {
  background: rgba(28, 28, 35, 0.35);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  overflow: hidden;
  transition: all 0.2s ease;
}

.project-row-card:hover {
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(28, 28, 35, 0.45);
}

.project-row-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 1.5rem;
  cursor: pointer;
  user-select: none;
}

.row-header-main {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.expand-arrow {
  color: #9ca3af;
  font-size: 0.8rem;
}

.project-info {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.project-name {
  font-size: 1.1rem;
  font-weight: 600;
  color: #fff;
}

.project-id {
  font-size: 0.8rem;
  color: #6b7280;
}

.row-header-metrics {
  display: flex;
  align-items: center;
  gap: 2rem;
}

.metric-col {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  min-width: 110px;
}

.col-label {
  font-size: 0.75rem;
  color: #6b7280;
  margin-bottom: 0.2rem;
}

.col-val {
  font-size: 0.95rem;
  color: #d1d5db;
}

.col-val.font-bold {
  font-weight: 700;
}

.col-val.gray {
  color: #6b7280;
}

.col-val.italic {
  font-style: italic;
  font-size: 0.8rem;
}

.actions-col {
  display: flex;
  gap: 0.5rem;
  margin-left: 1rem;
}

.edit-btn {
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(59, 130, 246, 0.3);
  color: #60a5fa;
  padding: 0.4rem 0.8rem;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.edit-btn:hover {
  background: rgba(59, 130, 246, 0.25);
  border-color: #60a5fa;
}

.details-btn {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #e5e7eb;
  padding: 0.4rem 0.8rem;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.details-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.25);
}

/* Accordion Content Details */
.project-row-content {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(10, 10, 12, 0.4);
}

.spinner-container {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 2.5rem;
  color: #9ca3af;
  font-size: 0.9rem;
}

.spinner-small {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.content-details {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

/* Variance summary styling */
.variance-summary-box {
  padding: 1rem 1.5rem;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.variance-summary-box.text-success {
  background: rgba(16, 185, 129, 0.04);
  border-color: rgba(16, 185, 129, 0.15);
}

.variance-summary-box.text-danger {
  background: rgba(239, 68, 68, 0.04);
  border-color: rgba(239, 68, 68, 0.15);
}

.variance-stat {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  font-size: 0.95rem;
  color: #d1d5db;
  margin-bottom: 0.5rem;
}

.variance-stat strong {
  color: #fff;
}

.variance-stat strong.large {
  font-size: 1.1rem;
}

.variance-summary-box.text-success strong.large {
  color: #34d399;
}

.variance-summary-box.text-danger strong.large {
  color: #f87171;
}

.variance-explanation {
  font-size: 0.85rem;
  margin: 0;
  color: #9ca3af;
}

/* Side-by-side details */
.sheets-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 1.5rem;
}

.sheet-column {
  background: rgba(28, 28, 35, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  overflow: hidden;
}

.sheet-column-header {
  background: rgba(255, 255, 255, 0.02);
  padding: 0.75rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.sheet-column-header h3 {
  font-size: 0.9rem;
  font-weight: 600;
  margin: 0;
  color: #e5e7eb;
}

.sheet-table-wrapper {
  overflow-y: auto;
  max-height: 350px;
}

.overview-detail-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.overview-detail-table th {
  background-color: rgba(0, 0, 0, 0.1);
  color: #9ca3af;
  padding: 0.5rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.overview-detail-table td {
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  color: #d1d5db;
}

.overview-detail-table tr.job-group-row {
  background-color: rgba(59, 130, 246, 0.04);
  font-weight: 600;
}

.overview-detail-table tr.job-group-row td {
  color: #9ca3af;
  font-size: 0.8rem;
  border-bottom: 1px solid rgba(59, 130, 246, 0.1);
}

.dim-text {
  color: #6b7280;
}

.empty-cell {
  text-align: center;
  padding: 2rem !important;
  color: #6b7280;
  font-style: italic;
}

/* Variance color labels */
.text-success {
  color: #34d399 !important;
}

.text-danger {
  color: #f87171 !important;
}

.text-neutral {
  color: #d1d5db !important;
}

/* Loading Spinner */
.loading-overlay {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 5rem 0;
  gap: 1.5rem;
  color: #9ca3af;
}

.spinner {
  width: 48px;
  height: 48px;
  border: 4px solid rgba(255, 255, 255, 0.1);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
