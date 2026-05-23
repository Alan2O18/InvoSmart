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
              <template v-if="cfg.type === 'amount_cells' && Array.isArray(cfg.xList)">
                <label v-for="(xVal, i) in cfg.xList" :key="i">X{{i}}
                  <input
                    type="number"
                    v-model.number="cfg.xList[i]"
                    @blur="syncCanvasFromState"
                    style="width: 45px"
                  />
                </label>
                <label>Y
                  <input
                    type="number"
                    v-model.number="cfg.y"
                    @blur="syncCanvasFromState"
                  />
                </label>
              </template>
              <template v-else>
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
              </template>
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
          <div class="safezone-hint">座標語義：x0/y0 = 左上角，x1/y1 = 右下角</div>
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
import {
  buildVoucherTextPreviewEntries,
  pdfBaselineToCanvasTop,
  canvasTopToPdfBaseline,
} from '../utils/voucher'

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
const previewFontFamily = ref('sans-serif')

const editableFields = reactive({})       // key → mutable copy of textField config
const editableBlockedZones = reactive([]) // mutable array of zone objects
const editableSafeZone = reactive({ x0: 30, y0: 394, x1: 565, y1: 730 })

const canvasSize = reactive({ width: 595, height: 842 })
const previewPixelSize = reactive({ width: 0, height: 0 })
const FIELD_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#ef4444']

// Per-object references on canvas
const fieldFabObjs = {}   // key → main draggable object
const fieldLabelObjs = {} // key → label text
const fieldSampleObjs = {} // key → sample text for boxed fields
const zoneFabObjs = {}    // zoneKey → fabric.Rect
let safeZoneFabObj = null

// ── Helpers ───────────────────────────────────────────────────────────────────
const FIELD_LABELS = {
  voucherNo: '憑證編號', budgetItem: '預算科目', amount: '金額格',
  purpose: '摘要文字框', receiptCount: '收據數量', payDate: '付款日',
  paymentAmount: '付款金額',
}
const FIELD_SAMPLES = {
  voucherNo: 'D-16-01',
  budgetItem: '膳食費',
  amount: '※12345',
  purpose: '範例摘要文字\n（可拖曳調整）',
  receiptCount: '3',
  // buildVoucherTextPreviewEntries expects ROC/ISO input.
  payDate: '2026-03-15',
  paymentAmount: '12,345',
}
const fieldLabel = (key) => FIELD_LABELS[key] || key
const fieldSample = (key) => FIELD_SAMPLES[key] || `範例-${key}`
const getBaselineRatio = (cfg) => {
  const ratio = Number(cfg?.preview?.baselineRatio)
  return Number.isFinite(ratio) ? ratio : 0.82
}

const buildFieldPreviewEntries = (key, cfg) => {
  const sampleFields = {
    voucherNo: FIELD_SAMPLES.voucherNo,
    budgetItem: FIELD_SAMPLES.budgetItem,
    receiptCount: FIELD_SAMPLES.receiptCount,
    payDate: FIELD_SAMPLES.payDate,
    amount: FIELD_SAMPLES.paymentAmount.replace(/,/g, ''),
    purpose: FIELD_SAMPLES.purpose,
  }
  const entries = buildVoucherTextPreviewEntries(sampleFields, {
    fields: { [key]: cfg },
    font: { family: previewFontFamily.value },
  })

  if (key === 'voucherNo') {
    return entries.filter(entry => String(entry.key).startsWith('voucherNo-'))
  }
  if (key === 'purpose') {
    return entries.filter(entry => entry.key === 'purpose')
  }
  return entries.filter(entry => entry.key === key)
}

const fitPreviewFontSize = (entry) => {
  if (!entry.autoScale || !entry.maxWidth) return entry.fontSize
  for (let fontSize = entry.fontSize; fontSize >= entry.minFontSize; fontSize -= 1) {
    const probe = new fabric.Text(entry.text, {
      left: entry.left,
      top: entry.top,
      fontSize,
      fontFamily: entry.fontFamily,
      originX: 'left',
      originY: 'top',
    })
    if (probe.getScaledWidth() <= entry.maxWidth) {
      return fontSize
    }
  }
  return entry.minFontSize
}

const createPointFieldPreviewGroup = (key, cfg, color) => {
  const entries = buildFieldPreviewEntries(key, cfg)
  if (!entries.length) {
    return null
  }

  const minLeft = Math.min(...entries.map(entry => Number(entry.left) || 0))
  const minTop = Math.min(...entries.map(entry => Number(entry.top) || 0))
  const objects = entries.map(entry => {
    const fontSize = fitPreviewFontSize(entry)
    return new fabric.Text(entry.text, {
      left: (Number(entry.left) || 0) - minLeft,
      top: (Number(entry.top) || 0) - minTop,
      fontSize,
      fontFamily: entry.fontFamily,
      fill: color,
      backgroundColor: `${color}1A`,
      selectable: false,
      evented: false,
      originX: 'left',
      originY: 'top',
      excludeFromExport: true,
    })
  })

  const group = new fabric.Group(objects, {
    left: minLeft,
    top: minTop,
    originX: 'left',
    originY: 'top',
    lockScalingX: true,
    lockScalingY: true,
    backgroundColor: undefined,
  })
  group.data = {
    kind: 'field_anchor',
    key,
    primaryFontSize: Number(entries[0]?.fontSize) || Number(cfg.fontSize) || 16,
  }
  return group
}

const loadCanvasPreviewFont = async (fontConfig) => {
  const family = String(fontConfig?.family || '').trim()
  const url = String(fontConfig?.url || '').trim()
  if (!family || !url || !window.FontFace) {
    return
  }

  previewFontFamily.value = family
  try {
    if (document.fonts?.check?.(`12px "${family}"`)) {
      return
    }
    const fontFace = new window.FontFace(family, `url(${api.toAbsoluteUrl(url)})`)
    const loaded = await fontFace.load()
    document.fonts?.add(loaded)
  } catch (error) {
    console.warn('voucher preview font load failed in config view', error)
    previewFontFamily.value = 'sans-serif'
  }
}

const fieldPoint = (cfg) => {
  if (cfg.point) return cfg.point[0]
  if (cfg.type === 'amount_cells' && Array.isArray(cfg.xList) && cfg.xList.length > 0) {
    return Math.min(...cfg.xList)
  }
  if (cfg.rect) return cfg.rect[0]
  return 0
}
const fieldPointY = (cfg) => {
  if (cfg.point) return cfg.point[1]
  if (cfg.type === 'amount_cells' && Number.isFinite(Number(cfg.y))) {
    return Number(cfg.y)
  }
  if (cfg.rect) return cfg.rect[1]
  return 0
}
const onPointXInput = (key, e) => {
  const v = parseFloat(e.target.value)
  if (isNaN(v)) return
  const cfg = editableFields[key]
  if (cfg.point) {
    cfg.point[0] = v
  } else if (cfg.type === 'amount_cells' && Array.isArray(cfg.xList) && cfg.xList.length > 0) {
    const oldMin = Math.min(...cfg.xList)
    const dx = v - oldMin
    cfg.xList = cfg.xList.map(x => x + dx)
  } else if (cfg.rect) {
    cfg.rect[0] = v
  }
}
const onPointYInput = (key, e) => {
  const v = parseFloat(e.target.value)
  if (isNaN(v)) return
  const cfg = editableFields[key]
  if (cfg.point) {
    cfg.point[1] = v
  } else if (cfg.type === 'amount_cells') {
    cfg.y = v
  } else if (cfg.rect) {
    cfg.rect[1] = v
  }
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
  const labelObj = fieldLabelObjs[key]
  const sampleObj = fieldSampleObjs[key]

  const updateLabel = (x, y) => {
    if (!fieldLabelObjs[key]) return
    fieldLabelObjs[key].set({ left: x, top: y - 14 })
    fieldLabelObjs[key].setCoords()
  }

  const ensureLabel = (x, y) => {
    if (fieldLabelObjs[key]) {
      updateLabel(x, y)
      return
    }
    const label = new fabric.Text(fieldLabel(key), {
      left: x, top: y - 14,
      fontSize: 10, fill: color, fontFamily: 'sans-serif',
      selectable: false, evented: false,
      excludeFromExport: true,
      originX: 'left', originY: 'top',
    })
    fieldLabelObjs[key] = label
    fabricCanvas.add(label)
  }

  // 1) Textbox field: draggable rect + sample text inside.
  if (cfg.type === 'textbox' && cfg.rect) {
    const [rx, ry, rx2, ry2] = cfg.rect
    const width = Math.max(10, rx2 - rx)
    const height = Math.max(10, ry2 - ry)

    if (fieldFabObjs[key]) {
      fieldFabObjs[key].set({ left: rx, top: ry, width, height })
      fieldFabObjs[key].setCoords()
      if (sampleObj) {
        sampleObj.set({ left: rx + 6, top: ry + 6, width: Math.max(20, width - 12), fontSize: Number(cfg.fontSize) || 16 })
        sampleObj.setCoords()
      }
      ensureLabel(rx, ry)
      return
    }

    const rect = new fabric.Rect({
      left: rx,
      top: ry,
      width,
      height,
      fill: `${color}22`,
      stroke: color,
      strokeWidth: 1.5,
      strokeDashArray: [5, 3],
      originX: 'left',
      originY: 'top',
      lockScalingFlip: true,
      cornerColor: color,
    })
    const sample = new fabric.Textbox(fieldSample(key), {
      left: rx + 6,
      top: ry + 6,
      width: Math.max(20, width - 12),
      fontSize: Number(cfg.fontSize) || 16,
      fill: color,
      editable: false,
      selectable: false,
      evented: false,
      excludeFromExport: true,
      fontFamily: previewFontFamily.value,
      originX: 'left', originY: 'top',
    })

    rect.data = { kind: 'field_anchor', key }
    fieldFabObjs[key] = rect
    fieldSampleObjs[key] = sample
    ensureLabel(rx, ry)

    rect.on('moving', () => {
      syncFieldFromFabricObj(key, rect)
      const [nx, ny] = cfg.rect
      sample.set({ left: nx + 6, top: ny + 6 })
      sample.setCoords()
      updateLabel(nx, ny)
      selectedKey.value = key
    })
    rect.on('scaling', () => {
      syncFieldFromFabricObj(key, rect)
      const [nx, ny, nx2, ny2] = cfg.rect
      sample.set({ left: nx + 6, top: ny + 6, width: Math.max(20, nx2 - nx - 12) })
      sample.setCoords()
      updateLabel(nx, ny)
    })

    fabricCanvas.add(rect)
    fabricCanvas.add(sample)
    return
  }

  // 2) Amount cells: draggable box for EACH digit.
  if (cfg.type === 'amount_cells' && Array.isArray(cfg.xList) && cfg.xList.length > 0) {
    const fontSize = Number(cfg.fontSize) || 16
    const rawY = Number(cfg.y) || 0
    const top = pdfBaselineToCanvasTop(rawY, fontSize, getBaselineRatio(cfg))
    const width = 16
    const height = fontSize + 4
    const digitLabels = ['十萬', '萬', '千', '百', '十', '元']

    cfg.xList.forEach((rawX, idx) => {
      const subKey = `${key}-${idx}`
      const renderLeft = rawX - 2
      const digitName = digitLabels[digitLabels.length - cfg.xList.length + idx] || `${idx}`
      const myColor = FIELD_COLORS[(colorIdx + idx) % FIELD_COLORS.length]
      
      const updateSubLabel = (lx, ly) => {
        if (fieldLabelObjs[subKey]) {
          fieldLabelObjs[subKey].set({ left: lx, top: ly - 14 })
          fieldLabelObjs[subKey].setCoords()
        }
      }

      const ensureSubLabel = (lx, ly) => {
        if (fieldLabelObjs[subKey]) {
          updateSubLabel(lx, ly)
          return
        }
        const labelText = new fabric.Text(digitName, {
          left: lx, top: ly - 14,
          fontSize: 10, fill: myColor, fontFamily: 'sans-serif',
          selectable: false, evented: false, excludeFromExport: true,
          originX: 'left', originY: 'top',
        })
        fieldLabelObjs[subKey] = labelText
        fabricCanvas.add(labelText)
      }

      if (fieldFabObjs[subKey]) {
        fieldFabObjs[subKey].set({ left: renderLeft, top, width, height })
        fieldFabObjs[subKey].setCoords()
        if (fieldSampleObjs[subKey]) {
          fieldSampleObjs[subKey].set({ left: renderLeft + 2, top: top + 2, fontSize })
          fieldSampleObjs[subKey].setCoords()
        }
        ensureSubLabel(renderLeft, top)
      } else {
        const rect = new fabric.Rect({
          left: renderLeft, top, width, height,
          fill: `${myColor}1A`, stroke: myColor, strokeWidth: 1.5, strokeDashArray: [4, 4],
          originX: 'left', originY: 'top', lockScalingFlip: true, lockScalingX: true, lockScalingY: true, cornerColor: myColor,
        })
        const sampleText = new fabric.Text('※', {
          left: renderLeft + 2, top: top + 2, fontSize, fill: myColor,
          selectable: false, evented: false, excludeFromExport: true, fontFamily: previewFontFamily.value, originX: 'left', originY: 'top',
        })

        rect.data = { kind: 'field_anchor', key, subKey, idx }
        fieldFabObjs[subKey] = rect
        fieldSampleObjs[subKey] = sampleText
        ensureSubLabel(renderLeft, top)

        rect.on('moving', () => {
          const newTop = rect.top
          // Sync state for this specific digit
          cfg.xList[idx] = Math.round(rect.left + 2)
          cfg.y = Math.round(canvasTopToPdfBaseline(newTop, fontSize, getBaselineRatio(cfg)))

          sampleText.set({ left: rect.left + 2, top: newTop + 2 })
          sampleText.setCoords()
          updateSubLabel(rect.left, newTop)
          
          // Force visual sync of Y for siblings
          cfg.xList.forEach((_, sIdx) => {
            if (sIdx !== idx) {
              const sr = fieldFabObjs[`${key}-${sIdx}`]
              const ss = fieldSampleObjs[`${key}-${sIdx}`]
              if (sr) { sr.set({ top: newTop }); sr.setCoords(); updateSubLabel(sr.left, newTop) }
              if (ss) { ss.set({ top: newTop + 2 }); ss.setCoords() }
            }
          })
          selectedKey.value = key
        })

        fabricCanvas.add(rect)
        fabricCanvas.add(sampleText)
      }
    })
    return
  }

  // 3) Normal text field: draggable sample text directly.
  if (fieldFabObjs[key]) {
    fabricCanvas.remove(fieldFabObjs[key])
    delete fieldFabObjs[key]
  }

  const group = createPointFieldPreviewGroup(key, cfg, color)
  if (!group) {
    return
  }

  fieldFabObjs[key] = group
  ensureLabel(group.left, group.top)

  group.on('moving', () => {
    syncFieldFromFabricObj(key, group)
    updateLabel(group.left, group.top)
    selectedKey.value = key
  })

  fabricCanvas.add(group)
  if (fieldLabelObjs[key]) {
    fabricCanvas.bringObjectToFront(fieldLabelObjs[key])
  }
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
    const previewFontSize = Number(obj?.data?.primaryFontSize) || Number(cfg.fontSize) || 16
    cfg.point[1] = Math.round(canvasTopToPdfBaseline(obj.top, previewFontSize, getBaselineRatio(cfg)))
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
  const syncSafeZoneFromObj = (obj, normalize = false) => {
    const left = Number(obj.left) || 0
    const top = Number(obj.top) || 0
    const width = Math.max(10, Number(obj.getScaledWidth()) || Number(obj.width) || 10)
    const height = Math.max(10, Number(obj.getScaledHeight()) || Number(obj.height) || 10)

    if (normalize) {
      // Normalize transform into width/height so scaling remains linear and predictable.
      obj.set({ left, top, width, height, scaleX: 1, scaleY: 1 })
      obj.setCoords()
    }

    editableSafeZone.x0 = Math.round(left)
    editableSafeZone.y0 = Math.round(top)
    editableSafeZone.x1 = Math.round(left + width)
    editableSafeZone.y1 = Math.round(top + height)
  }

  if (safeZoneFabObj) {
    safeZoneFabObj.set({
      left: sz.x0, top: sz.y0,
      width: sz.x1 - sz.x0, height: sz.y1 - sz.y0,
      scaleX: 1,
      scaleY: 1,
    })
    safeZoneFabObj.setCoords()
    return
  }
  const obj = new fabric.Rect({
    left: sz.x0, top: sz.y0,
    width: sz.x1 - sz.x0, height: sz.y1 - sz.y0,
    fill: 'rgba(34,197,94,0.06)',
    stroke: '#22c55e', strokeDashArray: [8, 6],
    strokeWidth: 2,
    cornerColor: '#22c55e',
    transparentCorners: false,
    originX: 'left',
    originY: 'top',
    centeredScaling: false,
    lockScalingFlip: true,
    lockRotation: true,
    selectable: true, evented: true,
    excludeFromExport: true,
  })
  safeZoneFabObj = obj
  
  obj.on('moving', () => {
    syncSafeZoneFromObj(obj, false)
  })
  obj.on('scaling', () => {
    // During drag-resize, only mirror coordinates; don't rewrite transform,
    // otherwise Fabric side-handle math can drift/jitter.
    syncSafeZoneFromObj(obj, false)
  })
  obj.on('modified', () => {
    // Normalize once after interaction ends to keep width/height canonical.
    syncSafeZoneFromObj(obj, true)
  })
  
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
    width: canvasSize.width, height: canvasSize.height,
    backgroundColor: '#e5e7eb',
    preserveObjectStacking: true,
    centeredScaling: false,
  })

  // Always render editable controls first, so the left panel is usable immediately.
  buildCanvasObjects()

  // Background image
  if (templatePng) {
    const imgElement = new window.Image()
    imgElement.onload = () => {
      if (!fabricCanvas) return
      
      const imgObj = new fabric.Image(imgElement)
      // Determine real width/height 
      const naturalW = imgElement.naturalWidth || imgElement.width || 1
      const naturalH = imgElement.naturalHeight || imgElement.height || 1
      
      const scaleX = canvasSize.width / naturalW
      const scaleY = canvasSize.height / naturalH
      
      imgObj.set({
        scaleX: scaleX,
        scaleY: scaleY,
        left: 0,
        top: 0,
        originX: 'left',
        originY: 'top',
        selectable: false,
        evented: false,
        excludeFromExport: true,
      })

      fabricCanvas.backgroundImage = imgObj
      fabricCanvas.requestRenderAll()
    }
    imgElement.src = `data:image/png;base64,${templatePng}`
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
    const preview = previewResp.data || {}

    // Keep canvas space in sync with the real PDF page dimensions.
    const pageWidth = Number(preview.pageWidth)
    const pageHeight = Number(preview.pageHeight)
    if (pageWidth > 0 && pageHeight > 0) {
      canvasSize.width = pageWidth
      canvasSize.height = pageHeight
    }
    previewPixelSize.width = Number(preview.previewPixelWidth) || 0
    previewPixelSize.height = Number(preview.previewPixelHeight) || 0

    // Populate editable fields (deep clone)
    const fields = layout.textFields || layout.fields || {}
    Object.keys(fields).forEach(k => {
      editableFields[k] = JSON.parse(JSON.stringify(fields[k]))
    })

    await loadCanvasPreviewFont(layout.font)

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
    initCanvas(preview.templatePng)
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

.safezone-hint {
  font-size: 0.76rem;
  color: #9ca3af;
  margin-bottom: 0.45rem;
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
