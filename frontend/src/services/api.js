import axios from 'axios'

const API_BASE_URL = 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {}
})

export default {
  // =====================
  // Projects CRUD
  // =====================
  getProjects() {
    return api.get('/api/projects/')
  },
  createProject(formData, onProgress) {
    return api.post('/api/projects/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onProgress,
    })
  },
  getProject(projectId) {
    return api.get(`/api/projects/${projectId}`)
  },
  getProjectDetail(projectId) {
    return api.get(`/api/projects/${projectId}/detail`)
  },
  updateProject(projectId, metadata) {
    return api.put(`/api/projects/${projectId}`, metadata)
  },
  deleteProject(projectId) {
    return api.delete(`/api/projects/${projectId}`)
  },

  // =====================
  // Jobs
  // =====================
  getProjectJobs(projectId) {
    return api.get(`/api/projects/${projectId}/jobs`)
  },
  deleteJob(projectId, jobId) {
    return api.delete(`/api/projects/${projectId}/jobs/${jobId}`)
  },

  // =====================
  // Files & Processing
  // =====================
  addFiles(projectId, formData, onProgress) {
    return api.post(`/api/projects/${projectId}/add_files`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onProgress,
    })
  },
  getRawFiles(projectId) {
    return api.get(`/api/projects/${projectId}/raw_files`)
  },
  deleteRawFile(projectId, filename) {
    return api.delete(`/api/projects/${projectId}/raw_files/${filename}`)
  },
  rotateImage(projectId, filename, angle) {
    return api.post(`/api/projects/${projectId}/rotate/${filename}?angle=${angle}`)
  },

  // =====================
  // PDF Processing
  // =====================
  uploadPdf(projectId, formData, onProgress) {
    return api.post(`/api/pdf/${projectId}/pdf`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onProgress,
    })
  },
  executePdfCommands(projectId, jobId, commands) {
    return api.post(`/api/pdf/${projectId}/${jobId}/commands`, commands)
  },
  downloadPdf(projectId, jobId) {
    return api.get(`/api/pdf/${projectId}/${jobId}/download`, { responseType: 'blob' })
  },

  // =====================
  // Pipeline Actions (VLM-First)
  // =====================
  runSplit(projectId) {
    return api.post(`/api/projects/${projectId}/run_split`)
  },
  runSplitSingle(projectId, filename) {
    return api.post(`/api/projects/${projectId}/split/${filename}`)
  },

  // VLM-First: 統一處理入口
  runProcessing(projectId) {
    return api.post(`/api/projects/${projectId}/run_processing`)
  },
  runSingleProcessing(projectId, jobId) {
    return api.post(`/api/projects/${projectId}/jobs/${jobId}/process`)
  },
  detectJobSubRects(projectId, jobId) {
    return api.post(`/api/projects/${projectId}/jobs/${jobId}/detect-sub-rects`)
  },
  applyJobResplit(projectId, jobId, subRects) {
    return api.post(`/api/projects/${projectId}/jobs/${jobId}/apply-resplit`, {
      sub_rects: subRects,
    })
  },

  // =====================
  // Export & Archive
  // =====================
  runExport(projectId) {
    return api.post(`/api/projects/${projectId}/run_export`)
  },
  runWordExport(projectId) {
    return api.post(`/api/projects/${projectId}/run_word_export`, null, {
      responseType: 'blob'
    })
  },
  getVoucherTextConfig() {
    return api.get('/api/voucher/text-config')
  },
  getVoucherTemplateLayout() {
    return api.get('/api/voucher/config/template-layout')
  },
  saveVoucherTemplateLayout(payload) {
    return api.put('/api/voucher/config/template-layout', payload)
  },
  getVoucherTemplatePreview() {
    return api.get('/api/voucher/config/template-preview')
  },
  getVoucherTemplate(projectId) {
    return api.get(`/api/voucher/${projectId}/template`)
  },
  getVoucherLayout(projectId) {
    return api.get(`/api/voucher/${projectId}/layout`)
  },
  saveVoucherLayout(projectId, payload) {
    return api.post(`/api/voucher/${projectId}/layout`, payload)
  },
  generateVoucherFromLayout(projectId, payload) {
    return api.post(`/api/voucher/${projectId}/generate`, payload, {
      responseType: 'blob'
    })
  },
  toAbsoluteUrl(path) {
    return new URL(path, API_BASE_URL).toString()
  },
  getVoucherImageUrl(projectId, jobId, thumb = true) {
    return `/api/voucher/${projectId}/image/${jobId}?thumb=${thumb ? 'true' : 'false'}`
  },
  runArchive(projectId) {
    return api.post(`/api/projects/${projectId}/run_archive`)
  },

  // =====================
  // Activity Info
  // =====================
  updateActivityInfo(projectId, info) {
    return api.post(`/api/projects/${projectId}/activity_info`, info)
  },

  // =====================
  // Groups
  // =====================
  listGroups() {
    return api.get('/api/projects/groups/list')
  },
  upsertGroup(groupName, leaderName) {
    return api.post('/api/projects/groups', { group_name: groupName, leader_name: leaderName })
  },
  deleteGroupLeader(groupName, leaderName) {
    return api.delete(`/api/projects/groups/${encodeURIComponent(groupName)}/leaders/${encodeURIComponent(leaderName)}`)
  },
  deleteGroup(groupName) {
    return api.delete(`/api/projects/groups/${encodeURIComponent(groupName)}`)
  },
  uploadLeaderStamps(groupName, leaderName, files) {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    return api.post(
      `/api/projects/groups/${encodeURIComponent(groupName)}/leaders/${encodeURIComponent(leaderName)}/stamps`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
  },
  deleteLeaderStamp(groupName, leaderName, filename) {
    return api.delete(
      `/api/projects/groups/${encodeURIComponent(groupName)}/leaders/${encodeURIComponent(leaderName)}/stamps/${encodeURIComponent(filename)}`
    )
  },

  // =====================
  // Stamp Repository
  // =====================
  listStamps() {
    return api.get('/api/stamps')
  },
  detectStamps(file, mode = 'red') {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('mode', mode)
    return api.post('/api/stamps/detect', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  registerStamps(file, mode = 'red', selections = []) {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('mode', mode)
    formData.append('selections', JSON.stringify(selections))
    return api.post('/api/stamps/register', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  deleteStampById(stampId) {
    return api.delete(`/api/stamps/${stampId}`)
  },

  // =====================
  // Manual Correction
  // =====================
  getJobDetails(projectId, jobId) {
    return api.get(`/api/projects/${projectId}/jobs/${jobId}/details`)
  },
  saveManualJson(projectId, jobId, jsonData) {
    return api.put(`/api/projects/${projectId}/jobs/${jobId}/json`, { json_data: jsonData })
  },

  // =====================
  // Config
  // =====================
  getConfig() {
    return api.get('/api/config/')
  },
  updateConfig(settings) {
    return api.post('/api/config/', settings)
  },
  listVisionModels() {
    return api.get('/api/config/vision-models')
  },

  // =====================
  // Suggestions (Autocomplete)
  // =====================
  getSuggestions(category, query = '', limit = 20) {
    return api.get(`/api/suggestions`, { params: { category, q: query, limit } })
  },
  addSuggestion(category, value) {
    return api.post(`/api/suggestions`, { category, value })
  },
  bulkAddSuggestions(category, values) {
    return api.post(`/api/suggestions/bulk`, { category, values })
  }
}
