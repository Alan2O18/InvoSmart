<template>
  <div v-if="modelValue" class="modal-overlay" @click.self="closeModal">
    <div class="modal-container">
      <header class="modal-header">
        <h2>編輯專案與預算資訊</h2>
        <button type="button" class="close-btn" @click="closeModal">✕</button>
      </header>

      <form @submit.prevent="updateProject" class="project-form">
        <!-- Basic Info -->
        <section>
          <h3>基本資訊</h3>
          <div class="form-row">
            <div class="form-group">
              <label for="activityId">活動編號 (唯讀)</label>
              <input type="text" id="activityId" :value="projectId" readonly class="readonly" />
            </div>
            <div class="form-group">
              <label for="activityName">活動名稱 *</label>
              <input type="text" id="activityName" v-model="projectName" required placeholder="請輸入活動名稱" />
            </div>
          </div>
          
          <div class="form-row">
            <div class="form-group">
              <label for="group">所屬群組</label>
              <input
                type="text"
                id="group"
                v-model="form.group"
                list="group-list"
                @change="onGroupChange"
                @blur="saveSuggestion('group_name', form.group)"
              />
              <datalist id="group-list">
                <option v-for="g in groups" :key="g.group_name" :value="g.group_name"></option>
              </datalist>
            </div>
            <div class="form-group">
              <label for="leader">組長</label>
              <input
                type="text"
                id="leader"
                v-model="form.leader"
                list="leader-list"
                @blur="savePeopleSuggestions(form.leader)"
              />
              <datalist id="leader-list">
                <option v-for="leader in leaderOptions" :key="leader" :value="leader"></option>
              </datalist>
            </div>
            <div class="form-group">
              <label for="coordinator">活動總召</label>
              <select id="coordinator" v-model="form.coordinator" @change="saveSuggestion('person_name', form.coordinator)">
                <option value="">請選擇</option>
                <option v-for="person in allPeopleOptions" :key="person" :value="person">{{ person }}</option>
              </select>
            </div>
            <div class="form-group">
              <label for="generalAffairs">活動總務</label>
              <input
                type="text"
                id="generalAffairs"
                v-model="form.generalAffairs"
                list="people-list"
                @blur="saveSuggestion('person_name', form.generalAffairs)"
              />
              <datalist id="people-list">
                <option v-for="person in allPeopleOptions" :key="`ga-${person}`" :value="person"></option>
              </datalist>
            </div>
          </div>
        </section>

        <!-- Date & Location -->
        <section>
          <h3>日期與地點</h3>
          <div class="form-row">
            <div class="form-group">
              <label for="startTime">開始時間</label>
              <input type="datetime-local" id="startTime" v-model="form.startTime" @input="calcDates" @change="calcDates" />
            </div>
            <div class="form-group">
              <label for="endTime">結束時間</label>
              <input type="datetime-local" id="endTime" v-model="form.endTime" @input="calcDates" @change="calcDates" />
            </div>
          </div>
          <div class="form-group">
            <label for="location">活動地點</label>
            <input type="text" id="location" v-model="form.location" list="location-list" @blur="saveSuggestion('location', form.location)" />
            <datalist id="location-list">
              <option v-for="loc in locationSuggestions" :key="loc" :value="loc"></option>
            </datalist>
          </div>
        </section>

        <!-- Participants -->
        <section>
          <h3>參與人數</h3>
          <div class="form-row">
            <div class="form-group">
              <label for="teacherCount">老師人數</label>
              <input type="number" id="teacherCount" v-model="form.teacherCount" min="0" />
            </div>
            <div class="form-group">
              <label for="studentCount">學生人數</label>
              <input type="number" id="studentCount" v-model="form.studentCount" min="0" />
            </div>
          </div>
        </section>

        <!-- Financial -->
        <section>
          <h3>財務與核備資訊</h3>
          <div class="form-group">
            <label for="subsidyReason">擬請補助原因</label>
            <textarea id="subsidyReason" v-model="form.subsidyReason" rows="2"></textarea>
          </div>
          <div class="form-group">
            <label for="subsidyMethod">擬請補助方式</label>
            <textarea id="subsidyMethod" v-model="form.subsidyMethod" rows="2"></textarea>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label for="balanceHandling">結餘處理方式</label>
              <input type="text" id="balanceHandling" v-model="form.balanceHandling" />
            </div>
            <div class="form-group">
              <label for="overdraftHandling">超支處理方式</label>
              <input type="text" id="overdraftHandling" v-model="form.overdraftHandling" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label for="budgetDate">預算核備日期</label>
              <input type="date" id="budgetDate" v-model="form.budgetDate" />
            </div>
            <div class="form-group">
              <label for="finalAccountDate">決算核備日期</label>
              <input type="date" id="finalAccountDate" v-model="form.finalAccountDate" />
            </div>
          </div>
        </section>

        <!-- Budget Entries -->
        <section>
          <h3>經費來源 (預算表 / 結算表)</h3>
          <datalist id="income-items">
            <option v-for="item in budgetIncomeSuggestions" :key="`income-${item}`" :value="item"></option>
          </datalist>
          <div class="table-container">
            <table class="dynamic-table">
              <thead>
                <tr>
                  <th>來源名稱</th>
                  <th>金額</th>
                  <th>備註</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, index) in form.budgetIncome" :key="'in'+index">
                  <td><input v-model="item.name" type="text" list="income-items" placeholder="下拉選單或自填" @blur="saveSuggestion('budget_income_item', item.name)" /></td>
                  <td><input v-model.number="item.amount" type="number" /></td>
                  <td><input v-model="item.note" type="text" /></td>
                  <td><button type="button" @click="removeIncome(index)" class="mini-btn danger">刪除</button></td>
                </tr>
                <tr v-if="!form.budgetIncome || form.budgetIncome.length === 0">
                  <td colspan="4" class="no-data">尚無經費來源</td>
                </tr>
              </tbody>
            </table>
            <button type="button" @click="addIncome" class="mini-btn text-btn">+ 新增來源</button>
          </div>
        </section>

        <section>
          <h3>各項費用支出預估</h3>
          <datalist id="expense-items">
            <option v-for="item in expenseCategorySuggestions" :key="`expense-${item}`" :value="item"></option>
          </datalist>
          <div class="table-container">
            <table class="dynamic-table">
              <thead>
                <tr>
                  <th>項目名稱 (類別)</th>
                  <th>數量</th>
                  <th>單價</th>
                  <th>總額</th>
                  <th>說明用途 (品項)</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, index) in form.budgetExpense" :key="'ex'+index">
                  <td><input v-model="item.name" type="text" list="expense-items" placeholder="下拉選單或自填" @blur="saveSuggestion('expense_category', item.name)" /></td>
                  <td><input v-model.number="item.qty" type="number" @input="calcExpenseTotal(item)" /></td>
                  <td><input v-model.number="item.price" type="number" @input="calcExpenseTotal(item)" /></td>
                  <td><input v-model.number="item.total" type="number" /></td>
                  <td><input v-model="item.purpose" type="text" /></td>
                  <td><button type="button" @click="removeExpense(index)" class="mini-btn danger">刪除</button></td>
                </tr>
                <tr v-if="!form.budgetExpense || form.budgetExpense.length === 0">
                  <td colspan="6" class="no-data">尚無支出預估</td>
                </tr>
              </tbody>
            </table>
            <button type="button" @click="addExpense" class="mini-btn text-btn">+ 新增支出</button>
          </div>
        </section>

        <footer class="modal-footer">
          <button type="button" @click="closeModal" class="secondary">取消</button>
          <button type="button" @click="runWordExport" :disabled="loading" class="export-btn">
            {{ loading ? '匯出中...' : '儲存並匯出 Word' }}
          </button>
          <button type="submit" :disabled="loading" class="primary-btn">
            {{ loading ? '儲存中...' : '儲存活動資訊' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, watch } from 'vue'
import api from '../services/api'

const props = defineProps({
  modelValue: {
    type: Boolean,
    required: true,
  },
  projectId: {
    type: String,
    required: true,
  }
})

const emit = defineEmits(['update:modelValue', 'saved'])

const loading = ref(false)
const projectName = ref('')

const form = reactive({
  group: '',
  leader: '',
  coordinator: '',
  generalAffairs: '',
  startTime: '',
  endTime: '',
  location: '',
  teacherCount: 0,
  studentCount: 0,
  subsidyReason: '',
  subsidyMethod: '',
  balanceHandling: '',
  overdraftHandling: '',
  budgetDate: '',
  finalAccountDate: '',
  budgetIncome: [],
  budgetExpense: []
})

const groups = ref([])
const availableLeaders = ref([])
const personSuggestions = ref([])
const budgetIncomeSuggestions = ref([])
const expenseCategorySuggestions = ref([])
const locationSuggestions = ref([])

const splitPeople = (raw) => {
  const text = String(raw || '').trim()
  if (!text) return []
  return text
    .replace(/\n/g, '、')
    .replace(/[,，;；]/g, '、')
    .split('、')
    .map((x) => x.trim())
    .filter(Boolean)
}

const allPeopleOptions = computed(() => {
  const merged = []
  const pushUnique = (name) => {
    const value = String(name || '').trim()
    if (!value || merged.includes(value)) return
    merged.push(value)
  }

  groups.value.forEach((group) => {
    ;(group.leader_names || []).forEach(pushUnique)
  })
  personSuggestions.value.forEach(pushUnique)
  splitPeople(form.leader).forEach(pushUnique)
  pushUnique(form.coordinator)
  pushUnique(form.generalAffairs)
  return merged
})

const leaderOptions = computed(() => {
  const merged = []
  const pushUnique = (name) => {
    const value = String(name || '').trim()
    if (!value || merged.includes(value)) return
    merged.push(value)
  }
  availableLeaders.value.forEach(pushUnique)
  allPeopleOptions.value.forEach(pushUnique)
  return merged
})

const loadSuggestions = async () => {
  try {
    const [peopleRes, incomeRes, expenseRes, locationRes] = await Promise.all([
      api.getSuggestions('person_name', '', 200),
      api.getSuggestions('budget_income_item', '', 200),
      api.getSuggestions('expense_category', '', 200),
      api.getSuggestions('location', '', 200),
    ])
    personSuggestions.value = peopleRes.data || []
    budgetIncomeSuggestions.value = incomeRes.data || []
    expenseCategorySuggestions.value = expenseRes.data || []
    locationSuggestions.value = locationRes.data || []
  } catch (e) {
    console.error('Failed to load suggestions', e)
  }
}

const saveSuggestion = async (category, value) => {
  const text = String(value || '').trim()
  if (!text) return
  try {
    await api.addSuggestion(category, text)
    if (category === 'person_name' && !personSuggestions.value.includes(text)) {
      personSuggestions.value = [...personSuggestions.value, text]
    }
    if (category === 'budget_income_item' && !budgetIncomeSuggestions.value.includes(text)) {
      budgetIncomeSuggestions.value = [...budgetIncomeSuggestions.value, text]
    }
    if (category === 'expense_category' && !expenseCategorySuggestions.value.includes(text)) {
      expenseCategorySuggestions.value = [...expenseCategorySuggestions.value, text]
    }
    if (category === 'location' && !locationSuggestions.value.includes(text)) {
      locationSuggestions.value = [...locationSuggestions.value, text]
    }
  } catch (e) {
    console.error(`Failed to save suggestion ${category}:`, e)
  }
}

const savePeopleSuggestions = async (raw) => {
  const names = splitPeople(raw)
  for (const name of names) {
    await saveSuggestion('person_name', name)
  }
}

const fetchGroups = async () => {
  try {
    const res = await api.listGroups()
    groups.value = res.data
  } catch (e) {
    console.error('Failed to load groups', e)
  }
}

const onGroupChange = () => {
  const selected = groups.value.find(g => g.group_name === form.group)
  const leaderNames = selected?.leader_names || []
  availableLeaders.value = leaderNames
  if (leaderNames.length > 0) {
    form.leader = leaderNames.join('、')
  }
}

const fetchProject = async () => {
  try {
    const res = await api.getProjects()
    const project = res.data.find(p => p.project_id === props.projectId)
    
    if (project) {
      projectName.value = project.name || props.projectId
      const meta = project.metadata || {}
      
      // Reset form fields with default structures
      Object.assign(form, {
        group: '',
        leader: '',
        coordinator: '',
        generalAffairs: '',
        startTime: '',
        endTime: '',
        location: '',
        teacherCount: 0,
        studentCount: 0,
        subsidyReason: '無',
        subsidyMethod: '無',
        balanceHandling: '無',
        overdraftHandling: '無',
        budgetDate: '',
        finalAccountDate: '',
        budgetIncome: [],
        budgetExpense: []
      }, meta)
      
      // Ensure fallbacks to '無' if fields are empty strings
      if (!form.subsidyReason) form.subsidyReason = '無'
      if (!form.subsidyMethod) form.subsidyMethod = '無'
      if (!form.balanceHandling) form.balanceHandling = '無'
      if (!form.overdraftHandling) form.overdraftHandling = '無'

      onGroupChange()
    }
  } catch (error) {
    console.error('Failed to fetch activity:', error)
  }
}

const calcDates = () => {
  if (form.startTime) {
    const start = new Date(form.startTime)
    if (!isNaN(start.getTime())) {
      const budget = new Date(start)
      budget.setDate(budget.getDate() - 3)
      form.budgetDate = `${budget.getFullYear()}-${String(budget.getMonth() + 1).padStart(2, '0')}-${String(budget.getDate()).padStart(2, '0')}`
    }
  }

  const endStr = form.endTime || form.startTime
  if (endStr) {
    const endBaseline = new Date(endStr)
    if (!isNaN(endBaseline.getTime())) {
      const final = new Date(endBaseline)
      final.setDate(final.getDate() + 1)
      form.finalAccountDate = `${final.getFullYear()}-${String(final.getMonth() + 1).padStart(2, '0')}-${String(final.getDate()).padStart(2, '0')}`
    }
  }
}

const updateProject = async (shouldClose = true) => {
  if (!projectName.value) {
    alert('Activity Name is required')
    return false
  }
  
  loading.value = true
  try {
    await saveSuggestion('group_name', form.group)
    await savePeopleSuggestions(form.leader)
    await saveSuggestion('person_name', form.coordinator)
    await saveSuggestion('person_name', form.generalAffairs)
    for (const item of form.budgetIncome || []) {
      await saveSuggestion('budget_income_item', item?.name)
    }
    for (const item of form.budgetExpense || []) {
      await saveSuggestion('expense_category', item?.name)
    }

    const metadata = {
      ...form,
      name: projectName.value,
      projectName: projectName.value
    }
    
    await api.updateProject(props.projectId, metadata)
    emit('saved')
    if (shouldClose) closeModal()
    return true
  } catch (error) {
    console.error('Failed to update activity:', error)
    alert('Failed to update activity.')
    return false
  } finally {
    loading.value = false
  }
}

const addIncome = () => {
  if (!form.budgetIncome) form.budgetIncome = []
  form.budgetIncome.push({ name: '', amount: 0, note: '' })
}

const removeIncome = (index) => {
  form.budgetIncome.splice(index, 1)
}

const addExpense = () => {
  if (!form.budgetExpense) form.budgetExpense = []
  form.budgetExpense.push({ name: '', qty: 1, price: 0, total: 0, purpose: '' })
}

const removeExpense = (index) => {
  form.budgetExpense.splice(index, 1)
}

const calcExpenseTotal = (item) => {
  item.total = (item.qty || 0) * (item.price || 0)
}

const runWordExport = async () => {
  const saved = await updateProject(false)
  if (!saved) return
  
  loading.value = true
  try {
    const res = await api.runWordExport(props.projectId);
    const url = window.URL.createObjectURL(new Blob([res.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${props.projectId}_word_export.docx`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    alert('Word 報表已匯出並下載！');
  } catch (e) {
    alert('Word export failed. Please check backend logs.');
  } finally {
    loading.value = false;
  }
}

const closeModal = () => {
  emit('update:modelValue', false)
}

watch(() => props.modelValue, (newVal) => {
  if (newVal) {
    fetchGroups()
    loadSuggestions()
    fetchProject()
  }
})
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  padding: 1rem;
}

.modal-container {
  width: min(850px, 95vw);
  max-height: 90vh;
  background: #2a2a2a;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  color: white;
  box-shadow: 0 4px 20px rgba(0,0,0,0.5);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #444;
}

.modal-header h2 {
  margin: 0;
  font-size: 1.3rem;
  color: #60a5fa;
}

.close-btn {
  background: transparent;
  border: none;
  color: #888;
  font-size: 1.5rem;
  cursor: pointer;
}

.close-btn:hover {
  color: white;
}

.project-form {
  padding: 1.5rem;
  overflow-y: auto;
  flex: 1;
  box-sizing: border-box;
}

section {
  margin-bottom: 2rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #444;
}

section:last-of-type {
  border-bottom: none;
}

h3 {
  font-size: 1.1rem;
  margin-top: 0;
  margin-bottom: 1rem;
  color: #60a5fa;
}

.form-row {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
}

.form-group {
  margin-bottom: 1rem;
  flex: 1;
  min-width: 200px;
}

label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #ddd;
  font-size: 0.9rem;
}

input, textarea, select {
  width: 100%;
  padding: 0.65rem;
  border: 1px solid #444;
  background: #1a1a1a;
  color: white;
  border-radius: 4px;
  box-sizing: border-box;
}

input:focus, textarea:focus, select:focus {
  border-color: #60a5fa;
  outline: none;
}

input.readonly {
  background-color: #0f0f0f;
  color: #888;
  cursor: not-allowed;
  border-color: #333;
}

.table-container {
  overflow-x: auto;
  margin-top: 0.5rem;
}

.dynamic-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 0.5rem;
}

.dynamic-table th, .dynamic-table td {
  padding: 0.6rem;
  border: 1px solid #444;
  text-align: left;
}

.dynamic-table th {
  background: #1f1f1f;
  font-size: 0.85rem;
  color: #888;
}

.no-data {
  text-align: center;
  color: #666;
  font-size: 0.9rem;
}

.mini-btn {
  padding: 0.35rem 0.65rem;
  font-size: 0.8rem;
  border-radius: 4px;
  cursor: pointer;
  border: none;
}

.mini-btn.danger {
  background: #dc2626;
  color: white;
}

.text-btn {
  background: transparent;
  border: 1px dashed #60a5fa;
  color: #60a5fa;
  width: 100%;
  margin-top: 0.5rem;
  text-align: center;
}

.text-btn:hover {
  background: rgba(96, 165, 250, 0.1);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #444;
}

.modal-footer button {
  padding: 0.6rem 1.2rem;
  border-radius: 4px;
  font-weight: bold;
  cursor: pointer;
  border: none;
}

.modal-footer .secondary {
  background: transparent;
  border: 1px solid #444;
  color: #ccc;
}

.modal-footer .secondary:hover {
  background: #333;
}

.modal-footer .primary-btn {
  background: #60a5fa;
  color: white;
}

.modal-footer .export-btn {
  background: #10b981;
  color: white;
}
</style>
