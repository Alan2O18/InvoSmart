<template>
  <div v-if="modelValue" class="dialog-overlay" @click.self="closeDialog">
    <div class="dialog-panel">
      <header class="dialog-header">
        <h2>印章匯入精靈</h2>
        <button type="button" class="close-btn" @click="closeDialog">關閉</button>
      </header>

      <div class="step-indicator">
        <span :class="{ active: step === 1 }">1. 上傳與模式</span>
        <span :class="{ active: step === 2 }">2. 框選與屬性</span>
      </div>

      <section v-if="step === 1" class="step-content">
        <label class="field-label">選擇印章圖紙</label>
        <input type="file" accept="image/*" @change="onFileChange" />

        <label class="field-label">偵測模式</label>
        <div class="mode-row">
          <label>
            <input type="radio" value="red" v-model="mode" />
            紅色印章
          </label>
          <label>
            <input type="radio" value="edge" v-model="mode" />
            黑色或混色印章
          </label>
        </div>

        <div v-if="filePreviewUrl" class="preview-thumb-wrap">
          <img :src="filePreviewUrl" alt="upload preview" class="preview-thumb" />
        </div>

        <p class="hint">下一步直接進入手動框選，不再執行自動偵測。</p>
      </section>

      <section v-else-if="step === 2" class="step-content">
        <div class="preview-stage" ref="stageRef">
          <img ref="imageRef" :src="filePreviewUrl" alt="stamp sheet" @load="onImageLoad" />
          <div
            class="box-layer"
            @pointerdown="startDraw"
            @pointermove="moveDraw"
            @pointerup="finishDraw"
            @pointerleave="cancelDraw"
          >
            <button
              v-for="item in boxes"
              :key="item.id"
              type="button"
              class="box-item"
              :class="{ disabled: !item.enabled }"
              :style="boxStyle(item)"
              @click.stop="toggleBox(item.id)"
              :title="item.enabled ? '點擊取消選取' : '點擊重新選取'"
            >
              {{ item.name || '未命名' }}
            </button>
            <div v-if="draftRect" class="draft-box" :style="draftStyle"></div>
          </div>
        </div>

        <div class="box-list">
          <div v-for="item in boxes" :key="`${item.id}-row`" class="box-row">
            <label>
              <input type="checkbox" v-model="item.enabled" />
              框 {{ item.id }} ({{ item.w }} x {{ item.h }})
            </label>
            <button type="button" class="mini-btn" @click="removeBox(item.id)">刪除</button>
          </div>
        </div>

        <table class="meta-table">
          <thead>
            <tr>
              <th>名稱</th>
              <th>類別</th>
              <th>所有者 ID (可留白)</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in enabledBoxes" :key="`${item.id}-meta`">
              <td><input type="text" v-model="item.name" placeholder="例如：美術社社章" /></td>
              <td><input type="text" v-model="item.category" placeholder="例如：社團 / 稽核" /></td>
              <td><input type="number" v-model.number="item.owner_id" placeholder="可留白（自動分配）" /></td>
            </tr>
            <tr v-if="enabledBoxes.length === 0">
              <td colspan="3" class="empty-tip">沒有可儲存的框，請回上一步至少選取一個。</td>
            </tr>
          </tbody>
        </table>
      </section>

      <footer class="dialog-footer">
        <div class="left-actions">
          <button type="button" @click="closeDialog">取消</button>
          <button v-if="step > 1" type="button" @click="step -= 1">上一步</button>
        </div>

        <div class="right-actions">
          <button
            v-if="step === 1"
            type="button"
            class="primary"
            :disabled="!selectedFile"
            @click="beginManualSelection"
          >
            下一步：框選印章
          </button>

          <button
            v-else
            type="button"
            class="primary"
            :disabled="!canSave || stampStore.saving"
            @click="saveStamps"
          >
            {{ stampStore.saving ? '儲存中...' : '儲存印章' }}
          </button>
        </div>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { useStampStore } from '../store/stamp'

const props = defineProps({
  modelValue: {
    type: Boolean,
    required: true,
  },
})

const emit = defineEmits(['update:modelValue', 'registered'])
const stampStore = useStampStore()

const step = ref(1)
const mode = ref('red')
const selectedFile = ref(null)
const filePreviewUrl = ref('')
const imageRef = ref(null)
const stageRef = ref(null)
const imageSize = ref({ width: 0, height: 0 })

const boxes = ref([])
const drawing = ref(false)
const drawStart = ref({ x: 0, y: 0 })
const draftRect = ref(null)

const enabledBoxes = computed(() => boxes.value.filter((item) => item.enabled))
const canSave = computed(() =>
  enabledBoxes.value.length > 0
  && enabledBoxes.value.every((item) => String(item.name || '').trim() && String(item.category || '').trim())
)

const draftStyle = computed(() => {
  if (!draftRect.value) return {}
  return {
    left: `${draftRect.value.x}px`,
    top: `${draftRect.value.y}px`,
    width: `${draftRect.value.w}px`,
    height: `${draftRect.value.h}px`,
  }
})

const resetState = () => {
  step.value = 1
  mode.value = 'red'
  selectedFile.value = null
  if (filePreviewUrl.value) {
    URL.revokeObjectURL(filePreviewUrl.value)
  }
  filePreviewUrl.value = ''
  imageSize.value = { width: 0, height: 0 }
  boxes.value = []
  drawing.value = false
  draftRect.value = null
}

const closeDialog = () => {
  resetState()
  emit('update:modelValue', false)
}

const onFileChange = (event) => {
  const file = event.target?.files?.[0]
  if (!file) return
  selectedFile.value = file
  boxes.value = []
  step.value = 1

  if (filePreviewUrl.value) {
    URL.revokeObjectURL(filePreviewUrl.value)
  }
  filePreviewUrl.value = URL.createObjectURL(file)
}

const onImageLoad = () => {
  if (!imageRef.value) return
  imageSize.value = {
    width: imageRef.value.naturalWidth,
    height: imageRef.value.naturalHeight,
  }
}

const beginManualSelection = () => {
  if (!selectedFile.value) return
  boxes.value = []
  step.value = 2
}

const boxStyle = (item) => {
  const width = imageSize.value.width || 1
  const height = imageSize.value.height || 1
  return {
    left: `${(item.x / width) * 100}%`,
    top: `${(item.y / height) * 100}%`,
    width: `${(item.w / width) * 100}%`,
    height: `${(item.h / height) * 100}%`,
  }
}

const toggleBox = (id) => {
  const target = boxes.value.find((item) => item.id === id)
  if (target) {
    target.enabled = !target.enabled
  }
}

const removeBox = (id) => {
  boxes.value = boxes.value.filter((item) => item.id !== id)
}

/**
 * 使用 imageRef 而非 stageRef 取得座標基準，
 * 排除 border / padding 對 getBoundingClientRect 的影響。
 */
const getImageMetrics = () => {
  const img = imageRef.value
  if (!img) return null
  const rect = img.getBoundingClientRect()
  if (rect.width <= 0 || rect.height <= 0) return null
  return rect
}

const clamp = (value, min, max) => Math.min(max, Math.max(min, value))

const startDraw = (event) => {
  if (step.value !== 2) return
  const rect = getImageMetrics()
  if (!rect) return

  const x = clamp(event.clientX - rect.left, 0, rect.width)
  const y = clamp(event.clientY - rect.top, 0, rect.height)

  drawStart.value = { x, y }
  draftRect.value = { x, y, w: 0, h: 0 }
  drawing.value = true
}

const moveDraw = (event) => {
  if (!drawing.value) return
  const rect = getImageMetrics()
  if (!rect) return

  const currentX = clamp(event.clientX - rect.left, 0, rect.width)
  const currentY = clamp(event.clientY - rect.top, 0, rect.height)

  const x = Math.min(drawStart.value.x, currentX)
  const y = Math.min(drawStart.value.y, currentY)
  const w = Math.abs(currentX - drawStart.value.x)
  const h = Math.abs(currentY - drawStart.value.y)

  draftRect.value = { x, y, w, h }
}

const cancelDraw = () => {
  if (!drawing.value) return
  drawing.value = false
  draftRect.value = null
}

const finishDraw = () => {
  if (!drawing.value || !draftRect.value) {
    drawing.value = false
    return
  }

  // 使用 imageRef 確保比例計算不被 border/padding 汙染
  const rect = getImageMetrics()
  if (!rect) {
    drawing.value = false
    draftRect.value = null
    return
  }

  if (draftRect.value.w < 8 || draftRect.value.h < 8) {
    drawing.value = false
    draftRect.value = null
    return
  }

  const width = imageSize.value.width || 1
  const height = imageSize.value.height || 1
  // rect 現在是 imageRef 的尺寸，不含外框，比例計算精準
  const scaleX = width / rect.width
  const scaleY = height / rect.height

  const x = Math.round(draftRect.value.x * scaleX)
  const y = Math.round(draftRect.value.y * scaleY)
  const w = Math.round(draftRect.value.w * scaleX)
  const h = Math.round(draftRect.value.h * scaleY)

  const id = `M${boxes.value.length + 1}`
  boxes.value.push({
    id,
    x,
    y,
    w,
    h,
    enabled: true,
    name: `手動印章 ${boxes.value.length + 1}`,
    category: mode.value === 'red' ? '社團' : '稽核',
    owner_id: null,
  })

  drawing.value = false
  draftRect.value = null
}

const saveStamps = async () => {
  if (!selectedFile.value || !canSave.value) return

  const payload = enabledBoxes.value.map((item) => ({
    x: item.x,
    y: item.y,
    w: item.w,
    h: item.h,
    name: String(item.name || '').trim(),
    category: String(item.category || '').trim(),
    owner_id: item.owner_id || null,
  }))

  try {
    await stampStore.registerStamps(selectedFile.value, mode.value, payload)
    emit('registered')
    closeDialog()
  } catch (e) {
    alert(`儲存失敗：${stampStore.error || e}`)
  }
}

onBeforeUnmount(() => {
  if (filePreviewUrl.value) {
    URL.revokeObjectURL(filePreviewUrl.value)
  }
})
</script>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1200;
  padding: 1rem;
}

.dialog-panel {
  width: min(1100px, 95vw);
  max-height: 92vh;
  overflow: auto;
  background: #1f2937;
  border: 1px solid #334155;
  border-radius: 10px;
  padding: 1rem;
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.8rem;
}

.dialog-header h2 {
  font-size: 1.15rem;
  color: #f8fafc;
}

.close-btn {
  background: transparent;
  border: 1px solid #64748b;
  color: #cbd5e1;
}

.step-indicator {
  display: flex;
  gap: 0.6rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.step-indicator span {
  padding: 0.35rem 0.7rem;
  border-radius: 999px;
  border: 1px solid #475569;
  color: #94a3b8;
  font-size: 0.85rem;
}

.step-indicator span.active {
  border-color: #38bdf8;
  color: #e0f2fe;
  background: rgba(56, 189, 248, 0.15);
}

.step-content {
  margin-bottom: 1rem;
}

.field-label {
  display: block;
  margin-bottom: 0.45rem;
  color: #e2e8f0;
}

.mode-row {
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
}

.hint {
  color: #94a3b8;
  margin-top: 0.7rem;
  font-size: 0.88rem;
}

.preview-thumb-wrap {
  margin-top: 0.8rem;
}

.preview-thumb {
  width: min(420px, 100%);
  border-radius: 8px;
  border: 1px solid #334155;
}

.preview-stage {
  position: relative;
  display: inline-block;
  border: 1px solid #334155;
  border-radius: 8px;
  overflow: hidden;
  max-width: 100%;
}

.preview-stage img {
  max-width: min(900px, 100%);
  display: block;
}

.box-layer {
  position: absolute;
  inset: 0;
  cursor: crosshair;
}

.box-item {
  position: absolute;
  border: 2px solid #22d3ee;
  background: rgba(34, 211, 238, 0.18);
  color: #ecfeff;
  font-size: 0.7rem;
  padding: 0.1rem 0.25rem;
  text-align: left;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.box-item.disabled {
  border-color: #f59e0b;
  background: rgba(245, 158, 11, 0.2);
  color: #fde68a;
}

.draft-box {
  position: absolute;
  border: 2px dashed #f97316;
  background: rgba(249, 115, 22, 0.2);
}

.box-list {
  margin-top: 1rem;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 0.5rem;
}

.box-row {
  background: #111827;
  border: 1px solid #374151;
  border-radius: 6px;
  padding: 0.45rem;
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
}

.mini-btn {
  border: 1px solid #ef4444;
  color: #fecaca;
  background: transparent;
  padding: 0.25rem 0.45rem;
}

.meta-table {
  width: 100%;
  border-collapse: collapse;
}

.meta-table th,
.meta-table td {
  border: 1px solid #334155;
  padding: 0.55rem;
}

.meta-table th {
  background: #0f172a;
  color: #bfdbfe;
}

.meta-table input {
  width: 100%;
  background: #0b1220;
  border: 1px solid #334155;
  color: #e2e8f0;
  border-radius: 4px;
  padding: 0.45rem;
}

.empty-tip {
  text-align: center;
  color: #9ca3af;
}

.dialog-footer {
  display: flex;
  justify-content: space-between;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.left-actions,
.right-actions {
  display: flex;
  gap: 0.5rem;
}

.primary {
  background: #0284c7;
  color: #fff;
  border: none;
}

.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .dialog-panel {
    width: 100%;
    max-height: 100vh;
    border-radius: 0;
  }

  .dialog-overlay {
    padding: 0;
  }

  .box-list {
    grid-template-columns: 1fr;
  }
}
</style>
