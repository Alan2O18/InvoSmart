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

        <!-- Group Management Section -->
        <div class="section">
          <h2>👥 群組人員管理 (Group Management)</h2>
          <p class="section-desc">同一組可維護多位組長。每位組長可上傳多張電子章，供稽核輪替蓋印使用。</p>
          
          <div class="group-management">
            <div class="add-group-form">
              <input type="text" v-model="newGroupName" placeholder="組別名稱 (e.g. 餐食組)" />
              <input type="text" v-model="newLeaderName" placeholder="組長名稱 (e.g. 王大明)" />
              <button @click="addGroup" :disabled="!newGroupName || !newLeaderName || processingGroup" class="add-btn" type="button">
                {{ processingGroup ? '處理中...' : '新增組長到群組' }}
              </button>
            </div>

            <div v-if="loadingGroups" class="loading-small">載入中...</div>
            <table v-else class="group-table">
              <thead>
                <tr>
                  <th>組別名稱</th>
                  <th>組長 (可多位)</th>
                  <th>電子章</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="g in groups" :key="g.group_name">
                  <td>{{ g.group_name }}</td>
                  <td>
                    <div class="leader-list" v-if="(g.leader_names || []).length > 0">
                      <div v-for="leader in g.leader_names" :key="`${g.group_name}:${leader}`" class="leader-item">
                        <span class="leader-name">{{ leader }}</span>
                        <button
                          type="button"
                          class="mini-delete-btn"
                          :disabled="processingGroup"
                          @click="deleteLeader(g.group_name, leader)"
                        >
                          移除組長
                        </button>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div v-if="(g.leaders || []).length > 0" class="stamp-manage-wrap">
                      <div v-for="leader in g.leaders" :key="`${g.group_name}:${leader.name}:stamps`" class="stamp-block">
                        <div class="stamp-header">
                          <span>{{ leader.name }}</span>
                          <label class="stamp-upload-label">
                            上傳電子章
                            <input
                              type="file"
                              accept="image/*"
                              multiple
                              :disabled="processingGroup"
                              @change="onStampFilesSelected(g.group_name, leader.name, $event)"
                            />
                          </label>
                        </div>
                        <div class="stamp-gallery" v-if="(leader.stamps || []).length > 0">
                          <div v-for="stamp in leader.stamps" :key="stamp.url" class="stamp-item">
                            <img :src="toAbsoluteUrl(stamp.url)" :alt="stamp.filename" />
                            <button
                              type="button"
                              class="mini-delete-btn"
                              :disabled="processingGroup"
                              @click="deleteStamp(g.group_name, leader.name, stamp.filename)"
                            >
                              刪除章
                            </button>
                          </div>
                        </div>
                        <small v-else class="hint">尚未上傳電子章</small>
                      </div>
                    </div>
                  </td>
                  <td>
                    <button type="button" @click="deleteGroup(g.group_name)" class="delete-btn" :disabled="processingGroup">刪除整組</button>
                  </td>
                </tr>
                <tr v-if="groups.length === 0">
                  <td colspan="4" class="empty-state">目前還沒有建立任何群組。</td>
                </tr>
              </tbody>
            </table>
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

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../services/api'

const loading = ref(true)
const saving = ref(false)
const showApiKey = ref(false)
const loadingModels = ref(false)
const modelsInfo = ref('')
const modelsError = ref('')
const availableModels = ref([])

// Group state
const groups = ref([])
const loadingGroups = ref(false)
const processingGroup = ref(false)
const newGroupName = ref('')
const newLeaderName = ref('')

// Local state mapping
const settings = ref({
  vision: {
    model_name: '',
    reasoning_effort: null,
    base_url: '',
    api_key: ''
  }
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

const toAbsoluteUrl = (path) => api.toAbsoluteUrl(path)

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

// Group Fetching Operations
const fetchGroups = async () => {
  loadingGroups.value = true
  try {
    const res = await api.listGroups()
    groups.value = res.data || []
  } catch (e) {
    console.error('Failed to load groups', e)
  } finally {
    loadingGroups.value = false
  }
}

const addGroup = async () => {
  if (!newGroupName.value || !newLeaderName.value) return
  processingGroup.value = true
  try {
    await api.upsertGroup(newGroupName.value, newLeaderName.value)
    newGroupName.value = ''
    newLeaderName.value = ''
    await fetchGroups()
  } catch (e) {
    alert('Failed to add group: ' + e)
  } finally {
    processingGroup.value = false
  }
}

const deleteGroup = async (groupName) => {
  if (!confirm(`確定要刪除群組 "${groupName}" 嗎？`)) return
  processingGroup.value = true
  try {
    await api.deleteGroup(groupName)
    await fetchGroups()
  } catch (e) {
    alert('Failed to delete group: ' + e)
  } finally {
    processingGroup.value = false
  }
}

const deleteLeader = async (groupName, leaderName) => {
  if (!confirm(`確定要把組長 "${leaderName}" 從群組 "${groupName}" 移除嗎？`)) return
  processingGroup.value = true
  try {
    await api.deleteGroupLeader(groupName, leaderName)
    await fetchGroups()
  } catch (e) {
    alert('Failed to delete leader: ' + e)
  } finally {
    processingGroup.value = false
  }
}

const onStampFilesSelected = async (groupName, leaderName, event) => {
  const selectedFiles = Array.from(event.target?.files || [])
  if (selectedFiles.length === 0) return
  processingGroup.value = true
  try {
    await api.uploadLeaderStamps(groupName, leaderName, selectedFiles)
    await fetchGroups()
  } catch (e) {
    alert('Failed to upload stamps: ' + e)
  } finally {
    processingGroup.value = false
    if (event?.target) {
      event.target.value = ''
    }
  }
}

const deleteStamp = async (groupName, leaderName, filename) => {
  if (!confirm(`確定刪除電子章 "${filename}" 嗎？`)) return
  processingGroup.value = true
  try {
    await api.deleteLeaderStamp(groupName, leaderName, filename)
    await fetchGroups()
  } catch (e) {
    alert('Failed to delete stamp: ' + e)
  } finally {
    processingGroup.value = false
  }
}

onMounted(() => {
  fetchSettings()
  fetchGroups()
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

/* Group Management Styles */
.group-management {
  background: #1a1a1a;
  padding: 1.5rem;
  border-radius: 8px;
  border: 1px solid #444;
}

.add-group-form {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.add-group-form input {
  flex: 1;
  padding: 0.75rem;
  background: #2a2a2a;
  border: 1px solid #444;
  color: #fff;
  border-radius: 4px;
}

.add-btn {
  background: #0ea5e9;
  color: white;
  border: none;
  padding: 0 1.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
}

.add-btn:hover:not(:disabled) {
  background: #0284c7;
}

.add-btn:disabled {
  background: #444;
  cursor: not-allowed;
}

.group-table {
  width: 100%;
  border-collapse: collapse;
}

.group-table th, .group-table td {
  padding: 1rem;
  text-align: left;
  border-bottom: 1px solid #333;
  vertical-align: top;
}

.group-table th {
  color: #888;
  font-weight: normal;
}

.delete-btn {
  background: #ef4444;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
}

.delete-btn:hover:not(:disabled) {
  background: #dc2626;
}

.delete-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.empty-state {
  text-align: center;
  color: #888;
  padding: 2rem !important;
}

.loading-small {
  text-align: center;
  padding: 1rem;
  color: #888;
}

.leader-list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.leader-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.leader-name {
  background: #1e293b;
  color: #cbd5e1;
  border: 1px solid #334155;
  border-radius: 999px;
  padding: 0.15rem 0.65rem;
  font-size: 0.78rem;
}

.mini-delete-btn {
  border: 1px solid #ef4444;
  color: #fca5a5;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.74rem;
  padding: 0.2rem 0.45rem;
}

.mini-delete-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.stamp-manage-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.stamp-block {
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 0.5rem;
  background: #111827;
}

.stamp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}

.stamp-upload-label {
  font-size: 0.74rem;
  color: #93c5fd;
  cursor: pointer;
}

.stamp-upload-label input {
  display: block;
  margin-top: 0.25rem;
  max-width: 170px;
  font-size: 0.72rem;
}

.stamp-gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(90px, 1fr));
  gap: 0.4rem;
}

.stamp-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  align-items: stretch;
}

.stamp-item img {
  width: 100%;
  height: 74px;
  object-fit: contain;
  background: #0b1220;
  border: 1px solid #1e293b;
  border-radius: 4px;
  padding: 0.2rem;
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
</style>
