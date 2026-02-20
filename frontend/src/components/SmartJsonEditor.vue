<template>
  <div class="smart-json-editor">
    
    <!-- Quick Fields Header -->
    <div class="quick-fields" v-if="showQuickFields">
      <div class="field-group" v-for="field in quickFields" :key="field.key">
        <label>{{ field.label }}</label>
        <input 
          type="text" 
          v-model="field.value"
          @input="onQuickFieldChange(field)"
          :placeholder="field.placeholder"
        />
      </div>
      <div v-if="jsonError" class="error-badge" title="JSON Syntax Error">⚠️ JSON Error</div>
    </div>

    <!-- CodeMirror Editor -->
    <div class="editor-container">
      <codemirror
        v-model="code"
        placeholder="Enter JSON here..."
        :style="{ height: '100%' }"
        :autofocus="true"
        :indent-with-tab="true"
        :tab-size="2"
        :extensions="extensions"
        @change="onCodeChange"
      />
    </div>

    <!-- Toolbar -->
    <div class="editor-toolbar">
      <button @click="formatJson" class="tool-btn">✨ Prettify</button>
      <span class="status-text">{{ statusText }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed, onMounted } from 'vue'
import { Codemirror } from 'vue-codemirror'
import { json } from '@codemirror/lang-json'
import { linter, lintGutter } from '@codemirror/lint'
import { EditorView } from '@codemirror/view'
import { get, set, cloneDeep, isEqual } from 'lodash-es'

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({})
  },
  showQuickFields: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['update:modelValue', 'save'])

// --- Configuration ---
const FIELD_MAP = [
  { key: 'invoice_id', label: '發票號碼', paths: ['invoice_id', 'header.invoice_id', 'invoice_number'], placeholder: 'AB-12345678' },
  { key: 'date', label: '日期', paths: ['date', 'header.date', 'invoice_date'], placeholder: 'YYYY-MM-DD' },
  { key: 'total', label: '總金額', paths: ['total', 'amount', 'summary.total', 'total_amount'], placeholder: '0' }
]

// --- State ---
const code = ref('')
const jsonError = ref(false)
const isLocked = ref(false) // Lock to prevent sync loops
const statusText = ref('')

const quickFields = ref(FIELD_MAP.map(f => ({
  ...f,
  value: ''
})))

// --- CodeMirror Extensions ---
const jsonLinter = linter(view => {
  try {
    JSON.parse(view.state.doc.toString())
    jsonError.value = false
    statusText.value = 'Valid JSON'
    return []
  } catch (e) {
    jsonError.value = true
    statusText.value = 'Invalid JSON'
    return [{
      from: 0,
      to: view.state.doc.length,
      severity: 'error',
      message: e.message
    }]
  }
})

// Custom keymap for Ctrl+S
const customKeymap = EditorView.domEventHandlers({
  keydown: (e, view) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault()
      emit('save')
      statusText.value = 'Saved via Shortcut'
      setTimeout(() => statusText.value = '', 2000)
      return true
    }
  }
})

const extensions = [json(), lintGutter(), jsonLinter, customKeymap]

// --- Logic ---

// 1. Initialize from Props
watch(() => props.modelValue, (newVal) => {
  // Only update code if it's materially different (deep compare) 
  // to avoid resetting cursor when typing in quick fields OR external form
  try {
    const currentObj = JSON.parse(code.value || '{}')
    if (!isEqual(newVal, currentObj)) {
      code.value = JSON.stringify(newVal, null, 2)
      if (props.showQuickFields) {
          syncJsonToQuickFields(newVal)
      }
    }
  } catch (e) {
    // If current code is invalid, we might legitimately want to replace it if prop changed from outside
    if (!isLocked.value) {
        code.value = JSON.stringify(newVal, null, 2)
        if (props.showQuickFields) {
            syncJsonToQuickFields(newVal)
        }
    }
  }
}, { immediate: true, deep: true })

// 2. Code Change Handler (JSON -> Quick Fields & Emit)
const onCodeChange = (value) => {
  if (isLocked.value) return

  try {
    const newObj = JSON.parse(value)
    jsonError.value = false
    
    // Update Quick Fields
    syncJsonToQuickFields(newObj)
    
    // Emit Update
    emit('update:modelValue', newObj)
  } catch (e) {
    jsonError.value = true
    // Do not emit update if JSON is invalid to keep parent state consistent?
    // Or emit null? Better to not emit trash.
  }
}

// 3. Quick Field Change Handler (Quick Fields -> JSON & Emit)
const onQuickFieldChange = (field) => {
  if (jsonError.value) return // Cannot patch invalid JSON

  isLocked.value = true // Lock to prevent circular update from code watch
  try {
    const currentObj = JSON.parse(code.value || '{}')
    
    // Find path to update
    const path = findActivePath(currentObj, field.paths) || field.paths[0]
    
    // Update Object
    set(currentObj, path, field.value)
    
    // Update Code (this normally triggers watch/onCodeChange, but we locked it)
    code.value = JSON.stringify(currentObj, null, 2)
    
    // Emit Update
    emit('update:modelValue', currentObj)
    
  } catch (e) {
    console.error("Failed to patch JSON", e)
  } finally {
    // Unlock after Vue tick or immediate?
    // CodeMirror update is sync, so we can unlock immediately
    setTimeout(() => { isLocked.value = false }, 0)
  }
}

// Helper: Find which path in the list actually exists in the object
const findActivePath = (obj, paths) => {
  for (const path of paths) {
    const val = get(obj, path)
    if (val !== undefined) return path
  }
  return null
}

const syncJsonToQuickFields = (obj) => {
  quickFields.value.forEach(field => {
    const path = findActivePath(obj, field.paths)
    if (path) {
      field.value = get(obj, path)
    } else {
      field.value = ''
    }
  })
}

const formatJson = () => {
    try {
        const obj = JSON.parse(code.value)
        code.value = JSON.stringify(obj, null, 2)
    } catch(e) {
        alert("Cannot format invalid JSON")
    }
}

// Ensure clean start
onMounted(() => {
    if (props.modelValue) {
        code.value = JSON.stringify(props.modelValue, null, 2)
        syncJsonToQuickFields(props.modelValue)
    }
})

</script>

<style scoped>
.smart-json-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1e1e1e;
}

.quick-fields {
  display: flex;
  gap: 1rem;
  padding: 0.5rem;
  background: #252526;
  border-bottom: 1px solid #333;
  flex-wrap: wrap;
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.field-group label {
  font-size: 0.75rem;
  color: #888;
}

.field-group input {
  background: #333;
  border: 1px solid #444;
  color: #ddd;
  padding: 4px 8px;
  border-radius: 3px;
  font-size: 0.9rem;
  width: 140px;
}

.field-group input:focus {
  border-color: #0ea5e9;
  outline: none;
}

.error-badge {
    background: #dc2626;
    color: white;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.8rem;
    align-self: center;
    margin-left: auto;
}

.editor-container {
  flex: 1;
  overflow: auto;
  font-size: 14px;
  /* Customize CodeMirror Scrollbar if needed */
}

/* CodeMirror Dark Theme Overrides (Basic) */
:deep(.cm-editor) {
  height: 100%;
}
:deep(.cm-scroller) {
  font-family: 'Consolas', 'Monaco', monospace;
}
:deep(.cm-focused) {
  outline: none;
}

.editor-toolbar {
    padding: 5px;
    background: #252526;
    border-top: 1px solid #333;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.tool-btn {
    background: #333;
    color: #ccc;
    border: 1px solid #444;
    padding: 2px 8px;
    cursor: pointer;
    font-size: 0.8rem;
    border-radius: 3px;
}

.tool-btn:hover {
    background: #444;
}

.status-text {
    font-size: 0.8rem;
    color: #666;
}
</style>
