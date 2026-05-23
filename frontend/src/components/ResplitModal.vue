<template>
  <teleport to="body">
    <div v-if="modelValue" class="resplit-modal-backdrop" @click.self="close">
      <div class="resplit-modal-panel">
        <header class="modal-header">
          <div>
            <h3>手動二切 / 細切</h3>
            <p class="subtitle">以原始大圖為底，拖曳角點調整切割區域後套用重新分割。</p>
          </div>
          <button class="close-btn" @click="close">✕</button>
        </header>

        <div class="modal-body">
          <div class="toolbar">
            <button class="mini-btn" @click="addRect" :disabled="loading || saving">新增區域</button>
            <button
              class="mini-btn danger"
              @click="removeSelectedRect"
              :disabled="!selectedRectId || loading || saving"
            >
              刪除選取區域
            </button>
            <span class="rect-count">區域數：{{ rects.length }}</span>

            <div class="zoom-controls">
              <button class="mini-btn icon-btn" @click="zoomIn" title="放大">＋</button>
              <button class="mini-btn icon-btn" @click="zoomOut" title="縮小">－</button>
              <button class="mini-btn icon-btn" @click="resetView" title="還原視角">⊡ Fit</button>
              <span class="zoom-label">{{ Math.round(transform.scale * 100) }}%</span>
            </div>

            <span class="pan-hint" :class="{ active: spaceDown }">
              {{ spaceDown ? '🤚 平移模式' : 'Space 鍵 = 平移' }}
            </span>
          </div>

          <div v-if="error" class="error-banner">{{ error }}</div>

          <!-- canvas-host: 固定視口，overflow hidden，接收 wheel / pan 事件 -->
          <div
            class="canvas-host"
            ref="canvasHostRef"
            :class="{ 'cursor-grab': spaceDown && !panState.active, 'cursor-grabbing': panState.active }"
            @wheel.prevent="onWheel"
            @mousedown="onHostMouseDown"
          >
            <div v-if="loading" class="loading-layer">偵測中...</div>

            <!-- transform-layer: 套用 scale+translate，完全包住 img + svg -->
            <div class="transform-layer" :style="transformLayerStyle">
              <img
                ref="imageEl"
                :src="imageUrl"
                class="target-image"
                alt="resplit target"
                draggable="false"
                @load="onImageLoad"
              />
              <!-- SVG viewBox = 0 0 naturalWidth naturalHeight
                   preserveAspectRatio="none" 使其與 img 完全重疊
                   點的座標直接以自然像素儲存，零轉換誤差 -->
              <!-- viewBox uses full-image dimensions (backend coords).
                   The SVG element physically fills the preview-sized transform-layer.
                   Browser auto-scales: full-res coords → preview-sized display. -->
              <svg
                v-if="naturalSize.width > 0 && svgViewW > 0"
                class="overlay"
                :viewBox="`0 0 ${svgViewW} ${svgViewH}`"
                preserveAspectRatio="none"
              >
                <g
                  v-for="rect in rects"
                  :key="rect.id"
                  @click.stop="selectRect(rect.id)"
                >
                  <polygon
                    :points="toSvgPolygon(rect)"
                    :class="['poly', { selected: selectedRectId === rect.id }]"
                  />
                  <circle
                    v-for="(point, pIdx) in rect.points"
                    :key="`${rect.id}-${pIdx}`"
                    :cx="point.x"
                    :cy="point.y"
                    :class="['handle', { selected: selectedRectId === rect.id }]"
                    :r="handleRadius"
                    @mousedown.prevent.stop="startDrag(rect.id, pIdx)"
                  />
                </g>
              </svg>
            </div>
          </div>
        </div>

        <footer class="modal-footer">
          <button class="mini-btn" @click="close" :disabled="saving">取消</button>
          <button
            class="mini-btn primary"
            @click="applyResplit"
            :disabled="saving || loading || rects.length === 0"
          >
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
  rawFile: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'applied'])

// ─── DOM refs ──────────────────────────────────────────────────────────────
const imageEl = ref(null)
const canvasHostRef = ref(null)

// ─── UI state ──────────────────────────────────────────────────────────────
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const rects = ref([])
const selectedRectId = ref(null)
const cacheToken = ref(Date.now())
const spaceDown = ref(false)

// ─── Image natural size (preview thumbnail dimensions) ───────────────────
const naturalSize = reactive({ width: 0, height: 0 })

// ─── Full-resolution image size (from backend detect API) ─────────────────
// SVG viewBox uses fullImageSize so coords match backend's full-res pixel space.
// transform-layer uses naturalSize so the image renders at preview thumbnail scale.
const fullImageSize = reactive({ width: 0, height: 0 })

// ─── Pan / Zoom transform ─────────────────────────────────────────────────
const transform = reactive({ scale: 1, x: 0, y: 0 })
const MIN_SCALE = 0.05
const MAX_SCALE = 10
const ZOOM_STEP = 1.25

// ─── Drag state (point handle) ────────────────────────────────────────────
const dragState = reactive({ active: false, rectId: null, pointIdx: -1 })

// ─── Pan state ────────────────────────────────────────────────────────────
const panState = reactive({ active: false, startClientX: 0, startClientY: 0, startTX: 0, startTY: 0 })

// ─── Computed ─────────────────────────────────────────────────────────────
const rawFilename = computed(() => {
  const raw = props.rawFile?.filename
  if (!raw) return ''
  return String(raw).split(/[/\\]/).at(-1) || ''
})

const imageUrl = computed(() => {
  if (!props.projectId || !rawFilename.value) return ''
  return api.toAbsoluteUrl(`/api/projects/${encodeURIComponent(props.projectId)}/preview/raw/${encodeURIComponent(rawFilename.value)}?v=${cacheToken.value}`)
})

// CSS transform applied to the layer containing both img and svg overlay
const transformLayerStyle = computed(() => ({
  transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
  transformOrigin: '0 0',
  // Physical size = preview naturalSize; SVG viewBox = fullImageSize.
  // Browser scales SVG coords automatically: full→preview ratio handled via viewBox.
  width: naturalSize.width > 0 ? `${naturalSize.width}px` : '100%',
  height: naturalSize.height > 0 ? `${naturalSize.height}px` : 'auto',
}))

// Effective full-image width / height for SVG viewBox.
// If backend provided full dimensions, use them; otherwise fall back to naturalSize.
const svgViewW = computed(() => fullImageSize.width > 0 ? fullImageSize.width : naturalSize.width)
const svgViewH = computed(() => fullImageSize.height > 0 ? fullImageSize.height : naturalSize.height)

// Scale factor: full-res pixel → preview pixel
const scaleToFull = computed(() => ({
  x: svgViewW.value / Math.max(1, naturalSize.width),
  y: svgViewH.value / Math.max(1, naturalSize.height),
}))

// Handle radius in SVG/full-image units: keep visually ~8px regardless of zoom
const handleRadius = computed(() => Math.max(3, 8 * scaleToFull.value.x / transform.scale))

// ─── Utilities ────────────────────────────────────────────────────────────
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v))

/**
 * Convert screen (client) coords → full-image pixel coords.
 *
 * The transform-layer renders at naturalSize (preview), but the SVG
 * viewBox and stored coords are in fullImageSize.
 * Formula:
 *   preview_x = (clientX - hostLeft - translate.x) / scale
 *   full_x    = preview_x * (fullWidth / previewWidth)
 */
const screenToNatural = (clientX, clientY) => {
  const host = canvasHostRef.value
  if (!host) return { x: 0, y: 0 }
  const bounds = host.getBoundingClientRect()
  const previewX = (clientX - bounds.left - transform.x) / transform.scale
  const previewY = (clientY - bounds.top - transform.y) / transform.scale
  return {
    x: clamp(previewX * scaleToFull.value.x, 0, svgViewW.value),
    y: clamp(previewY * scaleToFull.value.y, 0, svgViewH.value),
  }
}

// Points are stored in natural coords → SVG renders 1:1 via viewBox
const toSvgPolygon = (rect) => rect.points.map((p) => `${p.x},${p.y}`).join(' ')

// ─── View fit ─────────────────────────────────────────────────────────────
const fitToHost = () => {
  const host = canvasHostRef.value
  if (!host || naturalSize.width <= 0) return
  const hw = host.clientWidth
  const hh = host.clientHeight
  const scale = Math.min(hw / naturalSize.width, hh / naturalSize.height, 1)
  transform.scale = scale
  transform.x = Math.round((hw - naturalSize.width * scale) / 2)
  transform.y = Math.round((hh - naturalSize.height * scale) / 2)
}

const resetView = () => fitToHost()

// ─── Zoom helpers ─────────────────────────────────────────────────────────
const zoomAt = (clientX, clientY, factor) => {
  const host = canvasHostRef.value
  if (!host) return
  const bounds = host.getBoundingClientRect()
  const ox = clientX - bounds.left
  const oy = clientY - bounds.top
  const newScale = clamp(transform.scale * factor, MIN_SCALE, MAX_SCALE)
  const ratio = newScale / transform.scale
  transform.x = ox - (ox - transform.x) * ratio
  transform.y = oy - (oy - transform.y) * ratio
  transform.scale = newScale
}

const zoomInAt = (clientX, clientY) => zoomAt(clientX, clientY, ZOOM_STEP)
const zoomOutAt = (clientX, clientY) => zoomAt(clientX, clientY, 1 / ZOOM_STEP)

const zoomIn = () => {
  const host = canvasHostRef.value
  if (!host) return
  const r = host.getBoundingClientRect()
  zoomInAt(r.left + host.clientWidth / 2, r.top + host.clientHeight / 2)
}

const zoomOut = () => {
  const host = canvasHostRef.value
  if (!host) return
  const r = host.getBoundingClientRect()
  zoomOutAt(r.left + host.clientWidth / 2, r.top + host.clientHeight / 2)
}

// ─── Host mouse events ────────────────────────────────────────────────────
const onWheel = (event) => {
  zoomAt(event.clientX, event.clientY, event.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP)
}

/**
 * Global (window-level) mousemove handler — attached only while dragging or panning.
 * Using window ensures the cursor is tracked even when it leaves canvas-host.
 */
const onWindowMouseMove = (event) => {
  if (panState.active) {
    transform.x = panState.startTX + (event.clientX - panState.startClientX)
    transform.y = panState.startTY + (event.clientY - panState.startClientY)
    return
  }
  if (dragState.active) {
    const rect = rects.value.find((r) => r.id === dragState.rectId)
    if (!rect) return
    const { x, y } = screenToNatural(event.clientX, event.clientY)
    rect.points[dragState.pointIdx] = { x, y }
  }
}

/** Global mouseup — ends any active drag/pan and removes window listeners. */
const onWindowMouseUp = () => {
  panState.active = false
  dragState.active = false
  dragState.rectId = null
  dragState.pointIdx = -1
  window.removeEventListener('mousemove', onWindowMouseMove)
  window.removeEventListener('mouseup', onWindowMouseUp)
}

const onHostMouseDown = (event) => {
  if (event.button !== 0) return
  if (spaceDown.value) {
    // Pan mode: capture pan start & attach window-level tracking
    panState.active = true
    panState.startClientX = event.clientX
    panState.startClientY = event.clientY
    panState.startTX = transform.x
    panState.startTY = transform.y
    event.preventDefault()
    window.addEventListener('mousemove', onWindowMouseMove)
    window.addEventListener('mouseup', onWindowMouseUp)
  }
  // Drag mode is handled by startDrag() on individual handles via @mousedown.stop
}

// ─── Point drag ───────────────────────────────────────────────────────────
const startDrag = (rectId, pointIdx) => {
  if (spaceDown.value) return // pan mode wins
  dragState.active = true
  dragState.rectId = rectId
  dragState.pointIdx = pointIdx
  selectedRectId.value = rectId
  // Attach window-level listeners so drag tracks even outside canvas-host
  window.addEventListener('mousemove', onWindowMouseMove)
  window.addEventListener('mouseup', onWindowMouseUp)
}

// ─── Keyboard ─────────────────────────────────────────────────────────────
const onKeyDown = (e) => {
  if (e.code === 'Space' && !e.target.matches('input, textarea, select')) {
    e.preventDefault()
    spaceDown.value = true
  }
}

const onKeyUp = (e) => {
  if (e.code === 'Space') {
    spaceDown.value = false
    panState.active = false
  }
}

// ─── Image load ───────────────────────────────────────────────────────────
const onImageLoad = async () => {
  if (!imageEl.value) return
  naturalSize.width = imageEl.value.naturalWidth || 1
  naturalSize.height = imageEl.value.naturalHeight || 1
  await nextTick()
  fitToHost()
  if (rects.value.length === 0) addRect()
}

// ─── Rect management ──────────────────────────────────────────────────────
const makeRect = (points, idx) => ({
  id: `rect-${Date.now()}-${idx}`,
  points,
})

const createDefaultRect = () => {
  // Use full-image dimensions for default rect; fall back to preview if unavailable
  const w = svgViewW.value || naturalSize.width || 100
  const h = svgViewH.value || naturalSize.height || 100
  const mx = Math.max(20, Math.round(w * 0.2))
  const my = Math.max(20, Math.round(h * 0.2))
  return makeRect(
    [
      { x: mx, y: my },
      { x: w - mx, y: my },
      { x: w - mx, y: h - my },
      { x: mx, y: h - my },
    ],
    0,
  )
}

const selectRect = (rectId) => {
  if (!spaceDown.value) selectedRectId.value = rectId
}

const addRect = () => {
  const base = createDefaultRect()
  rects.value.push(base)
  selectedRectId.value = base.id
}

const removeSelectedRect = () => {
  if (!selectedRectId.value) return
  rects.value = rects.value.filter((r) => r.id !== selectedRectId.value)
  selectedRectId.value = rects.value[0]?.id || null
}

const normalizeRect = (rawRect, idx) => {
  if (!rawRect || !Array.isArray(rawRect.points) || rawRect.points.length !== 4) return null
  const points = []
  for (const pair of rawRect.points) {
    if (!Array.isArray(pair) || pair.length !== 2) return null
    const x = Number(pair[0])
    const y = Number(pair[1])
    if (!Number.isFinite(x) || !Number.isFinite(y)) return null
    points.push({ x, y })
  }
  return makeRect(points, idx)
}

// ─── API calls ────────────────────────────────────────────────────────────
const fetchDetectedRects = async () => {
  if (!props.projectId || !rawFilename.value) return
  loading.value = true
  error.value = ''
  try {
    const response = await api.detectRawSubRects(props.projectId, rawFilename.value)
    const data = response.data || {}
    const detected = Array.isArray(data?.rects) ? data.rects : []

    // Store full-image dimensions from backend (used for SVG viewBox)
    if (data.full_width > 0 && data.full_height > 0) {
      fullImageSize.width = data.full_width
      fullImageSize.height = data.full_height
    }

    const normalized = detected.map((r, i) => normalizeRect(r, i)).filter(Boolean)
    if (normalized.length > 0) {
      rects.value = normalized
    } else if (naturalSize.width > 0) {
      rects.value = [createDefaultRect()]
    } else {
      rects.value = []
    }
    selectedRectId.value = rects.value[0]?.id || null
  } catch (err) {
    const message = err?.response?.data?.detail || err?.message || '偵測失敗'
    error.value = `偵測失敗：${message}`
    if (naturalSize.width > 0) {
      rects.value = [createDefaultRect()]
    } else {
      rects.value = []
    }
  } finally {
    loading.value = false
  }
}

const applyResplit = async () => {
  if (!props.projectId || !rawFilename.value) return
  if (rects.value.length === 0) {
    error.value = '至少需要一個切割區域'
    return
  }
  saving.value = true
  error.value = ''
  try {
    const payload = rects.value.map((rect) => ({
      points: rect.points.map((p) => [Math.round(p.x), Math.round(p.y)]),
    }))
    await api.applyRawResplit(props.projectId, rawFilename.value, payload)
    emit('applied')
    close()
  } catch (err) {
    const message = err?.response?.data?.detail || err?.message || '套用失敗'
    error.value = `套用失敗：${message}`
  } finally {
    saving.value = false
  }
}

// ─── Modal lifecycle helpers ──────────────────────────────────────────────
const close = () => emit('update:modelValue', false)

const onResize = () => fitToHost()

const attachListeners = () => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  window.addEventListener('resize', onResize)
}

const detachListeners = () => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  window.removeEventListener('resize', onResize)
  // Clean up any lingering drag/pan window listeners
  window.removeEventListener('mousemove', onWindowMouseMove)
  window.removeEventListener('mouseup', onWindowMouseUp)
}

const resetModalState = () => {
  detachListeners()
  dragState.active = false
  panState.active = false
  spaceDown.value = false
  error.value = ''
  rects.value = []
  selectedRectId.value = null
  naturalSize.width = 0
  naturalSize.height = 0
  fullImageSize.width = 0
  fullImageSize.height = 0
}

// ─── Watchers ─────────────────────────────────────────────────────────────
watch(
  () => props.modelValue,
  async (visible) => {
    if (visible) {
      cacheToken.value = Date.now()
      await nextTick()
      attachListeners()
      await fetchDetectedRects()
    } else {
      resetModalState()
    }
  },
)

watch(
  () => props.rawFile?.filename,
  async () => {
    if (!props.modelValue) return
    cacheToken.value = Date.now()
    await fetchDetectedRects()
  },
)

onBeforeUnmount(resetModalState)
</script>

<style scoped>
.resplit-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1200;
}

.resplit-modal-panel {
  width: min(1100px, 97vw);
  max-height: 95vh;
  display: flex;
  flex-direction: column;
  background: #1a2234;
  border: 1px solid #2d3a52;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.6);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid #2d3a52;
  flex-shrink: 0;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.05rem;
  color: #f1f5f9;
}

.subtitle {
  margin: 0.2rem 0 0;
  font-size: 0.82rem;
  color: #94a3b8;
}

.close-btn {
  background: transparent;
  border: 1px solid #3d4f6e;
  color: #94a3b8;
  border-radius: 6px;
  padding: 0.25rem 0.6rem;
  cursor: pointer;
  font-size: 0.9rem;
  transition: color 0.15s, border-color 0.15s;
}
.close-btn:hover {
  color: #f1f5f9;
  border-color: #64748b;
}

.modal-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0.85rem 1.25rem;
  overflow: hidden;
  gap: 0.6rem;
}

/* ── Toolbar ── */
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.rect-count {
  font-size: 0.82rem;
  color: #94a3b8;
}

.zoom-controls {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  margin-left: auto;
}

.zoom-label {
  font-size: 0.78rem;
  color: #94a3b8;
  min-width: 3.5ch;
  text-align: right;
}

.pan-hint {
  font-size: 0.76rem;
  color: #64748b;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  border: 1px solid transparent;
  transition: all 0.15s;
}
.pan-hint.active {
  color: #38bdf8;
  border-color: #38bdf8;
  background: rgba(56, 189, 248, 0.1);
}

/* ── Canvas host ── */
.canvas-host {
  position: relative;
  flex: 1;
  min-height: 300px;
  overflow: hidden;
  background: #0d1117;
  border: 1px solid #2d3a52;
  border-radius: 8px;
  user-select: none;
  cursor: default;
}

.canvas-host.cursor-grab {
  cursor: grab;
}
.canvas-host.cursor-grabbing {
  cursor: grabbing;
}

/* ── Transform layer ── */
.transform-layer {
  position: absolute;
  top: 0;
  left: 0;
  /* width/height set dynamically in style binding */
}

.target-image {
  display: block;
  width: 100%;
  height: 100%;
  /* NO object-fit — fills transform-layer exactly */
  pointer-events: none;
}

.overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
}

.loading-layer {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #f1f5f9;
  background: rgba(0, 0, 0, 0.55);
  z-index: 10;
  font-size: 0.9rem;
}

/* ── SVG elements ── */
.poly {
  fill: rgba(14, 165, 233, 0.15);
  stroke: rgba(14, 165, 233, 0.85);
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
  pointer-events: auto;
  cursor: pointer;
  transition: fill 0.12s;
}
.poly:hover {
  fill: rgba(14, 165, 233, 0.25);
}
.poly.selected {
  fill: rgba(16, 185, 129, 0.2);
  stroke: rgba(16, 185, 129, 0.95);
}

.handle {
  fill: #e2e8f0;
  stroke: #0f172a;
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
  pointer-events: auto;
  cursor: move;
  transition: fill 0.1s;
}
.handle:hover {
  fill: #f8fafc;
}
.handle.selected {
  fill: #fbbf24;
  stroke: #78350f;
}

/* ── Error banner ── */
.error-banner {
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  background: rgba(220, 38, 38, 0.15);
  border: 1px solid rgba(220, 38, 38, 0.4);
  color: #fca5a5;
  font-size: 0.85rem;
  flex-shrink: 0;
}

/* ── Footer ── */
.modal-footer {
  border-top: 1px solid #2d3a52;
  padding: 0.75rem 1.25rem;
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  flex-shrink: 0;
}

/* ── Buttons ── */
.mini-btn {
  padding: 0.3rem 0.7rem;
  font-size: 0.8rem;
  border: none;
  border-radius: 5px;
  background: #2563eb;
  color: #fff;
  cursor: pointer;
  transition: background 0.15s, opacity 0.15s;
  white-space: nowrap;
}
.mini-btn:hover:not(:disabled) {
  background: #3b82f6;
}
.mini-btn.primary {
  background: #0ea5e9;
}
.mini-btn.primary:hover:not(:disabled) {
  background: #38bdf8;
}
.mini-btn.danger {
  background: #dc2626;
}
.mini-btn.danger:hover:not(:disabled) {
  background: #ef4444;
}
.mini-btn.icon-btn {
  padding: 0.3rem 0.55rem;
  background: #1e293b;
  border: 1px solid #334155;
  color: #cbd5e1;
}
.mini-btn.icon-btn:hover:not(:disabled) {
  background: #273549;
  color: #f1f5f9;
}
.mini-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
