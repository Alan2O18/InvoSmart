<template>
  <div class="stamp-source-upload">
    <div class="header">
      <h1>印章圖片上傳與管理</h1>
      <p class="subtitle">上傳掃描圖或照片，框選個別印章並分配給人員</p>
    </div>

    <div class="container">
      <!-- 上傳區 -->
      <section class="upload-section">
        <div class="upload-box" @click="triggerFileInput" :class="{ dragging: isDragging }"
             @dragover.prevent="isDragging = true"
             @dragleave.prevent="isDragging = false"
             @drop.prevent="handleDrop">
          <div class="upload-content">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="17 8 12 3 7 8"></polyline>
              <line x1="12" y1="3" x2="12" y2="15"></line>
            </svg>
            <p>拖放檔案到這裡或點擊上傳</p>
            <span class="hint">支援 PNG, JPG, GIF (推薦 PNG)</span>
          </div>
          <input type="file" ref="fileInput" @change="handleFileSelect" accept="image/*" style="display: none">
        </div>

        <div v-if="uploadedImages.length" class="uploaded-images">
          <h3>已上傳的圖片 ({{ uploadedImages.length }})</h3>
          <div class="image-grid">
            <div v-for="(img, idx) in uploadedImages" :key="idx" class="image-card">
              <img :src="img.preview" @click="selectImage(idx)">
              <button @click.stop="removeImage(idx)" class="remove-btn">✕</button>
              <div v-if="selectedImageIndex === idx" class="selection-indicator">選中</div>
            </div>
          </div>
        </div>
      </section>

      <!-- 框選編輯區 -->
      <section v-if="selectedImage" class="editor-section">
        <div class="editor-container">
          <h3>框選印章</h3>
          <div class="canvas-wrapper">
            <img :src="selectedImage.preview" @mousedown="startSelection" @mousemove="updateSelection" @mouseup="endSelection" @mouseleave="endSelection" style="cursor: crosshair;">
            <canvas ref="selectionCanvas" class="selection-overlay" :width="canvasWidth" :height="canvasHeight"></canvas>
          </div>

          <div class="stamp-assignment">
            <h4>將選中的印章分配給人員</h4>
            <div class="form-group">
              <label>選擇人員</label>
              <select v-model="selectedPerson">
                <option value="">-- 選擇人員 --</option>
                <option v-for="person in persons" :key="person.id" :value="person.id">
                  {{ person.name }} ({{ person.role }})
                </option>
              </select>
            </div>

            <button v-if="selectedRect" @click="extractAndSave" class="primary full-width">
              保存此印章 ({{ stampCount }})
            </button>
          </div>
        </div>

        <div class="extracted-stamps">
          <h3>已提取的印章 ({{ extractedStamps.length }})</h3>
          <div class="stamp-preview-grid">
            <div v-for="(stamp, idx) in extractedStamps" :key="idx" class="stamp-preview">
              <img :src="stamp.preview">
              <div class="stamp-info">
                <p>{{ stamp.personName }}</p>
                <button @click="removeStamp(idx)" class="remove-small">刪除</button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 成功提示 -->
      <div v-if="successMsg" class="success-msg">{{ successMsg }}</div>
      <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const api = axios.create({ baseURL: API_BASE })

const fileInput = ref(null)
const isDragging = ref(false)
const uploadedImages = ref([])
const selectedImageIndex = ref(null)
const selectedPerson = ref('')
const persons = ref([])
const selectionCanvas = ref(null)
const canvasWidth = ref(0)
const canvasHeight = ref(0)
const isSelecting = ref(false)
const selectedRect = ref(null)
const extractedStamps = ref([])
const successMsg = ref('')
const errorMsg = ref('')
const stampCount = ref(0)

// Computed
const selectedImage = computed(() => uploadedImages.value[selectedImageIndex.value] || null)

// 加載人員列表
const loadPersons = async () => {
  try {
    const response = await api.get('/persons')
    persons.value = response.data
  } catch (error) {
    errorMsg.value = `載入人員失敗: ${error.message}`
  }
}

// 觸發文件輸入
const triggerFileInput = () => {
  fileInput.value?.click()
}

// 文件選擇
const handleFileSelect = (event) => {
  const files = Array.from(event.target.files || [])
  files.forEach(file => {
    const reader = new FileReader()
    reader.onload = (e) => {
      uploadedImages.value.push({
        file,
        preview: e.target.result,
        stamps: []
      })
      selectedImageIndex.value = uploadedImages.value.length - 1
    }
    reader.readAsDataURL(file)
  })
}

// 拖放
const handleDrop = (event) => {
  isDragging.value = false
  const files = Array.from(event.dataTransfer?.files || [])
  const fileInput_elem = fileInput.value
  if (fileInput_elem) {
    fileInput_elem.files = new DataTransfer().items.add(...files)[0]
    handleFileSelect({ target: fileInput_elem })
  }
}

// 選擇圖片
const selectImage = (idx) => {
  selectedImageIndex.value = idx
  selectedRect.value = null
  stampCount.value = extractedStamps.value.length
}

// 移除圖片
const removeImage = (idx) => {
  uploadedImages.value.splice(idx, 1)
  if (selectedImageIndex.value === idx) {
    selectedImageIndex.value = uploadedImages.value.length ? 0 : null
  }
}

// 框選邏輯
const startSelection = (event) => {
  if (!selectedImage.value) return
  isSelecting.value = true
  const rect = event.target.getBoundingClientRect()
  const startX = event.clientX - rect.left
  const startY = event.clientY - rect.top
  selectedRect.value = { x: startX, y: startY, width: 0, height: 0 }
}

const updateSelection = (event) => {
  if (!isSelecting.value || !selectedRect.value) return
  const img = event.target
  if (!img || !img.src) return
  const rect = img.getBoundingClientRect()
  const currentX = event.clientX - rect.left
  const currentY = event.clientY - rect.top
  
  selectedRect.value.width = currentX - selectedRect.value.x
  selectedRect.value.height = currentY - selectedRect.value.y
  
  drawSelection()
}

const endSelection = () => {
  isSelecting.value = false
}

// 繪製選擇框
const drawSelection = () => {
  const canvas = selectionCanvas.value
  if (!canvas || !selectedImage.value || !selectedRect.value) return
  
  const img = new Image()
  img.onload = () => {
    canvasWidth.value = img.width
    canvasHeight.value = img.height
    
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.strokeStyle = '#059669'
    ctx.lineWidth = 2
    ctx.strokeRect(
      selectedRect.value.x,
      selectedRect.value.y,
      selectedRect.value.width,
      selectedRect.value.height
    )
  }
  img.src = selectedImage.value.preview
}

// 提取並保存印章
const extractAndSave = async () => {
  if (!selectedPerson.value || !selectedRect.value || !selectedImage.value) {
    errorMsg.value = '請選擇人員並框選印章範圍'
    return
  }

  try {
    // 轉換座標到原始圖片尺寸
    const img = new Image()
    img.onload = async () => {
      const canvas = document.createElement('canvas')
      const rect = selectedRect.value
      canvas.width = Math.abs(rect.width)
      canvas.height = Math.abs(rect.height)
      
      const ctx = canvas.getContext('2d')
      ctx.drawImage(
        img,
        Math.min(rect.x, rect.x + rect.width),
        Math.min(rect.y, rect.y + rect.height),
        Math.abs(rect.width),
        Math.abs(rect.height),
        0, 0,
        canvas.width,
        canvas.height
      )

      // 保存到提取列表
      const preview = canvas.toDataURL('image/png')
      const personName = persons.value.find(p => p.id === parseInt(selectedPerson.value))?.name || '未知'
      extractedStamps.value.push({
        preview,
        personId: selectedPerson.value,
        personName,
        data: canvas.toDataURL('image/png')
      })

      stampCount.value = extractedStamps.value.length
      successMsg.value = `印章已保存 (共 ${extractedStamps.value.length} 個)`
      setTimeout(() => { successMsg.value = '' }, 3000)
      selectedRect.value = null
    }
    img.src = selectedImage.value.preview
  } catch (error) {
    errorMsg.value = `保存失敗: ${error.message}`
  }
}

// 移除印章
const removeStamp = (idx) => {
  extractedStamps.value.splice(idx, 1)
  stampCount.value = extractedStamps.value.length
}

// 組件掛載
onMounted(() => {
  loadPersons()
})
</script>

<style scoped>
.stamp-source-upload {
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
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

/* 上傳區 */
.upload-section {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.upload-box {
  border: 2px dashed #4b5563;
  border-radius: 8px;
  padding: 3rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
}

.upload-box:hover {
  border-color: #059669;
  background: rgba(5, 150, 105, 0.05);
}

.upload-box.dragging {
  border-color: #059669;
  background: rgba(5, 150, 105, 0.1);
}

.upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  color: #9ca3af;
}

.upload-content svg {
  color: #059669;
}

.upload-content p {
  font-size: 1.1rem;
  margin: 0;
  color: #e5e7eb;
}

.hint {
  font-size: 0.875rem;
  color: #6b7280;
}

/* 圖片網格 */
.uploaded-images h3 {
  color: #e5e7eb;
  margin: 0 0 1rem 0;
}

.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 1rem;
}

.image-card {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  border: 2px solid #374151;
  transition: border-color 0.3s;
}

.image-card:hover {
  border-color: #059669;
}

.image-card img {
  width: 100%;
  height: 120px;
  object-fit: cover;
  display: block;
}

.image-card .remove-btn {
  position: absolute;
  top: 2px;
  right: 2px;
  background: #dc2626;
  color: white;
  border: none;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  cursor: pointer;
  font-size: 0.875rem;
}

.image-card .selection-indicator {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(5, 150, 105, 0.9);
  color: white;
  text-align: center;
  padding: 0.25rem;
  font-size: 0.75rem;
  font-weight: bold;
}

/* 編輯區 */
.editor-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2rem;
}

.editor-container {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.editor-container h3,
.extracted-stamps h3 {
  color: #e5e7eb;
  margin: 0;
}

.editor-container h4 {
  color: #d1d5db;
  margin: 0.5rem 0 1rem 0;
  font-size: 0.95rem;
}

.canvas-wrapper {
  position: relative;
  display: inline-block;
  border-radius: 8px;
  overflow: hidden;
  background: #1f2937;
}

.canvas-wrapper img {
  max-width: 100%;
  height: auto;
  display: block;
}

.selection-overlay {
  position: absolute;
  top: 0;
  left: 0;
}

/* 表單 */
.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-group label {
  color: #d1d5db;
  font-size: 0.9rem;
  font-weight: 500;
}

.form-group select {
  padding: 0.65rem;
  background: #1f2937;
  border: 1px solid #4b5563;
  border-radius: 6px;
  color: #e5e7eb;
  font-size: 0.95rem;
}

.form-group select:focus {
  outline: none;
  border-color: #059669;
}

/* 按鈕 */
.primary {
  padding: 0.75rem 1.5rem;
  background: #059669;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  transition: background 0.3s;
}

.primary:hover {
  background: #047857;
}

.primary.full-width {
  width: 100%;
}

.remove-small {
  padding: 0.25rem 0.5rem;
  background: #dc2626;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 0.75rem;
  cursor: pointer;
}

/* 提取的印章 */
.extracted-stamps {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.stamp-preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 1rem;
}

.stamp-preview {
  border: 1px solid #374151;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.stamp-preview img {
  width: 100%;
  height: 100px;
  object-fit: cover;
  display: block;
}

.stamp-info {
  padding: 0.5rem;
  background: #1f2937;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}

.stamp-info p {
  margin: 0;
  color: #9ca3af;
  font-size: 0.75rem;
  flex: 1;
  text-align: center;
}

/* 提示訊息 */
.success-msg {
  padding: 0.75rem;
  background: rgba(6, 78, 59, 0.35);
  border: 1px solid #10b981;
  border-radius: 6px;
  color: #a7f3d0;
}

.error-msg {
  padding: 0.75rem;
  background: rgba(127, 29, 29, 0.35);
  border: 1px solid #ef4444;
  border-radius: 6px;
  color: #fecaca;
}

/* 響應式 */
@media (max-width: 768px) {
  .editor-section {
    grid-template-columns: 1fr;
  }

  .image-grid {
    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  }
}
</style>
