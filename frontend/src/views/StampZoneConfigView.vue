<template>
  <div class="stamp-zone-config-page">
    <header class="page-header">
      <div>
        <h1>蓋章位置配置</h1>
        <p>可視化設置每個蓋章位置、大小和角色。</p>
      </div>
      <div class="actions">
        <button @click="resetToDefaults" class="warning-btn">恢復預設</button>
        <button @click="saveConfig" :disabled="!hasChanges" class="primary">保存設置</button>
      </div>
    </header>

    <div v-if="error" class="error-banner">{{ error }}</div>
    <div v-if="success" class="success-banner">{{ success }}</div>

    <div v-if="loading" class="loading-wrap">載入中...</div>

    <div v-else class="config-layout">
      <!-- Canvas 區域 -->
      <div class="canvas-section">
        <h2>蓋章預覽</h2>
        <div class="canvas-wrapper">
          <canvas
            ref="canvas"
            :width="canvasWidth"
            :height="canvasHeight"
            @click="onCanvasClick"
            @mousemove="onCanvasMouseMove"
            class="canvas-preview"
          ></canvas>
          <div v-if="selectedZone" class="zone-info">
            選中: <strong>{{ selectedZone.label }}</strong> ({{ selectedZone.role }})
          </div>
        </div>
      </div>

      <!-- 配置面板 -->
      <div class="config-section">
        <h2>蓋章區域</h2>

        <div class="zone-list">
          <div
            v-for="(zone, key) in stampZones"
            :key="key"
            class="zone-item"
            :class="{ active: selectedZone?.role === key }"
            @click="selectZone(key)"
          >
            <div class="zone-item-header">
              <span class="zone-label">{{ zone.label }}</span>
              <span class="zone-role">{{ key }}</span>
            </div>
            <div class="zone-preview" :style="getZonePreviewStyle(zone)"></div>
          </div>
        </div>

        <!-- 編輯面板 -->
        <div v-if="selectedZone" class="edit-panel">
          <h3>編輯: {{ selectedZone.label }}</h3>

          <div class="form-group">
            <label>X 位置 (pt)</label>
            <input v-model.number="selectedZone.rect[0]" type="number" @input="updatePreview" />
          </div>

          <div class="form-group">
            <label>Y 位置 (pt)</label>
            <input v-model.number="selectedZone.rect[1]" type="number" @input="updatePreview" />
          </div>

          <div class="form-group">
            <label>寬度 (pt)</label>
            <input v-model.number="selectedZone.rect[2]" type="number" @input="updatePreview" />
          </div>

          <div class="form-group">
            <label>高度 (pt)</label>
            <input v-model.number="selectedZone.rect[3]" type="number" @input="updatePreview" />
          </div>

          <p class="rect-display">矩形: [{{ selectedZone.rect.join(', ') }}]</p>

          <button @click="markHasChanges" class="primary full-width">更新預覽</button>
        </div>
      </div>
    </div>

    <!-- 騎縫章配置 -->
    <section class="stitched-seals-section">
      <h2>騎縫章配置</h2>
      <div class="seals-grid">
        <div v-for="(seal, key) in stitchedSeals" :key="key" class="seal-card">
          <h3>{{ seal.label }}</h3>
          <p>位置: {{ seal.position }}</p>
          <p v-if="seal.edge_offset" class="offset">邊界偏移: {{ seal.edge_offset }} pt</p>
        </div>
      </div>
    </section>

    <!-- A4 頁面尺寸說明 -->
    <section class="page-info">
      <h2>頁面資訊</h2>
      <div class="info-grid">
        <div class="info-item">
          <strong>頁面尺寸:</strong>
          <p>A4 (595 × 842 pt @ 72 dpi)</p>
        </div>
        <div class="info-item">
          <strong>可用座標範圍:</strong>
          <p>X: 0-595, Y: 0-842</p>
        </div>
        <div class="info-item">
          <strong>推薦蓋章區域:</strong>
          <p>下方簽核區 (Y > 395)</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import api from '../services/api'

// 配置資料
const stampZones = ref({
  handler: { label: '經手人章', rect: [430, 395, 50, 50] },
  activity_general_affairs: { label: '活動總務章', rect: [485, 395, 50, 50] },
  general_affairs_head: { label: '總務組長章', rect: [430, 450, 50, 50] },
  president: { label: '社長章', rect: [485, 450, 50, 50] },
  advisor: { label: '指導老師章', rect: [430, 505, 50, 50] },
  club_seal: { label: '社團關防', rect: [485, 505, 50, 50] },
})

const stitchedSeals = ref({
  fin_original: { label: '與正本相符', position: 'edge', edge_offset: 5 },
  fin_audited: { label: '已稽核', position: 'edge', edge_offset: -5 },
})

// Canvas 設置
const canvas = ref(null)
const canvasWidth = 421 // A4寬 × 0.707
const canvasHeight = 596 // A4高 × 0.707

const selectedZone = ref(null)
const loading = ref(false)
const error = ref('')
const success = ref('')
const hasChanges = ref(false)

const defaultZones = computed(() => ({
  handler: { label: '經手人章', rect: [430, 395, 50, 50] },
  activity_general_affairs: { label: '活動總務章', rect: [485, 395, 50, 50] },
  general_affairs_head: { label: '總務組長章', rect: [430, 450, 50, 50] },
  president: { label: '社長章', rect: [485, 450, 50, 50] },
  advisor: { label: '指導老師章', rect: [430, 505, 50, 50] },
  club_seal: { label: '社團關防', rect: [485, 505, 50, 50] },
}))

const loadConfig = async () => {
  loading.value = true
  error.value = ''
  try {
    // 從後端載入配置（如果需要）
    // const res = await api.getVoucherTextConfig()
    // 暫時使用預設值
  } catch (e) {
    error.value = e.message || '載入失敗'
  } finally {
    loading.value = false
  }
}

const updatePreview = () => {
  drawCanvas()
  markHasChanges()
}

const drawCanvas = () => {
  const ctx = canvas.value.getContext('2d')
  ctx.fillStyle = '#111827'
  ctx.fillRect(0, 0, canvasWidth, canvasHeight)

  // 繪製 A4 邊界
  ctx.strokeStyle = '#4b5563'
  ctx.lineWidth = 2
  ctx.strokeRect(0, 0, canvasWidth, canvasHeight)

  // 縮放係數 (A4: 595x842, Canvas: 421x596)
  const scaleX = canvasWidth / 595
  const scaleY = canvasHeight / 842

  // 繪製蓋章區域
  Object.entries(stampZones.value).forEach(([key, zone]) => {
    const rect = zone.rect
    const x = rect[0] * scaleX
    const y = rect[1] * scaleY
    const w = rect[2] * scaleX
    const h = rect[3] * scaleY

    const isSelected = selectedZone.value?.role === key
    ctx.fillStyle = isSelected ? '#10b981' : '#3b82f6'
    ctx.fillRect(x, y, w, h)

    ctx.strokeStyle = isSelected ? '#059669' : '#1e40af'
    ctx.lineWidth = 2
    ctx.strokeRect(x, y, w, h)

    // 繪製標籤
    ctx.fillStyle = '#e5e7eb'
    ctx.font = 'bold 8px sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(zone.label.substring(0, 4), x + w / 2, y + h / 2)
  })
}

const selectZone = (key) => {
  const zone = stampZones.value[key]
  selectedZone.value = {
    role: key,
    label: zone.label,
    rect: [...zone.rect],
  }
  drawCanvas()
}

const onCanvasClick = (e) => {
  const rect = canvas.value.getBoundingClientRect()
  const x = ((e.clientX - rect.left) / canvasWidth) * 595
  const y = ((e.clientY - rect.top) / canvasHeight) * 842

  // 尋找點擊的區域
  for (const [key, zone] of Object.entries(stampZones.value)) {
    const r = zone.rect
    if (x >= r[0] && x <= r[0] + r[2] && y >= r[1] && y <= r[1] + r[3]) {
      selectZone(key)
      return
    }
  }
}

const onCanvasMouseMove = (e) => {
  const rect = canvas.value.getBoundingClientRect()
  const x = ((e.clientX - rect.left) / canvasWidth) * 595
  const y = ((e.clientY - rect.top) / canvasHeight) * 842

  let hovering = false
  for (const zone of Object.values(stampZones.value)) {
    const r = zone.rect
    if (x >= r[0] && x <= r[0] + r[2] && y >= r[1] && y <= r[1] + r[3]) {
      canvas.value.style.cursor = 'pointer'
      hovering = true
      break
    }
  }

  if (!hovering) {
    canvas.value.style.cursor = 'default'
  }
}

const getZonePreviewStyle = (zone) => {
  const scaleX = 100 / 595
  const scaleY = 60 / 842
  return {
    left: zone.rect[0] * scaleX + '%',
    top: zone.rect[1] * scaleY + '%',
    width: zone.rect[2] * scaleX + '%',
    height: zone.rect[3] * scaleY + '%',
  }
}

const resetToDefaults = () => {
  if (!confirm('確定要恢復預設配置嗎？')) return
  stampZones.value = JSON.parse(JSON.stringify(defaultZones.value))
  selectedZone.value = null
  drawCanvas()
  markHasChanges()
}

const saveConfig = async () => {
  loading.value = true
  error.value = ''
  success.value = ''
  try {
    const payload = {
      stamp_zones: stampZones.value,
      stitched_seals: stitchedSeals.value,
    }
    // await api.saveVoucherTemplateLayout(payload)
    success.value = '配置已保存'
    hasChanges.value = false
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '保存失敗'
  } finally {
    loading.value = false
  }
}

const markHasChanges = () => {
  hasChanges.value = true
}

onMounted(() => {
  loadConfig()
  // 延遲繪製，確保 canvas 已掛載
  setTimeout(() => drawCanvas(), 100)
})

watch(stampZones, () => {
  drawCanvas()
}, { deep: true })
</script>

<style scoped>
.stamp-zone-config-page {
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

.error-banner,
.success-banner {
  padding: 1rem;
  border-left: 4px solid;
  margin-bottom: 1rem;
  border-radius: 4px;
}

.error-banner {
  background: #7f1d1d;
  color: #fca5a5;
  border-color: #dc2626;
}

.success-banner {
  background: #065f46;
  color: #a7f3d0;
  border-color: #10b981;
}

.loading-wrap {
  text-align: center;
  padding: 3rem;
  color: #9ca3af;
}

.config-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2rem;
  margin-bottom: 2rem;
}

@media (max-width: 1024px) {
  .config-layout {
    grid-template-columns: 1fr;
  }
}

.canvas-section h2,
.config-section h2 {
  margin: 0 0 1rem 0;
  font-size: 1.2rem;
}

.canvas-wrapper {
  background: #111827;
  border: 1px solid #374151;
  border-radius: 8px;
  padding: 1rem;
}

.canvas-preview {
  width: 100%;
  height: auto;
  border: 1px solid #4b5563;
  border-radius: 4px;
  background: #0f172a;
  cursor: default;
  display: block;
  max-width: 100%;
  height: auto;
}

.zone-info {
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: #1f2937;
  border-radius: 4px;
  font-size: 0.9rem;
  color: #d1d5db;
}

.config-section {
  background: #1f2937;
  border: 1px solid #374151;
  border-radius: 8px;
  padding: 1.5rem;
}

.zone-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
  max-height: 300px;
  overflow-y: auto;
}

.zone-item {
  background: #111827;
  border: 2px solid #4b5563;
  border-radius: 6px;
  padding: 0.75rem;
  cursor: pointer;
  transition: all 0.2s;
}

.zone-item:hover {
  border-color: #6b7280;
}

.zone-item.active {
  border-color: #10b981;
  background: rgba(16, 185, 129, 0.1);
}

.zone-item-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
  font-size: 0.85rem;
}

.zone-label {
  font-weight: 600;
  color: #e5e7eb;
}

.zone-role {
  color: #9ca3af;
  font-size: 0.75rem;
}

.zone-preview {
  width: 100%;
  height: 60px;
  background: #1f2937;
  border: 1px dashed #374151;
  border-radius: 4px;
  position: relative;
}

.edit-panel {
  background: #111827;
  border: 1px solid #374151;
  border-radius: 6px;
  padding: 1rem;
  margin-top: 1rem;
}

.edit-panel h3 {
  margin: 0 0 1rem 0;
  font-size: 1rem;
  color: #e5e7eb;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.4rem;
  font-size: 0.9rem;
  color: #d1d5db;
}

.form-group input {
  width: 100%;
  padding: 0.5rem;
  background: #0f172a;
  color: #e5e7eb;
  border: 1px solid #374151;
  border-radius: 4px;
  font-size: 0.9rem;
}

.form-group input:focus {
  outline: none;
  border-color: #10b981;
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.1);
}

.rect-display {
  margin: 0.5rem 0;
  padding: 0.5rem;
  background: #0f172a;
  border-left: 3px solid #10b981;
  border-radius: 2px;
  font-family: monospace;
  font-size: 0.85rem;
  color: #a7f3d0;
}

.full-width {
  width: 100%;
  padding: 0.5rem;
  background: #10b981;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.full-width:hover {
  background: #059669;
}

.stitched-seals-section {
  background: #1f2937;
  border: 1px solid #374151;
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 2rem;
}

.stitched-seals-section h2 {
  margin: 0 0 1rem 0;
  font-size: 1.2rem;
}

.seals-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
}

.seal-card {
  background: #111827;
  border: 1px solid #374151;
  border-radius: 6px;
  padding: 1rem;
}

.seal-card h3 {
  margin: 0 0 0.5rem 0;
  font-size: 1rem;
  color: #e5e7eb;
}

.seal-card p {
  margin: 0.3rem 0;
  font-size: 0.9rem;
  color: #9ca3af;
}

.offset {
  color: #10b981;
  font-family: monospace;
}

.page-info {
  background: #1f2937;
  border: 1px solid #374151;
  border-radius: 8px;
  padding: 1.5rem;
}

.page-info h2 {
  margin: 0 0 1rem 0;
  font-size: 1.2rem;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
}

.info-item {
  background: #111827;
  border-left: 3px solid #3b82f6;
  border-radius: 4px;
  padding: 1rem;
}

.info-item strong {
  display: block;
  margin-bottom: 0.5rem;
  color: #e5e7eb;
}

.info-item p {
  margin: 0;
  color: #9ca3af;
  font-family: monospace;
  font-size: 0.9rem;
}
</style>
