<template>
  <div class="edit-project" v-if="form.projectName">
    <h1>Edit Project: {{ form.projectName }}</h1>
    <form @submit.prevent="updateProject" class="project-form">
      
      <!-- Basic Info -->
      <section>
        <h2>Basic Information</h2>
        <div class="form-row">
          <div class="form-group">
            <label for="activityId">Activity ID</label>
            <input type="text" id="activityId" v-model="form.activityId" placeholder="e.g. ACT-001" />
          </div>
        </div>
        
        <div class="form-row">
          <div class="form-group">
            <label for="group">Group</label>
            <input type="text" id="group" v-model="form.group" />
          </div>
          <div class="form-group">
            <label for="leader">Leader</label>
            <input type="text" id="leader" v-model="form.leader" />
          </div>
          <div class="form-group">
            <label for="coordinator">Coordinator</label>
            <input type="text" id="coordinator" v-model="form.coordinator" />
          </div>
        </div>
      </section>

      <!-- Date & Location -->
      <section>
        <h2>Date & Location</h2>
        <div class="form-row">
          <div class="form-group">
            <label for="startTime">Start Time</label>
            <input type="datetime-local" id="startTime" v-model="form.startTime" @change="onStartTimeChange" />
          </div>
          <div class="form-group">
            <label for="endTime">End Time</label>
            <input type="datetime-local" id="endTime" v-model="form.endTime" />
          </div>
        </div>
        <div class="form-group">
          <label for="location">Location</label>
          <input type="text" id="location" v-model="form.location" />
        </div>
      </section>

      <!-- Participants -->
      <section>
        <h2>Participants</h2>
        <div class="form-row">
          <div class="form-group">
            <label for="teacherCount">Teacher Count</label>
            <input type="number" id="teacherCount" v-model="form.teacherCount" min="0" />
          </div>
          <div class="form-group">
            <label for="studentCount">Student Count</label>
            <input type="number" id="studentCount" v-model="form.studentCount" min="0" />
          </div>
        </div>
      </section>

      <!-- Financial -->
      <section>
        <h2>Financial Details</h2>
        <div class="form-group">
          <label for="subsidyReason">Subsidy Reason</label>
          <textarea id="subsidyReason" v-model="form.subsidyReason" rows="2"></textarea>
        </div>
        <div class="form-group">
          <label for="subsidyMethod">Subsidy Method</label>
          <textarea id="subsidyMethod" v-model="form.subsidyMethod" rows="2"></textarea>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label for="balanceHandling">Balance Handling</label>
            <input type="text" id="balanceHandling" v-model="form.balanceHandling" />
          </div>
          <div class="form-group">
            <label for="overdraftHandling">Overdraft Handling</label>
            <input type="text" id="overdraftHandling" v-model="form.overdraftHandling" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label for="budgetDate">Budget Approval Date</label>
            <input type="date" id="budgetDate" v-model="form.budgetDate" />
          </div>
          <div class="form-group">
            <label for="finalAccountDate">Final Account Date</label>
            <input type="date" id="finalAccountDate" v-model="form.finalAccountDate" />
          </div>
        </div>
      </section>

      <div class="actions">
        <button type="button" @click="$router.push('/')" class="secondary">Cancel</button>
        <button type="submit" :disabled="loading">
          {{ loading ? 'Saving...' : 'Save Changes' }}
        </button>
      </div>
    </form>
  </div>
  <div v-else class="loading">Loading project data...</div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import api from '../services/api'

const router = useRouter()
const route = useRoute()
const projectId = route.params.id
const loading = ref(false)

const form = reactive({
  projectName: '',
  activityId: '',
  group: '',
  leader: '',
  coordinator: '',
  startTime: '',
  endTime: '',
  location: '',
  teacherCount: 0,
  studentCount: 0,
  subsidyReason: '',
  subsidyMethod: '',
  balanceHandling: '',
  overdraftHandling: '',
  budgetDate: '',
  finalAccountDate: ''
})

const fetchProject = async () => {
  try {
    // We need a way to get project metadata. 
    // Currently list_projects returns it, but getProject (status) does not.
    // Let's assume we can get it from list_projects for now or update backend.
    // Actually, list_projects is efficient enough for small number of projects.
    const res = await api.getProjects()
    const project = res.data.find(p => p.project_id === projectId)
    
    if (project) {
      form.projectName = project.name
      const meta = project.metadata || {}
      Object.assign(form, meta)
      // Ensure name is consistent
      form.projectName = project.name 
    } else {
      alert('Project not found')
      router.push('/')
    }
  } catch (error) {
    console.error('Failed to fetch project:', error)
  }
}

const onStartTimeChange = () => {
  if (!form.startTime) return
  // Only auto-set if empty to avoid overwriting user manual changes? 
  // User said "don't link", so manual override is possible. 
  // But "auto-generate based on start time" implies a trigger.
  // I'll trigger it only if the target fields are empty or user explicitly changed start time just now.
  // Simple logic: just set it, user can change it back.
  
  const start = new Date(form.startTime)
  
  const budget = new Date(start)
  budget.setDate(start.getDate() - 3)
  form.budgetDate = budget.toISOString().split('T')[0]
  
  const final = new Date(start)
  final.setDate(start.getDate() + 1)
  form.finalAccountDate = final.toISOString().split('T')[0]
}

const updateProject = async () => {
  loading.value = true
  try {
    const metadata = { ...form }
    delete metadata.projectName // stored in main table, but we only update metadata col for now
    
    await api.updateProject(projectId, metadata)
    router.push('/')
  } catch (error) {
    console.error('Failed to update project:', error)
    alert('Failed to update project.')
  } finally {
    loading.value = false
  }
}

onMounted(fetchProject)
</script>

<style scoped>
.edit-project {
  max-width: 800px;
  margin: 0 auto;
  padding: 2rem;
}

.project-form {
  background: #2a2a2a;
  padding: 2rem;
  border-radius: 8px;
  margin-top: 2rem;
}

section {
  margin-bottom: 2rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #444;
}

section:last-child {
  border-bottom: none;
}

h2 {
  font-size: 1.2rem;
  margin-bottom: 1rem;
  color: #60a5fa; /* Blue for edit mode */
}

.form-row {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.form-group {
  margin-bottom: 1rem;
  flex: 1;
  min-width: 200px;
}

label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #ddd;
}

input, textarea {
  width: 100%;
  padding: 0.8rem;
  border: 1px solid #444;
  background: #1a1a1a;
  color: white;
  border-radius: 4px;
}

input:focus, textarea:focus {
  border-color: #60a5fa;
  outline: none;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 2rem;
}

button {
  padding: 0.8rem 1.5rem;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  background: #60a5fa;
  color: white;
}

button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

button.secondary {
  background: transparent;
  border: 1px solid #444;
}

button.secondary:hover {
  border-color: #666;
  background: #333;
}
</style>
