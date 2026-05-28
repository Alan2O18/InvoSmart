<template>
  <div class="budget-editor-view">
    <!-- Top Bar -->
    <header class="editor-header">
      <div class="header-left">
        <button @click="goBack" class="back-btn">← 返回專案詳情</button>
        <div class="title-section">
          <h1>{{ projectName }} 預決算編輯器</h1>
          <span class="project-id">活動編號：{{ projectId }}</span>
        </div>
      </div>
      <div class="header-right">
        <span v-if="isBudgetDirty || dirtyJobs.size > 0" class="dirty-badge">● 有未儲存的變更</span>
        <button @click="handleSave" :disabled="saving" class="save-btn">
          {{ saving ? '儲存中...' : '儲存變更' }}
        </button>
        <button @click="exportWord" :disabled="loading" class="export-btn">
          匯出 Word 報表
        </button>
      </div>
    </header>

    <!-- Tab Selection -->
    <div class="tabs-container">
      <button 
        class="tab-btn" 
        :class="{ active: activeTab === 'budget' }" 
        @click="activeTab = 'budget'"
      >
        📊 預算配置 (Budget)
      </button>
      <button 
        class="tab-btn" 
        :class="{ active: activeTab === 'final' }" 
        @click="activeTab = 'final'"
      >
        💸 決算明細 (Final Account)
      </button>
    </div>

    <!-- Main Content Area -->
    <main class="editor-main" v-if="!loading">
      <datalist id="income-items">
        <option v-for="item in budgetIncomeSuggestions" :key="`income-${item}`" :value="item"></option>
      </datalist>
      <datalist id="expense-items">
        <option v-for="item in expenseCategorySuggestions" :key="`expense-${item}`" :value="item"></option>
      </datalist>

      <!-- 1. BUDGET TAB -->
      <div v-if="activeTab === 'budget'" class="tab-content">
        <!-- 1.1 Budget Income -->
        <section class="grid-section">
          <div class="section-header">
            <h2>1. 預算收入配置 (Estimated Income)</h2>
            <div class="section-actions">
              <button @click="copyBudgetIncomeTSV" class="action-btn-secondary">📤 匯出 TSV</button>
              <button @click="openImportModal('budgetIncome')" class="action-btn-secondary">📥 匯入 TSV</button>
              <button @click="addBudgetIncomeRow" class="action-btn">+ 新增收入項目</button>
            </div>
          </div>

          <div class="table-container">
            <table class="excel-table">
              <thead>
                <tr>
                  <th style="width: 40%">項目名稱</th>
                  <th style="width: 25%">預算金額</th>
                  <th style="width: 25%">備註說明</th>
                  <th style="width: 10%">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, idx) in budgetIncome" :key="'income-' + idx">
                  <td>
                    <input 
                      v-model="row.name" 
                      list="income-items"
                      placeholder="請輸入項目名稱 (e.g. 報名費)" 
                      @change="isBudgetDirty = true"
                      @keydown="handleCellKeydown($event, 'budgetIncome', idx, 0)"
                      @paste="handleCellPaste($event, 'budgetIncome', idx, 0, budgetIncome)"
                      :data-row="idx"
                      data-col="0"
                    />
                  </td>
                  <td>
                    <input 
                      type="number"
                      v-model.number="row.amount" 
                      placeholder="0"
                      class="num-input"
                      @change="isBudgetDirty = true"
                      @keydown="handleCellKeydown($event, 'budgetIncome', idx, 1)"
                      @paste="handleCellPaste($event, 'budgetIncome', idx, 1, budgetIncome)"
                      :data-row="idx"
                      data-col="1"
                    />
                  </td>
                  <td>
                    <input 
                      v-model="row.note" 
                      placeholder="備註說明" 
                      @change="isBudgetDirty = true"
                      @keydown="handleCellKeydown($event, 'budgetIncome', idx, 2)"
                      @paste="handleCellPaste($event, 'budgetIncome', idx, 2, budgetIncome)"
                      :data-row="idx"
                      data-col="2"
                    />
                  </td>
                  <td class="action-cell">
                    <button @click="removeBudgetIncomeRow(idx)" class="delete-row-btn" title="刪除項目">✕</button>
                  </td>
                </tr>
                <!-- Empty State -->
                <tr v-if="budgetIncome.length === 0">
                  <td colspan="4" class="empty-state-cell">
                    <p>目前無任何收入項目</p>
                    <button @click="addBudgetIncomeRow" class="empty-add-btn">+ 新增第一筆</button>
                  </td>
                </tr>
                <!-- Total Row -->
                <tr class="total-row" v-if="budgetIncome.length > 0">
                  <td>合計 (Total Income)</td>
                  <td class="num-cell">{{ formatCurrency(budgetIncomeTotal) }}</td>
                  <td></td>
                  <td></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- 1.2 Budget Expense -->
        <section class="grid-section">
          <div class="section-header">
            <h2>2. 預算支出配置 (Estimated Expense)</h2>
            <div class="section-actions">
              <button @click="copyBudgetExpenseTSV" class="action-btn-secondary">📤 匯出 TSV</button>
              <button @click="openImportModal('budgetExpense')" class="action-btn-secondary">📥 匯入 TSV</button>
              <button @click="addBudgetExpenseRow" class="action-btn">+ 新增支出項目</button>
            </div>
          </div>

          <div class="table-container">
            <table class="excel-table">
              <thead>
                <tr>
                  <th style="width: 25%">項目名稱</th>
                  <th style="width: 12%">數量</th>
                  <th style="width: 15%">預估單價</th>
                  <th style="width: 15%">小計 (自動計算)</th>
                  <th style="width: 23%">用途說明</th>
                  <th style="width: 10%">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, idx) in budgetExpense" :key="'expense-' + idx">
                  <td>
                    <input 
                      v-model="row.name" 
                      list="expense-items"
                      placeholder="項目名稱 (e.g. 印製費)" 
                      @change="onBudgetExpenseChange(row)"
                      @keydown="handleCellKeydown($event, 'budgetExpense', idx, 0)"
                      @paste="handleCellPaste($event, 'budgetExpense', idx, 0, budgetExpense)"
                      :data-row="idx"
                      data-col="0"
                    />
                  </td>
                  <td>
                    <input 
                      type="number"
                      v-model.number="row.qty" 
                      placeholder="1"
                      class="num-input"
                      @change="onBudgetExpenseChange(row)"
                      @keydown="handleCellKeydown($event, 'budgetExpense', idx, 1)"
                      @paste="handleCellPaste($event, 'budgetExpense', idx, 1, budgetExpense)"
                      :data-row="idx"
                      data-col="1"
                    />
                  </td>
                  <td>
                    <input 
                      type="number"
                      v-model.number="row.price" 
                      placeholder="0"
                      class="num-input"
                      @change="onBudgetExpenseChange(row)"
                      @keydown="handleCellKeydown($event, 'budgetExpense', idx, 2)"
                      @paste="handleCellPaste($event, 'budgetExpense', idx, 2, budgetExpense)"
                      :data-row="idx"
                      data-col="2"
                    />
                  </td>
                  <td>
                    <input 
                      type="number"
                      :value="row.total" 
                      class="num-input readonly"
                      readonly
                      placeholder="0"
                      @keydown="handleCellKeydown($event, 'budgetExpense', idx, 3)"
                      :data-row="idx"
                      data-col="3"
                    />
                  </td>
                  <td>
                    <input 
                      v-model="row.purpose" 
                      placeholder="用途說明 (e.g. 宣傳海報印製)" 
                      @change="isBudgetDirty = true"
                      @keydown="handleCellKeydown($event, 'budgetExpense', idx, 4)"
                      @paste="handleCellPaste($event, 'budgetExpense', idx, 4, budgetExpense)"
                      :data-row="idx"
                      data-col="4"
                    />
                  </td>
                  <td class="action-cell">
                    <button @click="removeBudgetExpenseRow(idx)" class="delete-row-btn" title="刪除項目">✕</button>
                  </td>
                </tr>
                <!-- Empty State -->
                <tr v-if="budgetExpense.length === 0">
                  <td colspan="6" class="empty-state-cell">
                    <p>目前無任何支出項目</p>
                    <button @click="addBudgetExpenseRow" class="empty-add-btn">+ 新增第一筆</button>
                  </td>
                </tr>
                <!-- Total Row -->
                <tr class="total-row" v-if="budgetExpense.length > 0">
                  <td>合計 (Total Expense)</td>
                  <td></td>
                  <td></td>
                  <td class="num-cell">{{ formatCurrency(budgetExpenseTotal) }}</td>
                  <td></td>
                  <td></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <!-- 2. FINAL ACCOUNT TAB -->
      <div v-else-if="activeTab === 'final'" class="tab-content">
        <!-- 2.1 Final Income (Read-only copy of Budget Income) -->
        <section class="grid-section">
          <div class="section-header">
            <h2>1. 決算收入 (Actual Income) - <span class="badge info">唯讀：自動代入預算項目</span></h2>
          </div>

          <div class="table-container">
            <table class="excel-table readonly-table">
              <thead>
                <tr>
                  <th style="width: 40%">項目名稱</th>
                  <th style="width: 30%">決算金額 (代入預算)</th>
                  <th style="width: 30%">備註說明</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, idx) in budgetIncome" :key="'final-income-' + idx">
                  <td>
                    <input :value="row.name" readonly class="readonly" />
                  </td>
                  <td>
                    <input type="number" :value="row.amount" readonly class="readonly num-input" />
                  </td>
                  <td>
                    <input :value="row.note" readonly class="readonly" />
                  </td>
                </tr>
                <tr v-if="budgetIncome.length === 0">
                  <td colspan="3" class="empty-state-cell">
                    <p>預算中無任何收入項目。請先至「預算配置」分頁新增。</p>
                  </td>
                </tr>
                <tr class="total-row" v-if="budgetIncome.length > 0">
                  <td>合計 (Total Income)</td>
                  <td class="num-cell">{{ formatCurrency(budgetIncomeTotal) }}</td>
                  <td></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- 2.2 Final Expense (Merged from Job Items) -->
        <section class="grid-section">
          <div class="section-header">
            <h2>2. 決算支出明細 (Actual Expense) - <span class="badge success">數據來源：發票憑證</span></h2>
            <div class="section-actions" v-if="doneJobIds.length > 0">
              <button @click="copyFinalExpenseTSV" class="action-btn-secondary">📤 匯出全部 TSV</button>
            </div>
          </div>

          <div class="table-container">
            <table class="excel-table final-account-table">
              <thead>
                <tr>
                  <th style="width: 30%">發票品項名稱</th>
                  <th style="width: 8%">數量</th>
                  <th style="width: 12%">單價</th>
                  <th style="width: 12%">金額 (自動計算)</th>
                  <th style="width: 15%">支出科目/類別</th>
                  <th style="width: 15%">備註說明</th>
                  <th style="width: 8%">操作</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="(row, idx) in finalExpenseItems" :key="'final-row-' + idx">
                  <!-- Header Row for Job if first item -->
                  <tr v-if="isFirstItemOfJob(row, idx)" class="job-group-header">
                    <td colspan="7">
                      <div class="job-group-title">
                        <span>📄 憑證檔案: <strong>{{ row.jobTitle }}</strong></span>
                        <div style="display: flex; gap: 0.5rem; align-items: center;">
                          <button type="button" @click="copyJobTSV(row.jobId, row.jobTitle)" class="add-job-item-btn" style="background: rgba(255,255,255,0.05); border-color: rgba(255,255,255,0.2); color: #fff;">📤 匯出 TSV</button>
                          <button type="button" @click="openImportModal('finalExpense', row.jobId, row.jobTitle)" class="add-job-item-btn" style="background: rgba(255,255,255,0.05); border-color: rgba(255,255,255,0.2); color: #fff;">📥 匯入 TSV</button>
                          <button type="button" @click="addFinalExpenseRow(row.jobId)" class="add-job-item-btn">+ 新增品項</button>
                        </div>
                      </div>
                    </td>
                  </tr>

                  <!-- Placeholder row if no items in job -->
                  <tr v-if="row.placeholder" class="job-placeholder-row">
                    <td colspan="7" class="placeholder-cell">
                      <span>尚無任何明細品項。請點擊上方按鈕新增。</span>
                    </td>
                  </tr>

                  <!-- Normal Item Row -->
                  <tr v-else :class="{ 'row-dirty': dirtyJobs.has(row.jobId) }">
                    <td>
                      <input 
                        v-model="row.name" 
                        placeholder="發票商品名稱" 
                        @change="onFinalItemChange(row)"
                        @keydown="handleCellKeydown($event, 'finalExpense', idx, 0)"
                        @paste="handleCellPaste($event, 'finalExpense', idx, 0, finalExpenseItems)"
                        :data-row="idx"
                        data-col="0"
                      />
                    </td>
                    <td>
                      <input 
                        type="number"
                        v-model.number="row.qty" 
                        placeholder="1"
                        class="num-input"
                        @change="onFinalItemChange(row)"
                        @keydown="handleCellKeydown($event, 'finalExpense', idx, 1)"
                        @paste="handleCellPaste($event, 'finalExpense', idx, 1, finalExpenseItems)"
                        :data-row="idx"
                        data-col="1"
                      />
                    </td>
                    <td>
                      <input 
                        type="number"
                        v-model.number="row.price" 
                        placeholder="0"
                        class="num-input"
                        @change="onFinalItemChange(row)"
                        @keydown="handleCellKeydown($event, 'finalExpense', idx, 2)"
                        @paste="handleCellPaste($event, 'finalExpense', idx, 2, finalExpenseItems)"
                        :data-row="idx"
                        data-col="2"
                      />
                    </td>
                    <td>
                      <input 
                        type="number"
                        :value="row.total" 
                        class="num-input readonly"
                        readonly
                        placeholder="0"
                        @keydown="handleCellKeydown($event, 'finalExpense', idx, 3)"
                        :data-row="idx"
                        data-col="3"
                      />
                    </td>
                    <td>
                      <input 
                        v-model="row.category" 
                        list="expense-items"
                        placeholder="e.g. 鐘點費、印刷費" 
                        @change="onFinalItemChange(row)"
                        @keydown="handleCellKeydown($event, 'finalExpense', idx, 4)"
                        @paste="handleCellPaste($event, 'finalExpense', idx, 4, finalExpenseItems)"
                        :data-row="idx"
                        data-col="4"
                      />
                    </td>
                    <td>
                      <input 
                        v-model="row.remark" 
                        placeholder="備註" 
                        @change="onFinalItemChange(row)"
                        @keydown="handleCellKeydown($event, 'finalExpense', idx, 5)"
                        @paste="handleCellPaste($event, 'finalExpense', idx, 5, finalExpenseItems)"
                        :data-row="idx"
                        data-col="5"
                      />
                    </td>
                    <td class="action-cell">
                      <button @click="deleteFinalExpenseRow(row)" class="delete-row-btn" title="刪除品項">✕</button>
                    </td>
                  </tr>
                </template>

                <!-- Done jobs list is completely empty -->
                <tr v-if="doneJobIds.length === 0">
                  <td colspan="7" class="empty-state-cell">
                    <p>目前尚無已完成處理 (done) 的憑證工作，無法代入決算支出明細。</p>
                    <p style="font-size: 0.85rem; color: #888; margin-top: 0.5rem;">請至專案詳情頁面上傳並執行 VLM 處理憑證。</p>
                  </td>
                </tr>

                <!-- Total Row -->
                <tr class="total-row" v-if="doneJobIds.length > 0">
                  <td>決算合計 (Total Actual Expense)</td>
                  <td></td>
                  <td></td>
                  <td class="num-cell">{{ formatCurrency(finalExpenseTotal) }}</td>
                  <td></td>
                  <td></td>
                  <td></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </main>

    <!-- Loading State -->
    <div v-else class="loading-overlay">
      <div class="spinner"></div>
      <p>讀取專案預決算資料中，請稍候...</p>
    </div>

    <!-- TSV Import Modal -->
    <div v-if="showImportModal" class="modal-overlay" @click.self="closeImportModal">
      <div class="modal-container-small">
        <header class="modal-header">
          <h2>📥 匯入 TSV 數據</h2>
          <button type="button" class="close-btn" @click="closeImportModal">✕</button>
        </header>
        <div class="modal-body">
          <p class="import-help">
            請貼上從 Excel 或 Google Sheets 複製的資料列：
          </p>
          <div class="format-hint">
            <span class="hint-title">預期欄位順序：</span>
            <code v-if="importTarget === 'budgetIncome'">項目名稱 &nbsp;&nbsp;|&nbsp;&nbsp; 預算金額 &nbsp;&nbsp;|&nbsp;&nbsp; 備註說明</code>
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
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import api from '../services/api'

const route = useRoute()
const router = useRouter()
const projectId = route.params.id

// State Variables
const activeTab = ref('budget') // 'budget' | 'final'
const projectName = ref(projectId)
const projectData = ref(null)
const budgetIncome = ref([])
const budgetExpense = ref([])
const doneJobIds = ref([])
const jobDetailsMap = ref({}) // jobId -> full normalized job detail object
const finalExpenseItems = ref([])
const dirtyJobs = ref(new Set())
const isBudgetDirty = ref(false)
const loading = ref(false)
const saving = ref(false)

// Autocomplete suggestions
const budgetIncomeSuggestions = ref([])
const expenseCategorySuggestions = ref([])

// TSV Import Modal state
const showImportModal = ref(false)
const importTarget = ref('') // 'budgetIncome' | 'budgetExpense' | 'finalExpense'
const importJobId = ref('')
const importJobTitle = ref('')
const importMode = ref('append') // 'append' | 'overwrite'
const tsvInputText = ref('')

// Computed Totals
const budgetIncomeTotal = computed(() => {
  return budgetIncome.value.reduce((sum, row) => sum + (Number(row.amount) || 0), 0)
})

const budgetExpenseTotal = computed(() => {
  return budgetExpense.value.reduce((sum, row) => sum + (Number(row.total) || 0), 0)
})

const finalExpenseTotal = computed(() => {
  return finalExpenseItems.value.reduce((sum, row) => {
    if (row.placeholder) return sum
    return sum + (Number(row.total) || 0)
  }, 0)
})

// Navigation
const goBack = () => {
  router.push({ name: 'project-detail', params: { id: projectId } })
}

// Check filename helper
const getFilename = (path) => {
  if (!path) return ''
  return path.split('\\').pop().split('/').pop()
}

// First item check for visual grouping in Final Account Expense
const isFirstItemOfJob = (row, index) => {
  if (index === 0) return true
  const prevRow = finalExpenseItems.value[index - 1]
  return prevRow.jobId !== row.jobId
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

const copyJobTSV = (jobId, jobTitle) => {
  const jobData = jobDetailsMap.value[jobId]
  if (!jobData) return
  let tsv = '品項名稱\t數量\t單價\t金額\t類別\t備註\n'
  const items = jobData.items || []
  items.forEach(row => {
    tsv += `${row.name || ''}\t${row.qty || 1}\t${row.price || 0}\t${row.total || 0}\t${row.category || ''}\t${row.remark || ''}\n`
  })
  navigator.clipboard.writeText(tsv)
  alert(`憑證 ${jobTitle} 支出已複製為 TSV 格式！`)
}

const openImportModal = (target, jobId = '', jobTitle = '') => {
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

    if (importTarget.value === 'budgetIncome') {
      parsedRows.push({
        name: cols[0] || '',
        amount: Number(cols[1]) || 0,
        note: cols[2] || ''
      })
    } else if (importTarget.value === 'budgetExpense') {
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

  if (importTarget.value === 'budgetIncome') {
    if (importMode.value === 'overwrite') {
      budgetIncome.value = parsedRows
    } else {
      budgetIncome.value = [...budgetIncome.value, ...parsedRows]
    }
    isBudgetDirty.value = true
  } else if (importTarget.value === 'budgetExpense') {
    if (importMode.value === 'overwrite') {
      budgetExpense.value = parsedRows
    } else {
      budgetExpense.value = [...budgetExpense.value, ...parsedRows]
    }
    isBudgetDirty.value = true
  } else if (importTarget.value === 'finalExpense') {
    const jobId = importJobId.value
    const jobData = jobDetailsMap.value[jobId]
    if (jobData) {
      if (importMode.value === 'overwrite') {
        jobData.items = parsedRows
      } else {
        if (!jobData.items) jobData.items = []
        jobData.items = [...jobData.items, ...parsedRows]
      }
      dirtyJobs.value.add(jobId)
      updateJobSummary(jobId)
      rebuildFinalExpenseItems()
    }
  }

  showImportModal.value = false
  alert(`成功匯入 ${parsedRows.length} 筆資料！`)
}

// -------------------------------------------------------------
// BUDGET CRUD
// -------------------------------------------------------------
const addBudgetIncomeRow = () => {
  budgetIncome.value.push({ name: '', amount: 0, note: '' })
  isBudgetDirty.value = true
}

const removeBudgetIncomeRow = (idx) => {
  budgetIncome.value.splice(idx, 1)
  isBudgetDirty.value = true
}

const addBudgetExpenseRow = () => {
  budgetExpense.value.push({ name: '', qty: 1, price: 0, total: 0, purpose: '' })
  isBudgetDirty.value = true
}

const removeBudgetExpenseRow = (idx) => {
  budgetExpense.value.splice(idx, 1)
  isBudgetDirty.value = true
}

const onBudgetExpenseChange = (row) => {
  row.total = (Number(row.qty) || 0) * (Number(row.price) || 0)
  isBudgetDirty.value = true
}

// -------------------------------------------------------------
// FINAL ACCOUNT CRUD & MERGING
// -------------------------------------------------------------
const rebuildFinalExpenseItems = () => {
  const items = []
  for (const jobId of doneJobIds.value) {
    const jobData = jobDetailsMap.value[jobId]
    if (!jobData) continue

    const jobTitle = jobData.voucher_id || jobData.job_id || getFilename(jobData.image_path) || jobId
    
    // Normalize items
    const fileItems = jobData.items || []
    if (fileItems.length === 0) {
      items.push({
        jobId,
        jobTitle,
        index: -1,
        placeholder: true,
        name: '',
        qty: null,
        price: null,
        total: 0,
        category: '',
        remark: ''
      })
    } else {
      fileItems.forEach((item, itemIdx) => {
        items.push({
          jobId,
          jobTitle,
          index: itemIdx,
          placeholder: false,
          name: item.name || '',
          qty: item.qty,
          price: item.price,
          total: item.total || 0,
          category: item.category || '',
          remark: item.remark || ''
        })
      })
    }
  }
  finalExpenseItems.value = items
}

const onFinalItemChange = (row) => {
  if (row.placeholder) return
  const jobData = jobDetailsMap.value[row.jobId]
  if (jobData && jobData.items) {
    const item = jobData.items[row.index]
    if (item) {
      item.name = row.name
      item.qty = row.qty
      item.price = row.price
      item.total = (Number(row.qty) || 0) * (Number(row.price) || 0)
      row.total = item.total
      item.category = row.category
      item.remark = row.remark
      
      dirtyJobs.value.add(row.jobId)
      updateJobSummary(row.jobId)
    }
  }
}

const addFinalExpenseRow = (jobId) => {
  const jobData = jobDetailsMap.value[jobId]
  if (jobData) {
    if (!jobData.items) jobData.items = []
    jobData.items.push({ name: '', qty: 1, price: 0, total: 0, category: '', remark: '' })
    dirtyJobs.value.add(jobId)
    updateJobSummary(jobId)
    rebuildFinalExpenseItems()
  }
}

const deleteFinalExpenseRow = (row) => {
  if (row.placeholder) return
  const jobData = jobDetailsMap.value[row.jobId]
  if (jobData && jobData.items) {
    jobData.items.splice(row.index, 1)
    dirtyJobs.value.add(row.jobId)
    updateJobSummary(row.jobId)
    rebuildFinalExpenseItems()
  }
}

const updateJobSummary = (jobId) => {
  const jobData = jobDetailsMap.value[jobId]
  if (jobData && jobData.items) {
    const totalSum = jobData.items.reduce((sum, item) => sum + (Number(item.total) || 0), 0)
    if (!jobData.summary) jobData.summary = {}
    jobData.summary.total = totalSum
    jobData.summary.subtotal = totalSum
  }
}

// -------------------------------------------------------------
// EXCEL-LIKE SPREADSHEET MECHANICS
// -------------------------------------------------------------
const handleCellKeydown = (e, tableType, rowIndex, colIndex) => {
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

  const nextInput = table.querySelector(`input[data-row="${targetRow}"][data-col="${targetCol}"]`)
  if (nextInput) {
    nextInput.focus()
    nextInput.select()
    e.preventDefault()
  }
}

const handleCellPaste = (e, tableType, startRowIndex, startColIndex, list) => {
  e.preventDefault()
  const clipboardData = e.clipboardData || window.clipboardData
  const pastedText = clipboardData.getData('Text')
  if (!pastedText) return

  const rows = pastedText.split(/\r?\n/).map(row => row.split('\t'))
  
  for (let r = 0; r < rows.length; r++) {
    const rowData = rows[r]
    if (rowData.length === 1 && rowData[0] === '') continue
    
    const targetRowIndex = startRowIndex + r
    
    // Add row if not enough in budget
    if (tableType === 'budgetIncome') {
      while (budgetIncome.value.length <= targetRowIndex) {
        budgetIncome.value.push({ name: '', amount: 0, note: '' })
      }
    } else if (tableType === 'budgetExpense') {
      while (budgetExpense.value.length <= targetRowIndex) {
        budgetExpense.value.push({ name: '', qty: 1, price: 0, total: 0, purpose: '' })
      }
    }

    const row = list[targetRowIndex]
    if (!row || row.placeholder) continue

    for (let c = 0; c < rowData.length; c++) {
      const val = rowData[c]
      const targetColIndex = startColIndex + c

      if (tableType === 'budgetIncome') {
        if (targetColIndex === 0) row.name = val
        if (targetColIndex === 1) row.amount = Number(val) || 0
        if (targetColIndex === 2) row.note = val
      } else if (tableType === 'budgetExpense') {
        if (targetColIndex === 0) row.name = val
        if (targetColIndex === 1) row.qty = Number(val) || 1
        if (targetColIndex === 2) row.price = Number(val) || 0
        if (targetColIndex === 4) row.purpose = val
        row.total = (Number(row.qty) || 0) * (Number(row.price) || 0)
      } else if (tableType === 'finalExpense') {
        if (targetColIndex === 0) row.name = val
        if (targetColIndex === 1) row.qty = Number(val) || 1
        if (targetColIndex === 2) row.price = Number(val) || 0
        if (targetColIndex === 4) row.category = val
        if (targetColIndex === 5) row.remark = val
        row.total = (Number(row.qty) || 0) * (Number(row.price) || 0)
        onFinalItemChange(row)
      }
    }
  }

  if (tableType === 'budgetIncome' || tableType === 'budgetExpense') {
    isBudgetDirty.value = true
  }
}

// -------------------------------------------------------------
// TSV COPY HELPER
// -------------------------------------------------------------
const copyBudgetIncomeTSV = () => {
  let tsv = '項目\t金額\t備註\n'
  budgetIncome.value.forEach(row => {
    tsv += `${row.name || ''}\t${row.amount || 0}\t${row.note || ''}\n`
  })
  navigator.clipboard.writeText(tsv)
  alert('預算收入已複製為 TSV 格式，可直接貼入 Excel！')
}

const copyBudgetExpenseTSV = () => {
  let tsv = '項目\t數量\t單價\t金額\t用途\n'
  budgetExpense.value.forEach(row => {
    tsv += `${row.name || ''}\t${row.qty || 1}\t${row.price || 0}\t${row.total || 0}\t${row.purpose || ''}\n`
  })
  navigator.clipboard.writeText(tsv)
  alert('預算支出已複製為 TSV 格式，可直接貼入 Excel！')
}

const copyFinalExpenseTSV = () => {
  let tsv = '憑證\t項目名稱\t數量\t單價\t金額\t類別\t備註\n'
  finalExpenseItems.value.forEach(row => {
    if (row.placeholder) return
    tsv += `${row.jobTitle || ''}\t${row.name || ''}\t${row.qty || 0}\t${row.price || 0}\t${row.total || 0}\t${row.category || ''}\t${row.remark || ''}\n`
  })
  navigator.clipboard.writeText(tsv)
  alert('決算支出已複製為 TSV 格式，可直接貼入 Excel！')
}

// Currency format helper
const formatCurrency = (val) => {
  return new Intl.NumberFormat('zh-TW', { style: 'currency', currency: 'TWD', maximumFractionDigits: 0 }).format(val)
}

// -------------------------------------------------------------
// DATA INGESTION & LIFECYCLE
// -------------------------------------------------------------
const loadData = async () => {
  loading.value = true
  try {
    // 1. Get Project Detail (including metadata)
    const projectRes = await api.getProjectDetail(projectId)
    projectData.value = projectRes.data
    projectName.value = projectRes.data.name || projectId
    
    const meta = projectRes.data.metadata || {}
    budgetIncome.value = meta.budgetIncome || []
    budgetExpense.value = meta.budgetExpense || []

    // 2. Load Jobs
    const jobsRes = await api.getProjectJobs(projectId)
    const jobs = jobsRes.data || []
    const doneJobs = jobs.filter(j => j.status === 'done')
    doneJobIds.value = doneJobs.map(j => j.job_id)

    // 3. Parallel fetch detail JSON for all completed jobs
    if (doneJobs.length > 0) {
      const details = await Promise.all(doneJobs.map(j => api.getJobDetails(projectId, j.job_id)))
      details.forEach((res, index) => {
        const jobId = doneJobs[index].job_id
        const detailData = res.data
        
        // Parse manual json or VLM result
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

        // Normalize
        const normalized = {
          receipt_type: detailData.receipt_type || parsedData.receipt_type || '電子發票證明聯',
          voucher_id: detailData.voucher_id || parsedData.voucher_id || '',
          job_id: jobId,
          image_path: detailData.image_path || '',
          header: parsedData.header || { supplier: '', buyer: '', invoice_id: '', date: '' },
          items: parsedData.items || [],
          summary: parsedData.summary || { subtotal: 0, tax: 0, total: 0 },
          verification: parsedData.verification || { handwritten_total_chinese: '', stamp_shop_name: '', qr_code_detected: false }
        }
        
        jobDetailsMap.value[jobId] = normalized
      })
      rebuildFinalExpenseItems()
    }
  } catch (e) {
    console.error('Failed to load project budget data:', e)
    alert('讀取預決算資料失敗：' + e)
  } finally {
    loading.value = false
  }
}

// -------------------------------------------------------------
// SAVE & EXPORT
// -------------------------------------------------------------
const saveBudget = async () => {
  const updatedMetadata = {
    ...projectData.value.metadata,
    budgetIncome: budgetIncome.value,
    budgetExpense: budgetExpense.value
  }
  
  await api.updateProject(projectId, updatedMetadata)
  // Re-fetch project details to update the cache
  const projectRes = await api.getProjectDetail(projectId)
  projectData.value = projectRes.data
}

const saveFinal = async () => {
  const promises = Array.from(dirtyJobs.value).map(jobId => {
    const jobData = jobDetailsMap.value[jobId]
    // Structure expected: { header, items, summary, verification, ... }
    const payload = {
      receipt_type: jobData.receipt_type,
      header: jobData.header,
      items: jobData.items,
      summary: jobData.summary,
      verification: jobData.verification
    }
    return api.saveManualJson(projectId, jobId, payload)
  })
  await Promise.all(promises)
}

const handleSave = async () => {
  saving.value = true
  try {
    let savedAny = false
    if (isBudgetDirty.value) {
      await saveBudget()
      isBudgetDirty.value = false
      savedAny = true
    }
    if (dirtyJobs.value.size > 0) {
      await saveFinal()
      dirtyJobs.value.clear()
      savedAny = true
    }
    
    // Dynamically persist suggestions
    if (savedAny) {
      for (const item of budgetIncome.value || []) {
        if (item.name) await saveSuggestion('budget_income_item', item.name)
      }
      for (const item of budgetExpense.value || []) {
        if (item.name) await saveSuggestion('expense_category', item.name)
      }
      for (const item of finalExpenseItems.value || []) {
        if (item.category) await saveSuggestion('expense_category', item.category)
      }
      
      alert('所有變更已成功儲存！')
    } else {
      alert('無任何變更需要儲存。')
    }
  } catch (e) {
    console.error('Save failed:', e)
    alert('儲存失敗：' + e)
  } finally {
    saving.value = false
  }
}

const exportWord = async () => {
  if (isBudgetDirty.value || dirtyJobs.value.size > 0) {
    const confirmSave = confirm('匯出前需要儲存變更。是否儲存並繼續？')
    if (confirmSave) {
      await handleSave()
      if (isBudgetDirty.value || dirtyJobs.value.size > 0) {
        return // Save failed
      }
    } else {
      return
    }
  }

  loading.value = true
  try {
    const res = await api.runWordExport(projectId)
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `${projectId}_word_export.docx`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    alert('Word 報表已匯出並下載！')
  } catch (e) {
    alert('匯出 Word 報表失敗：' + e)
  } finally {
    loading.value = false
  }
}

// Router leave guard
onBeforeRouteLeave((to, from, next) => {
  if (isBudgetDirty.value || dirtyJobs.value.size > 0) {
    const confirmLeave = confirm('您有未儲存的變更。確定要離開嗎？')
    if (confirmLeave) next()
    else next(false)
  } else {
    next()
  }
})

onMounted(() => {
  loadData()
  loadSuggestions()
})
</script>

<style scoped>
.budget-editor-view {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: #0f0f12;
  color: #f3f4f6;
  padding: 1.5rem;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

/* Header style with premium dark backdrop */
.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 2rem;
  background: rgba(28, 28, 35, 0.45);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  margin-bottom: 1.5rem;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1.5rem;
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

.title-section h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
  background: linear-gradient(135deg, #60a5fa, #3b82f6);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.project-id {
  font-size: 0.8rem;
  color: #9ca3af;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.dirty-badge {
  font-size: 0.85rem;
  color: #fbbf24;
  margin-right: 0.5rem;
  animation: pulse 2s infinite;
}

.save-btn {
  background: linear-gradient(135deg, #10b981, #059669);
  color: white;
  border: none;
  padding: 0.6rem 1.25rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 600;
  transition: all 0.2s ease;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2);
}

.save-btn:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}

.save-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.export-btn {
  background: linear-gradient(135deg, #8b5cf6, #7c3aed);
  color: white;
  border: none;
  padding: 0.6rem 1.25rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 600;
  transition: all 0.2s ease;
  box-shadow: 0 4px 12px rgba(139, 92, 246, 0.2);
}

.export-btn:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

/* Tabs switcher */
.tabs-container {
  display: flex;
  gap: 0.5rem;
  background: rgba(28, 28, 35, 0.45);
  padding: 0.4rem;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  margin-bottom: 1.5rem;
  width: fit-content;
}

.tab-btn {
  background: transparent;
  border: none;
  color: #9ca3af;
  padding: 0.6rem 1.5rem;
  border-radius: 6px;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-btn:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.04);
}

.tab-btn.active {
  color: #3b82f6;
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(59, 130, 246, 0.25);
}

/* Main layouts */
.editor-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.tab-content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.grid-section {
  background: rgba(28, 28, 35, 0.3);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.15);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding-bottom: 0.75rem;
}

.section-header h2 {
  font-size: 1.15rem;
  font-weight: 600;
  margin: 0;
  color: #9ca3af;
}

.section-actions {
  display: flex;
  gap: 0.75rem;
}

.action-btn {
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.3);
  color: #60a5fa;
  padding: 0.4rem 0.9rem;
  border-radius: 5px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn:hover {
  background: rgba(59, 130, 246, 0.2);
  border-color: #60a5fa;
}

.action-btn-secondary {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #d1d5db;
  padding: 0.4rem 0.9rem;
  border-radius: 5px;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn-secondary:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.3);
}

/* Excel table styling */
.table-container {
  overflow-x: auto;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.excel-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  background-color: rgba(18, 18, 22, 0.6);
}

.excel-table th {
  background-color: rgba(255, 255, 255, 0.03);
  color: #9ca3af;
  font-weight: 600;
  font-size: 0.85rem;
  padding: 0.75rem 1rem;
  border-bottom: 2px solid rgba(255, 255, 255, 0.08);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.excel-table td {
  padding: 0.25rem 0.4rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

/* Excel Cell Inputs */
.excel-table input {
  width: 100%;
  background: transparent;
  border: 1px solid transparent;
  color: #fff;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  border-radius: 4px;
  box-sizing: border-box;
  transition: all 0.15s ease;
}

.excel-table input:focus {
  background: rgba(0, 0, 0, 0.35);
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.4);
  outline: none;
}

.excel-table input.num-input {
  text-align: right;
}

.excel-table input.readonly {
  color: #9ca3af;
  background-color: rgba(255, 255, 255, 0.01);
  cursor: not-allowed;
}

.excel-table input.readonly:focus {
  border-color: transparent;
  box-shadow: none;
  background-color: rgba(255, 255, 255, 0.01);
}

.excel-table tr:hover {
  background-color: rgba(255, 255, 255, 0.01);
}

/* Delete Row button */
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

.action-cell {
  text-align: center;
}

/* Total row */
.total-row {
  background-color: rgba(255, 255, 255, 0.02) !important;
  font-weight: 700;
  font-size: 0.95rem;
}

.total-row td {
  padding: 1rem 1.25rem;
  border-top: 2px solid rgba(255, 255, 255, 0.08);
}

.num-cell {
  text-align: right;
  color: #60a5fa;
}

/* Badges */
.badge {
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-weight: 600;
  margin-left: 0.5rem;
}

.badge.info {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.3);
}

.badge.success {
  background: rgba(16, 185, 129, 0.15);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

/* Final Account Table styles */
.job-group-header {
  background-color: rgba(59, 130, 246, 0.08) !important;
}

.job-group-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.6rem 1rem;
  font-size: 0.88rem;
  color: #e5e7eb;
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

.job-placeholder-row {
  background-color: rgba(255, 255, 255, 0.01);
}

.placeholder-cell {
  padding: 1.5rem !important;
  text-align: center;
  color: #6b7280;
  font-style: italic;
  font-size: 0.85rem;
}

.row-dirty {
  background-color: rgba(251, 191, 36, 0.02);
  border-left: 3px solid #fbbf24;
}

/* Empty States */
.empty-state-cell {
  padding: 3rem !important;
  text-align: center;
  color: #9ca3af;
}

.empty-state-cell p {
  margin: 0 0 1rem 0;
  font-size: 0.95rem;
}

.empty-add-btn {
  background: #2563eb;
  color: white;
  border: none;
  padding: 0.5rem 1.25rem;
  border-radius: 5px;
  font-weight: 600;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.empty-add-btn:hover {
  background: #1d4ed8;
}

/* Loading Spinner Overlay */
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
.modal-container-small {
  width: min(550px, 90vw);
  background: #2a2a35;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  color: white;
  box-shadow: 0 10px 40px rgba(0,0,0,0.6);
  overflow: hidden;
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
</style>
