<template>
  <div class="settings-view">
    <header class="view-header">
      <h1>⚙️ 系統設定 (System Settings)</h1>
    </header>

    <div class="settings-container">
      <div v-if="loading" class="loading">Loading settings...</div>
      <div v-else class="settings-form">
        
        <div class="section">
          <h2>🧠 VLM 模型設定 (Vision Language Model)</h2>
          <p class="section-desc">設定用於辨識收據的 AI 模型參數。</p>
          
          <div class="form-group">
            <label>Model Name</label>
            <input type="text" v-model="settings.vision.model_name" placeholder="e.g. gemini-2.5-flash-lite" list="provider-model-list" />
            <datalist id="provider-model-list">
              <option v-for="name in availableModels" :key="name" :value="name"></option>
            </datalist>
          </div>

          <div class="form-group model-fetcher">
            <button class="secondary-btn" @click="fetchProviderModels" :disabled="loadingModels || !settings.vision.api_key">
              {{ loadingModels ? '取得中...' : '🔎 自動抓取供應商模型列表' }}
            </button>
            <small class="hint" v-if="modelsInfo">{{ modelsInfo }}</small>
            <small class="hint error-text" v-if="modelsError">{{ modelsError }}</small>
            <div class="quick-models" v-if="availableModels.length > 0">
              <span>快速套用：</span>
              <button
                v-for="name in availableModels.slice(0, 10)"
                :key="name"
                type="button"
                class="chip-btn"
                @click="settings.vision.model_name = name"
              >
                {{ name }}
              </button>
            </div>
          </div>

          <div class="form-group">
            <label>Reasoning Effort (思考深度)</label>
            <select v-model="settings.vision.reasoning_effort">
              <option :value="null">None (Disabled)</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
            <small class="hint">僅適用於支援 Reasoning 的模型 (如 Gemini 2.0 Flash Thinking, o1, o3-mini)</small>
          </div>

          <div class="form-group">
            <label>API Provider / Base URL</label>
            <div class="input-with-select">
              <input type="text" v-model="settings.vision.base_url" placeholder="Enter custom base url..." />
              <select @change="applyPreset($event.target.value)" class="preset-select">
                <option value="" disabled selected>Load Preset...</option>
                <option value="google">Google Gemini</option>
                <option value="openrouter">OpenRouter</option>
                <option value="deepseek">DeepSeek</option>
                <option value="openai">OpenAI</option>
              </select>
            </div>
          </div>

          <div class="form-group">
            <label>API Key</label>
            <div class="api-key-input">
              <input 
                :type="showApiKey ? 'text' : 'password'" 
                v-model="settings.vision.api_key" 
                placeholder="Enter API Key" 
              />
              <button @click="showApiKey = !showApiKey" class="toggle-btn">
                {{ showApiKey ? 'Hide' : 'Show' }}
              </button>
            </div>
            <small class="hint" v-if="settings.vision.api_key && settings.vision.api_key.includes('***')">
              Current key is masked. Enter a new key to update, or leave as is to keep current key.
            </small>
          </div>
        </div>

        <!-- Admin Tools Section -->
        <div class="section">
          <h2>🛠️ 系統維護工具 (Admin Tools)</h2>
          <p class="section-desc">以下工具僅供維護者使用，修改後將影響全系統憑證輸出。</p>
          <div class="admin-tools">
            <router-link to="/voucher-template-config" class="admin-tool-btn">
              📐 憑證範本座標設定
              <span class="tool-desc">調整文字欄位位置、蓋章死區與安全區範圍</span>
            </router-link>
          </div>
        </div>

        <div class="actions">
          <button @click="saveSettings" :disabled="saving" class="save-btn">
            {{ saving ? 'Saving...' : '💾 Save Settings' }}
          </button>
        </div>


        <div class="section">
          <h2>📚 推薦詞庫管理 (Suggestion Management)</h2>
          <p class="section-desc">管理系統自動完成的推薦詞。你可以編輯或刪除不再使用的詞彙。</p>
          
          <div class="form-group">
            <label>分類 (Category)</label>
            <select v-model="suggestionCategory" @change="fetchSuggestions" class="form-control">
              <option value="">請選擇分類</option>
              <option value="location">活動地點</option>
              <option value="group_name">活動群組名稱</option>
              <option value="person_name">人員姓名</option>
              <option value="item_name">品項名稱</option>
              <option value="shop_name">店家名稱</option>
              <option value="supplier_name">供應商名稱</option>
              <option value="buyer_name">買受人名稱</option>
              <option value="expense_category">報帳名目</option>
              <option value="budget_income_item">預算收入項目</option>
            </select>
          </div>

          <!-- 新增推薦詞 -->
          <div class="form-group" v-if="suggestionCategory">
            <label>新增推薦詞 (Add Suggestion)</label>
            <div class="add-suggestion-box">
              <input type="text" v-model="newSuggestionValue" placeholder="請輸入欲新增的推薦詞..." class="form-control" @keyup.enter="addNewSuggestion" />
              <button class="primary-btn add-btn" @click="addNewSuggestion">➕ 新增</button>
            </div>
          </div>

          <!-- 搜尋推薦詞 -->
          <div class="form-group" v-if="suggestionCategory && suggestions.length > 0">
            <label>搜尋推薦詞 (Search)</label>
            <input type="text" v-model="searchQuery" placeholder="搜尋此分類的推薦詞..." class="form-control search-input" />
          </div>

          <div v-if="suggestionCategory && suggestions.length === 0" class="hint">此分類尚無推薦詞。</div>

          <div v-if="suggestions.length > 0" class="suggestion-list">
            <table class="table">
              <thead>
                <tr>
                  <th>詞彙 (Value)</th>
                  <th>使用次數 (Count)</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="s in filteredSuggestions" :key="s.id">
                  <td>
                    <input v-if="s._editing" type="text" v-model="s._newValue" class="form-control form-control-sm" />
                    <span v-else>{{ s.value }}</span>
                  </td>
                  <td>{{ s.count }}</td>
                  <td>
                    <button v-if="s._editing" class="primary-btn small-btn" @click="saveSuggestionEdit(s)">儲存</button>
                    <button v-if="s._editing" class="secondary-btn small-btn" @click="s._editing = false">取消</button>
                    
                    <button v-if="!s._editing" class="secondary-btn small-btn" @click="editSuggestion(s)">編輯</button>
                    <button v-if="!s._editing" class="danger-btn small-btn" @click="deleteSuggestion(s)">刪除</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '../services/api'

const loading = ref(true)
const saving = ref(false)
const showApiKey = ref(false)
const loadingModels = ref(false)
const modelsInfo = ref('')
const modelsError = ref('')
const availableModels = ref([])

// Local state mapping
const settings = ref({
  vision: {
    model_name: '',
    reasoning_effort: null,
    base_url: '',
    api_key: ''
  }
})

// Suggestion Management state
const suggestionCategory = ref('')
const suggestions = ref([])
const newSuggestionValue = ref('')
const searchQuery = ref('')

const fetchSuggestions = async () => {
  if (!suggestionCategory.value) {
    suggestions.value = []
    return
  }
  try {
    const res = await api.getAllSuggestions(suggestionCategory.value)
    suggestions.value = (res.data || []).map(s => ({
      ...s,
      _editing: false,
      _newValue: s.value
    }))
  } catch (e) {
    alert('無法取得推薦詞: ' + e)
  }
}

const addNewSuggestion = async () => {
  const val = newSuggestionValue.value.trim()
  if (!val) return
  try {
    await api.addSuggestion(suggestionCategory.value, val)
    newSuggestionValue.value = ''
    await fetchSuggestions()
  } catch (e) {
    alert('新增推薦詞失敗: ' + e)
  }
}

const editSuggestion = (s) => {
  s._editing = true
  s._newValue = s.value
}

const saveSuggestionEdit = async (s) => {
  const val = s._newValue.trim()
  if (!val) {
    alert('推薦詞不可為空')
    return
  }
  try {
    await api.updateSuggestion(s.id, s.category, val)
    s.value = val
    s._editing = false
  } catch (e) {
    alert('更新推薦詞失敗: ' + e)
  }
}

const deleteSuggestion = async (s) => {
  if (!confirm(`確定要刪除推薦詞「${s.value}」嗎？`)) return
  try {
    await api.deleteSuggestion(s.id)
    suggestions.value = suggestions.value.filter(item => item.id !== s.id)
  } catch (e) {
    alert('刪除推薦詞失敗: ' + e)
  }
}

const filteredSuggestions = computed(() => {
  if (!searchQuery.value) return suggestions.value
  return suggestions.value.filter(s => s.value.toLowerCase().includes(searchQuery.value.toLowerCase()))
})

// Presets
const presets = {
  google: "https://generativelanguage.googleapis.com/v1beta/openai/",
  openrouter: "https://openrouter.ai/api/v1",
  deepseek: "https://api.deepseek.com",
  openai: "https://api.openai.com/v1"
}

const applyPreset = (key) => {
  if (presets[key]) {
    settings.value.vision.base_url = presets[key]
  }
}

const fetchProviderModels = async () => {
  loadingModels.value = true
  modelsError.value = ''
  modelsInfo.value = ''
  try {
    const res = await api.listVisionModels()
    availableModels.value = res.data.models || []
    const provider = res.data.provider || 'provider'
    modelsInfo.value = `已取得 ${res.data.count || availableModels.value.length} 個模型 (${provider})`
  } catch (e) {
    const detail = e?.response?.data?.detail || e.message || e
    modelsError.value = `模型列表抓取失敗：${detail}`
  } finally {
    loadingModels.value = false
  }
}

const fetchSettings = async () => {
  loading.value = true
  try {
    const res = await api.getConfig()
    const vision = res.data.vision_settings || {}
    
    settings.value.vision = {
      model_name: vision.model_name || 'gemini-2.5-flash-lite',
      reasoning_effort: vision.reasoning_effort || null,
      base_url: vision.base_url || presets.google,
      api_key: vision.api_key || ''
    }
    if (settings.value.vision.api_key) {
      await fetchProviderModels()
    }
  } catch (e) {
    alert('Failed to load settings: ' + e)
  } finally {
    loading.value = false
  }
}

const saveSettings = async () => {
  saving.value = true
  try {
    const payload = {
      vision_settings: {
        model_name: settings.value.vision.model_name,
        reasoning_effort: settings.value.vision.reasoning_effort,
        base_url: settings.value.vision.base_url,
        api_key: settings.value.vision.api_key
      }
    }
    
    await api.updateConfig(payload)
    alert('Settings saved successfully!')
    // Reload to get masked key if needed
    fetchSettings()
  } catch (e) {
    alert('Failed to save settings: ' + e)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchSettings()
})
</script>

<style scoped>
.settings-view {
  padding: 2rem;
  color: #e0e0e0;
  max-width: 800px;
  margin: 0 auto;
}

.view-header {
  margin-bottom: 2rem;
  border-bottom: 1px solid #444;
  padding-bottom: 1rem;
}

.settings-container {
  background: #2a2a2a;
  padding: 2rem;
  border-radius: 8px;
  border: 1px solid #444;
}

.section {
  margin-bottom: 2rem;
}

.section h2 {
  font-size: 1.25rem;
  margin-bottom: 0.5rem;
  color: #0ea5e9;
}

.section-desc {
  color: #888;
  margin-bottom: 1.5rem;
  font-size: 0.9rem;
}

.form-group {
  margin-bottom: 1.5rem;
}

.model-fetcher {
  border: 1px dashed #3b82f6;
  border-radius: 8px;
  padding: 0.9rem;
  background: rgba(59, 130, 246, 0.06);
}

.secondary-btn {
  background: #1d4ed8;
  color: #fff;
  border: none;
  padding: 0.55rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
}

.secondary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.quick-models {
  margin-top: 0.7rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  align-items: center;
}

.chip-btn {
  background: #0f172a;
  border: 1px solid #334155;
  color: #93c5fd;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  cursor: pointer;
  font-size: 0.75rem;
}

.chip-btn:hover {
  border-color: #60a5fa;
}

.error-text {
  color: #fca5a5;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: bold;
}

.form-group input[type="text"],
.form-group input[type="password"],
.form-group select {
  width: 100%;
  padding: 0.75rem;
  background: #1a1a1a;
  border: 1px solid #444;
  color: #fff;
  border-radius: 4px;
  font-size: 1rem;
}

.form-group input:focus,
.form-group select:focus {
  border-color: #0ea5e9;
  outline: none;
}

.input-with-select {
  display: flex;
  gap: 10px;
}

.preset-select {
  width: 150px !important;
}

.api-key-input {
  display: flex;
  gap: 10px;
}

.toggle-btn {
  background: #444;
  border: none;
  color: white;
  padding: 0 1rem;
  cursor: pointer;
  border-radius: 4px;
}

.hint {
  display: block;
  margin-top: 5px;
  color: #888;
  font-size: 0.85rem;
}

.actions {
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid #444;
  padding-top: 1.5rem;
}

.save-btn {
  background: #059669;
  color: white;
  border: none;
  padding: 0.75rem 2rem;
  border-radius: 4px;
  font-size: 1rem;
  font-weight: bold;
  cursor: pointer;
  transition: background 0.2s;
}

.save-btn:hover {
  background: #047857;
}

.save-btn:disabled {
  background: #444;
  cursor: not-allowed;
}

.loading {
  text-align: center;
  padding: 2rem;
  color: #888;
}

/* Admin Tools Section */
.admin-tools {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.admin-tool-btn {
  display: flex;
  flex-direction: column;
  background: #1a1a1a;
  border: 1px solid #555;
  border-radius: 8px;
  padding: 1rem 1.25rem;
  color: #e0e0e0;
  text-decoration: none;
  transition: border-color 0.2s, background 0.2s;
}

.admin-tool-btn:hover {
  border-color: #2563eb;
  background: #1e2d4d;
}

.admin-tool-btn .tool-desc {
  margin-top: 0.25rem;
  font-size: 0.82rem;
  color: #888;
}

/* Suggestion Management Styles */
.add-suggestion-box {
  display: flex;
  gap: 0.75rem;
}

.add-suggestion-box input {
  flex: 1;
}

.add-btn {
  background: #0284c7;
  color: white;
  border: none;
  padding: 0.75rem 1.5rem !important;
  border-radius: 4px;
  font-weight: bold;
  cursor: pointer;
  transition: background 0.2s;
}

.add-btn:hover {
  background: #0369a1;
}

.search-input {
  margin-bottom: 1rem;
}

.suggestion-list {
  margin-top: 1.5rem;
  overflow-x: auto;
}

.table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 1rem;
}

.table th, .table td {
  padding: 0.75rem;
  text-align: left;
  border-bottom: 1px solid #444;
}

.table th {
  background: #1a1a1a;
  color: #0ea5e9;
  font-weight: bold;
}

.table td {
  vertical-align: middle;
}

.small-btn {
  padding: 0.4rem 0.8rem;
  font-size: 0.85rem;
  border-radius: 4px;
  cursor: pointer;
  border: none;
  margin-right: 0.4rem;
  font-weight: bold;
}

.primary-btn {
  background: #0ea5e9;
  color: white;
}

.primary-btn:hover {
  background: #0284c7;
}

.danger-btn {
  background: #dc2626;
  color: white;
}

.danger-btn:hover {
  background: #b91c1c;
}
</style>
