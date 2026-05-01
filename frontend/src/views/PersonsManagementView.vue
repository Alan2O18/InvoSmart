<template>
  <div class="persons-page">
    <header class="page-header">
      <div>
        <h1>人員與角色管理</h1>
        <p>管理簽核人員、初始化虛擬實體、關聯個人印章。</p>
      </div>
      <div class="actions">
        <button @click="reload" :disabled="loading">重新整理</button>
        <button @click="initVirtuals" :disabled="loading" class="warning-btn">初始化虛擬實體</button>
        <button @click="openAddPersonDialog" class="primary">新增人員</button>
      </div>
    </header>

    <div v-if="error" class="error-banner">{{ error }}</div>
    <div v-if="success" class="success-banner">{{ success }}</div>

    <div v-if="loading && persons.length === 0" class="loading-wrap">載入中...</div>

    <div v-else-if="persons.length === 0" class="empty-wrap">
      <h2>尚未建立人員</h2>
      <p>點擊「新增人員」或「初始化虛擬實體」開始。</p>
    </div>

    <section v-else class="persons-grid">
      <article v-for="person in persons" :key="person.id" class="person-card" :class="{ virtual: person.is_virtual }">
        <div class="person-header">
          <h3>{{ person.name }}</h3>
          <span class="role-badge">{{ person.role }}</span>
          <span v-if="person.is_virtual" class="virtual-badge">虛擬實體</span>
        </div>

        <div class="person-content">
          <p class="created">建立時間：{{ formatDate(person.created_at) }}</p>
          <p class="stamps-count">印章數量：{{ (stampsByPerson[person.id] || []).length }}</p>

          <div class="stamps-preview">
            <span v-if="stampsByPerson[person.id]?.length === 0" class="no-stamps">尚無印章</span>
            <div v-else class="stamp-thumbnails">
              <img
                v-for="stamp in (stampsByPerson[person.id] || []).slice(0, 3)"
                :key="stamp.id"
                :src="toAbsoluteUrl(stamp.image_url)"
                :alt="stamp.name"
                class="stamp-thumb"
                :title="stamp.name"
              />
              <span v-if="(stampsByPerson[person.id] || []).length > 3" class="more">
                +{{ (stampsByPerson[person.id] || []).length - 3 }}
              </span>
            </div>
          </div>
        </div>

        <div class="person-actions">
          <button @click="openStampDialog(person)" class="action-btn upload-btn">上傳印章</button>
          <button @click="viewStamps(person)" class="action-btn view-btn">檢視</button>
          <button @click="deletePerson(person)" class="action-btn delete-btn">刪除</button>
        </div>
      </article>
    </section>

    <!-- 新增人員對話框 -->
    <div v-if="showAddDialog" class="modal-overlay" @click.self="closeAddDialog">
      <div class="modal-panel">
        <h2>新增人員</h2>
        <div class="form-group">
          <label>姓名</label>
          <input v-model="newPerson.name" type="text" placeholder="輸入人員姓名" />
        </div>
        <div class="form-group">
          <label>角色</label>
          <select v-model="newPerson.role">
            <option value="">-- 選擇角色 --</option>
            <option value="handler">經手人</option>
            <option value="activity_general_affairs">活動總務</option>
            <option value="general_affairs_head">總務組長</option>
            <option value="president">社長</option>
            <option value="advisor">指導老師</option>
          </select>
        </div>
        <div class="form-actions">
          <button @click="createPerson" class="primary" :disabled="!newPerson.name || !newPerson.role">建立</button>
          <button @click="closeAddDialog">取消</button>
        </div>
      </div>
    </div>

    <!-- 上傳印章對話框 -->
    <div v-if="showStampDialog" class="modal-overlay" @click.self="closeStampDialog">
      <div class="modal-panel">
        <h2>為 {{ selectedPerson?.name }} 上傳印章</h2>
        <div class="form-group">
          <label>選擇印章圖紙</label>
          <input type="file" accept="image/*" @change="onStampFileChange" />
        </div>
        <div v-if="stampPreviewUrl" class="preview-wrap">
          <img :src="stampPreviewUrl" alt="preview" class="preview-img" />
        </div>
        <div class="form-group">
          <label>偵測模式</label>
          <div class="mode-row">
            <label>
              <input type="radio" value="red" v-model="stampMode" />
              紅色印章
            </label>
            <label>
              <input type="radio" value="edge" v-model="stampMode" />
              黑色或混色印章
            </label>
          </div>
        </div>
        <div class="form-actions">
          <button @click="registerPersonStamp" class="primary" :disabled="!stampFile">匯入</button>
          <button @click="closeStampDialog">取消</button>
        </div>
      </div>
    </div>

    <!-- 查看印章對話框 -->
    <div v-if="showViewDialog" class="modal-overlay" @click.self="closeViewDialog">
      <div class="modal-panel modal-wide">
        <h2>{{ selectedPerson?.name }} 的印章</h2>
        <div v-if="selectedPersonStamps.length === 0" class="empty">尚無印章</div>
        <div v-else class="stamps-grid-modal">
          <div v-for="stamp in selectedPersonStamps" :key="stamp.id" class="stamp-item-modal">
            <img :src="toAbsoluteUrl(stamp.image_url)" :alt="stamp.name" />
            <p class="stamp-name">{{ stamp.name }}</p>
            <button @click="deletePersonStamp(stamp)" class="delete-mini">刪除</button>
          </div>
        </div>
        <button @click="closeViewDialog" class="primary">關閉</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../services/api'

const persons = ref([])
const stampsByPerson = ref({})
const loading = ref(false)
const error = ref('')
const success = ref('')

const showAddDialog = ref(false)
const showStampDialog = ref(false)
const showViewDialog = ref(false)

const newPerson = ref({ name: '', role: '' })
const selectedPerson = ref(null)
const stampFile = ref(null)
const stampPreviewUrl = ref('')
const stampMode = ref('red')
const selectedPersonStamps = ref([])

const reload = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await api.listPersons()
    persons.value = res.data
    // 加载每个人的印章
    for (const person of persons.value) {
      const stampsRes = await api.listStampsByOwner(person.id)
      stampsByPerson.value[person.id] = stampsRes.data
    }
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '載入失敗'
  } finally {
    loading.value = false
  }
}

const initVirtuals = async () => {
  if (!confirm('這將初始化虛擬實體（財務原本、財務已稽核、社團關防）。確定嗎？')) return
  loading.value = true
  error.value = ''
  success.value = ''
  try {
    await api.ensureVirtualPersons()
    success.value = '虛擬實體已初始化'
    setTimeout(() => reload(), 500)
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '初始化失敗'
  } finally {
    loading.value = false
  }
}

const openAddPersonDialog = () => {
  newPerson.value = { name: '', role: '' }
  showAddDialog.value = true
}

const closeAddDialog = () => {
  showAddDialog.value = false
}

const createPerson = async () => {
  if (!newPerson.value.name || !newPerson.value.role) {
    error.value = '請填入姓名和角色'
    return
  }
  loading.value = true
  error.value = ''
  try {
    await api.createPerson(newPerson.value.name, newPerson.value.role, false)
    success.value = '人員已建立'
    closeAddDialog()
    setTimeout(() => reload(), 500)
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '建立失敗'
  } finally {
    loading.value = false
  }
}

const deletePerson = async (person) => {
  if (!confirm(`確定刪除 ${person.name} 嗎？此操作無法復原。`)) return
  loading.value = true
  error.value = ''
  try {
    await api.deletePerson(person.id)
    success.value = '人員已刪除'
    setTimeout(() => reload(), 500)
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '刪除失敗'
  } finally {
    loading.value = false
  }
}

const openStampDialog = (person) => {
  selectedPerson.value = person
  stampFile.value = null
  stampPreviewUrl.value = ''
  stampMode.value = 'red'
  showStampDialog.value = true
}

const closeStampDialog = () => {
  showStampDialog.value = false
  selectedPerson.value = null
}

const onStampFileChange = (e) => {
  stampFile.value = e.target.files[0]
  if (stampFile.value) {
    stampPreviewUrl.value = URL.createObjectURL(stampFile.value)
  }
}

const registerPersonStamp = async () => {
  if (!stampFile.value || !selectedPerson.value) return
  loading.value = true
  error.value = ''
  try {
    await api.registerStamps(stampFile.value, stampMode.value, [], selectedPerson.value.id)
    success.value = '印章已上傳'
    closeStampDialog()
    setTimeout(() => reload(), 500)
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '上傳失敗'
  } finally {
    loading.value = false
  }
}

const viewStamps = (person) => {
  selectedPerson.value = person
  selectedPersonStamps.value = stampsByPerson.value[person.id] || []
  showViewDialog.value = true
}

const closeViewDialog = () => {
  showViewDialog.value = false
}

const deletePersonStamp = async (stamp) => {
  if (!confirm(`確定刪除印章「${stamp.name}」嗎？`)) return
  loading.value = true
  error.value = ''
  try {
    await api.deleteStampById(stamp.id)
    success.value = '印章已刪除'
    setTimeout(() => {
      viewStamps(selectedPerson.value)
      reload()
    }, 300)
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '刪除失敗'
  } finally {
    loading.value = false
  }
}

const toAbsoluteUrl = (url) => {
  if (!url) return ''
  return api.toAbsoluteUrl(url)
}

const formatDate = (epoch) => {
  if (!epoch) return '-'
  return new Date(epoch * 1000).toLocaleString('zh-TW')
}

onMounted(() => {
  reload()
})
</script>

<style scoped>
.persons-page {
  padding: 1.5rem;
  color: #e5e7eb;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 2rem;
}

.page-header > div:first-child h1 {
  margin: 0 0 0.5rem 0;
  font-size: 1.8rem;
}

.page-header > div:first-child p {
  margin: 0;
  color: #9ca3af;
}

.actions {
  display: flex;
  gap: 0.5rem;
}

.actions button {
  padding: 0.5rem 1rem;
  background: #374151;
  color: #e5e7eb;
  border: 1px solid #4b5563;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.actions button:hover:not(:disabled) {
  background: #4b5563;
}

.actions button.primary {
  background: #10b981;
  border-color: #059669;
}

.actions button.primary:hover:not(:disabled) {
  background: #059669;
}

.actions button.warning-btn {
  background: #f59e0b;
  border-color: #d97706;
}

.actions button.warning-btn:hover:not(:disabled) {
  background: #d97706;
}

.actions button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error-banner {
  padding: 1rem;
  background: #7f1d1d;
  color: #fca5a5;
  border-left: 4px solid #dc2626;
  margin-bottom: 1rem;
  border-radius: 4px;
}

.success-banner {
  padding: 1rem;
  background: #065f46;
  color: #a7f3d0;
  border-left: 4px solid #10b981;
  margin-bottom: 1rem;
  border-radius: 4px;
}

.loading-wrap,
.empty-wrap {
  text-align: center;
  padding: 3rem;
  color: #9ca3af;
}

.empty-wrap h2 {
  margin-top: 0;
  color: #d1d5db;
}

.persons-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 1.5rem;
}

.person-card {
  background: #1f2937;
  border: 1px solid #374151;
  border-radius: 8px;
  padding: 1.5rem;
  transition: all 0.3s;
}

.person-card:hover {
  border-color: #4b5563;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.person-card.virtual {
  border-left: 4px solid #8b5cf6;
}

.person-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.person-header h3 {
  margin: 0;
  font-size: 1.1rem;
}

.role-badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  background: #3b82f6;
  color: #fff;
  border-radius: 12px;
  font-size: 0.8rem;
}

.virtual-badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  background: #8b5cf6;
  color: #fff;
  border-radius: 12px;
  font-size: 0.8rem;
}

.person-content {
  margin-bottom: 1rem;
}

.created {
  margin: 0.5rem 0;
  font-size: 0.9rem;
  color: #9ca3af;
}

.stamps-count {
  margin: 0.5rem 0;
  font-size: 0.9rem;
  color: #9ca3af;
  font-weight: 500;
}

.stamps-preview {
  margin-top: 1rem;
  padding: 0.75rem;
  background: #111827;
  border-radius: 4px;
  min-height: 60px;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.no-stamps {
  color: #6b7280;
  font-size: 0.9rem;
}

.stamp-thumbnails {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.stamp-thumb {
  width: 50px;
  height: 50px;
  border-radius: 4px;
  object-fit: cover;
  cursor: pointer;
  transition: transform 0.2s;
}

.stamp-thumb:hover {
  transform: scale(1.1);
}

.more {
  display: inline-block;
  padding: 0 0.5rem;
  color: #9ca3af;
  font-size: 0.85rem;
}

.person-actions {
  display: flex;
  gap: 0.5rem;
}

.action-btn {
  flex: 1;
  padding: 0.5rem;
  border: 1px solid #4b5563;
  background: #374151;
  color: #e5e7eb;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.2s;
}

.action-btn:hover {
  background: #4b5563;
}

.upload-btn {
  background: #10b981;
  border-color: #059669;
}

.upload-btn:hover {
  background: #059669;
}

.delete-btn {
  background: #ef4444;
  border-color: #dc2626;
}

.delete-btn:hover {
  background: #dc2626;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-panel {
  background: #1f2937;
  border: 1px solid #374151;
  border-radius: 8px;
  padding: 2rem;
  width: 90%;
  max-width: 500px;
  max-height: 80vh;
  overflow-y: auto;
}

.modal-panel.modal-wide {
  max-width: 800px;
}

.modal-panel h2 {
  margin-top: 0;
  color: #e5e7eb;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: #d1d5db;
  font-weight: 500;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 0.5rem;
  background: #111827;
  color: #e5e7eb;
  border: 1px solid #374151;
  border-radius: 4px;
  font-size: 0.9rem;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #10b981;
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.1);
}

.mode-row {
  display: flex;
  gap: 1rem;
}

.mode-row label {
  display: flex;
  align-items: center;
  margin-bottom: 0;
}

.mode-row input[type='radio'] {
  width: auto;
  margin-right: 0.5rem;
}

.preview-wrap {
  margin-bottom: 1rem;
  text-align: center;
}

.preview-img {
  max-width: 100%;
  max-height: 300px;
  border-radius: 4px;
}

.form-actions {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
}

.form-actions button {
  padding: 0.5rem 1.5rem;
  border: 1px solid #4b5563;
  background: #374151;
  color: #e5e7eb;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.form-actions button:hover {
  background: #4b5563;
}

.form-actions button.primary {
  background: #10b981;
  border-color: #059669;
}

.form-actions button.primary:hover:not(:disabled) {
  background: #059669;
}

.form-actions button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.stamps-grid-modal {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stamp-item-modal {
  text-align: center;
}

.stamp-item-modal img {
  width: 100%;
  height: 120px;
  object-fit: cover;
  border-radius: 4px;
  margin-bottom: 0.5rem;
}

.stamp-name {
  font-size: 0.8rem;
  color: #d1d5db;
  margin: 0 0 0.5rem 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.delete-mini {
  width: 100%;
  padding: 0.25rem;
  font-size: 0.75rem;
  background: #ef4444;
  border: 1px solid #dc2626;
  color: #fff;
  border-radius: 2px;
  cursor: pointer;
  transition: all 0.2s;
}

.delete-mini:hover {
  background: #dc2626;
}

.empty {
  text-align: center;
  padding: 2rem;
  color: #9ca3af;
}
</style>
