<template>
  <div 
    class="image-viewer-container" 
    ref="container"
    @wheel.prevent="handleWheel"
    @mousedown="handleMouseDown"
    @dblclick="resetZoom"
  >
    <div class="image-wrapper" :style="wrapperStyle">
      <img 
        ref="img"
        :src="src" 
        :alt="alt" 
        @load="onImageLoad"
        :style="{ imageRendering: scale > 2 ? 'pixelated' : 'auto' }"
      />
    </div>

    <!-- Controls / Indicator -->
    <div class="viewer-controls">
      <span class="scale-indicator">{{ Math.round(scale * 100) }}%</span>
      <button @click.stop="zoomIn" class="control-btn" title="Zoom In">+</button>
      <button @click.stop="zoomOut" class="control-btn" title="Zoom Out">-</button>
      <button @click.stop="resetZoom" class="control-btn reset-btn" title="Reset / Fit">⟲</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  src: { type: String, required: true },
  alt: { type: String, default: '' }
})

const container = ref(null)
const img = ref(null)

// State
const scale = ref(1)
const translateX = ref(0)
const translateY = ref(0)
const isDragging = ref(false)

// Config
const MIN_SCALE = 0.1
const MAX_SCALE = 5.0
const ZOOM_SPEED = 0.1

// Internal limits for boundary check
let imageWidth = 0
let imageHeight = 0

const wrapperStyle = computed(() => ({
  transform: `translate(${translateX.value}px, ${translateY.value}px) scale(${scale.value})`,
  transition: isDragging.value ? 'none' : 'transform 0.1s ease-out',
  cursor: isDragging.value ? 'grabbing' : 'grab'
}))

const onImageLoad = () => {
  if (img.value) {
    imageWidth = img.value.naturalWidth
    imageHeight = img.value.naturalHeight
    resetZoom()
  }
}

// Fit to container logic
const fitScale = () => {
  if (!container.value || !imageWidth || !imageHeight) return 1
  
  const { clientWidth, clientHeight } = container.value
  const scaleX = clientWidth / imageWidth
  const scaleY = clientHeight / imageHeight
  return Math.min(scaleX, scaleY) * 0.95 // 95% fit
}

const resetZoom = () => {
  if (!container.value) return
  
  const newScale = fitScale()
  scale.value = newScale
  
  // Center image
  const { clientWidth, clientHeight } = container.value
  translateX.value = (clientWidth - imageWidth * newScale) / 2
  translateY.value = (clientHeight - imageHeight * newScale) / 2
}

// --- Zoom Logic ---
const handleWheel = (e) => {
  if (!container.value) return

  const rect = container.value.getBoundingClientRect()
  const mouseX = e.clientX - rect.left
  const mouseY = e.clientY - rect.top

  const delta = e.deltaY > 0 ? (1 - ZOOM_SPEED) : (1 + ZOOM_SPEED)
  let newScale = scale.value * delta
  newScale = Math.min(Math.max(newScale, MIN_SCALE), MAX_SCALE)

  // Zoom to Cursor Formula
  const scaleRatio = newScale / scale.value
  const newX = mouseX - (mouseX - translateX.value) * scaleRatio
  const newY = mouseY - (mouseY - translateY.value) * scaleRatio

  scale.value = newScale
  translateX.value = newX
  translateY.value = newY
}

const zoomIn = () => updateZoomCenter(1 + ZOOM_SPEED)
const zoomOut = () => updateZoomCenter(1 - ZOOM_SPEED)

const updateZoomCenter = (factor) => {
  if (!container.value) return
  
  const { clientWidth, clientHeight } = container.value
  const centerX = clientWidth / 2
  const centerY = clientHeight / 2
  
  let newScale = scale.value * factor
  newScale = Math.min(Math.max(newScale, MIN_SCALE), MAX_SCALE)
  
  const scaleRatio = newScale / scale.value
  const newX = centerX - (centerX - translateX.value) * scaleRatio
  const newY = centerY - (centerY - translateY.value) * scaleRatio
  
  scale.value = newScale
  translateX.value = newX
  translateY.value = newY
}

// --- Pan Logic ---
let startX = 0
let startY = 0
let initialTx = 0
let initialTy = 0

const handleMouseDown = (e) => {
  // Only left click
  if (e.button !== 0) return
  
  isDragging.value = true
  startX = e.clientX
  startY = e.clientY
  initialTx = translateX.value
  initialTy = translateY.value
  
  window.addEventListener('mousemove', handleMouseMove)
  window.addEventListener('mouseup', handleMouseUp)
}

const handleMouseMove = (e) => {
  if (!isDragging.value) return
  e.preventDefault()
  
  const dx = e.clientX - startX
  const dy = e.clientY - startY
  
  let nextTx = initialTx + dx
  let nextTy = initialTy + dy
  
  // Boundary Check (Keep 20% visible)
  if (container.value) {
    const { clientWidth, clientHeight } = container.value
    const curW = imageWidth * scale.value
    const curH = imageHeight * scale.value
    
    // Limits
    const minX = - (curW * 0.8)
    const maxX = clientWidth - (curW * 0.2)
    const minY = - (curH * 0.8)
    const maxY = clientHeight - (curH * 0.2)
    
    // Apply constraints
    if (nextTx < minX) nextTx = minX
    if (nextTx > maxX) nextTx = maxX
    if (nextTy < minY) nextTy = minY
    if (nextTy > maxY) nextTy = maxY
  }

  translateX.value = nextTx
  translateY.value = nextTy
}

const handleMouseUp = () => {
  isDragging.value = false
  window.removeEventListener('mousemove', handleMouseMove)
  window.removeEventListener('mouseup', handleMouseUp)
}

// Resize Observer
let resizeObserver = null
onMounted(() => {
  if (container.value) {
    resizeObserver = new ResizeObserver(() => {
       // Optional: Re-center or adjust constraints
       // For now simple re-fit if totally off? 
       // Or do nothing to let user control
    })
    resizeObserver.observe(container.value)
  }
})

onUnmounted(() => {
  if (resizeObserver) resizeObserver.disconnect()
  window.removeEventListener('mousemove', handleMouseMove)
  window.removeEventListener('mouseup', handleMouseUp)
})

// Reset on source change
watch(() => props.src, () => {
  // Wait for load event
})

</script>

<style scoped>
.image-viewer-container {
  width: 100%;
  height: 100%;
  background: #1a1a1a;
  overflow: hidden;
  position: relative;
  user-select: none;
}

.image-wrapper {
  position: absolute;
  top: 0;
  left: 0;
  transform-origin: 0 0; /* Critical for dynamic translate calculation */
  will-change: transform;
}

.image-wrapper img {
  display: block;
  pointer-events: none;
  /* max-width/height removed to allow scaling */
}

.viewer-controls {
  position: absolute;
  bottom: 1rem;
  right: 1rem;
  display: flex;
  gap: 0.5rem;
  background: rgba(0, 0, 0, 0.7);
  padding: 0.5rem;
  border-radius: 6px;
  align-items: center;
  z-index: 10;
}

.scale-indicator {
  color: #fff;
  font-family: monospace;
  font-size: 0.9rem;
  margin-right: 0.5rem;
  min-width: 3.5em;
  text-align: right;
}

.control-btn {
  background: #444;
  color: #fff;
  border: 1px solid #666;
  width: 30px;
  height: 30px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
  line-height: 1;
  padding: 0;
}

.control-btn:hover {
  background: #666;
}

.reset-btn {
  font-size: 1rem;
}
</style>
