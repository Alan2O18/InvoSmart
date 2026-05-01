<template>
  <div class="voucher-stamp-preview">
    <div class="header">
      <h1>憑證蓋章預覽</h1>
      <p class="subtitle">確認所有印章的蓋印位置無誤後，點擊「產出 PDF」正式生成</p>
    </div>

    <div class="container">
      <!-- 控制面板 -->
      <section class="control-panel">
        <div class="info-group">
          <h3>蓋章配置</h3>
          <div class="config-display">
            <div v-if="stampConfig" class="config-item">
              <p><strong>蓋章位置設定版本:</strong> {{ stampConfig.version }}</p>
              <p><strong>配置角色:</strong> {{ Object.keys(stampConfig.stampZones || {}).length }} 個</p>
            </div>
            <div v-else class="config-item warning">
              <p>⚠️ 尚未載入蓋章配置</p>
            </div>
          </div>
        </div>

        <div class="action-group">
          <button @click="loadConfig" class="secondary">重新加載配置</button>
          <button @click="generatePDF" class="primary" :disabled="isGenerating">
            {{ isGenerating ? '產出中...' : '產出 PDF' }}
          </button>
        </div>
      </section>

      <!-- A4 範本預覽 -->
      <section class="preview-section">
        <div class="preview-header">
          <h3>A4 範本預覽 (210mm × 297mm)</h3>
          <div class="zoom-controls">
            <button @click="zoomOut" :disabled="zoom <= 50">−</button>
            <span>{{ zoom }}%</span>
            <button @click="zoomIn" :disabled="zoom >= 200">+</button>
          </div>
        </div>

        <div class="preview-canvas" :style="{ transform: `scale(${zoom / 100})` }">
          <!-- A4 背景 -->
          <div class="a4-page">
            <!-- 示意圖 -->
            <div class="content-area">
              <div class="content-placeholder">
                <p>憑證內容區域</p>
                <p style="font-size: 0.75rem; color: #999;">
                  (實際內容由編輯器提供)
                </p>
              </div>
            </div>

            <!-- 蓋章預覽 -->
            <div class="stamp-overlay">
              <div v-for="(zone, role) in stampZones" :key="role" 
                   class="stamp-zone"
                   :style="getRectStyle(zone.rect)"
                   :title="`${zone.label} (${role})`">
                <div class="stamp-preview-box">
                  <div class="stamp-placeholder">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="currentColor" opacity="0.3">
                      <circle cx="12" cy="12" r="10"></circle>
                      <text x="12" y="14" text-anchor="middle" font-size="8" fill="white">章</text>
                    </svg>
                  </div>
                  <span class="zone-label">{{ zone.label }}</span>
                </div>
              </div>
            </div>

            <!-- 簽名區 -->
            <div class="signature-area">
              <div class="signature-line"></div>
              <p class="signature-text">簽名欄</p>
            </div>
          </div>
        </div>
      </section>

      <!-- 蓋章詳情 -->
      <section class="stamp-details">
        <h3>蓋章詳情</h3>
        <div class="details-grid">
          <div v-for="(zone, role) in stampZones" :key="role" class="detail-card">
            <div class="detail-header">
              <h4>{{ zone.label }}</h4>
              <span class="role-tag">{{ role }}</span>
            </div>
            <div class="detail-body">
              <p><strong>位置:</strong> X: {{ zone.rect[0].toFixed(0) }}, Y: {{ zone.rect[1].toFixed(0) }}</p>
              <p><strong>尺寸:</strong> {{ zone.rect[2].toFixed(0) }} × {{ zone.rect[3].toFixed(0) }} pt</p>
              <p><strong>旋轉:</strong> ±10° (隨機)</p>
              <p><strong>透明度:</strong> 保留 (PNG alpha 通道)</p>
            </div>
          </div>
        </div>
      </section>

      <!-- 狀態提示 -->
      <div v-if="successMsg" class="success-msg">✓ {{ successMsg }}</div>
      <div v-if="errorMsg" class="error-msg">✗ {{ errorMsg }}</div>
      <div v-if="loadingMsg" class="loading-msg">⟳ {{ loadingMsg }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const api = axios.create({ baseURL: API_BASE })

const projectId = ref(null)
const stampConfig = ref(null)
const zoom = ref(100)
const isGenerating = ref(false)
const successMsg = ref('')
const errorMsg = ref('')
const loadingMsg = ref('')

// 預設蓋章區域 (STAMP_ZONES)
const stampZones = computed(() => {
  return {
    handler: { label: '經手人章', rect: [430, 395, 50, 50] },
    activity_general_affairs: { label: '活動總務章', rect: [485, 395, 50, 50] },
    general_affairs_head: { label: '總務組長章', rect: [430, 450, 50, 50] },
    president: { label: '社長章', rect: [485, 450, 50, 50] },
    advisor: { label: '指導老師章', rect: [430, 505, 50, 50] },
    club_seal: { label: '社團關防', rect: [485, 505, 50, 50] },
  }
})

// 取得矩形樣式
const getRectStyle = (rect) => {
  return {
    left: `${rect[0]}px`,
    top: `${rect[1]}px`,
    width: `${rect[2]}px`,
    height: `${rect[3]}px`,
  }
}

// 加載配置
const loadConfig = async () => {
  try {
    loadingMsg.value = '加載配置中...'
    const response = await api.get('/config/template-layout')
    stampConfig.value = response.data
    loadingMsg.value = ''
    successMsg.value = '配置加載成功'
    setTimeout(() => { successMsg.value = '' }, 2000)
  } catch (error) {
    errorMsg.value = `加載失敗: ${error.message}`
    loadingMsg.value = ''
  }
}

// 縮放控制
const zoomIn = () => {
  if (zoom.value < 200) zoom.value += 10
}

const zoomOut = () => {
  if (zoom.value > 50) zoom.value -= 10
}

// 產出 PDF
const generatePDF = async () => {
  if (!projectId.value) {
    errorMsg.value = '未指定憑證 ID'
    return
  }

  try {
    isGenerating.value = true
    loadingMsg.value = '正在產出 PDF...'
    
    // 模擬 API 呼叫
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    // 實際應該呼叫: POST /project/{id}/voucher/export
    const response = await api.post(`/project/${projectId.value}/voucher/export`, {
      format: 'pdf',
      include_stamps: true,
    })
    
    // 下載 PDF
    const blob = new Blob([response.data], { type: 'application/pdf' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `voucher_${projectId.value}.pdf`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
    
    successMsg.value = 'PDF 已產出並下載'
    setTimeout(() => { successMsg.value = '' }, 3000)
  } catch (error) {
    errorMsg.value = `產出失敗: ${error.message || error}`
  } finally {
    isGenerating.value = false
    loadingMsg.value = ''
  }
}

// 組件掛載
onMounted(() => {
  // 從路由參數取得 projectId
  const route = window.location.pathname
  const match = route.match(/\/project\/(\d+)/)
  if (match) {
    projectId.value = match[1]
  }
  
  loadConfig()
})
</script>

<style scoped>
.voucher-stamp-preview {
  min-height: 100vh;
  background: #0f1419;
  padding: 2rem;
}

.header {
  margin-bottom: 2rem;
}

.header h1 {
  font-size: 1.75rem;
  color: #e5e7eb;
  margin: 0;
}

.subtitle {
  color: #9ca3af;
  margin: 0.5rem 0 0 0;
}

.container {
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

/* 控制面板 */
.control-panel {
  background: #1f2937;
  border-radius: 8px;
  padding: 1.5rem;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2rem;
}

.info-group h3,
.action-group h3 {
  color: #e5e7eb;
  margin: 0 0 1rem 0;
}

.config-display {
  background: #111827;
  border-radius: 6px;
  padding: 1rem;
  border-left: 3px solid #059669;
}

.config-item {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.config-item p {
  margin: 0;
  color: #d1d5db;
  font-size: 0.95rem;
}

.config-item.warning {
  border-left-color: #f59e0b;
}

.config-item.warning p {
  color: #fbbf24;
}

.action-group {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 1rem;
}

.primary, .secondary {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}

.primary {
  background: #059669;
  color: white;
}

.primary:hover:not(:disabled) {
  background: #047857;
}

.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.secondary {
  background: transparent;
  border: 1px solid #4b5563;
  color: #d1d5db;
}

.secondary:hover {
  border-color: #6b7280;
  color: #e5e7eb;
}

/* 預覽區 */
.preview-section {
  background: #1f2937;
  border-radius: 8px;
  padding: 1.5rem;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.preview-header h3 {
  color: #e5e7eb;
  margin: 0;
}

.zoom-controls {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.zoom-controls button {
  width: 32px;
  height: 32px;
  padding: 0;
  background: #374151;
  border: 1px solid #4b5563;
  border-radius: 4px;
  color: #e5e7eb;
  cursor: pointer;
  font-weight: bold;
}

.zoom-controls button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.zoom-controls span {
  min-width: 50px;
  text-align: center;
  color: #9ca3af;
}

.preview-canvas {
  display: flex;
  justify-content: center;
  align-items: flex-start;
  background: #111827;
  padding: 2rem;
  border-radius: 6px;
  overflow: auto;
  transform-origin: top center;
  transition: transform 0.3s;
}

.a4-page {
  width: 210mm;
  height: 297mm;
  background: white;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.content-area {
  flex: 1;
  padding: 20px;
  border-bottom: 1px dashed #ddd;
  display: flex;
  align-items: center;
  justify-content: center;
}

.content-placeholder {
  text-align: center;
  color: #9ca3af;
}

.content-placeholder p {
  margin: 0.5rem 0;
  font-size: 0.9rem;
}

.stamp-overlay {
  position: absolute;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.stamp-zone {
  position: absolute;
  border: 2px dashed #059669;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(5, 150, 105, 0.05);
}

.stamp-preview-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  width: 100%;
  height: 100%;
  justify-content: center;
}

.stamp-placeholder {
  color: #059669;
  opacity: 0.5;
  display: flex;
  align-items: center;
  justify-content: center;
}

.zone-label {
  font-size: 0.6rem;
  color: #059669;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
  padding: 0 2px;
}

.signature-area {
  padding: 20px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.signature-line {
  width: 100px;
  height: 1px;
  background: #333;
}

.signature-text {
  font-size: 0.75rem;
  color: #999;
  margin: 0;
}

/* 蓋章詳情 */
.stamp-details {
  background: #1f2937;
  border-radius: 8px;
  padding: 1.5rem;
}

.stamp-details h3 {
  color: #e5e7eb;
  margin: 0 0 1rem 0;
}

.details-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.detail-card {
  background: #111827;
  border-radius: 6px;
  padding: 1rem;
  border-left: 3px solid #059669;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.75rem;
}

.detail-header h4 {
  color: #e5e7eb;
  margin: 0;
  font-size: 0.95rem;
}

.role-tag {
  background: #059669;
  color: white;
  padding: 0.25rem 0.5rem;
  border-radius: 3px;
  font-size: 0.7rem;
  font-weight: 600;
}

.detail-body p {
  margin: 0.25rem 0;
  color: #9ca3af;
  font-size: 0.85rem;
}

/* 提示訊息 */
.success-msg, .error-msg, .loading-msg {
  padding: 0.75rem;
  border-radius: 6px;
  margin-top: 1rem;
}

.success-msg {
  background: rgba(6, 78, 59, 0.35);
  border: 1px solid #10b981;
  color: #a7f3d0;
}

.error-msg {
  background: rgba(127, 29, 29, 0.35);
  border: 1px solid #ef4444;
  color: #fecaca;
}

.loading-msg {
  background: rgba(37, 99, 235, 0.35);
  border: 1px solid #3b82f6;
  color: #93c5fd;
}
</style>
