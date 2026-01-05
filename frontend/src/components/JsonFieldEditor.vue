<template>
  <div class="json-field-editor">
    <!-- 收據類型 -->
    <div class="field-group">
      <label>收據類型</label>
      <select v-model="formData.receipt_type">
        <option value="">請選擇</option>
        <option value="電子發票">電子發票</option>
        <option value="免用統一發票收據">免用統一發票收據</option>
        <option value="其他收據">其他收據</option>
      </select>
    </div>

    <!-- QR Code 區塊 (僅電子發票顯示) -->
    <fieldset v-if="formData.receipt_type === '電子發票'">
      <legend>📱 QR Code 資訊</legend>
      <div v-if="formData.qr_decode">
        <div class="field-row">
          <label>發票號碼</label>
          <input v-model="formData.qr_decode.invoice_id" />
        </div>
        <div class="field-row">
          <label>日期</label>
          <input v-model="formData.qr_decode.date" type="date" />
        </div>
        <div class="field-row">
          <label>賣方統編</label>
          <input v-model="formData.qr_decode.seller_id" list="seller_id-list" @blur="saveSuggestion('seller_id', formData.qr_decode.seller_id)" />
          <datalist id="seller_id-list">
            <option v-for="s in suggestions.seller_id" :key="s" :value="s" />
          </datalist>
        </div>
        <div class="field-row">
          <label>買方統編</label>
          <input v-model="formData.qr_decode.buyer_id" list="buyer_id-list" @blur="saveSuggestion('buyer_id', formData.qr_decode.buyer_id)" />
          <datalist id="buyer_id-list">
            <option v-for="s in suggestions.buyer_id" :key="s" :value="s" />
          </datalist>
        </div>
        <div class="field-row">
          <label>總金額</label>
          <input v-model.number="formData.qr_decode.total" type="number" />
        </div>
        <div class="field-row">
          <label>隨機碼</label>
          <input v-model="formData.qr_decode.random_code" />
        </div>
      </div>
      <div v-else class="empty-qr">
        無 QR Code 資料
      </div>
    </fieldset>

    <!-- Header 區塊 -->
    <fieldset v-if="formData.header">
      <legend>📋 發票資訊</legend>
      <div class="field-row">
        <label>商家名稱</label>
        <input v-model="formData.header.supplier" list="supplier-list" @blur="saveSuggestion('supplier', formData.header.supplier)" />
        <datalist id="supplier-list">
          <option v-for="s in suggestions.supplier" :key="s" :value="s" />
        </datalist>
      </div>
      <div class="field-row">
        <label>買受人</label>
        <input v-model="formData.header.buyer" list="buyer-list" @blur="saveSuggestion('buyer', formData.header.buyer)" />
        <datalist id="buyer-list">
          <option v-for="s in suggestions.buyer" :key="s" :value="s" />
        </datalist>
      </div>
      
      <!-- 僅電子發票顯示 -->
      <template v-if="formData.receipt_type === '電子發票'">
        <div class="field-row">
          <label>發票號碼</label>
          <input v-model="formData.header.invoice_id" />
        </div>
        <div class="field-row">
          <label>統一編號</label>
          <input v-model="formData.header.tax_id" />
        </div>
      </template>

      <div class="field-row">
        <label>日期</label>
        <input v-model="formData.header.date" placeholder="YYYY-MM-DD" />
      </div>
    </fieldset>

    <!-- Items 區塊 -->
    <fieldset v-if="formData.items">
      <legend>🛒 品項明細</legend>
      <div v-for="(item, idx) in formData.items" :key="idx" class="item-row">
        <input v-model="item.name" placeholder="品名" class="item-name" list="item_name-list" @blur="saveSuggestion('item_name', item.name)" />
        <input v-model.number="item.qty" type="number" placeholder="數量" class="item-num" />
        <input v-model.number="item.price" type="number" placeholder="單價" class="item-num" />
        <input v-model.number="item.total" type="number" placeholder="小計" class="item-num" />
        <button @click="removeItem(idx)" class="remove-btn">×</button>
      </div>
      <datalist id="item_name-list">
        <option v-for="s in suggestions.item_name" :key="s" :value="s" />
      </datalist>
      <button @click="addItem" class="add-btn">+ 新增品項</button>
    </fieldset>

    <!-- Summary 區塊 -->
    <fieldset v-if="formData.summary">
      <legend>💰 總計</legend>
      <div class="field-row">
        <label>總金額</label>
        <input v-model.number="formData.summary.total" type="number" />
      </div>
    </fieldset>

    <!-- Verification 區塊 (僅免用統一發票顯示) -->
    <fieldset v-if="formData.receipt_type === '免用統一發票收據' && formData.verification">
      <legend>✅ 驗證資訊</legend>
      <div class="field-row">
        <label>中文大寫</label>
        <input v-model="formData.verification.handwritten_total_chinese" />
      </div>
      <div class="field-row">
        <label>店章店名</label>
        <input v-model="formData.verification.stamp_shop_name" list="stamp_shop_name-list" @blur="saveSuggestion('stamp_shop_name', formData.verification.stamp_shop_name)" />
        <datalist id="stamp_shop_name-list">
          <option v-for="s in suggestions.stamp_shop_name" :key="s" :value="s" />
        </datalist>
      </div>
    </fieldset>

    <!-- Audit 區塊 (唯讀) -->
    <fieldset v-if="formData.audit" class="readonly-section">
      <legend>📊 稽核資訊 (唯讀)</legend>
      <div class="field-row">
        <label>信心分數</label>
        <span class="readonly-value">{{ formData.audit.confidence ? (formData.audit.confidence * 100).toFixed(1) + '%' : 'N/A' }}</span>
      </div>
      <div class="field-row" v-if="formData.audit.issues?.length">
        <label>發現問題</label>
        <ul class="issues-list">
          <li v-for="issue in formData.audit.issues" :key="issue">{{ issue }}</li>
        </ul>
      </div>
    </fieldset>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import api from '../services/api'

const props = defineProps({
  modelValue: { type: Object, default: () => ({}) }
})

const emit = defineEmits(['update:modelValue'])

// 建議詞快取
const suggestions = ref({
  supplier: [],
  item_name: [],
  buyer: [],
  seller_id: [],
  buyer_id: [],
  stamp_shop_name: []
})

// 載入所有建議詞
const loadAllSuggestions = async () => {
  const categories = ['supplier', 'item_name', 'buyer', 'seller_id', 'buyer_id', 'stamp_shop_name']
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

// 預設資料結構
const getEmptyForm = () => ({
  receipt_type: '',
  qr_decode: {
    invoice_id: '', date: '', seller_id: '', buyer_id: '', total: null, random_code: ''
  },
  header: { supplier: '', buyer: '', invoice_id: '', date: '', tax_id: '' },
  items: [{ name: '', qty: null, price: null, total: null }],
  summary: { total: null },
  verification: { handwritten_total_chinese: '', stamp_shop_name: '' },
  audit: { confidence: null, issues: [], corrections: [] }
})

const formData = ref(getEmptyForm())

// 從 props 初始化
watch(() => props.modelValue, (newVal) => {
  if (newVal && Object.keys(newVal).length > 0) {
    const empty = getEmptyForm()
    formData.value = {
        ...empty,
        ...newVal,
        header: { ...empty.header, ...(newVal.header || {}) },
        qr_decode: { ...empty.qr_decode, ...(newVal.qr_decode || {}) },
        items: newVal.items || empty.items,
        summary: { ...empty.summary, ...(newVal.summary || {}) },
        verification: { ...empty.verification, ...(newVal.verification || {}) },
        audit: { ...empty.audit, ...(newVal.audit || {}) }
    }
  }
}, { immediate: true, deep: true })

// 同步回 parent
watch(formData, (newVal) => {
  emit('update:modelValue', newVal)
}, { deep: true })

// 監聽收據類型改變
watch(() => formData.value.receipt_type, (newType) => {
  if (newType !== '電子發票') {
    formData.value.qr_decode = null
    if (formData.value.header) {
      formData.value.header.invoice_id = ''
      formData.value.header.tax_id = ''
    }
  } else {
    if (!formData.value.qr_decode) {
      formData.value.qr_decode = {
        invoice_id: '', date: '', seller_id: '', buyer_id: '', total: null, random_code: ''
      }
    }
  }
  
  if (newType !== '免用統一發票收據') {
      if (formData.value.verification) {
          formData.value.verification.handwritten_total_chinese = ''
          formData.value.verification.stamp_shop_name = ''
      }
  }
})

const addItem = () => {
  if (!formData.value.items) formData.value.items = []
  formData.value.items.push({ name: '', qty: null, price: null, total: null })
}

const removeItem = (idx) => {
  if (formData.value.items && formData.value.items.length > 0) {
    formData.value.items.splice(idx, 1)
  }
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

.field-row label {
  width: 80px;
  min-width: 80px;
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

.issues-list {
  padding-left: 20px;
  margin: 0;
  color: #ef5350;
}

.empty-qr {
  color: #888;
  font-style: italic;
  padding: 10px;
  text-align: center;
}
</style>
