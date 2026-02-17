import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {}
})

export default {
  // =====================
  // Projects CRUD
  // =====================
  getProjects() {
    return api.get('/api/projects/')
  },
  createProject(formData) {
    return api.post('/api/projects/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  getProject(projectId) {
    return api.get(`/api/projects/${projectId}`)
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
  addFiles(projectId, formData) {
    return api.post(`/api/projects/${projectId}/add_files`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
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

  // =====================
  // Export & Archive
  // =====================
  runExport(projectId) {
    return api.post(`/api/projects/${projectId}/run_export`)
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
  deleteGroup(groupName) {
    return api.delete(`/api/projects/groups/${groupName}`)
  },

  // =====================
  // Manual Correction
  // =====================
  getJobDetails(projectId, jobId) {
    return api.get(`/api/projects/${projectId}/jobs/${jobId}/details`)
  },
  
  getProjectJobIds(projectId) {
    return api.get(`/api/projects/${projectId}/job-ids`)
  },
  saveManualJson(projectId, jobId, jsonData) {
    return api.put(`/api/projects/${projectId}/jobs/${jobId}/json`, { json_data: jsonData })
  },
  regenerateFromManual(projectId, jobId) {
      // Deprecated, but keeping method signature for now if needed by legacy calls
      console.warn("regenerateFromManual is deprecated. Use runSingleProcessing instead.")
      return api.post(`/api/projects/${projectId}/jobs/${jobId}/regenerate_from_manual`)
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
