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

    <!-- Autocomplete datalists -->
    <datalist id="income-items">
      <option v-for="item in budgetIncomeSuggestions" :key="`income-${item}`" :value="item"></option>
    </datalist>
    <datalist id="expense-items">
      <option v-for="item in expenseCategorySuggestions" :key="`expense-${item}`" :value="item"></option>
    </datalist>

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
            <!-- Edit Mode Toggle and Action Buttons -->
            <div class="edit-mode-bar">
              <label class="switch-label">
                <input type="checkbox" v-model="project.editMode" :disabled="project.status === 'ARCHIVED' || project.status === 'SEALED'" />
                <span class="switch-text">✏️ 啟用編輯模式</span>
                <span v-if="project.status === 'ARCHIVED' || project.status === 'SEALED'" class="archive-inline-badge">（專案已封存，無法編輯）</span>
              </label>
              <div class="edit-actions" v-if="project.editMode">
                <span v-if="project.isBudgetDirty || project.dirtyJobs?.size > 0" class="dirty-badge">● 有未儲存的變更</span>
                <button @click="saveProjectBudget(project)" :disabled="project.savingBudget" class="save-btn small blue">
                  {{ project.savingBudget ? '儲存中...' : '💾 儲存預算' }}
                </button>
                <button @click="saveProjectFinal(project)" :disabled="project.savingFinal" class="save-btn small green">
                  {{ project.savingFinal ? '儲存中...' : '💾 儲存決算' }}
                </button>
              </div>
            </div>

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
                  <div class="sheet-header-flex">
                    <h3>📊 預算支出項目 (Budget Estimated)</h3>
                    <div class="sheet-actions">
                      <button @click="copyBudgetExpenseTSV(project)" class="add-job-item-btn mini" style="background: rgba(255,255,255,0.05); border-color: rgba(255,255,255,0.2); color: #fff;">📤 匯出 TSV</button>
                      <button v-if="project.editMode" @click="openImportModal(project, 'budgetExpense')" class="add-job-item-btn mini" style="background: rgba(255,255,255,0.05); border-color: rgba(255,255,255,0.2); color: #fff;">📥 匯入 TSV</button>
                      <button v-if="project.editMode" @click="addBudgetExpenseRow(project)" class="add-job-item-btn mini">+ 新增項目</button>
                    </div>
                  </div>
                </div>
                <div class="sheet-table-wrapper">
                  <table class="overview-detail-table">
                    <thead v-if="project.editMode">
                      <tr>
                        <th style="width: 25%">項目</th>
                        <th style="width: 15%; text-align: right">數量</th>
                        <th style="width: 15%; text-align: right">單價</th>
                        <th style="width: 15%; text-align: right">小計</th>
                        <th style="width: 22%">用途</th>
                        <th style="width: 8%; text-align: center">操作</th>
                      </tr>
                    </thead>
                    <thead v-else>
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
                        <template v-if="project.editMode">
                          <td>
                            <input 
                              v-model="item.name" 
                              list="expense-items"
                              placeholder="項目名稱" 
                              @change="onBudgetExpenseChange(project, item)"
                              @keydown="handleCellKeydown($event, 'budgetExpense', project.project_id, idx, 0)"
                              @paste="handleCellPaste($event, 'budgetExpense', project, idx, 0, getBudgetExpenses(project))"
                              :data-project="project.project_id"
                              :data-row="idx"
                              data-col="0"
                            />
                          </td>
                          <td>
                            <input 
                              type="number"
                              v-model.number="item.qty" 
                              placeholder="1"
                              class="num-input"
                              @change="onBudgetExpenseChange(project, item)"
                              @keydown="handleCellKeydown($event, 'budgetExpense', project.project_id, idx, 1)"
                              @paste="handleCellPaste($event, 'budgetExpense', project, idx, 1, getBudgetExpenses(project))"
                              :data-project="project.project_id"
                              :data-row="idx"
                              data-col="1"
                            />
                          </td>
                          <td>
                            <input 
                              type="number"
                              v-model.number="item.price" 
                              placeholder="0"
                              class="num-input"
                              @change="onBudgetExpenseChange(project, item)"
                              @keydown="handleCellKeydown($event, 'budgetExpense', project.project_id, idx, 2)"
                              @paste="handleCellPaste($event, 'budgetExpense', project, idx, 2, getBudgetExpenses(project))"
                              :data-project="project.project_id"
                              :data-row="idx"
                              data-col="2"
                            />
                          </td>
                          <td>
                            <input 
                              type="number"
                              :value="item.total" 
                              class="num-input readonly"
                              readonly
                              placeholder="0"
                              @keydown="handleCellKeydown($event, 'budgetExpense', project.project_id, idx, 3)"
                              :data-project="project.project_id"
                              :data-row="idx"
                              data-col="3"
                            />
                          </td>
                          <td>
                            <input 
                              v-model="item.purpose" 
                              placeholder="用途說明" 
                              @change="project.isBudgetDirty = true"
                              @keydown="handleCellKeydown($event, 'budgetExpense', project.project_id, idx, 4)"
                              @paste="handleCellPaste($event, 'budgetExpense', project, idx, 4, getBudgetExpenses(project))"
                              :data-project="project.project_id"
                              :data-row="idx"
                              data-col="4"
                            />
                          </td>
                          <td style="text-align: center">
                            <button @click="removeBudgetExpenseRow(project, idx)" class="delete-row-btn" title="刪除項目">✕</button>
                          </td>
                        </template>
                        <template v-else>
                          <td>{{ item.name }}</td>
                          <td style="text-align: right">{{ item.qty }}</td>
                          <td style="text-align: right">{{ formatCurrency(item.price) }}</td>
                          <td style="text-align: right; color: #60a5fa;">{{ formatCurrency(item.total) }}</td>
                          <td class="dim-text">{{ item.purpose }}</td>
                        </template>
                      </tr>
                      <tr v-if="getBudgetExpenses(project).length === 0">
                        <td :colspan="project.editMode ? 6 : 5" class="empty-cell">無預算支出資料</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <!-- Right: Actual details -->
              <div class="sheet-column">
                <div class="sheet-column-header">
                  <div class="sheet-header-flex">
                    <h3>💸 決算支出項目 (Actual Expenses)</h3>
                    <div class="sheet-actions">
                      <button @click="copyAllFinalExpenseTSV(project)" class="add-job-item-btn mini" style="background: rgba(255,255,255,0.05); border-color: rgba(255,255,255,0.2); color: #fff;">📤 匯出全部 TSV</button>
                    </div>
                  </div>
                </div>
                <div class="sheet-table-wrapper">
                  <table class="overview-detail-table">
                    <thead v-if="project.editMode">
                      <tr>
                        <th style="width: 30%">發票品項名稱</th>
                        <th style="width: 10%; text-align: right">數量</th>
                        <th style="width: 15%; text-align: right">單價</th>
                        <th style="width: 15%; text-align: right">金額</th>
                        <th style="width: 22%">支出科目/類別</th>
                        <th style="width: 8%; text-align: center">操作</th>
                      </tr>
                    </thead>
                    <thead v-else>
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
                          <td :colspan="project.editMode ? 6 : 5">
                            <div class="job-group-header-flex">
                              <span>📄 {{ job.voucherId || job.jobId }} (合計: {{ formatCurrency(job.total) }})</span>
                              <div class="job-actions" @click.stop>
                                <button type="button" @click="copyJobTSV(project, job)" class="add-job-item-btn mini" style="background: rgba(255,255,255,0.05); border-color: rgba(255,255,255,0.2); color: #fff;">📤 匯出 TSV</button>
                                <button v-if="project.editMode" type="button" @click="openImportModal(project, 'finalExpense', job.jobId, job.voucherId || job.jobId)" class="add-job-item-btn mini" style="background: rgba(255,255,255,0.05); border-color: rgba(255,255,255,0.2); color: #fff;">📥 匯入 TSV</button>
                                <button v-if="project.editMode" type="button" @click="addFinalExpenseRow(project, job.jobId)" class="add-job-item-btn mini">+ 新增品項</button>
                              </div>
                            </div>
                          </td>
                        </tr>
                        <!-- Items -->
                        <tr v-for="(item, idx) in job.items" :key="'item-' + jobIdx + '-' + idx" :class="{ 'row-dirty': project.dirtyJobs?.has(job.jobId) }">
                          <template v-if="project.editMode">
                            <td>
                              <input 
                                v-model="item.name" 
                                placeholder="發票商品名稱" 
                                @change="onFinalItemChange(project, job.jobId, item)"
                                @keydown="handleCellKeydown($event, 'finalExpense', project.project_id, getFlatIndex(project, jobIdx, idx), 0)"
                                @paste="handleCellPaste($event, 'finalExpense', project, getFlatIndex(project, jobIdx, idx), 0, getFlatItemsList(project))"
                                :data-project="project.project_id"
                                :data-row="getFlatIndex(project, jobIdx, idx)"
                                data-col="0"
                              />
                            </td>
                            <td>
                              <input 
                                type="number"
                                v-model.number="item.qty" 
                                placeholder="1"
                                class="num-input"
                                @change="onFinalItemChange(project, job.jobId, item)"
                                @keydown="handleCellKeydown($event, 'finalExpense', project.project_id, getFlatIndex(project, jobIdx, idx), 1)"
                                @paste="handleCellPaste($event, 'finalExpense', project, getFlatIndex(project, jobIdx, idx), 1, getFlatItemsList(project))"
                                :data-project="project.project_id"
                                :data-row="getFlatIndex(project, jobIdx, idx)"
                                data-col="1"
                              />
                            </td>
                            <td>
                              <input 
                                type="number"
                                v-model.number="item.price" 
                                placeholder="0"
                                class="num-input"
                                @change="onFinalItemChange(project, job.jobId, item)"
                                @keydown="handleCellKeydown($event, 'finalExpense', project.project_id, getFlatIndex(project, jobIdx, idx), 2)"
                                @paste="handleCellPaste($event, 'finalExpense', project, getFlatIndex(project, jobIdx, idx), 2, getFlatItemsList(project))"
                                :data-project="project.project_id"
                                :data-row="getFlatIndex(project, jobIdx, idx)"
                                data-col="2"
                              />
                            </td>
                            <td>
                              <input 
                                type="number"
                                :value="item.total" 
                                class="num-input readonly"
                                readonly
                                placeholder="0"
                                @keydown="handleCellKeydown($event, 'finalExpense', project.project_id, getFlatIndex(project, jobIdx, idx), 3)"
                                :data-project="project.project_id"
                                :data-row="getFlatIndex(project, jobIdx, idx)"
                                data-col="3"
                              />
                            </td>
                            <td>
                              <input 
                                v-model="item.category" 
                                list="expense-items"
                                placeholder="e.g. 鐘點費、印刷費" 
                                @change="onFinalItemChange(project, job.jobId, item)"
                                @keydown="handleCellKeydown($event, 'finalExpense', project.project_id, getFlatIndex(project, jobIdx, idx), 4)"
                                @paste="handleCellPaste($event, 'finalExpense', project, getFlatIndex(project, jobIdx, idx), 4, getFlatItemsList(project))"
                                :data-project="project.project_id"
                                :data-row="getFlatIndex(project, jobIdx, idx)"
                                data-col="4"
                              />
                            </td>
                            <td style="text-align: center">
                              <button @click="deleteFinalExpenseRow(project, job.jobId, idx)" class="delete-row-btn" title="刪除品項">✕</button>
                            </td>
                          </template>
                          <template v-else>
                            <td style="padding-left: 1.5rem;">{{ item.name }}</td>
                            <td style="text-align: right">{{ item.qty }}</td>
                            <td style="text-align: right">{{ formatCurrency(item.price) }}</td>
                            <td style="text-align: right; color: #34d399;">{{ formatCurrency(item.total) }}</td>
                            <td class="dim-text">{{ item.category }}</td>
                          </template>
                        </tr>
                        <tr v-if="job.items.length === 0">
                          <td :colspan="project.editMode ? 6 : 5" class="empty-cell" style="padding-left: 1.5rem;">無明細項目</td>
                        </tr>
                      </template>
                      <tr v-if="!project.jobDetails || project.jobDetails.length === 0">
                        <td :colspan="project.editMode ? 6 : 5" class="empty-cell">無決算明細資料</td>
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

    <!-- TSV Import Modal -->
    <div v-if="showImportModal" class="modal-overlay" @click.self="closeImportModal">
      <div class="modal-container-small">
        <header class="modal-header">
          <h2>📥 匯入 TSV 數據 (專案: {{ currentImportProject?.name || currentImportProject?.project_id }})</h2>
          <button type="button" class="close-btn" @click="closeImportModal">✕</button>
        </header>
        <div class="modal-body">
          <p class="import-help">
            請貼上從 Excel 或 Google Sheets 複製的資料列：
          </p>
          <div class="format-hint">
            <span class="hint-title">預期欄位順序：</span>
            <code v-if="importTarget === 'budgetExpense'">項目名稱 &nbsp;&nbsp;|&nbsp;&nbsp; 數量 &nbsp;&nbsp;|&nbsp;&nbsp; 預估單價 &nbsp;&nbsp;|&nbsp;&nbsp; 用途說明</code>
            <code v-if="importTarget === 'finalExpense'">品項名稱 &nbsp;&nbsp;|&nbsp;&nbsp; 數量 &nbsp;&nbsp;|&nbsp;&nbsp; 單價 &nbsp;&nbsp;|&nbsp;&nbsp; 支出科目/類別 &nbsp;&nbsp;|&nbsp;&nbsp; 備註</code>
          </div>

          <div class="radio-group">
            <label>
              <input type="radio" v-model="importMode" value="append" />
              附加至現有資料末端 (Append)
            </label>
            <label>
              <input type="radio" v-model="importMode" value="overwrite" />
              覆蓋現有資料 (Overwrite)
            </label>
          </div>

          <textarea 
            v-model="tsvInputText" 
            placeholder="在此貼上複製的試算表格內容..."
            rows="8" 
            class="tsv-textarea"
          ></textarea>
        </div>
        <footer class="modal-footer">
          <button type="button" @click="closeImportModal" class="secondary">取消</button>
          <button type="button" @click="handleTsvImport" class="primary-btn">確認匯入</button>
        </footer>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import api from '../services/api'

const projects = ref([])
const initialLoading = ref(false)

// Autocomplete suggestions
const budgetIncomeSuggestions = ref([])
const expenseCategorySuggestions = ref([])

// TSV Import Modal state
const showImportModal = ref(false)
const importTarget = ref('') // 'budgetExpense' | 'finalExpense'
const currentImportProject = ref(null)
const importJobId = ref('')
const importJobTitle = ref('')
const importMode = ref('append') // 'append' | 'overwrite'
const tsvInputText = ref('')

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
      if (!project.metadata.budgetExpense) project.metadata.budgetExpense = []
      if (!project.metadata.budgetIncome) project.metadata.budgetIncome = []

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
      
      project.editMode = false
      project.isBudgetDirty = false
      project.dirtyJobs = new Set()
      project.savingBudget = false
      project.savingFinal = false
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
        jobDetails: [],
        editMode: false,
        isBudgetDirty: false,
        dirtyJobs: new Set(),
        savingBudget: false,
        savingFinal: false
      }
    })
  } catch (e) {
    console.error('Failed to load projects list:', e)
    alert('載入專案清單失敗：' + e)
  } finally {
    initialLoading.value = false
  }
}

// -------------------------------------------------------------
// SUGGESTIONS & TSV IMPORT/EXPORT
// -------------------------------------------------------------
const loadSuggestions = async () => {
  try {
    const [incomeRes, expenseRes] = await Promise.all([
      api.getSuggestions('budget_income_item', '', 200),
      api.getSuggestions('expense_category', '', 200),
    ])
    budgetIncomeSuggestions.value = incomeRes.data || []
    expenseCategorySuggestions.value = expenseRes.data || []
  } catch (e) {
    console.error('Failed to load suggestions:', e)
  }
}

const saveSuggestion = async (category, value) => {
  const text = String(value || '').trim()
  if (!text) return
  try {
    await api.addSuggestion(category, text)
    if (category === 'budget_income_item' && !budgetIncomeSuggestions.value.includes(text)) {
      budgetIncomeSuggestions.value.push(text)
    }
    if (category === 'expense_category' && !expenseCategorySuggestions.value.includes(text)) {
      expenseCategorySuggestions.value.push(text)
    }
  } catch (e) {
    console.error(`Failed to save suggestion ${category}:`, e)
  }
}

const recalculateTotals = (project) => {
  if (project.metadata?.budgetExpense) {
    project.budgetTotal = project.metadata.budgetExpense.reduce((sum, item) => sum + (Number(item.total) || 0), 0)
  }
  if (project.jobDetails) {
    let actualSum = 0
    project.jobDetails.forEach(job => {
      const items = job.items || []
      const jobSum = items.reduce((sum, item) => sum + (Number(item.total) || 0), 0)
      job.total = jobSum
      actualSum += jobSum
    })
    project.actualTotal = actualSum
  }
}

// -------------------------------------------------------------
// BUDGET CRUD
// -------------------------------------------------------------
const addBudgetExpenseRow = (project) => {
  if (!project.metadata) project.metadata = {}
  if (!project.metadata.budgetExpense) project.metadata.budgetExpense = []
  project.metadata.budgetExpense.push({ name: '', qty: 1, price: 0, total: 0, purpose: '' })
  project.isBudgetDirty = true
}

const removeBudgetExpenseRow = (project, idx) => {
  if (project.metadata?.budgetExpense) {
    project.metadata.budgetExpense.splice(idx, 1)
    project.isBudgetDirty = true
    recalculateTotals(project)
  }
}

const onBudgetExpenseChange = (project, item) => {
  item.total = (Number(item.qty) || 0) * (Number(item.price) || 0)
  project.isBudgetDirty = true
  recalculateTotals(project)
}

// -------------------------------------------------------------
// FINAL ACCOUNT CRUD & MERGING
// -------------------------------------------------------------
const getFlatItemsList = (project) => {
  const list = []
  if (!project.jobDetails) return list
  project.jobDetails.forEach(job => {
    const items = job.items || []
    items.forEach(item => {
      list.push(item)
    })
  })
  return list
}

const getFlatIndex = (project, jobIdx, idx) => {
  let flatIndex = 0
  for (let j = 0; j < jobIdx; j++) {
    flatIndex += project.jobDetails[j]?.items?.length || 0
  }
  return flatIndex + idx
}

const onFinalItemChange = (project, jobId, item) => {
  item.total = (Number(item.qty) || 0) * (Number(item.price) || 0)
  if (!project.dirtyJobs) project.dirtyJobs = new Set()
  project.dirtyJobs.add(jobId)
  recalculateTotals(project)
}

const addFinalExpenseRow = (project, jobId) => {
  const job = project.jobDetails.find(j => j.jobId === jobId)
  if (job) {
    if (!job.items) job.items = []
    job.items.push({ name: '', qty: 1, price: 0, total: 0, category: '', remark: '' })
    if (!project.dirtyJobs) project.dirtyJobs = new Set()
    project.dirtyJobs.add(jobId)
    recalculateTotals(project)
  }
}

const deleteFinalExpenseRow = (project, jobId, idx) => {
  const job = project.jobDetails.find(j => j.jobId === jobId)
  if (job && job.items) {
    job.items.splice(idx, 1)
    if (!project.dirtyJobs) project.dirtyJobs = new Set()
    project.dirtyJobs.add(jobId)
    recalculateTotals(project)
  }
}

// -------------------------------------------------------------
// SAVE FUNCTIONS
// -------------------------------------------------------------
const saveProjectBudget = async (project) => {
  project.savingBudget = true
  try {
    const updatedMetadata = {
      ...project.metadata,
      budgetExpense: project.metadata.budgetExpense || [],
      budgetIncome: project.metadata.budgetIncome || []
    }
    await api.updateProject(project.project_id, updatedMetadata)

    // Save category suggestions
    for (const item of project.metadata.budgetExpense || []) {
      if (item.name) await saveSuggestion('expense_category', item.name)
    }

    project.isBudgetDirty = false
    alert(`專案 ${project.name || project.project_id} 預算儲存成功！`)
  } catch (e) {
    console.error('Failed to save project budget:', e)
    alert('儲存預算失敗：' + e)
  } finally {
    project.savingBudget = false
  }
}

const saveProjectFinal = async (project) => {
  if (!project.dirtyJobs || project.dirtyJobs.size === 0) {
    alert('決算無任何變更需要儲存。')
    return
  }
  project.savingFinal = true
  try {
    const promises = Array.from(project.dirtyJobs).map(async (jobId) => {
      const job = project.jobDetails.find(j => j.jobId === jobId)
      if (!job) return

      const res = await api.getJobDetails(project.project_id, jobId)
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

      const totalSum = job.items.reduce((sum, item) => sum + (Number(item.total) || 0), 0)
      const summary = parsedData.summary || { subtotal: 0, tax: 0, total: 0 }
      summary.total = totalSum
      summary.subtotal = totalSum

      const payload = {
        receipt_type: detailData.receipt_type || parsedData.receipt_type || '電子發票證明聯',
        header: parsedData.header || { supplier: '', buyer: '', invoice_id: '', date: '' },
        items: job.items,
        summary: summary,
        verification: parsedData.verification || { handwritten_total_chinese: '', stamp_shop_name: '', qr_code_detected: false }
      }
      return api.saveManualJson(project.project_id, jobId, payload)
    })

    await Promise.all(promises)

    // Save category suggestions
    for (const job of project.jobDetails || []) {
      for (const item of job.items || []) {
        if (item.category) await saveSuggestion('expense_category', item.category)
      }
    }

    project.dirtyJobs.clear()
    alert(`專案 ${project.name || project.project_id} 決算儲存成功！`)
  } catch (e) {
    console.error('Failed to save project final details:', e)
    alert('儲存決算失敗：' + e)
  } finally {
    project.savingFinal = false
  }
}

// -------------------------------------------------------------
// TSV COPY/EXPORT HELPERS
// -------------------------------------------------------------
const copyBudgetExpenseTSV = (project) => {
  let tsv = '項目\t數量\t單價\t金額\t用途\n'
  const items = project.metadata?.budgetExpense || []
  items.forEach(row => {
    tsv += `${row.name || ''}\t${row.qty || 1}\t${row.price || 0}\t${row.total || 0}\t${row.purpose || ''}\n`
  })
  navigator.clipboard.writeText(tsv)
  alert('預算支出已複製為 TSV 格式，可直接貼入 Excel！')
}

const copyJobTSV = (project, job) => {
  let tsv = '品項名稱\t數量\t單價\t金額\t類別\t備註\n'
  const items = job.items || []
  items.forEach(row => {
    tsv += `${row.name || ''}\t${row.qty || 1}\t${row.price || 0}\t${row.total || 0}\t${row.category || ''}\t${row.remark || ''}\n`
  })
  navigator.clipboard.writeText(tsv)
  alert(`憑證 ${job.voucherId || job.jobId} 支出已複製為 TSV 格式！`)
}

const copyAllFinalExpenseTSV = (project) => {
  let tsv = '憑證\t項目名稱\t數量\t單價\t金額\t類別\n'
  if (project.jobDetails) {
    project.jobDetails.forEach(job => {
      const items = job.items || []
      const jobTitle = job.voucherId || job.jobId
      items.forEach(row => {
        tsv += `${jobTitle}\t${row.name || ''}\t${row.qty || 0}\t${row.price || 0}\t${row.total || 0}\t${row.category || ''}\n`
      })
    })
  }
  navigator.clipboard.writeText(tsv)
  alert('決算支出已複製為 TSV 格式，可直接貼入 Excel！')
}

// -------------------------------------------------------------
// EXCEL-LIKE KEYBOARD NAVIGATION & PASTE
// -------------------------------------------------------------
const handleCellKeydown = (e, tableType, projectId, rowIndex, colIndex) => {
  const table = e.currentTarget.closest('table')
  if (!table) return

  let targetRow = rowIndex
  let targetCol = colIndex

  if (e.key === 'ArrowUp') {
    targetRow--
  } else if (e.key === 'ArrowDown') {
    targetRow++
  } else if (e.key === 'ArrowLeft') {
    if (e.target.selectionStart === 0) {
      targetCol--
    } else {
      return
    }
  } else if (e.key === 'ArrowRight') {
    if (e.target.selectionStart === e.target.value.length) {
      targetCol++
    } else {
      return
    }
  } else if (e.key === 'Enter') {
    e.preventDefault()
    targetRow++
  } else {
    return
  }

  const nextInput = table.querySelector(`input[data-project="${projectId}"][data-row="${targetRow}"][data-col="${targetCol}"]`)
  if (nextInput) {
    nextInput.focus()
    nextInput.select()
    e.preventDefault()
  }
}

const handleCellPaste = (e, tableType, project, startRowIndex, startColIndex, list) => {
  e.preventDefault()
  const clipboardData = e.clipboardData || window.clipboardData
  const pastedText = clipboardData.getData('Text')
  if (!pastedText) return

  const rows = pastedText.split(/\r?\n/).map(row => row.split('\t'))
  
  for (let r = 0; r < rows.length; r++) {
    const rowData = rows[r]
    if (rowData.length === 1 && rowData[0] === '') continue
    
    const targetRowIndex = startRowIndex + r
    
    if (tableType === 'budgetExpense') {
      while (project.metadata.budgetExpense.length <= targetRowIndex) {
        project.metadata.budgetExpense.push({ name: '', qty: 1, price: 0, total: 0, purpose: '' })
      }
    }

    const row = list[targetRowIndex]
    if (!row || row.placeholder) continue

    for (let c = 0; c < rowData.length; c++) {
      const val = rowData[c]
      const targetColIndex = startColIndex + c

      if (tableType === 'budgetExpense') {
        if (targetColIndex === 0) row.name = val
        if (targetColIndex === 1) row.qty = Number(val) || 1
        if (targetColIndex === 2) row.price = Number(val) || 0
        if (targetColIndex === 4) row.purpose = val
        row.total = (Number(row.qty) || 0) * (Number(row.price) || 0)
      } else if (tableType === 'finalExpense') {
        // Find job ID for this flat item row
        // Note: list contains flat list of items which are mutated in-place
        if (targetColIndex === 0) row.name = val
        if (targetColIndex === 1) row.qty = Number(val) || 1
        if (targetColIndex === 2) row.price = Number(val) || 0
        if (targetColIndex === 4) row.category = val
        if (targetColIndex === 5) row.remark = val
        row.total = (Number(row.qty) || 0) * (Number(row.price) || 0)
        
        // Find parent jobId for this item to mark it dirty
        if (project.jobDetails) {
          project.jobDetails.forEach(job => {
            if (job.items && job.items.includes(row)) {
              if (!project.dirtyJobs) project.dirtyJobs = new Set()
              project.dirtyJobs.add(job.jobId)
            }
          })
        }
      }
    }
  }

  if (tableType === 'budgetExpense') {
    project.isBudgetDirty = true
  }
  recalculateTotals(project)
}

// -------------------------------------------------------------
// TSV IMPORT MODAL
// -------------------------------------------------------------
const openImportModal = (project, target, jobId = '', jobTitle = '') => {
  currentImportProject.value = project
  importTarget.value = target
  importJobId.value = jobId
  importJobTitle.value = jobTitle
  importMode.value = 'append'
  tsvInputText.value = ''
  showImportModal.value = true
}

const closeImportModal = () => {
  showImportModal.value = false
}

const handleTsvImport = () => {
  const text = tsvInputText.value.trim()
  if (!text) {
    alert('請貼上 TSV 資料')
    return
  }

  const rows = text.split(/\r?\n/).map(row => row.split('\t'))
  
  // Parse rows (skip header row if it contains column titles)
  let startIndex = 0
  const firstRow = rows[0]
  if (firstRow && firstRow.some(cell => cell.includes('項目') || cell.includes('名稱') || cell.includes('科目') || cell.includes('類別') || cell.includes('金額') || cell.includes('單價') || cell.includes('數量'))) {
    startIndex = 1 // Skip header
  }

  const parsedRows = []
  for (let i = startIndex; i < rows.length; i++) {
    const cols = rows[i]
    if (cols.length === 1 && cols[0] === '') continue

    if (importTarget.value === 'budgetExpense') {
      const qty = Number(cols[1]) || 1
      const price = Number(cols[2]) || 0
      parsedRows.push({
        name: cols[0] || '',
        qty: qty,
        price: price,
        total: qty * price,
        purpose: cols[4] || cols[3] || ''
      })
    } else if (importTarget.value === 'finalExpense') {
      const qty = Number(cols[1]) || 1
      const price = Number(cols[2]) || 0
      parsedRows.push({
        name: cols[0] || '',
        qty: qty,
        price: price,
        total: qty * price,
        category: cols[4] || cols[3] || '',
        remark: cols[5] || ''
      })
    }
  }

  if (parsedRows.length === 0) {
    alert('沒有解析出有效的資料列')
    return
  }

  const project = currentImportProject.value
  if (!project) return

  if (importTarget.value === 'budgetExpense') {
    if (!project.metadata) project.metadata = {}
    if (!project.metadata.budgetExpense) project.metadata.budgetExpense = []

    if (importMode.value === 'overwrite') {
      project.metadata.budgetExpense = parsedRows
    } else {
      project.metadata.budgetExpense = [...project.metadata.budgetExpense, ...parsedRows]
    }
    project.isBudgetDirty = true
  } else if (importTarget.value === 'finalExpense') {
    const jobId = importJobId.value
    const job = project.jobDetails.find(j => j.jobId === jobId)
    if (job) {
      if (importMode.value === 'overwrite') {
        job.items = parsedRows
      } else {
        if (!job.items) job.items = []
        job.items = [...job.items, ...parsedRows]
      }
      if (!project.dirtyJobs) project.dirtyJobs = new Set()
      project.dirtyJobs.add(jobId)
    }
  }

  recalculateTotals(project)
  showImportModal.value = false
  alert(`成功匯入 ${parsedRows.length} 筆資料！`)
}

// Router leave guard
onBeforeRouteLeave((to, from, next) => {
  const dirtyProject = projects.value.find(p => p.isBudgetDirty || p.dirtyJobs?.size > 0)
  if (dirtyProject) {
    const confirmLeave = confirm(`專案「${dirtyProject.name || dirtyProject.project_id}」有未儲存的變更。確定要離開嗎？`)
    if (confirmLeave) next()
    else next(false)
  } else {
    next()
  }
})

onMounted(() => {
  loadProjects()
  loadSuggestions()
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

/* Edit Mode Bar */
.edit-mode-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.25rem;
  background: rgba(28, 28, 35, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
}

.switch-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  user-select: none;
  font-size: 0.9rem;
  font-weight: 500;
  color: #9ca3af;
}

.switch-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.edit-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.dirty-badge {
  font-size: 0.85rem;
  color: #fbbf24;
  margin-right: 0.5rem;
  animation: pulse 2s infinite;
}

.save-btn {
  color: white;
  border: none;
  padding: 0.6rem 1.25rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 600;
  transition: all 0.2s ease;
}

.save-btn:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}

.save-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.save-btn.small {
  padding: 0.4rem 0.8rem;
  font-size: 0.8rem;
}

.save-btn.green {
  background: linear-gradient(135deg, #10b981, #059669);
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2);
}

.save-btn.blue {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
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

.sheet-header-flex {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.sheet-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.sheet-table-wrapper {
  overflow-y: auto;
  max-height: 450px;
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
  padding: 0.25rem 0.4rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  color: #d1d5db;
}

/* Excel inputs style inside table */
.overview-detail-table input {
  width: 100%;
  background: transparent;
  border: 1px solid transparent;
  color: #fff;
  padding: 0.4rem 0.6rem;
  font-size: 0.85rem;
  border-radius: 4px;
  box-sizing: border-box;
  transition: all 0.15s ease;
}

.overview-detail-table input:focus {
  background: rgba(0, 0, 0, 0.35);
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.4);
  outline: none;
}

.overview-detail-table input.num-input {
  text-align: right;
}

.overview-detail-table input.readonly {
  color: #9ca3af;
  background-color: rgba(255, 255, 255, 0.01);
  cursor: not-allowed;
}

.overview-detail-table input.readonly:focus {
  border-color: transparent;
  box-shadow: none;
  background-color: rgba(255, 255, 255, 0.01);
}

.overview-detail-table tr:hover {
  background-color: rgba(255, 255, 255, 0.01);
}

.overview-detail-table tr.job-group-row {
  background-color: rgba(59, 130, 246, 0.04);
  font-weight: 600;
}

.overview-detail-table tr.job-group-row td {
  color: #9ca3af;
  font-size: 0.8rem;
  border-bottom: 1px solid rgba(59, 130, 246, 0.1);
  padding: 0.5rem 0.75rem;
}

.job-group-header-flex {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.job-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.add-job-item-btn {
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.4);
  color: #34d399;
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.add-job-item-btn:hover {
  background: rgba(16, 185, 129, 0.25);
  border-color: #34d399;
}

.add-job-item-btn.mini {
  padding: 0.15rem 0.5rem;
  font-size: 0.75rem;
}

.delete-row-btn {
  background: transparent;
  border: none;
  color: #ef4444;
  cursor: pointer;
  font-size: 1rem;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  margin: 0 auto;
  transition: all 0.2s ease;
}

.delete-row-btn:hover {
  background-color: rgba(239, 68, 68, 0.15);
}

.row-dirty {
  background-color: rgba(251, 191, 36, 0.02);
  border-left: 3px solid #fbbf24;
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

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* TSV Import Modal styles */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  padding: 1rem;
}

.modal-container-small {
  width: min(550px, 90vw);
  background: #1c1c24;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  color: white;
  box-shadow: 0 10px 40px rgba(0,0,0,0.6);
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.modal-header h2 {
  margin: 0;
  font-size: 1.15rem;
  color: #60a5fa;
  font-weight: 600;
}

.close-btn {
  background: transparent;
  border: none;
  color: #888;
  font-size: 1.5rem;
  cursor: pointer;
  transition: color 0.2s ease;
}

.close-btn:hover {
  color: white;
}

.modal-body {
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.import-help {
  font-size: 0.9rem;
  color: #9ca3af;
  margin: 0;
}

.format-hint {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 6px;
  padding: 0.75rem;
  font-size: 0.85rem;
}

.hint-title {
  color: #60a5fa;
  font-weight: 600;
  display: block;
  margin-bottom: 0.25rem;
}

.format-hint code {
  color: #10b981;
  font-family: monospace;
}

.radio-group {
  display: flex;
  gap: 1.5rem;
  font-size: 0.9rem;
}

.radio-group label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.tsv-textarea {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(0, 0, 0, 0.4);
  color: white;
  border-radius: 6px;
  font-family: monospace;
  font-size: 0.85rem;
  resize: vertical;
  box-sizing: border-box;
}

.tsv-textarea:focus {
  border-color: #3b82f6;
  outline: none;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  padding: 1rem 1.25rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(0, 0, 0, 0.1);
}

.modal-footer button {
  padding: 0.5rem 1.25rem;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
  transition: all 0.2s ease;
}

.modal-footer button.secondary {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: #e5e7eb;
}

.modal-footer button.secondary:hover {
  background: rgba(255, 255, 255, 0.05);
}

.modal-footer button.primary-btn {
  background: #3b82f6;
  border: none;
  color: white;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
}

.modal-footer button.primary-btn:hover {
  background: #2563eb;
}

.archive-inline-badge {
  color: #f87171;
  font-size: 0.85rem;
  font-weight: 500;
  margin-left: 0.5rem;
}
</style>
