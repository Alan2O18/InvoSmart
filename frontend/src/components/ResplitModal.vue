<template>
  <teleport to="body">
    <div v-if="modelValue" class="resplit-modal-backdrop" @click.self="close">
      <div class="resplit-modal-panel">
        <header class="modal-header">
          <div>
            <h3>手動二切 / 細切</h3>
            <p class="subtitle">拖曳角點調整切割區域，確認後套用重新分割。</p>
          </div>
          <button class="close-btn" @click="close">X</button>
        </header>

        <div class="modal-body">
          <div class="toolbar">
            <button class="mini-btn" @click="addRect" :disabled="loading || saving">新增區域</button>
            <button class="mini-btn danger" @click="removeSelectedRect" :disabled="!selectedRectId || loading || saving">
              刪除選取區域
            </button>
            <span class="rect-count">目前區域數：{{ rects.length }}</span>
          </div>

          <div v-if="error" class="error-banner">{{ error }}</div>

          <div class="canvas-host">
            <div v-if="loading" class="loading-layer">偵測中...</div>
            <img
              ref="imageEl"
              :src="imageUrl"
              class="target-image"
              alt="resplit target"
              @load="onImageLoad"
            />
            <svg class="overlay" :width="displaySize.width" :height="displaySize.height">
              <g
                v-for="rect in rects"
                :key="rect.id"
                @click.stop="selectRect(rect.id)"
              >
                <polygon
                  :points="toDisplayPolygon(rect)"
                  :class="['poly', { selected: selectedRectId === rect.id }]"
                />
                <circle
                  v-for="(point, pIdx) in rect.points"
                  :key="`${rect.id}-${pIdx}`"
                  :cx="toDisplayX(point.x)"
                  :cy="toDisplayY(point.y)"
                  :class="['handle', { selected: selectedRectId === rect.id }]"
                  r="6"
                  @mousedown.prevent.stop="startDrag(rect.id, pIdx, $event)"
                />
              </g>
            </svg>
          </div>
        </div>

        <footer class="modal-footer">
          <button class="mini-btn" @click="close" :disabled="saving">取消</button>
          <button class="mini-btn primary" @click="applyResplit" :disabled="saving || loading || rects.length === 0">
            {{ saving ? '套用中...' : '套用二切' }}
          </button>
        </footer>
      </div>
    </div>
  </teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import api from '../services/api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  projectId: { type: String, required: true },
  job: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'applied'])

const imageEl = ref(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const rects = ref([])
const selectedRectId = ref(null)
const cacheToken = ref(Date.now())

const naturalSize = reactive({ width: 1, height: 1 })
const displaySize = reactive({ width: 1, height: 1 })
const dragState = reactive({ active: false, rectId: null, pointIdx: -1 })

const filename = computed(() => {
  const raw = props.job?.image_path
  if (!raw) return ''
  const parts = String(raw).split(/[/\\]/)
  return parts[parts.length - 1] || ''
})

const imageUrl = computed(() => {
  if (!props.projectId || !filename.value) return ''
  return `http://localhost:8000/api/projects/${encodeURIComponent(props.projectId)}/preview/split/${encodeURIComponent(filename.value)}?v=${cacheToken.value}`
})

const scaleX = computed(() => displaySize.width / Math.max(1, naturalSize.width))
const scaleY = computed(() => displaySize.height / Math.max(1, naturalSize.height))

const clamp = (value, min, max) => Math.max(min, Math.min(max, value))

const close = () => {
  emit('update:modelValue', false)
}

const toDisplayX = (x) => x * scaleX.value
const toDisplayY = (y) => y * scaleY.value

const toDisplayPolygon = (rect) => {
  return rect.points.map((point) => `${toDisplayX(point.x)},${toDisplayY(point.y)}`).join(' ')
}

const updateDisplaySize = () => {
  if (!imageEl.value) return
  naturalSize.width = Math.max(1, imageEl.value.naturalWidth || 1)
  naturalSize.height = Math.max(1, imageEl.value.naturalHeight || 1)
  displaySize.width = Math.max(1, imageEl.value.clientWidth || 1)
  displaySize.height = Math.max(1, imageEl.value.clientHeight || 1)
}

const onImageLoad = () => {
  updateDisplaySize()
  if (rects.value.length === 0) {
    addRect()
  }
}

const makeRect = (points, idx) => ({
  id: `rect-${Date.now()}-${idx}`,
  points,
})

const createDefaultRect = () => {
  const marginX = Math.max(20, Math.round(naturalSize.width * 0.2))
  const marginY = Math.max(20, Math.round(naturalSize.height * 0.2))
  const left = marginX
  const top = marginY
  const right = Math.max(left + 20, naturalSize.width - marginX)
  const bottom = Math.max(top + 20, naturalSize.height - marginY)
  return makeRect(
    [
      { x: left, y: top },
      { x: right, y: top },
      { x: right, y: bottom },
      { x: left, y: bottom },
    ],
    0,
  )
}

const selectRect = (rectId) => {
  selectedRectId.value = rectId
}

const addRect = () => {
  const base = createDefaultRect()
  rects.value.push(base)
  selectedRectId.value = base.id
}

const removeSelectedRect = () => {
  if (!selectedRectId.value) return
  rects.value = rects.value.filter((rect) => rect.id !== selectedRectId.value)
  selectedRectId.value = rects.value[0]?.id || null
}

const normalizeRect = (rawRect, idx) => {
  if (!rawRect || !Array.isArray(rawRect.points) || rawRect.points.length !== 4) {
    return null
  }
  const points = []
  for (const pair of rawRect.points) {
    if (!Array.isArray(pair) || pair.length !== 2) {
      return null
    }
    const x = Number(pair[0])
    const y = Number(pair[1])
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      return null
    }
    points.push({ x, y })
  }
  return makeRect(points, idx)
}

const fetchDetectedRects = async () => {
  if (!props.projectId || !props.job?.job_id) return

  loading.value = true
  error.value = ''
  try {
    const response = await api.detectJobSubRects(props.projectId, props.job.job_id)
    const detected = Array.isArray(response.data?.rects) ? response.data.rects : []
    const normalized = detected
      .map((rect, idx) => normalizeRect(rect, idx))
      .filter(Boolean)

    rects.value = normalized
    if (rects.value.length === 0) {
      rects.value = [createDefaultRect()]
    }
    selectedRectId.value = rects.value[0]?.id || null
    await nextTick()
    updateDisplaySize()
  } catch (err) {
    const message = err?.response?.data?.detail || err?.message || '偵測失敗'
    error.value = `偵測失敗：${message}`
    rects.value = [createDefaultRect()]
    selectedRectId.value = rects.value[0]?.id || null
  } finally {
    loading.value = false
  }
}

const stopDrag = () => {
  dragState.active = false
  dragState.rectId = null
  dragState.pointIdx = -1
  window.removeEventListener('mousemove', onDragMove)
  window.removeEventListener('mouseup', stopDrag)
}

const onDragMove = (event) => {
  if (!dragState.active || !imageEl.value) return
  const rect = rects.value.find((r) => r.id === dragState.rectId)
  if (!rect) return

  const bounds = imageEl.value.getBoundingClientRect()
  const dispX = clamp(event.clientX - bounds.left, 0, bounds.width)
  const dispY = clamp(event.clientY - bounds.top, 0, bounds.height)

  const x = clamp(dispX / Math.max(0.0001, scaleX.value), 0, naturalSize.width)
  const y = clamp(dispY / Math.max(0.0001, scaleY.value), 0, naturalSize.height)

  rect.points[dragState.pointIdx] = { x, y }
}

const startDrag = (rectId, pointIdx) => {
  dragState.active = true
  dragState.rectId = rectId
  dragState.pointIdx = pointIdx
  selectedRectId.value = rectId
  window.addEventListener('mousemove', onDragMove)
  window.addEventListener('mouseup', stopDrag)
}

const applyResplit = async () => {
  if (!props.projectId || !props.job?.job_id) return
  if (rects.value.length === 0) {
    error.value = '至少需要一個切割區域'
    return
  }

  saving.value = true
  error.value = ''
  try {
    const payload = rects.value.map((rect) => ({
      points: rect.points.map((point) => [Math.round(point.x), Math.round(point.y)]),
    }))
    await api.applyJobResplit(props.projectId, props.job.job_id, payload)
    emit('applied')
    close()
  } catch (err) {
    const message = err?.response?.data?.detail || err?.message || '套用失敗'
    error.value = `套用失敗：${message}`
  } finally {
    saving.value = false
  }
}

watch(
  () => props.modelValue,
  async (visible) => {
    if (visible) {
      cacheToken.value = Date.now()
      await nextTick()
      await fetchDetectedRects()
      window.addEventListener('resize', updateDisplaySize)
    } else {
      window.removeEventListener('resize', updateDisplaySize)
      stopDrag()
      error.value = ''
      rects.value = []
      selectedRectId.value = null
    }
  },
)

watch(
  () => props.job?.job_id,
  async () => {
    if (!props.modelValue) return
    cacheToken.value = Date.now()
    await fetchDetectedRects()
  },
)

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateDisplaySize)
  stopDrag()
})
</script>

<style scoped>
.resplit-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1200;
}

.resplit-modal-panel {
  width: min(1000px, 96vw);
  max-height: 92vh;
  display: flex;
  flex-direction: column;
  background: #1f2937;
  border: 1px solid #374151;
  border-radius: 10px;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  padding: 1rem 1.2rem;
  border-bottom: 1px solid #374151;
}

.modal-header h3 {
  margin: 0;
  color: #f3f4f6;
}

.subtitle {
  margin: 0.25rem 0 0;
  color: #9ca3af;
  font-size: 0.88rem;
}

.close-btn {
  border: 1px solid #4b5563;
  background: transparent;
  color: #d1d5db;
  border-radius: 6px;
  padding: 0.2rem 0.55rem;
  cursor: pointer;
}

.modal-body {
  padding: 1rem 1.2rem;
  overflow: auto;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.8rem;
}

.rect-count {
  color: #cbd5e1;
  font-size: 0.85rem;
  margin-left: auto;
}

.error-banner {
  padding: 0.55rem 0.7rem;
  border-radius: 6px;
  margin-bottom: 0.8rem;
  background: rgba(220, 38, 38, 0.2);
  border: 1px solid rgba(220, 38, 38, 0.5);
  color: #fecaca;
}

.canvas-host {
  position: relative;
  width: 100%;
  min-height: 260px;
  border: 1px solid #374151;
  border-radius: 8px;
  overflow: hidden;
  background: #111827;
}

.loading-layer {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #f3f4f6;
  background: rgba(0, 0, 0, 0.5);
  z-index: 3;
}

.target-image {
  display: block;
  width: 100%;
  height: auto;
  max-height: 62vh;
  object-fit: contain;
}

.overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.poly {
  fill: rgba(14, 165, 233, 0.18);
  stroke: rgba(14, 165, 233, 0.9);
  stroke-width: 2;
  pointer-events: auto;
  cursor: pointer;
}

.poly.selected {
  fill: rgba(16, 185, 129, 0.22);
  stroke: rgba(16, 185, 129, 0.95);
}

.handle {
  fill: #d1d5db;
  stroke: #111827;
  stroke-width: 2;
  pointer-events: auto;
  cursor: move;
}

.handle.selected {
  fill: #f59e0b;
}

.modal-footer {
  border-top: 1px solid #374151;
  padding: 0.9rem 1.2rem;
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
}

.mini-btn {
  padding: 0.35rem 0.75rem;
  font-size: 0.82rem;
  border: none;
  border-radius: 4px;
  background: #2563eb;
  color: white;
  cursor: pointer;
}

.mini-btn.primary {
  background: #0ea5e9;
}

.mini-btn.danger {
  background: #dc2626;
}

.mini-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
