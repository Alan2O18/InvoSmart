<template>
  <div class="stamps-page">
    <header class="page-header">
      <div>
        <h1>印章管理中心</h1>
        <p>集中管理去背後的印章素材，可快速刪除與重新匯入。</p>
      </div>
      <div class="actions">
        <button type="button" @click="reload" :disabled="stampStore.loading">重新整理</button>
        <button type="button" class="primary" @click="openDialog">匯入新印章</button>
      </div>
    </header>

    <div v-if="stampStore.error" class="error-banner">{{ stampStore.error }}</div>

    <div v-if="stampStore.loading && stamps.length === 0" class="loading-wrap">載入中...</div>

    <div v-else-if="stamps.length === 0" class="empty-wrap">
      <h2>尚未建立印章</h2>
      <p>點擊「匯入新印章」上傳圖紙並自動切分。</p>
    </div>

    <section v-else class="stamp-grid">
      <article v-for="stamp in stamps" :key="stamp.id" class="stamp-card">
        <img :src="toAbsoluteUrl(stamp.image_url)" :alt="stamp.name" />

        <div class="stamp-meta">
          <h3>{{ stamp.name }}</h3>
          <p class="category">{{ stamp.category }}</p>
          <p v-if="stamp.group_name" class="group">群組：{{ stamp.group_name }}</p>
          <p class="time">{{ formatDate(stamp.created_at) }}</p>
        </div>

        <button type="button" class="delete-btn" @click="removeStamp(stamp)">刪除</button>
      </article>
    </section>

    <StampAssignDialog v-model="showAssignDialog" @registered="onRegistered" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import StampAssignDialog from '../components/StampAssignDialog.vue'
import api from '../services/api'
import { useStampStore } from '../store/stamp'

const stampStore = useStampStore()
const showAssignDialog = ref(false)

const stamps = computed(() => stampStore.stamps)

const reload = async () => {
  try {
    await stampStore.fetchStamps()
  } catch (e) {
    console.error('Failed to fetch stamps', e)
  }
}

const openDialog = () => {
  showAssignDialog.value = true
}

const onRegistered = () => {
  reload()
}

const removeStamp = async (stamp) => {
  if (!confirm(`確定刪除印章「${stamp.name}」嗎？`)) return
  try {
    await stampStore.deleteStamp(stamp.id)
  } catch (e) {
    alert(`刪除失敗：${stampStore.error || e}`)
  }
}

const toAbsoluteUrl = (url) => api.toAbsoluteUrl(url)

const formatDate = (epoch) => {
  if (!epoch) return '-'
  return new Date(epoch * 1000).toLocaleString()
}

onMounted(() => {
  reload()
})
</script>

<style scoped>
.stamps-page {
  padding: 1.5rem;
  color: #e5e7eb;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1.1rem;
}

.page-header h1 {
  font-size: 1.6rem;
  margin-bottom: 0.25rem;
}

.page-header p {
  color: #9ca3af;
}

.actions {
  display: flex;
  gap: 0.6rem;
  align-items: center;
}

.primary {
  background: #059669;
  color: #fff;
  border: none;
}

.error-banner {
  margin-bottom: 0.8rem;
  padding: 0.55rem;
  border: 1px solid #ef4444;
  border-radius: 6px;
  color: #fecaca;
  background: rgba(127, 29, 29, 0.35);
}

.loading-wrap,
.empty-wrap {
  border: 1px dashed #4b5563;
  border-radius: 8px;
  padding: 1.4rem;
  text-align: center;
  color: #9ca3af;
}

.empty-wrap h2 {
  color: #f8fafc;
  margin-bottom: 0.35rem;
}

.stamp-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.8rem;
}

.stamp-card {
  background: #111827;
  border: 1px solid #334155;
  border-radius: 10px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.stamp-card img {
  width: 100%;
  height: 180px;
  object-fit: contain;
  background: linear-gradient(45deg, #f8fafc 25%, #e5e7eb 25%, #e5e7eb 50%, #f8fafc 50%, #f8fafc 75%, #e5e7eb 75%);
  background-size: 18px 18px;
}

.stamp-meta {
  padding: 0.65rem;
  display: grid;
  gap: 0.25rem;
  flex: 1;
}

.stamp-meta h3 {
  font-size: 1rem;
  color: #f9fafb;
}

.category {
  color: #7dd3fc;
}

.group {
  color: #a5b4fc;
  font-size: 0.85rem;
}

.time {
  font-size: 0.78rem;
  color: #9ca3af;
}

.delete-btn {
  border: none;
  border-top: 1px solid #374151;
  background: #1f2937;
  color: #fca5a5;
  border-radius: 0;
}

.delete-btn:hover {
  background: #7f1d1d;
  border-color: #7f1d1d;
}

@media (max-width: 768px) {
  .stamps-page {
    padding: 1rem;
  }

  .stamp-grid {
    grid-template-columns: 1fr;
  }
}
</style>
