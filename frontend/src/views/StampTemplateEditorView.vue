<template>
  <div class="stamp-template-editor-page">
    <header class="page-header">
      <div class="header-content">
        <button class="back-btn" @click="router.push('/management')">← 返回管理中心</button>
        <div class="title-group">
          <h1>{{ isEditing ? '編輯蓋章模板' : '新增蓋章模板' }}</h1>
          <p>可視化設定各角色在特定版型上的預設蓋章座標</p>
        </div>
      </div>
      <div class="actions">
        <button @click="router.push('/management')" class="secondary">取消</button>
        <button @click="saveTemplate" :disabled="loading" class="primary">保存模板</button>
      </div>
    </header>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <div v-if="loading && isEditing" class="loading-wrap">載入中...</div>

    <div v-else class="config-layout">
      <!-- 畫布預覽區 -->
      <div class="canvas-section">
        <h2>位置預覽</h2>
        <div class="canvas-wrapper">
          <canvas
            ref="canvas"
            :width="canvasWidth"
            :height="canvasHeight"
            @click="onCanvasClick"
            @mousemove="onCanvasMouseMove"
            class="canvas-preview"
          ></canvas>
          <div v-if="selectedRole" class="zone-info">
            選中角色: <strong>{{ getRoleLabel(selectedRole) }}</strong>
          </div>
        </div>
      </div>

      <!-- 設定面板 -->
      <div class="config-section">
        <div class="form-panel">
          <h2>模板基本資料</h2>
          <div class="form-group">
            <label>模板名稱 *</label>
            <input v-model="templateName" type="text" placeholder="例如：2026 發票標準版" required />
          </div>
          <div class="form-group">
            <label>描述</label>
            <input v-model="templateDesc" type="text" placeholder="此版型的適用情境" />
          </div>
          <div class="form-group checkbox">
            <label>
              <input v-model="templateActive" type="checkbox" /> 啟用此模板
            </label>
          </div>
        </div>

        <div class="zone-panel">
          <h2>配置角色位置</h2>
          <div class="role-grid">
            <button
              v-for="role in availableRoles"
              :key="role.value"
              class="role-btn"
              :class="{ 
                active: selectedRole === role.value,
                configured: !!positions[role.value] 
              }"
              @click="selectRole(role.value)"
            >
              <span class="indicator"></span>
              {{ role.label }}
            </button>
          </div>

          <div v-if="selectedRole" class="edit-panel">
            <h3>{{ getRoleLabel(selectedRole) }} 位置設定</h3>
            
            <div class="coords-form" v-if="positions[selectedRole]">
              <div class="form-group">
                <label>X</label>
                <input v-model.number="positions[selectedRole].x" type="number" @input="drawCanvas" />
              </div>
              <div class="form-group">
                <label>Y</label>
                <input v-model.number="positions[selectedRole].y" type="number" @input="drawCanvas" />
              </div>
              <div class="form-group">
                <label>寬 (W)</label>
                <input v-model.number="positions[selectedRole].w" type="number" @input="drawCanvas" />
              </div>
              <div class="form-group">
                <label>高 (H)</label>
                <input v-model.number="positions[selectedRole].h" type="number" @input="drawCanvas" />
              </div>
            </div>
            
            <div class="coords-actions">
              <button v-if="!positions[selectedRole]" @click="initRolePosition(selectedRole)" class="primary full-width">新增此角色設定</button>
              <button v-else @click="removeRolePosition(selectedRole)" class="danger full-width">移除此角色</button>
            </div>
          </div>
          <div v-else class="empty-edit-panel">
            <p>請從上方選擇一個角色來設定座標</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import api from '../services/api'

const router = useRouter()
const route = useRoute()

const templateId = computed(() => route.params.id)
const isEditing = computed(() => !!templateId.value)

// 模板基本資料
const templateName = ref('')
const templateDesc = ref('')
const templateActive = ref(true)
const positions = ref({})

// 預設可配置角色
const availableRoles = [
  { value: 'handler', label: '經手人' },
  { value: 'activity_general_affairs', label: '活動總務' },
  { value: 'general_affairs_head', label: '總務組長' },
  { value: 'president', label: '社長' },
  { value: 'advisor', label: '指導老師' },
  { value: 'club_seal', label: '社團關防' },
  { value: 'fin_original', label: '與正本相符(騎縫)' },
  { value: 'fin_audited', label: '已稽核(騎縫)' },
]

// Canvas 設置 (以 A4 為基礎)
const canvas = ref(null)
const canvasWidth = 421 // A4寬 × 0.707
const canvasHeight = 596 // A4高 × 0.707
const A4_W = 595
const A4_H = 842

const selectedRole = ref(null)
const loading = ref(false)
const error = ref('')

const getRoleLabel = (val) => availableRoles.find(r => r.value === val)?.label || val

const loadTemplate = async () => {
  if (!isEditing.value) return
  loading.value = true
  try {
    const res = await api.getStampTemplate(templateId.value)
    templateName.value = res.data.name
    templateDesc.value = res.data.description || ''
    templateActive.value = res.data.active
    positions.value = res.data.positions || {}
    
    // Load images for existing roles
    for (const role of Object.keys(positions.value)) {
      loadStampForRole(role)
    }
  } catch (err) {
    error.value = '載入模板失敗：' + (err.response?.data?.detail || err.message)
  } finally {
    loading.value = false
    drawCanvas()
  }
}

// Cache for loaded HTMLImageElements
const stampImages = {}

const loadStampForRole = async (role) => {
  if (stampImages[role]) return // Already loaded
  try {
    const res = await api.listStampsByRole(role)
    if (res.data && res.data.length > 0) {
      const stamp = res.data[0]
      if (stamp.image_url) {
        const img = new Image()
        img.src = api.defaults?.baseURL ? api.defaults.baseURL + stamp.image_url : stamp.image_url
        // Workaround for base URL if axios instance uses baseURL but image.src doesn't know it
        if (img.src.startsWith('/') && !img.src.startsWith('//')) {
             img.src = 'http://localhost:8000' + img.src
        }
        img.onload = () => {
          stampImages[role] = img
          drawCanvas()
        }
      }
    }
  } catch (err) {
    console.warn(`Failed to load stamp image for role ${role}`, err)
  }
}

const selectRole = (roleVal) => {
  selectedRole.value = roleVal
  drawCanvas()
}

const initRolePosition = (roleVal) => {
  // 給一個預設的中間偏下位置
  positions.value[roleVal] = { x: 300, y: 500, w: 50, h: 50 }
  loadStampForRole(roleVal)
  drawCanvas()
}

const removeRolePosition = (roleVal) => {
  delete positions.value[roleVal]
  drawCanvas()
}

const drawCanvas = () => {
  if (!canvas.value) return
  const ctx = canvas.value.getContext('2d')
  
  // 背景與邊界
  ctx.fillStyle = '#111827'
  ctx.fillRect(0, 0, canvasWidth, canvasHeight)
  ctx.strokeStyle = '#4b5563'
  ctx.lineWidth = 2
  ctx.strokeRect(0, 0, canvasWidth, canvasHeight)

  const scaleX = canvasWidth / A4_W
  const scaleY = canvasHeight / A4_H

  // 畫出所有已配置的角色
  Object.entries(positions.value).forEach(([role, rect]) => {
    if (!rect) return
    const x = rect.x * scaleX
    const y = rect.y * scaleY
    const w = rect.w * scaleX
    const h = rect.h * scaleY

    const isSelected = selectedRole.value === role
    const img = stampImages[role]

    if (img) {
      ctx.globalAlpha = isSelected ? 1.0 : 0.7
      ctx.drawImage(img, x, y, w, h)
      ctx.globalAlpha = 1.0

      if (isSelected) {
        ctx.strokeStyle = '#10b981'
        ctx.lineWidth = 2
        ctx.strokeRect(x, y, w, h)
      }
      
      // Draw text with background
      ctx.font = '10px sans-serif'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      const text = getRoleLabel(role).substring(0, 4)
      const textWidth = ctx.measureText(text).width + 8
      
      ctx.fillStyle = 'rgba(0, 0, 0, 0.6)'
      ctx.fillRect(x + w/2 - textWidth/2, y + h/2 - 10, textWidth, 20)
      
      ctx.fillStyle = '#e5e7eb'
      ctx.fillText(text, x + w / 2, y + h / 2)
      
    } else {
      // 填滿
      ctx.fillStyle = isSelected ? 'rgba(16, 185, 129, 0.4)' : 'rgba(59, 130, 246, 0.3)'
      ctx.fillRect(x, y, w, h)

      // 外框
      ctx.strokeStyle = isSelected ? '#10b981' : '#3b82f6'
      ctx.lineWidth = isSelected ? 3 : 1
      ctx.strokeRect(x, y, w, h)

      // 文字
      ctx.fillStyle = '#e5e7eb'
      ctx.font = '10px sans-serif'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(getRoleLabel(role).substring(0, 4), x + w / 2, y + h / 2)
    }
  })
}

const onCanvasClick = (e) => {
  const rect = canvas.value.getBoundingClientRect()
  const clickX = ((e.clientX - rect.left) / canvasWidth) * A4_W
  const clickY = ((e.clientY - rect.top) / canvasHeight) * A4_H

  // 尋找被點擊的方塊 (後畫的在上方)
  let found = null
  for (const [role, r] of Object.entries(positions.value)) {
    if (!r) continue
    if (clickX >= r.x && clickX <= r.x + r.w && clickY >= r.y && clickY <= r.y + r.h) {
      found = role
    }
  }

  if (found) {
    selectRole(found)
  }
}

const onCanvasMouseMove = (e) => {
  if (!canvas.value) return
  const rect = canvas.value.getBoundingClientRect()
  const clickX = ((e.clientX - rect.left) / canvasWidth) * A4_W
  const clickY = ((e.clientY - rect.top) / canvasHeight) * A4_H

  let hovering = false
  for (const r of Object.values(positions.value)) {
    if (!r) continue
    if (clickX >= r.x && clickX <= r.x + r.w && clickY >= r.y && clickY <= r.y + r.h) {
      hovering = true
      break
    }
  }
  canvas.value.style.cursor = hovering ? 'pointer' : 'default'
}

const saveTemplate = async () => {
  if (!templateName.value.trim()) {
    error.value = '請輸入模板名稱'
    return
  }
  
  loading.value = true
  error.value = ''
  
  const payload = {
    name: templateName.value,
    description: templateDesc.value,
    active: templateActive.value,
    positions: positions.value
  }

  try {
    if (isEditing.value) {
      await api.updateStampTemplate(templateId.value, payload)
    } else {
      await api.createStampTemplate(payload)
    }
    router.push('/management')
  } catch (err) {
    error.value = '保存失敗：' + (err.response?.data?.detail || err.message)
    loading.value = false
  }
}

onMounted(() => {
  if (isEditing.value) {
    loadTemplate()
  } else {
    setTimeout(drawCanvas, 100)
  }
})
</script>

<style scoped>
.stamp-template-editor-page {
  padding: 1.5rem;
  color: #e5e7eb;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
  background: #1f2937;
  padding: 1rem 1.5rem;
  border-radius: 8px;
  border: 1px solid #374151;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.back-btn {
  background: transparent;
  color: #9ca3af;
  border: none;
  cursor: pointer;
  font-size: 1rem;
}
.back-btn:hover {
  color: #e5e7eb;
}

.title-group h1 { margin: 0 0 0.2rem 0; font-size: 1.5rem; }
.title-group p { margin: 0; color: #9ca3af; font-size: 0.9rem; }

.actions { display: flex; gap: 0.5rem; }
.actions button { padding: 0.5rem 1.5rem; border-radius: 6px; cursor: pointer; border: none; font-weight: 500; }
.actions button.primary { background: #10b981; color: #fff; }
.actions button.primary:hover:not(:disabled) { background: #059669; }
.actions button.secondary { background: #374151; color: #e5e7eb; border: 1px solid #4b5563; }
.actions button.secondary:hover { background: #4b5563; }
.actions button:disabled { opacity: 0.5; cursor: not-allowed; }

.error-banner {
  background: #7f1d1d; color: #fca5a5; padding: 1rem; border-radius: 6px; margin-bottom: 1.5rem;
}

.config-layout {
  display: grid;
  grid-template-columns: 450px 1fr;
  gap: 2rem;
}

@media (max-width: 1024px) {
  .config-layout { grid-template-columns: 1fr; }
}

.canvas-section h2, .form-panel h2, .zone-panel h2 {
  font-size: 1.1rem;
  margin-bottom: 1rem;
  color: #d1d5db;
}

.canvas-wrapper {
  background: #111827;
  border: 1px solid #374151;
  border-radius: 8px;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.canvas-preview {
  border: 1px solid #4b5563;
  border-radius: 4px;
}

.zone-info {
  margin-top: 1rem;
  padding: 0.5rem 1rem;
  background: #1f2937;
  border-radius: 6px;
  border: 1px solid #374151;
  color: #10b981;
}

.config-section {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.form-panel, .zone-panel {
  background: #1f2937;
  border: 1px solid #374151;
  border-radius: 8px;
  padding: 1.5rem;
}

.form-group {
  margin-bottom: 1rem;
}
.form-group label {
  display: block; margin-bottom: 0.4rem; color: #9ca3af; font-size: 0.9rem;
}
.form-group input[type="text"], .form-group input[type="number"] {
  width: 100%; padding: 0.6rem; background: #111827; border: 1px solid #4b5563; color: #e5e7eb; border-radius: 4px;
}
.form-group.checkbox {
  display: flex; align-items: center; gap: 0.5rem;
}
.form-group.checkbox label { margin: 0; display: flex; align-items: center; gap: 0.5rem; cursor: pointer; color: #e5e7eb;}

.role-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 0.8rem;
  margin-bottom: 1.5rem;
}

.role-btn {
  background: #111827;
  border: 1px solid #374151;
  color: #d1d5db;
  padding: 0.8rem;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: all 0.2s;
}
.role-btn:hover { background: #374151; }
.role-btn.active { border-color: #3b82f6; background: rgba(59, 130, 246, 0.1); }
.role-btn.configured .indicator { background: #10b981; }
.indicator { width: 8px; height: 8px; border-radius: 50%; background: #4b5563; }

.edit-panel {
  background: #111827;
  padding: 1.5rem;
  border-radius: 6px;
  border: 1px dashed #4b5563;
}
.edit-panel h3 { margin: 0 0 1rem 0; color: #3b82f6; }

.empty-edit-panel {
  padding: 3rem; text-align: center; color: #6b7280; background: #111827; border-radius: 6px; border: 1px dashed #374151;
}

.coords-form {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.full-width { width: 100%; padding: 0.8rem; border-radius: 4px; border: none; cursor: pointer; font-weight: bold; }
.full-width.primary { background: #3b82f6; color: white; }
.full-width.primary:hover { background: #2563eb; }
.full-width.danger { background: #ef4444; color: white; }
.full-width.danger:hover { background: #dc2626; }
</style>
