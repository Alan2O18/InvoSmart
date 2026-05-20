<template>
  <div class="stamps-page">
    <header class="page-header">
      <div>
        <h1>印章與人員管理</h1>
        <p>建立各角色的實體/虛擬人員，並統一管理他們的專屬印章。</p>
      </div>
      <div class="actions">
        <button type="button" @click="fetchData" :disabled="loading">重新整理</button>
        <button type="button" @click="ensureVirtuals" :disabled="loading" class="secondary">建立系統預設虛擬角色</button>
        <button type="button" class="primary" @click="goToUploadView">批次上傳印章/PDF</button>
      </div>
    </header>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <div class="person-creation">
      <form @submit.prevent="handleCreatePerson">
        <input v-model="newPersonName" type="text" placeholder="人員姓名 (例如：王小明)" required />
        <select v-model="newPersonRole" required>
          <option value="handler">經手人 (Handler)</option>
          <option value="activity_general_affairs">活動總務 (Activity GA)</option>
          <option value="general_affairs_head">總務組長 (GA Head)</option>
          <option value="president">社長 (President)</option>
          <option value="advisor">指導老師 (Advisor)</option>
          <option value="club_seal">社團關防 (Club Seal)</option>
        </select>
        <button type="submit" class="action-btn">新增實體人員</button>
      </form>
    </div>

    <div v-if="loading && groupedData.length === 0" class="loading-wrap">載入中...</div>

    <div v-else-if="groupedData.length === 0" class="empty-wrap">
      <h2>目前尚無任何人與印章紀錄</h2>
      <p>請在上方「新增人員」，或是「批次上傳印章/PDF」。</p>
    </div>

    <!-- Persons and their Stamps -->
    <div class="persons-list" v-else>
      <div v-for="personGroup in groupedData" :key="personGroup.person.id" class="person-card">
        <div class="person-header">
          <div>
            <h3>
              {{ personGroup.person.name }}
              <span class="role-badge">{{ personGroup.person.role }}</span>
              <span v-if="personGroup.person.is_virtual" class="virtual-badge">系統預設</span>
            </h3>
            <span class="person-id">ID: {{ personGroup.person.id }}</span>
          </div>
          <div>
            <button @click="goToUploadViewWithPerson(personGroup.person.id)" class="mini-btn">為此人上傳印章</button>
            <button v-if="!personGroup.person.is_virtual" @click="handleDeletePerson(personGroup.person)" class="mini-btn danger">刪除人員</button>
          </div>
        </div>

        <div v-if="personGroup.stamps.length === 0" class="no-stamps">
          此人員尚未綁定任何印章。
        </div>
        <div v-else class="stamp-grid">
          <div v-for="stamp in personGroup.stamps" :key="stamp.id" class="stamp-item">
            <div class="img-wrapper">
              <img :src="toAbsoluteUrl(stamp.image_url)" :alt="stamp.name || 'stamp'" />
            </div>
            <div class="stamp-info">
              <span class="stamp-cat">區域: {{ stamp.category || '自動' }}</span>
              <button @click="handleDeleteStamp(stamp)" class="delete-icon" title="移除印章">✕</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <section class="template-management">
      <div class="template-header">
        <div>
          <h2>蓋章模板管理</h2>
          <p>建立不同版型的蓋章座標配置，供 PDF 任務與憑證編輯時選用。</p>
        </div>
        <button type="button" class="mini-btn" @click="fetchTemplates" :disabled="loadingTemplates">重新整理</button>
      </div>

      <div class="template-actions-bar" style="margin-bottom: 1rem;">
        <button type="button" class="action-btn" @click="router.push('/stamp-templates/create')">新增視覺化模板</button>
      </div>

      <div v-if="loadingTemplates" class="loading-wrap">載入模板中...</div>
      <div v-else-if="templates.length === 0" class="empty-wrap">
        <h2>目前尚無蓋章模板</h2>
        <p>請先建立一個模板，之後才能在 PDF 任務中套用。</p>
      </div>
      <div v-else class="template-list">
        <article v-for="template in templates" :key="template.id" class="template-card">
          <div class="template-card-head">
            <div>
              <h3>{{ template.name }}</h3>
              <p>{{ template.description || '沒有描述' }}</p>
            </div>
            <span class="template-status" :class="{ active: template.active }">{{ template.active ? '啟用' : '停用' }}</span>
          </div>
          <div class="template-actions">
            <button type="button" class="mini-btn primary" @click="router.push(`/stamp-templates/${template.id}/edit`)">編輯模板</button>
            <button type="button" class="mini-btn danger" :disabled="processingTemplate" @click="handleDeleteTemplate(template.id)">刪除模板</button>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'
import { useStampStore } from '../store/stamp'

const router = useRouter()
const stampStore = useStampStore()

const persons = ref([])
const templates = ref([])
const error = ref('')
const loading = ref(false)
const loadingTemplates = ref(false)

const newPersonName = ref('')
const newPersonRole = ref('handler')
const processingTemplate = ref(false)

const groupedData = computed(() => {
  const g = []
  for (const p of persons.value) {
    const pStamps = stampStore.stamps.filter(s => s.owner_id === p.id)
    g.push({ person: p, stamps: pStamps })
  }
  return g
})

const toAbsoluteUrl = (url) => api.toAbsoluteUrl(url)

const fetchData = async () => {
  loading.value = true
  error.value = ''
  try {
    const [personsRes] = await Promise.all([
      api.listPersons(),
      stampStore.fetchStamps()
    ])
    persons.value = personsRes.data || []
  } catch (err) {
    error.value = err.message || '載入失敗'
    console.error(err)
  } finally {
    loading.value = false
  }
}

const fetchTemplates = async () => {
  loadingTemplates.value = true
  try {
    const res = await api.listStampTemplates()
    templates.value = res.data || []
  } catch (err) {
    error.value = err.message || '載入模板失敗'
  } finally {
    loadingTemplates.value = false
  }
}

const ensureVirtuals = async () => {
  loading.value = true
  try {
    await api.ensureVirtualPersons()
    await fetchData()
  } catch (err) {
    error.value = '無法建立虛擬人員：' + err
  } finally {
    loading.value = false
  }
}

const handleCreatePerson = async () => {
  if (!newPersonName.value) return
  loading.value = true
  try {
    await api.createPerson(newPersonName.value, newPersonRole.value, false)
    newPersonName.value = ''
    await fetchData()
  } catch (err) {
    error.value = '新增人員失敗：' + err
  } finally {
    loading.value = false
  }
}

const handleDeletePerson = async (person) => {
  if (!confirm(`確定刪除人員「${person.name}」與其所有印章嗎？`)) return
  try {
    await api.deletePerson(person.id)
    await fetchData()
  } catch (err) {
    error.value = '刪除失敗：' + err
  }
}

const handleDeleteStamp = async (stamp) => {
  if (!confirm('確定刪除此印章嗎？')) return
  try {
    await stampStore.deleteStamp(stamp.id)
    await fetchData()
  } catch (err) {
    error.value = '刪除印章失敗：' + err
  }
}



const handleDeleteTemplate = async (templateId) => {
  if (!confirm('確定刪除此蓋章模板嗎？')) return
  processingTemplate.value = true
  try {
    await api.deleteStampTemplate(templateId)
    await fetchTemplates()
  } catch (err) {
    error.value = '刪除模板失敗：' + (err?.message || err)
  } finally {
    processingTemplate.value = false
  }
}

const goToUploadView = () => {
  router.push('/stamps/upload')
}

const goToUploadViewWithPerson = (ownerId) => {
  router.push({ path: '/stamps/upload', query: { owner: ownerId } })
}

onMounted(() => {
  fetchData()
  fetchTemplates()
})
</script>

<style scoped>
.stamps-page {
  padding: 1.5rem;
  color: #e5e7eb;
  max-width: 1100px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 2rem;
  border-bottom: 1px solid #374151;
  padding-bottom: 1rem;
}

.page-header h1 {
  font-size: 1.8rem;
  margin: 0 0 0.5rem 0;
}

.page-header p {
  color: #9ca3af;
  margin: 0;
}

.actions {
  display: flex;
  gap: 0.6rem;
  align-items: center;
}

button {
  background: #374151;
  color: #fff;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  transition: opacity 0.2s;
}
button:hover:not(:disabled) {
  opacity: 0.8;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
button.primary {
  background: #059669;
  font-weight: bold;
}
button.secondary {
  background: #1d4ed8;
}
.mini-btn {
  padding: 0.25rem 0.5rem;
  font-size: 0.85rem;
  background: #4f46e5;
  border-radius: 4px;
}
.mini-btn.danger {
  background: #dc2626;
  margin-left: 0.5rem;
}

.person-creation {
  background: #1f2937;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1.5rem;
}
.person-creation form {
  display: flex;
  gap: 1rem;
  align-items: center;
}
.person-creation input, .person-creation select {
  padding: 0.5rem;
  border-radius: 4px;
  border: 1px solid #4b5563;
  background: #374151;
  color: white;
}
.action-btn {
  background: #2563eb;
}

.error-banner {
  background: rgba(220, 38, 38, 0.2);
  border: 1px solid #ef4444;
  color: #fca5a5;
  padding: 1rem;
  border-radius: 6px;
  margin-bottom: 1.5rem;
}

.persons-list {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
.person-card {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 1rem;
}
.person-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #334155;
  padding-bottom: 0.75rem;
  margin-bottom: 1rem;
}
.person-header h3 {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.25rem;
}
.role-badge {
  font-size: 0.75rem;
  background: #2563eb;
  padding: 0.1rem 0.4rem;
  border-radius: 12px;
}
.virtual-badge {
  font-size: 0.75rem;
  background: #9333ea;
  padding: 0.1rem 0.4rem;
  border-radius: 12px;
}
.person-id {
  font-size: 0.8rem;
  color: #64748b;
  margin-top: 0.25rem;
}

.no-stamps {
  color: #94a3b8;
  font-style: italic;
  font-size: 0.9rem;
}

.stamp-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
}
.stamp-item {
  position: relative;
  background: #fff;
  border-radius: 6px;
  padding: 0.5rem;
  width: 120px;
  text-align: center;
}
.img-wrapper {
  background: #f8fafc;
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.img-wrapper img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  mix-blend-mode: multiply;
}
.stamp-info {
  margin-top: 0.5rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #1e293b;
}
.stamp-cat {
  font-size: 0.8rem;
  font-weight: 500;
}
.delete-icon {
  background: #ef4444;
  color: white;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  font-size: 0.7rem;
  line-height: 1;
}
.delete-icon:hover {
  background: #dc2626;
}

.template-management {
  margin-top: 2rem;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 12px;
  padding: 1rem;
}

.template-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  margin-bottom: 1rem;
}

.template-header h2,
.template-card h3 {
  margin: 0;
}

.template-header p,
.template-card p {
  margin: 0.35rem 0 0;
  color: #94a3b8;
}

.template-form {
  display: grid;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.template-form input,
.template-form textarea {
  width: 100%;
  padding: 0.75rem;
  border-radius: 4px;
  border: 1px solid #4b5563;
  background: #374151;
  color: white;
  box-sizing: border-box;
}

.template-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1rem;
}

.template-card {
  background: #111827;
  border: 1px solid #334155;
  border-radius: 10px;
  padding: 1rem;
}

.template-card-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 0.75rem;
}

.template-status {
  font-size: 0.75rem;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  background: #475569;
}

.template-status.active {
  background: #0f766e;
}

.template-json {
  margin: 0;
  padding: 0.75rem;
  border-radius: 8px;
  overflow: auto;
  background: #020617;
  border: 1px solid #1e293b;
  color: #cbd5e1;
  font-size: 0.8rem;
}

.template-actions {
  margin-top: 0.75rem;
  display: flex;
  justify-content: flex-end;
}
</style>
