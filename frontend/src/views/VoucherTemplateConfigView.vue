<template>
  <div class="vtc-view">
    <header class="vtc-header">
      <button class="back-btn" @click="$router.push('/settings')">← 返回設定</button>
      <h1>📐 憑證範本座標設定</h1>
      <div class="header-actions">
        <button class="reset-btn" @click="resetToDefaults" :disabled="saving">重置預設</button>
        <button class="save-btn" @click="saveConfig" :disabled="saving">
          {{ saving ? '儲存中...' : '💾 儲存設定' }}
        </button>
      </div>
    </header>

    <div v-if="loading" class="loading">載入範本中...</div>
    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <div v-else class="vtc-body">
      <!-- Left: canvas -->
      <div class="canvas-panel">
        <div class="canvas-hint">
          拖移 <span class="chip text-chip">文字錨點</span> 或 <span class="chip zone-chip">蓋章死區</span> 調整位置；縮放死區四角調整大小
        </div>
        <div class="canvas-wrap" ref="canvasWrapRef">
          <canvas ref="canvasRef"></canvas>
        </div>
      </div>

      <!-- Right: inspector -->
      <div class="inspector-panel">
        <section class="inspector-section">
          <h3>📝 文字欄位座標</h3>
          <div
            v-for="(cfg, key) in editableFields"
            :key="key"
            class="field-row"
            :class="{ active: selectedKey === key }"
            @click="selectField(key)"
          >
            <span class="field-name">{{ fieldLabel(key) }}</span>
            <div class="coord-inputs">
              <label>X
                <input
                  type="number"
                  :value="fieldPoint(cfg)"
                  @input="onPointXInput(key, $event)"
                  @blur="syncCanvasFromState"
                />
              </label>
              <label>Y
                <input
                  type="number"
                  :value="fieldPointY(cfg)"
                  @input="onPointYInput(key, $event)"
                  @blur="syncCanvasFromState"
                />
              </label>
              <label v-if="cfg.fontSize !== undefined">字級
                <input
                  type="number"
                  v-model.number="cfg.fontSize"
                  @blur="syncCanvasFromState"
                  min="6" max="36"
                />
              </label>
            </div>
          </div>
        </section>

        <section class="inspector-section">
          <h3>🚫 蓋章死區 (Blocked Zones)</h3>
          <div
            v-for="(zone, idx) in editableBlockedZones"
            :key="zone.key"
            class="field-row"
            :class="{ active: selectedZoneKey === zone.key }"
            @click="selectZone(zone.key)"
          >
            <span class="field-name">{{ zone.label || zone.key }}</span>
            <div class="coord-inputs">
              <label>X <input type="number" v-model.number="zone.rect[0]" @blur="syncCanvasFromState" /></label>
              <label>Y <input type="number" v-model.number="zone.rect[1]" @blur="syncCanvasFromState" /></label>
              <label>W <input type="number" v-model.number="zone.rect[2]" @blur="syncCanvasFromState" /></label>
              <label>H <input type="number" v-model.number="zone.rect[3]" @blur="syncCanvasFromState" /></label>
            </div>
            <label class="toggle-vis">
              <input type="checkbox" v-model="zone.visible" @change="syncCanvasFromState" />
              顯示
            </label>
          </div>
          <button class="add-zone-btn" @click="addBlockedZone">+ 新增死區</button>
        </section>

        <section class="inspector-section">
          <h3>🟩 安全區 (Safe Zone)</h3>
          <div class="coord-inputs four-col">
            <label>x0 <input type="number" v-model.number="editableSafeZone.x0" @blur="syncCanvasFromState" /></label>
            <label>y0 <input type="number" v-model.number="editableSafeZone.y0" @blur="syncCanvasFromState" /></label>
            <label>x1 <input type="number" v-model.number="editableSafeZone.x1" @blur="syncCanvasFromState" /></label>
            <label>y1 <input type="number" v-model.number="editableSafeZone.y1" @blur="syncCanvasFromState" /></label>
          </div>
        </section>
      </div>
    </div>

    <div v-if="saveMsg" class="save-toast" :class="{ error: saveError }">{{ saveMsg }}</div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as fabric from 'fabric'
import api from '../services/api'

// ── State ─────────────────────────────────────────────────────────────────────
const canvasRef = ref(null)
const canvasWrapRef = ref(null)
let fabricCanvas = null

const loading = ref(true)
const error = ref('')
const saving = ref(false)
const saveMsg = ref('')
const saveError = ref(false)

const selectedKey = ref(null)
const selectedZoneKey = ref(null)

const editableFields = reactive({})       // key → mutable copy of textField config
const editableBlockedZones = reactive([]) // mutable array of zone objects
const editableSafeZone = reactive({ x0: 30, y0: 394, x1: 565, y1: 730 })

const CANVAS_W = 595
const CANVAS_H = 842
const FIELD_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#ef4444']

// Per-object references on canvas
const fieldFabObjs = {}   // key → fabric.Circle or fabric.Rect
const zoneFabObjs = {}    // zoneKey → fabric.Rect
let safeZoneFabObj = null

// ── Helpers ───────────────────────────────────────────────────────────────────
const FIELD_LABELS = {
  voucherNo: '憑證編號', budgetItem: '預算科目', amount: '金額格',
  purpose: '摘要文字框', receiptCount: '收據數量', payDate: '付款日',
  paymentAmount: '付款金額',
}
const fieldLabel = (key) => FIELD_LABELS[key] || key

const fieldPoint = (cfg) => {
  if (cfg.point) return cfg.point[0]
  if (cfg.rect) return cfg.rect[0]
  return 0
}
const fieldPointY = (cfg) => {
  if (cfg.point) return cfg.point[1]
  if (cfg.rect) return cfg.rect[1]
  return 0
}
const onPointXInput = (key, e) => {
  const v = parseFloat(e.target.value)
  if (isNaN(v)) return
  const cfg = editableFields[key]
  if (cfg.point) cfg.point[0] = v
  else if (cfg.rect) cfg.rect[0] = v
}
const onPointYInput = (key, e) => {
  const v = parseFloat(e.target.value)
  if (isNaN(v)) return
  const cfg = editableFields[key]
  if (cfg.point) cfg.point[1] = v
  else if (cfg.rect) cfg.rect[1] = v
}

// ── Canvas helpers ─────────────────────────────────────────────────────────────
const selectField = (key) => {
  selectedKey.value = key
  selectedZoneKey.value = null
  if (fieldFabObjs[key]) fabricCanvas.setActiveObject(fieldFabObjs[key])
  fabricCanvas.requestRenderAll()
}
const selectZone = (key) => {
  selectedZoneKey.value = key
  selectedKey.value = null
  if (zoneFabObjs[key]) fabricCanvas.setActiveObject(zoneFabObjs[key])
  fabricCanvas.requestRenderAll()
}

// Draw or update a text field anchor on canvas
const upsertFieldAnchor = (key, cfg, colorIdx) => {
  const color = FIELD_COLORS[colorIdx % FIELD_COLORS.length]
  let x = 0, y = 0
  if (cfg.point) { x = cfg.point[0]; y = cfg.point[1] }
  else if (cfg.rect) { x = cfg.rect[0]; y = cfg.rect[1] }

  if (fieldFabObjs[key]) {
    fieldFabObjs[key].set({ left: x, top: y })
    fieldFabObjs[key].setCoords()
    return
  }

  const isBox = cfg.type === 'textbox' || cfg.type === 'amount_cells'
  let obj
  if (isBox && cfg.rect) {
    const [rx, ry, rx2, ry2] = cfg.rect
    obj = new fabric.Rect({
      left: rx, top: ry,
      width: rx2 - rx, height: ry2 - ry,
      fill: `${color}22`,
      stroke: color, strokeWidth: 1.5,
      strokeDashArray: [5, 3],
      originX: 'left', originY: 'top',
      lockScalingFlip: true,
    })
  } else {
    obj = new fabric.Circle({
      left: x, top: y, radius: 6,
      fill: color, stroke: '#fff', strokeWidth: 1.5,
      originX: 'center', originY: 'center',
    })
  }
  const label = new fabric.Text(fieldLabel(key), {
    left: x + 8, top: y - 14,
    fontSize: 10, fill: color, fontFamily: 'sans-serif',
    selectable: false, evented: false,
    excludeFromExport: true,
  })

  obj.data = { kind: 'field_anchor', key }
  fieldFabObjs[key] = obj

  obj.on('moving', () => {
    syncFieldFromFabricObj(key, obj)
    label.set({ left: obj.left + 8, top: obj.top - 14 })
    selectedKey.value = key
  })
  obj.on('scaling', () => { syncFieldFromFabricObj(key, obj) })

  fabricCanvas.add(obj)
  fabricCanvas.add(label)
}

const syncFieldFromFabricObj = (key, obj) => {
  const cfg = editableFields[key]
  if (!cfg) return
  if (cfg.type === 'textbox' && cfg.rect) {
    cfg.rect[0] = Math.round(obj.left)
    cfg.rect[1] = Math.round(obj.top)
    cfg.rect[2] = Math.round(obj.left + obj.getScaledWidth())
    cfg.rect[3] = Math.round(obj.top + obj.getScaledHeight())
  } else if (cfg.point) {
    cfg.point[0] = Math.round(obj.left)
    cfg.point[1] = Math.round(obj.top)
  }
}

const upsertZoneRect = (zone) => {
  const [x, y, w, h] = zone.rect
  const visible = zone.visible !== false
  if (zoneFabObjs[zone.key]) {
    zoneFabObjs[zone.key].set({
      left: x, top: y, width: w, height: h,
      visible,
    })
    zoneFabObjs[zone.key].setCoords()
    return
  }
  const obj = new fabric.Rect({
    left: x, top: y, width: w, height: h,
    fill: 'rgba(239, 68, 68, 0.18)',
    stroke: '#ef4444', strokeWidth: 2,
    transparentCorners: false,
    cornerColor: '#ef4444',
    visible,
  })
  obj.data = { kind: 'blocked_zone', key: zone.key }
  zoneFabObjs[zone.key] = obj
  obj.on('moving', () => {
    const idx = editableBlockedZones.findIndex(z => z.key === zone.key)
    if (idx < 0) return
    editableBlockedZones[idx].rect[0] = Math.round(obj.left)
    editableBlockedZones[idx].rect[1] = Math.round(obj.top)
    selectedZoneKey.value = zone.key
  })
  obj.on('scaling', () => {
    const idx = editableBlockedZones.findIndex(z => z.key === zone.key)
    if (idx < 0) return
    editableBlockedZones[idx].rect[0] = Math.round(obj.left)
    editableBlockedZones[idx].rect[1] = Math.round(obj.top)
    editableBlockedZones[idx].rect[2] = Math.round(obj.getScaledWidth())
    editableBlockedZones[idx].rect[3] = Math.round(obj.getScaledHeight())
    selectedZoneKey.value = zone.key
  })
  fabricCanvas.add(obj)
}

const upsertSafeZoneRect = () => {
  const sz = editableSafeZone
  if (safeZoneFabObj) {
    safeZoneFabObj.set({
      left: sz.x0, top: sz.y0,
      width: sz.x1 - sz.x0, height: sz.y1 - sz.y0,
    })
    safeZoneFabObj.setCoords()
    return
  }
  const obj = new fabric.Rect({
    left: sz.x0, top: sz.y0,
    width: sz.x1 - sz.x0, height: sz.y1 - sz.y0,
    fill: 'rgba(34,197,94,0.04)',
    stroke: '#22c55e', strokeDashArray: [8, 6],
    strokeWidth: 1,
    selectable: false, evented: false,
    excludeFromExport: true,
  })
  safeZoneFabObj = obj
  fabricCanvas.add(obj)
}

// Re-sync all canvas objects from editable state (called after input blur)
const syncCanvasFromState = () => {
  Object.keys(editableFields).forEach((key, idx) => {
    upsertFieldAnchor(key, editableFields[key], idx)
  })
  editableBlockedZones.forEach(zone => upsertZoneRect(zone))
  upsertSafeZoneRect()
  fabricCanvas.requestRenderAll()
}

// ── Init ──────────────────────────────────────────────────────────────────────
const initCanvas = (templatePng) => {
  if (fabricCanvas) { fabricCanvas.dispose(); fabricCanvas = null }

  fabricCanvas = new fabric.Canvas(canvasRef.value, {
    width: CANVAS_W, height: CANVAS_H,
    backgroundColor: '#e5e7eb',
    preserveObjectStacking: true,
  })

  // Always render editable controls first, so the left panel is usable immediately.
  buildCanvasObjects()

  // Background image
  if (templatePng) {
    const img = new window.Image()
    img.onload = () => {
      if (!fabricCanvas) return
      const bg = new fabric.Image(img, {
        left: 0, top: 0,
        selectable: false, evented: false, excludeFromExport: true,
      })
      bg.data = { kind: 'background' }
      if (bg.width && bg.height) {
        bg.scaleX = CANVAS_W / bg.width
        bg.scaleY = CANVAS_H / bg.height
      }
      fabricCanvas.add(bg)
      bg.sendToBack()
      fabricCanvas.requestRenderAll()
    }
    img.onerror = () => {
      // Keep interactive objects even when template image fails.
      fabricCanvas?.requestRenderAll()
    }
    img.src = `data:image/png;base64,${templatePng}`
  }
}

const buildCanvasObjects = () => {
  upsertSafeZoneRect()
  editableBlockedZones.forEach(zone => upsertZoneRect(zone))
  Object.keys(editableFields).forEach((key, idx) => {
    upsertFieldAnchor(key, editableFields[key], idx)
  })
  fabricCanvas.requestRenderAll()
}

// ── Load data ─────────────────────────────────────────────────────────────────
onMounted(async () => {
  try {
    const [layoutResp, previewResp] = await Promise.all([
      api.getVoucherTemplateLayout(),
      api.getVoucherTemplatePreview(),
    ])
    const layout = layoutResp.data

    // Populate editable fields (deep clone)
    const fields = layout.textFields || layout.fields || {}
    Object.keys(fields).forEach(k => {
      editableFields[k] = JSON.parse(JSON.stringify(fields[k]))
    })

    // Populate blocked zones
    const zones = layout.blockedZones || []
    zones.forEach(z => editableBlockedZones.push(JSON.parse(JSON.stringify(z))))

    // Safe zone
    if (layout.safeZone) {
      Object.assign(editableSafeZone, layout.safeZone)
    }

    // Mark loading done so Vue renders the canvas element in the DOM
    loading.value = false
    await nextTick()
    initCanvas(previewResp.data?.templatePng)
  } catch (e) {
    error.value = `載入失敗: ${e.message || e}`
    loading.value = false
  }
})

onBeforeUnmount(() => {
  if (fabricCanvas) { fabricCanvas.dispose(); fabricCanvas = null }
})

// ── Add blocked zone ───────────────────────────────────────────────────────────
const addBlockedZone = () => {
  const sz = editableSafeZone
  const newZone = {
    key: `zone_${Date.now()}`,
    rect: [sz.x0 + 20, sz.y0 + 20, 80, 60],
    label: '新死區',
    visible: true,
  }
  editableBlockedZones.push(newZone)
  upsertZoneRect(newZone)
  fabricCanvas.requestRenderAll()
  selectZone(newZone.key)
}

// ── Save / Reset ───────────────────────────────────────────────────────────────
const saveConfig = async () => {
  saving.value = true
  saveMsg.value = ''
  saveError.value = false
  try {
    // Build textFields payload from editableFields
    const textFields = {}
    Object.keys(editableFields).forEach(k => {
      textFields[k] = JSON.parse(JSON.stringify(editableFields[k]))
    })
    const blockedZones = editableBlockedZones.map(z => JSON.parse(JSON.stringify(z)))
    const safeZone = { ...editableSafeZone }

    await api.saveVoucherTemplateLayout({ textFields, blockedZones, safeZone })
    saveMsg.value = '✅ 儲存成功！下次進入憑證編輯器即生效。'
    setTimeout(() => { saveMsg.value = '' }, 4000)
  } catch (e) {
    saveMsg.value = `❌ 儲存失敗: ${e.message || e}`
    saveError.value = true
  } finally {
    saving.value = false
  }
}

const resetToDefaults = async () => {
  if (!confirm('確定重置為系統預設排版嗎？此操作無法復原。')) return
  saving.value = true
  try {
    // PUT with empty payload deletes custom overrides → trigger fallback to defaults
    await api.saveVoucherTemplateLayout({})
    // Reload
    window.location.reload()
  } catch (e) {
    saveMsg.value = `❌ 重置失敗: ${e.message || e}`
    saveError.value = true
    saving.value = false
  }
}
</script>

<style scoped>
.vtc-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #111;
  color: #e0e0e0;
  font-family: sans-serif;
}

.vtc-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1.5rem;
  background: #1a1a1a;
  border-bottom: 1px solid #333;
  flex-shrink: 0;
}
.vtc-header h1 { flex: 1; font-size: 1.1rem; margin: 0; }

.back-btn {
  background: none; border: 1px solid #555; color: #aaa;
  padding: 0.4rem 0.8rem; border-radius: 4px; cursor: pointer;
}
.back-btn:hover { border-color: #aaa; color: #fff; }

.header-actions { display: flex; gap: 0.5rem; }
.reset-btn {
  background: none; border: 1px solid #ef4444; color: #ef4444;
  padding: 0.4rem 1rem; border-radius: 4px; cursor: pointer;
}
.reset-btn:hover { background: rgba(239,68,68,0.1); }
.save-btn {
  background: #059669; border: none; color: #fff;
  padding: 0.4rem 1.2rem; border-radius: 4px; cursor: pointer; font-weight: bold;
}
.save-btn:hover:not(:disabled) { background: #047857; }
.save-btn:disabled,.reset-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.loading, .error-msg {
  text-align: center; padding: 3rem; color: #888;
}
.error-msg { color: #ef4444; }

.vtc-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ── Canvas panel ── */
.canvas-panel {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 1rem;
  overflow: auto;
  background: #1a1a1a;
}
.canvas-hint {
  font-size: 0.8rem; color: #888; margin-bottom: 0.5rem; text-align: center;
}
.chip {
  display: inline-block; padding: 1px 6px; border-radius: 3px;
  font-size: 0.78rem; font-weight: bold;
}
.text-chip { background: rgba(59,130,246,0.25); color: #93c5fd; }
.zone-chip { background: rgba(239,68,68,0.25); color: #fca5a5; }

.canvas-wrap {
  background: linear-gradient(135deg, #111827, #1f2937);
  padding: 12px;
  border: 1px solid #444;
  box-shadow: 0 4px 20px rgba(0,0,0,0.5);
}

/* ── Inspector panel ── */
.inspector-panel {
  flex: 1;
  overflow-y: auto;
  padding: 1rem 1.25rem;
  border-left: 1px solid #2a2a2a;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.inspector-section h3 {
  font-size: 0.9rem;
  color: #aaa;
  margin: 0 0 0.75rem;
  border-bottom: 1px solid #2a2a2a;
  padding-bottom: 0.4rem;
}

.field-row {
  padding: 0.5rem 0.6rem;
  border-radius: 5px;
  cursor: pointer;
  border: 1px solid transparent;
  margin-bottom: 0.4rem;
  transition: border-color 0.15s;
}
.field-row:hover { border-color: #444; }
.field-row.active { border-color: #3b82f6; background: rgba(59,130,246,0.06); }

.field-name {
  display: block;
  font-size: 0.8rem;
  color: #9ca3af;
  margin-bottom: 0.3rem;
}

.coord-inputs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}
.coord-inputs.four-col label { flex: 1 1 calc(50% - 0.4rem); }

.coord-inputs label {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.78rem;
  color: #aaa;
}

.coord-inputs input {
  width: 60px;
  background: #2a2a2a;
  border: 1px solid #444;
  border-radius: 3px;
  color: #e0e0e0;
  padding: 2px 4px;
  font-size: 0.78rem;
}

.toggle-vis {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.78rem;
  color: #aaa;
  margin-top: 0.3rem;
  cursor: pointer;
}

.add-zone-btn {
  margin-top: 0.5rem;
  background: none;
  border: 1px dashed #555;
  color: #888;
  padding: 0.35rem 0.8rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.82rem;
}
.add-zone-btn:hover { border-color: #ef4444; color: #ef4444; }

/* ── Toast ── */
.save-toast {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  background: #064e3b;
  color: #6ee7b7;
  border: 1px solid #059669;
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  font-size: 0.9rem;
  box-shadow: 0 4px 12px rgba(0,0,0,0.4);
  z-index: 999;
}
.save-toast.error {
  background: #450a0a;
  color: #fca5a5;
  border-color: #ef4444;
}
</style>
