<template>
  <div class="json-field-editor" :class="{ 'disabled-mode': isJsonInvalid }">
    
    <!-- Validation Guard Overlay -->
    <div v-if="isJsonInvalid" class="validation-overlay">
      <div class="validation-message">
        <h3>⚠️ JSON Syntax Error</h3>
        <p>Please fix the JSON syntax in the editor to enable Form View.</p>
      </div>
    </div>

    <!-- 收據類型 -->
    <div class="field-group">
      <label>收據類型</label>
      <select v-model="formData.receipt_type" :disabled="isJsonInvalid">
        <option value="">請選擇</option>
        <option value="電子發票證明聯">電子發票證明聯</option>
        <option value="免用統一發票收據">免用統一發票收據</option>
        <option value="傳統發票">傳統發票</option>
        <option value="其他">其他</option>
      </select>
    </div>

    <!-- Header 區塊 -->
    <fieldset v-if="formData.header">
      <legend>📋 發票資訊</legend>
      <div class="field-row">
        <label>商家名稱</label>
        <input v-model="formData.header.supplier" list="supplier-list" @blur="saveSuggestion('supplier', formData.header.supplier)" :disabled="isJsonInvalid" />
        <datalist id="supplier-list">
          <option v-for="s in suggestions.supplier" :key="s" :value="s" />
        </datalist>
      </div>
      <div class="field-row">
        <label>統一編號/買受人</label>
        <input v-model="formData.header.buyer" list="buyer-list" @blur="saveSuggestion('buyer', formData.header.buyer)" :disabled="isJsonInvalid" placeholder="買方統編或名稱" />
        <datalist id="buyer-list">
          <option v-for="s in suggestions.buyer" :key="s" :value="s" />
        </datalist>
      </div>
      <div class="field-row">
        <label>發票號碼</label>
        <input v-model="formData.header.invoice_id" :disabled="isJsonInvalid" />
      </div>
      <div class="field-row">
        <label>內部憑證編號</label>
        <input v-model="formData.header.voucher_id" placeholder="自訂流水號 e.g. V-001" :disabled="isJsonInvalid" />
      </div>
      <div class="field-row">
        <label>日期</label>
        <input v-model="formData.header.date" placeholder="YYYY-MM-DD" :disabled="isJsonInvalid" />
      </div>
    </fieldset>

    <!-- Items 區塊 -->
    <fieldset v-if="formData.items">
      <legend>🛒 品項明細</legend>
      <div v-for="(item, idx) in formData.items" :key="idx" class="item-row">
        <input v-model="item.category" placeholder="報帳名目" class="item-cat" list="expense_category-list" @blur="saveSuggestion('expense_category', item.category)" :disabled="isJsonInvalid" />
        <input v-model="item.name" placeholder="品名" class="item-name" list="item_name-list" @blur="saveSuggestion('item_name', item.name)" :disabled="isJsonInvalid" />
        <input v-model.number="item.qty" type="number" placeholder="數量" class="item-num" :disabled="isJsonInvalid" />
        <input v-model.number="item.price" type="number" placeholder="單價" class="item-num" :disabled="isJsonInvalid" />
        <input v-model.number="item.total" type="number" placeholder="小計" class="item-num" :disabled="isJsonInvalid" />
        <button @click="removeItem(idx)" class="remove-btn" :disabled="isJsonInvalid">×</button>
      </div>
      <datalist id="expense_category-list">
        <option v-for="s in suggestions.expense_category" :key="s" :value="s" />
      </datalist>
      <datalist id="item_name-list">
        <option v-for="s in suggestions.item_name" :key="s" :value="s" />
      </datalist>
      <button @click="addItem" class="add-btn" :disabled="isJsonInvalid">+ 新增品項</button>
    </fieldset>

    <!-- Summary 區塊 -->
    <fieldset v-if="formData.summary">
      <legend>💰 金額總結</legend>
      <div class="field-row">
        <label>銷售額</label>
        <input v-model.number="formData.summary.subtotal" type="number" :disabled="isJsonInvalid" placeholder="未稅或含稅小計" />
      </div>
      <div class="field-row">
        <label>稅額</label>
        <input v-model.number="formData.summary.tax" type="number" :disabled="isJsonInvalid" />
      </div>
      <div class="field-row">
        <label>總計金額</label>
        <input v-model.number="formData.summary.total" type="number" :disabled="isJsonInvalid" />
      </div>
    </fieldset>

    <!-- Verification 區塊 -->
    <fieldset v-if="formData.verification">
      <legend>✅ 驗證特徵</legend>
      <div class="field-row">
        <label>中文大寫</label>
        <input v-model="formData.verification.handwritten_total_chinese" :disabled="isJsonInvalid" placeholder="e.g. 壹佰元整" />
      </div>
      <div class="field-row">
        <label>店章店名</label>
        <input v-model="formData.verification.stamp_shop_name" list="stamp_shop_name-list" @blur="saveSuggestion('stamp_shop_name', formData.verification.stamp_shop_name)" :disabled="isJsonInvalid" />
        <datalist id="stamp_shop_name-list">
          <option v-for="s in suggestions.stamp_shop_name" :key="s" :value="s" />
        </datalist>
      </div>
      <div class="field-row checkbox-row">
        <label>QR Code 偵測</label>
        <input type="checkbox" v-model="formData.verification.qr_code_detected" :disabled="isJsonInvalid" />
        <span>已偵測到 QR Code</span>
      </div>
      <div class="field-row" v-if="formData.verification.qr_verified !== undefined">
        <label>QR 二次對帳</label>
        <span class="qr-status-badge" :class="formData.verification.qr_verified ? 'verified' : 'unverified'">
          {{ formData.verification.qr_verified ? '🟢 已通過 QR 數位驗證對帳' : '⚪ 未進行 QR 數位對帳' }}
        </span>
      </div>
    </fieldset>

    <!-- Audit 區塊 (唯讀, 來自 props.validation) -->
    <fieldset v-if="validation" class="readonly-section">
      <legend>📊 邏輯驗證結果 (唯讀)</legend>
      <div class="field-row">
        <label>是否通過</label>
        <span class="readonly-value" :class="validation.is_valid ? 'text-green' : 'text-red'">
             {{ validation.is_valid ? 'PASS' : 'FAIL' }}
        </span>
      </div>
      <div class="field-row">
        <label>信心分數</label>
        <span class="readonly-value">{{ validation.confidence ? (validation.confidence * 100).toFixed(1) + '%' : 'N/A' }}</span>
      </div>
      <div class="field-row" v-if="validation.issues?.length">
        <label>發現問題</label>
        <ul class="issues-list">
          <li v-for="issue in validation.issues" :key="issue">{{ issue }}</li>
        </ul>
      </div>
      <div class="field-row">
          <label>驗算比對</label>
          <span class="readonly-value text-small">
              計算={{ validation.calculated_total }} / 申報={{ validation.reported_total }}
          </span>
      </div>
    </fieldset>

    <!-- Miscellaneous Fields Section -->
    <fieldset v-if="miscFields.length > 0">
        <legend>🔧 其他自定義欄位</legend>
        <div v-for="key in miscFields" :key="key" class="field-row">
            <label>{{ key }}</label>
            <input v-model="formData[key]" :disabled="isJsonInvalid" />
            <button @click="removeMiscField(key)" class="remove-btn" :disabled="isJsonInvalid">×</button>
        </div>
        <button @click="addMiscField" class="add-btn" :disabled="isJsonInvalid">+ 新增欄位</button>
    </fieldset>
    <div v-else>
        <button @click="addMiscField" class="add-btn" style="margin-top: 10px;" :disabled="isJsonInvalid">+ 新增其他欄位</button>
    </div>

  </div>
</template>

<script setup>
import { ref, watch, onMounted, computed } from 'vue'
import { isEqual, cloneDeep } from 'lodash-es'
import api from '../services/api'

const props = defineProps({
  modelValue: { type: Object, default: () => ({}) },
  isJsonInvalid: { type: Boolean, default: false },
  validation: { type: Object, default: null } // New prop for read-only validation data
})

const emit = defineEmits(['update:modelValue'])

// 建議詞快取
const suggestions = ref({
  supplier: [],
  item_name: [],
  expense_category: [],
  buyer: [],
  seller_id: [],
  buyer_id: [],
  stamp_shop_name: []
})

// 載入所有建議詞
const loadAllSuggestions = async () => {
  const categories = ['supplier', 'item_name', 'expense_category', 'buyer', 'seller_id', 'buyer_id', 'stamp_shop_name']
  for (const cat of categories) {
    try {
      const res = await api.getSuggestions(cat)
      suggestions.value[cat] = res.data || []
    } catch (e) {
      console.error(`Failed to load suggestions for ${cat}`, e)
    }
  }
}

// 儲存新建議
const saveSuggestion = async (category, value) => {
  if (!value || !value.trim()) return
  try {
    await api.addSuggestion(category, value.trim())
    // 重新載入該類別
    const res = await api.getSuggestions(category)
    suggestions.value[category] = res.data || []
  } catch (e) {
    console.error(`Failed to save suggestion ${category}: ${value}`, e)
  }
}

onMounted(() => {
  loadAllSuggestions()
})

// 預設資料結構 (Aligned with VlmResult in json_structure.md)
const getEmptyForm = () => ({
  receipt_type: '電子發票證明聯', // Default
  header: { 
      supplier: '', 
      buyer: '', 
      invoice_id: '', 
      date: '' 
  },
  items: [{ name: '', qty: null, price: null, total: null, category: '' }],
  summary: { 
      subtotal: null, 
      tax: null, 
      total: null 
  },
  verification: { 
      handwritten_total_chinese: '', 
      stamp_shop_name: '',
      qr_code_detected: false
  }
})

const formData = ref(getEmptyForm())

// 從 props 初始化
watch(() => props.modelValue, (newVal) => {
  // Infinite Loop Prevention: Only update if meaningfully different
  if (newVal && !isEqual(newVal, formData.value)) {
    const empty = getEmptyForm()
    // Defensively merge to avoid nulls
    formData.value = {
        ...empty,
        ...newVal,
        header: { ...empty.header, ...(newVal.header || {}) },
        items: newVal.items || empty.items,
        summary: { ...empty.summary, ...(newVal.summary || {}) },
        verification: { ...empty.verification, ...(newVal.verification || {}) }
    }
  }
}, { immediate: true, deep: true })

// 同步回 parent
watch(formData, (newVal) => {
  // Infinite Loop Prevention: check if different from prop before emitting
  // Note: Parent also has checks, but this saves an emit
  if (!isEqual(newVal, props.modelValue)) {
      emit('update:modelValue', newVal)
  }
}, { deep: true })

const addItem = () => {
  if (!formData.value.items) formData.value.items = []
  formData.value.items.push({ name: '', qty: null, price: null, total: null, category: '' })
}

const removeItem = (idx) => {
  if (formData.value.items && formData.value.items.length > 0) {
    formData.value.items.splice(idx, 1)
  }
}

// --- Miscellaneous Fields Logic ---
const KNOWN_KEYS = ['receipt_type', 'header', 'items', 'summary', 'verification']
const miscFields = computed(() => {
    const allKeys = Object.keys(formData.value)
    return allKeys.filter(k => !KNOWN_KEYS.includes(k))
})

const addMiscField = () => {
    const key = prompt("Enter new field name:")
    if (key && !formData.value[key]) {
        formData.value[key] = ""
    }
}

const removeMiscField = (key) => {
    delete formData.value[key]
}
</script>

<style scoped>
/* Dark Theme */
.json-field-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 10px;
  background: #2a2a2a;
  color: #e0e0e0;
  border-radius: 4px;
  max-width: 100%;
  box-sizing: border-box;
}

/* Scrollbar Styles */
.json-field-editor::-webkit-scrollbar {
  width: 8px;
}
.json-field-editor::-webkit-scrollbar-track {
  background: #1a1a1a;
}
.json-field-editor::-webkit-scrollbar-thumb {
  background: #555;
  border-radius: 4px;
}

fieldset {
  border: 1px solid #555;
  padding: 10px;
  border-radius: 4px;
  background: #333;
  margin: 0;
  max-width: 100%;
  box-sizing: border-box;
}

legend {
  font-weight: bold;
  padding: 0 5px;
  color: #ccc;
}

.field-group {
  display: flex;
  flex-direction: column;
}

.field-row {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  gap: 8px;
}

.checkbox-row {
    justify-content: flex-start;
}
.checkbox-row input {
    flex: 0;
    width: auto;
    margin-right: 10px;
}

.field-row label {
  width: 90px;
  min-width: 90px;
  font-size: 0.85em;
  color: #aaa;
}

.field-row input, .field-group select {
  flex: 1;
  min-width: 0;
  padding: 6px;
  border: 1px solid #555;
  border-radius: 4px;
  background: #1a1a1a;
  color: #e0e0e0;
}

/* 品項明細 - 統一寬度 */
.item-row {
  display: flex;
  gap: 4px;
  margin-bottom: 6px;
  max-width: 100%;
  box-sizing: border-box;
}

.item-row input {
  min-width: 0;
  padding: 5px;
  border: 1px solid #555;
  border-radius: 4px;
  background: #1a1a1a;
  color: #e0e0e0;
}

.item-name { flex: 2; }
.item-cat { flex: 1; max-width: 100px; }
.item-num { flex: 1; max-width: 70px; }

.remove-btn {
  background: #ff4444;
  color: white;
  border: none;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.add-btn {
  width: 100%;
  padding: 6px;
  background: #4CAF50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  margin-top: 5px;
}

.readonly-section {
  background: #252525;
  border-color: #444;
}

.readonly-value {
  font-weight: bold;
  color: #fff;
}

.text-green { color: #4ade80; }
.text-red { color: #f87171; }
.text-small { font-size: 0.8em; color: #bbb; }

.issues-list {
  padding-left: 20px;
  margin: 0;
  color: #ef5350;
}

.validation-overlay {
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    z-index: 10;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
}
.validation-message {
    background: #2a2a2a;
    padding: 20px;
    border: 2px solid #ef5350;
    border-radius: 8px;
    text-align: center;
}
.disabled-mode {
    pointer-events: none;
    opacity: 0.8;
}

.qr-status-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.85em;
  font-weight: bold;
}
.qr-status-badge.verified {
  background-color: rgba(74, 222, 128, 0.15);
  border: 1px solid #4ade80;
  color: #4ade80;
}
.qr-status-badge.unverified {
  background-color: rgba(239, 83, 80, 0.15);
  border: 1px solid #ef5350;
  color: #ef5350;
}
</style>
