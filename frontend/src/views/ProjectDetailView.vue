<template>
  <div class="project-detail" v-if="project">
    <header class="detail-header">
      <button @click="$router.push('/')" class="back-btn">← Back</button>
      <h1>{{ project.projectName || project.name || project.project_id }} ({{ project.project_id }})</h1>
      <span class="status-badge" :class="project.status">{{ project.status }}</span>
    </header>

    <div class="pipeline-controls">
      <div class="step" :class="{ active: canSplit }">
        <h3>1. Split</h3>
        <button @click="runSplit" :disabled="!canSplit || loading">Run Split (All)</button>
      </div>
      <div class="arrow">→</div>
      <div class="step" :class="{ active: canOCR }">
        <h3>2. OCR</h3>
        <button @click="runOCR" :disabled="!canOCR || loading">Run OCR (All)</button>
      </div>
      <div class="arrow">→</div>
      <div class="step" :class="{ active: canLLM }">
        <h3>3. LLM</h3>
        <button @click="runLLM" :disabled="!canLLM || loading">Run LLM (All)</button>
      </div>
      <div class="arrow">→</div>
      <div class="step" :class="{ active: canExport }">
        <h3>4. Export</h3>
        <button @click="runExport" :disabled="!canExport || loading">Export Excel</button>
      </div>
      <div class="arrow">→</div>
      <div class="step" :class="{ active: canArchive }">
        <h3>5. Archive</h3>
        <button @click="runArchive" :disabled="!canArchive || loading">Archive</button>
      </div>
    </div>

    <div class="actions-section">
      <h3>Actions</h3>
      <div class="action-group">
        <label>Add Files (Raw):</label>
        <input type="file" multiple @change="(e) => handleFileUpload(e, 'raw')" />
      </div>
      <div class="action-group">
        <label>Add Files (Split):</label>
        <input type="file" multiple @change="(e) => handleFileUpload(e, 'split')" />
      </div>
    </div>

    <div class="jobs-section">
      <h3>Raw Files</h3>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Preview</th>
              <th>Filename</th>
              <th>Split Count</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="file in rawFiles" :key="file.filename">
              <td class="preview-cell">
                <img :src="getRawImageUrl(file.filename)" class="preview-img" @error="handleImgError" />
              </td>
              <td class="filename">{{ file.filename }}</td>
              <td>
                <span class="badge" :class="file.split_count > 0 ? 'success' : 'pending'">
                  {{ file.split_count }}
                </span>
              </td>
              <td>
                <button @click="runSplitSingle(file)" class="mini-btn">Split This File</button>
                <button @click="deleteRawFile(file)" class="mini-btn danger">Delete</button>
              </td>
            </tr>
            <tr v-if="rawFiles.length === 0">
              <td colspan="4" class="no-data">No raw files found.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="jobs-section">
      <h3>Jobs / Invoices</h3>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Preview</th>
              <th>Filename</th>
              <th>OCR</th>
              <th>LLM</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in jobs" :key="job.job_id">
              <td>
                <div class="img-preview">
                  <img :src="getImageUrl(job.image_path)" alt="preview" @error="handleImgError" />
                </div>
              </td>
              <td class="filename" :title="job.image_path">{{ getFilename(job.image_path) }}</td>
              <td>
                <span class="badge" :class="getOCRBadgeClass(job)">
                  {{ getOCRStatusText(job) }}
                </span>
                <button v-if="!isOCRDone(job) || job.status === 'done'" @click="runSingleOCR(job)" class="mini-btn">
                  {{ isOCRDone(job) ? 'Rerun' : 'Run' }}
                </button>
              </td>
              <td>
                <span class="badge" :class="getLLMBadgeClass(job)">
                  {{ getLLMStatusText(job) }}
                </span>
                <button v-if="(isOCRDone(job) && !isLLMDone(job)) || job.status === 'done'" @click="runSingleLLM(job)" class="mini-btn">
                  {{ isLLMDone(job) ? 'Rerun' : 'Run' }}
                </button>
              </td>
              <td>
                <div class="actions-cell">
                  <button @click="editJob(job)" class="mini-btn edit">Edit</button>
                  <button @click="rotateImage(job, 90)" class="icon-btn" title="Rotate Right">↻</button>
                  <button @click="rotateImage(job, -90)" class="icon-btn" title="Rotate Left">↺</button>
                  <button @click="deleteJob(job)" class="mini-btn danger">Delete</button>
                </div>
              </td>
            </tr>
            <tr v-if="jobs.length === 0">
              <td colspan="5" class="no-data">No jobs found.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
  <div v-else class="loading">Loading...</div>
</template>

<script setup>
import { ref, onMounted, computed, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../services/api'

const route = useRoute()
const router = useRouter()
const projectId = route.params.id
const project = ref(null)
const progress = ref(null)
const jobs = ref([])
const rawFiles = ref([])
const loading = ref(false)
let pollInterval = null

const fetchProjectData = async () => {
  try {
    const statusRes = await api.getProject(projectId)
    progress.value = statusRes.data
    
    project.value = { 
        project_id: projectId, 
        status: progress.value.suggested_status,
        name: statusRes.data.metadata?.projectName || projectId,
        projectName: statusRes.data.metadata?.projectName
    }

    const jobsRes = await api.getProjectJobs(projectId)
    jobs.value = jobsRes.data

    const rawRes = await api.getRawFiles(projectId)
    rawFiles.value = rawRes.data
  } catch (error) {
    console.error('Error fetching project data:', error)
  }
}

onMounted(() => {
  fetchProjectData()
  pollInterval = setInterval(fetchProjectData, 2000)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})

const canSplit = computed(() => progress.value?.ingested)
const canOCR = computed(() => progress.value?.split)
const canLLM = computed(() => progress.value?.split)
const canExport = computed(() => progress.value?.processed)
const canArchive = computed(() => project.value?.status === 'ARCHIVED' || project.value?.status === 'SEALED' || progress.value?.processed)

const imageVersions = ref({})

const getImageUrl = (path) => {
  if (!path) return '';
  const filename = path.split('\\').pop().split('/').pop();
  const v = imageVersions.value[filename] || 0;
  return `http://localhost:8000/static/${encodeURIComponent(projectId)}/分割發票/${encodeURIComponent(filename)}?v=${v}`;
}

const getRawImageUrl = (filename) => {
  if (!filename) return '';
  return `http://localhost:8000/static/${encodeURIComponent(projectId)}/原始輸入/${encodeURIComponent(filename)}`;
}

const getFilename = (path) => {
  if (!path) return '';
  return path.split('\\').pop().split('/').pop();
}

const handleImgError = (e) => {
  e.target.src = 'https://via.placeholder.com/100x150?text=No+Image';
}

const isOCRDone = (job) => {
  return job.ocr_done_at || job.status === 'done' || (job.stage === 'llm') || (job.stage === 'finalize');
}

const isLLMDone = (job) => {
  return job.llm_done_at || (job.status === 'done' && job.stage === 'finalize');
}

const getOCRStatusText = (job) => {
  // Priority: active status first, then done status
  if (job.status === 'running' && job.stage === 'ocr') return 'Running';
  if (job.status === 'pending' && job.stage === 'ocr') return 'Pending';
  if (isOCRDone(job)) return '✓ Done';
  if (job.status === 'ready' && job.stage === 'ocr') return 'Ready';
  return '-';
}

const getOCRBadgeClass = (job) => {
  // Priority: active status first
  if (job.status === 'running' && job.stage === 'ocr') return 'pending';
  if (job.status === 'pending' && job.stage === 'ocr') return 'pending';
  if (isOCRDone(job)) return 'success';
  if (job.status === 'ready' && job.stage === 'ocr') return 'info';
  return 'pending';
}

const getLLMStatusText = (job) => {
  // Priority: active status first, then done status
  if (job.status === 'running' && job.stage === 'llm') return 'Running';
  if (job.status === 'pending' && job.stage === 'llm') return 'Pending';
  if (isLLMDone(job)) return '✓ Done';
  if (job.status === 'ready' && job.stage === 'llm') return 'Ready';
  if (isOCRDone(job)) return '-';  // OCR done but LLM not started
  return '-';
}

const getLLMBadgeClass = (job) => {
  // Priority: active status first
  if (job.status === 'running' && job.stage === 'llm') return 'pending';
  if (job.status === 'pending' && job.stage === 'llm') return 'pending';
  if (isLLMDone(job)) return 'success';
  if (job.status === 'ready' && job.stage === 'llm') return 'info';
  return 'pending';
}

const runSplit = async () => {
  loading.value = true
  try { await api.runSplit(projectId); await fetchProjectData(); } 
  catch (e) { alert(e); } 
  finally { loading.value = false; }
}

const runSplitSingle = async (file) => {
  loading.value = true
  try { await api.runSplitSingle(projectId, file.filename); await fetchProjectData(); } 
  catch (e) { alert(e); } 
  finally { loading.value = false; }
}

const deleteJob = async (job) => {
  if (!confirm('Are you sure you want to delete this job?')) return;
  loading.value = true
  try { await api.deleteJob(projectId, job.job_id); await fetchProjectData(); } 
  catch (e) { alert(e); } 
  finally { loading.value = false; }
}

const deleteRawFile = async (file) => {
  if (!confirm('Are you sure you want to delete this raw file?')) return;
  loading.value = true
  try { await api.deleteRawFile(projectId, file.filename); await fetchProjectData(); } 
  catch (e) { alert(e); } 
  finally { loading.value = false; }
}

const runOCR = async () => {
  loading.value = true
  try { await api.runOCR(projectId); await fetchProjectData(); } 
  catch (e) { alert(e); } 
  finally { loading.value = false; }
}

const runLLM = async () => {
  loading.value = true
  try { await api.runLLM(projectId); await fetchProjectData(); } 
  catch (e) { alert(e); } 
  finally { loading.value = false; }
}

const runExport = async () => {
  loading.value = true
  try { 
      const res = await api.runExport(projectId); 
      alert('Exported to: ' + (res.data.path || res.data));
      await fetchProjectData(); 
  } 
  catch (e) { alert(e); } 
  finally { loading.value = false; }
}

const runArchive = async () => {
  loading.value = true
  try { 
      const res = await api.runArchive(projectId); 
      if(res.data.status === 'sealed') alert('Archived to: ' + res.data.path);
      else alert('Archive result: ' + JSON.stringify(res.data));
      await fetchProjectData(); 
  } 
  catch (e) { alert(e); } 
  finally { loading.value = false; }
}

const handleFileUpload = async (event, type) => {
  const files = event.target.files;
  if (!files.length) return;

  const formData = new FormData();
  formData.append('type', type);
  for (let i = 0; i < files.length; i++) {
    formData.append('files', files[i]);
  }

  loading.value = true;
  try {
    await api.addFiles(projectId, formData);
    alert('Files added successfully');
    await fetchProjectData();
  } catch (e) {
    alert('Error adding files: ' + e);
  } finally {
    loading.value = false;
    event.target.value = ''; // Reset input
  }
}

const rotateImage = async (job, angle) => {
  const filename = getFilename(job.image_path);
  try {
    await api.rotateImage(projectId, filename, angle);
    imageVersions.value[filename] = Date.now();
    await fetchProjectData();
  } catch (e) {
    alert('Error rotating image: ' + e);
  }
}

const runSingleOCR = async (job) => {
  loading.value = true;
  try {
    await api.runSingleOCR(projectId, job.job_id);
    await fetchProjectData();
  } catch (e) {
    alert('Error running OCR: ' + e);
  } finally {
    loading.value = false;
  }
}

const runSingleLLM = async (job) => {
  loading.value = true;
  try {
    await api.runSingleLLM(projectId, job.job_id);
    await fetchProjectData();
  } catch (e) {
    alert('Error running LLM: ' + e);
  } finally {
    loading.value = false;
  }
}

const editJob = (job) => {
  router.push(`/project/${projectId}/edit-job?jobId=${job.job_id}`)
}

</script>

<style scoped>
.project-detail {
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
  color: #e0e0e0;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 2rem;
}

.back-btn {
  background: transparent;
  border: 1px solid #666;
  color: #e0e0e0;
  padding: 0.5rem 1rem;
  cursor: pointer;
}

.status-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 99px;
  font-size: 0.875rem;
  background: #444;
  color: white;
}

.status-badge.NEW { background: #3b82f6; }
.status-badge.SPLIT { background: #8b5cf6; }
.status-badge.PROCESSING { background: #f59e0b; }
.status-badge.PROCESSED { background: #10b981; }
.status-badge.ARCHIVED { background: #6366f1; }
.status-badge.SEALED { background: #64748b; }

.pipeline-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
  background: #2a2a2a;
  padding: 2rem;
  border-radius: 8px;
  margin-bottom: 2rem;
  overflow-x: auto;
}

.step {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  align-items: center;
  min-width: 120px;
  opacity: 0.5;
  transition: opacity 0.3s;
}

.step.active {
  opacity: 1;
}

.step button {
    background: #444;
    color: white;
    border: none;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    cursor: pointer;
}

.step button:disabled {
    cursor: not-allowed;
    opacity: 0.7;
}

.arrow {
  color: #666;
  font-size: 1.5rem;
}

.actions-section, .jobs-section {
  background: #2a2a2a;
  padding: 1.5rem;
  border-radius: 8px;
  margin-bottom: 2rem;
}

.action-group {
    margin-bottom: 1rem;
}

.action-group label {
    display: inline-block;
    width: 150px;
    color: #aaa;
}

.table-container {
    overflow-x: auto;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 1rem;
}

th, td {
    padding: 1rem;
    text-align: left;
    border-bottom: 1px solid #444;
}

th {
    color: #888;
    font-weight: 600;
}

.img-preview img {
    max-width: 100px;
    max-height: 100px;
    object-fit: contain;
    border: 1px solid #444;
    background: #000;
}

.preview-img {
    max-width: 80px;
    max-height: 80px;
    object-fit: contain;
}

.badge {
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: bold;
    margin-right: 0.5rem;
}

.badge.success { background: #059669; color: white; }
.badge.warning { background: #d97706; color: white; }
.badge.pending { background: #4b5563; color: #d1d5db; }
.badge.info { background: #0ea5e9; color: white; }

.status-cell {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.mini-btn {
    padding: 0.2rem 0.5rem;
    font-size: 0.75rem;
    background: #2563eb;
    color: white;
    border: none;
    border-radius: 3px;
    cursor: pointer;
    margin-left: 0.25rem;
}

.mini-btn.danger {
    background: #dc2626;
}

.mini-btn.edit {
    background: #8b5cf6;
}

.icon-btn {
    background: transparent;
    border: 1px solid #555;
    color: #ddd;
    padding: 0.25rem 0.5rem;
    border-radius: 3px;
    cursor: pointer;
    margin-right: 0.25rem;
}

.icon-btn:hover {
    background: #444;
}

.actions-cell {
    display: flex;
    gap: 0.5rem;
    align-items: center;
}

.no-data {
    text-align: center;
    color: #666;
    padding: 2rem;
}
</style>
