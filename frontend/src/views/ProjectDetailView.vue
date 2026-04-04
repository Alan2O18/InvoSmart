<template>
  <div class="project-detail" v-if="project">
    <header class="detail-header">
      <div style="display: flex; gap: 1rem; align-items: center; justify-content: flex-start;">
        <button @click="$router.push('/')" class="back-btn">← 返回列表</button>
        <h1 style="margin: 0;">{{ project.name || project.project_id }}</h1>
        <button @click="$router.push(`/edit/${project.project_id}`)" class="edit-btn">編輯預算與報表</button>
      </div>
      <div class="header-info">
        <span class="activity-id">活動編號：{{ project.project_id }}</span>
        <span class="status-badge" :class="project.status">{{ project.status }}</span>
      </div>
    </header>

    <!-- VLM-First Pipeline: 簡化為 3 步驟 -->
    <div class="pipeline-controls">
      <div class="step" :class="{ active: canSplit }">
        <h3>1. 分割</h3>
        <button @click="runSplit" :disabled="!canSplit || loading">分割圖片</button>
      </div>
      <div class="arrow">→</div>
      <div class="step" :class="{ active: canProcess }">
        <h3>2. 處理</h3>
        <button @click="runProcessing" :disabled="!canProcess || loading">VLM 處理</button>
      </div>
      <div class="arrow">→</div>
      <div class="step" :class="{ active: canExport }">
        <h3>3. 匯出</h3>
        <div style="display: flex; flex-direction: column; gap: 0.5rem; justify-content: center; align-items: center;">
          <button @click="runExport" :disabled="!canExport || loading">匯出 Excel</button>
        </div>
      </div>
      <div class="arrow">→</div>
      <div class="step" :class="{ active: canGenerateVoucher }">
        <h3>4. 匯出憑證</h3>
        <div style="display: flex; flex-direction: column; gap: 0.5rem; justify-content: center; align-items: center;">
          <button @click="openVoucherEditor" :disabled="!canGenerateVoucher || loading" class="mini-btn">開啟憑證編輯器</button>
        </div>
      </div>
      <div class="arrow">→</div>
      <div class="step" :class="{ active: canArchive }">
        <h3>5. 封存</h3>
        <button @click="runArchive" :disabled="!canArchive || loading">封存活動</button>
      </div>
    </div>

    <div class="actions-section">
      <h3>新增憑證圖片</h3>
      <div class="action-group">
        <label>上傳未分割的原始圖 (Raw):</label>
        <input type="file" multiple @change="(e) => handleFileUpload(e, 'raw')" />
      </div>
      <div class="action-group">
        <label>上傳已分割的圖 (Split):</label>
        <input type="file" multiple @change="(e) => handleFileUpload(e, 'split')" />
      </div>
      <div class="action-group" style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #444;">
        <label style="color: #60a5fa; font-weight: bold;">上傳 PDF 檔案:</label>
        <input type="file" multiple accept="application/pdf" @change="(e) => handlePdfUpload(e)" />
      </div>

      <!-- Progress Bars -->
      <div v-if="showProgressOverlay" class="progress-overlay">
        <div class="progress-item">
          <label>📤 上傳進度 (A):</label>
          <div class="progress-bar-track">
            <div class="progress-bar-fill upload" :style="{ width: uploadProgress + '%' }"></div>
          </div>
          <span class="progress-text">{{ uploadProgress }}%</span>
        </div>
        <div v-if="conversionProgress" class="progress-item">
          <label>🔄 轉檔進度 (B):</label>
          <div class="progress-bar-track">
            <div class="progress-bar-fill conversion" :style="{ width: conversionPercent + '%' }"></div>
          </div>
          <span class="progress-text">{{ conversionProgress.current }} / {{ conversionProgress.total }}</span>
        </div>
      </div>
    </div>

    <div class="jobs-section">
      <h3>原始圖清單 (Raw Files)</h3>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>預覽</th>
              <th>檔名</th>
              <th>分割數</th>
              <th>操作</th>
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
                <button @click="runSplitSingle(file)" class="mini-btn">分割此圖</button>
                <button @click="deleteRawFile(file)" class="mini-btn danger">刪除</button>
              </td>
            </tr>
            <tr v-if="rawFiles.length === 0">
              <td colspan="4" class="no-data">尚無原始檔。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="jobs-section">
      <h3>單張憑證處理 (Jobs / Invoices)</h3>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>預覽</th>
              <th>檔名</th>
              <th>狀態</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in receiptJobs" :key="job.job_id">
              <td>
                <div class="img-preview">
                  <img :src="getImageUrl(job.image_path)" alt="preview" @error="handleImgError" />
                </div>
              </td>
              <td class="filename" :title="job.image_path">
                {{ getFilename(job.image_path) }}
              </td>
              <td>
                <div>
                  <span class="badge" :class="getStatusBadgeClass(job)">
                    {{ getStatusText(job) }}
                  </span>
                </div>
                <button v-if="canShowProcessButton(job)" @click="runSingleProcessing(job)" class="mini-btn mt-2">
                  {{ isDone(job) ? '重新處理' : '處理' }}
                </button>
              </td>
              <td>
                <div class="actions-cell">
                  <button @click="editJob(job)" class="mini-btn edit">核對資料</button>
                  <button @click="openResplitModal(job)" class="mini-btn split-btn">手動二切</button>
                  <button @click="rotateImage(job, 90)" class="icon-btn" title="Rotate Right">↻</button>
                  <button @click="rotateImage(job, -90)" class="icon-btn" title="Rotate Left">↺</button>
                  <button @click="deleteJob(job)" class="mini-btn danger">Delete</button>
                </div>
              </td>
            </tr>
            <tr v-if="receiptJobs.length === 0">
              <td colspan="4" class="no-data">尚無發票憑證。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- PDF 檔案區塊 -->
    <div class="jobs-section">
      <h3>獨立 PDF 文件 (PDF Files)</h3>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>預覽</th>
              <th>檔名</th>
              <th>狀態</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in pdfJobs" :key="job.job_id">
              <td>
                <div class="img-preview">
                  <img :src="getImageUrl(job.image_path)" alt="preview" @error="handleImgError" />
                </div>
              </td>
              <td class="filename" :title="job.source_pdf_path">
                {{ getFilename(job.source_pdf_path) }}
                <div class="pdf-indicator">📄 PDF 檔案</div>
              </td>
              <td>
                <div>
                  <span class="badge" :class="getPdfStatusBadgeClass(job)">
                    PDF: {{ job.pdf_status || 'uploaded' }}
                  </span>
                </div>
              </td>
              <td>
                <div class="actions-cell">
                  <button @click="editPdfJob(job)" class="mini-btn pdf-btn">PDF 蓋章排版</button>
                  <button @click="deleteJob(job)" class="mini-btn danger">Delete</button>
                </div>
              </td>
            </tr>
            <tr v-if="pdfJobs.length === 0">
              <td colspan="4" class="no-data">尚無 PDF 文件。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <ResplitModal
      v-model="showResplitModal"
      :project-id="projectId"
      :job="selectedResplitJob"
      @applied="handleResplitApplied"
    />
  </div>
  <div v-else class="loading">Loading...</div>
</template>

<script setup>
import { ref, onMounted, computed, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../services/api'
import ResplitModal from '../components/ResplitModal.vue'

const route = useRoute()
const router = useRouter()
const projectId = route.params.id
const project = ref(null)
const progress = ref(null)
const jobs = ref([])
const receiptJobs = computed(() => jobs.value.filter(j => !j.source_pdf_path))
const pdfJobs = computed(() => jobs.value.filter(j => j.source_pdf_path))
const rawFiles = ref([])
const loading = ref(false)
const uploadProgress = ref(0)
const conversionProgress = ref(null)
const showProgressOverlay = ref(false)
const showResplitModal = ref(false)
const selectedResplitJob = ref(null)
const conversionPercent = computed(() => {
  if (!conversionProgress.value || conversionProgress.value.total === 0) return 0
  return Math.round((conversionProgress.value.current / conversionProgress.value.total) * 100)
})
let pollInterval = null

const fetchProjectData = async () => {
  try {
    const statusRes = await api.getProject(projectId)
    progress.value = statusRes.data
    
    const projectsRes = await api.getProjects()
    const projectData = projectsRes.data.find(p => p.project_id === projectId)
    
    project.value = { 
        project_id: projectId, 
        status: projectData?.status || 'NEW',
        name: projectData?.name || projectId
    }

    const jobsRes = await api.getProjectJobs(projectId)
    jobs.value = jobsRes.data

    const rawRes = await api.getRawFiles(projectId)
    rawFiles.value = rawRes.data

    // Update conversion progress from backend
    if (statusRes.data?.conversion_progress) {
      conversionProgress.value = statusRes.data.conversion_progress
      const cp = statusRes.data.conversion_progress
      if (cp.current >= cp.total && showProgressOverlay.value && uploadProgress.value >= 100) {
        // Conversion done — hide overlay after a short delay
        setTimeout(() => {
          showProgressOverlay.value = false
          conversionProgress.value = null
        }, 1500)
      }
    } else if (uploadProgress.value >= 100) {
      conversionProgress.value = null
    }
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

// VLM-First: 簡化條件
const canSplit = computed(() => progress.value?.ingested)
const canProcess = computed(() => progress.value?.split)
const canExport = computed(() => progress.value?.processed)
const canArchive = computed(() => project.value?.status === 'ARCHIVED' || project.value?.status === 'SEALED' || progress.value?.processed)
const canGenerateVoucher = computed(() => receiptJobs.value.some(j => j.status === 'done'))

const imageVersions = ref({})

const getImageUrl = (path) => {
  if (!path) return '';
  const filename = path.split('\\').pop().split('/').pop();
  const v = imageVersions.value[filename] || 0;
  return `http://localhost:8000/api/projects/${encodeURIComponent(projectId)}/preview/split/${encodeURIComponent(filename)}?v=${v}`;
}

const getRawImageUrl = (filename) => {
  if (!filename) return '';
  return `http://localhost:8000/api/projects/${encodeURIComponent(projectId)}/preview/raw/${encodeURIComponent(filename)}`;
}

const getFilename = (path) => {
  if (!path) return '';
  return path.split('\\').pop().split('/').pop();
}

const handleImgError = (e) => {
  e.target.src = 'https://via.placeholder.com/100x150?text=No+Image';
}

// VLM-First: 簡化狀態判斷
const isDone = (job) => {
  return job.status === 'done' || job.llm_done_at;
}

const getStatusText = (job) => {
  if (job.status === 'failed') return '✗ 失敗';
  if (job.status === 'running') return '處理中...';
  if (job.status === 'pending') return '等待中';
  if (isDone(job)) return '✓ 完成';
  if (job.status === 'ready') return '待處理';
  return '-';
}

const getStatusBadgeClass = (job) => {
  if (job.status === 'failed') return 'danger';
  if (job.status === 'running') return 'pending';
  if (job.status === 'pending') return 'pending';
  if (isDone(job)) return 'success';
  if (job.status === 'ready') return 'info';
  return 'pending';
}

const getPdfStatusBadgeClass = (job) => {
  if (job.pdf_status === 'failed') return 'danger';
  if (job.pdf_status === 'completed') return 'success';
  if (job.pdf_status === 'uploaded') return 'info';
  if (job.pdf_status === 'pending_compression' || job.pdf_status === 'compressing') return 'pending';
  return 'pending';
}

const canShowProcessButton = (job) => {
  if (job.source_pdf_path) return false;
  if (job.status === 'pending' || job.status === 'running') return false;
  return true;
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

// VLM-First: 單一處理入口
const runProcessing = async () => {
  loading.value = true
  try { 
    await api.runProcessing(projectId); 
    setTimeout(() => fetchProjectData(), 100);
  } 
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

const openVoucherEditor = () => {
  router.push(`/project/${projectId}/voucher-editor`)
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
  uploadProgress.value = 0;
  conversionProgress.value = null;
  showProgressOverlay.value = true;

  try {
    await api.addFiles(projectId, formData, (progressEvent) => {
      if (progressEvent.total) {
        uploadProgress.value = Math.round((progressEvent.loaded * 100) / progressEvent.total);
      }
    });
    await fetchProjectData();
  } catch (e) {
    alert('Error adding files: ' + e);
  } finally {
    loading.value = false;
    event.target.value = '';
  }
}

const handlePdfUpload = async (event) => {
  const files = event.target.files;
  if (!files.length) return;

  const formData = new FormData();
  for (let i = 0; i < files.length; i++) {
    formData.append('files', files[i]);
  }

  loading.value = true;
  uploadProgress.value = 0;
  conversionProgress.value = null;
  showProgressOverlay.value = true;

  try {
    await api.uploadPdf(projectId, formData, (progressEvent) => {
      if (progressEvent.total) {
        uploadProgress.value = Math.round((progressEvent.loaded * 100) / progressEvent.total);
      }
    });
    await fetchProjectData();
  } catch (e) {
    alert('Error adding PDF files: ' + e);
  } finally {
    loading.value = false;
    event.target.value = '';
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

// VLM-First: 單一處理
const runSingleProcessing = async (job) => {
  loading.value = true;
  try {
    await api.runSingleProcessing(projectId, job.job_id);
    await fetchProjectData();
  } catch (e) {
    alert('Error running processing: ' + e);
  } finally {
    loading.value = false;
  }
}

const editJob = (job) => {
  router.push(`/project/${projectId}/edit-job?jobId=${job.job_id}`)
}

const editPdfJob = (job) => {
  router.push(`/project/${projectId}/pdf-editor?jobId=${job.job_id}`)
}

const openResplitModal = (job) => {
  selectedResplitJob.value = job
  showResplitModal.value = true
}

const handleResplitApplied = async () => {
  selectedResplitJob.value = null
  await fetchProjectData()
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
  flex-direction: column;
  gap: 1rem;
  margin-bottom: 2rem;
}

.detail-header h1 {
  margin: 0;
}

.header-info {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.activity-id {
  color: #888;
  font-size: 0.9rem;
  font-weight: 500;
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
    width: 100%;
}

.step button.secondary-btn {
    background: #10b981;
}

.step button:disabled {
    cursor: not-allowed;
    opacity: 0.7;
}

.edit-btn {
  background: transparent;
  border: 1px solid #10b981;
  color: #10b981;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
}
.edit-btn:hover {
  background: #10b98122;
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
.badge.danger { background: #dc2626; color: white; }

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

.mini-btn.pdf-btn {
    background: #0ea5e9;
}

.mini-btn.split-btn {
  background: #14b8a6;
}

.mt-2 {
    margin-top: 0.5rem;
}

.pdf-indicator {
    font-size: 0.75rem;
    color: #60a5fa;
    margin-top: 0.25rem;
    font-weight: 500;
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

.progress-overlay {
    margin-top: 1rem;
    padding: 1rem;
    background: #1a1a2e;
    border-radius: 8px;
    border: 1px solid #333;
}

.progress-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
}

.progress-item:last-child {
    margin-bottom: 0;
}

.progress-item label {
    min-width: 140px;
    font-size: 0.85rem;
    color: #ccc;
}

.progress-bar-track {
    flex: 1;
    height: 12px;
    background: #333;
    border-radius: 6px;
    overflow: hidden;
}

.progress-bar-fill {
    height: 100%;
    border-radius: 6px;
    transition: width 0.3s ease;
}

.progress-bar-fill.upload {
    background: linear-gradient(90deg, #3b82f6, #60a5fa);
}

.progress-bar-fill.conversion {
    background: linear-gradient(90deg, #10b981, #34d399);
}

.progress-text {
    min-width: 60px;
    font-size: 0.8rem;
    color: #aaa;
    text-align: right;
}
</style>
