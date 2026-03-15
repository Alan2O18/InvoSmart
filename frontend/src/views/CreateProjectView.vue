<template>
  <div class="create-project">
    <h1>Create New Activity</h1>
    <form @submit.prevent="createProject" class="project-form">
      
      <!-- Basic Info -->
      <section>
        <h2>Basic Information</h2>
        <div class="form-row">
          <div class="form-group">
            <label for="projectId">Activity ID *</label>
            <input type="text" id="projectId" v-model="form.projectId" required placeholder="e.g. ACT-001" />
          </div>
          <div class="form-group">
            <label for="projectName">Activity Name *</label>
            <input type="text" id="projectName" v-model="form.projectName" required placeholder="Enter activity name" />
          </div>
        </div>
        
        <div class="form-row">
          <div class="form-group">
            <label for="group">Group</label>
            <input type="text" id="group" v-model="form.group" list="group-list" @change="onGroupChange" />
            <datalist id="group-list">
              <option v-for="g in groups" :key="g.group_name" :value="g.group_name"></option>
            </datalist>
          </div>
          <div class="form-group">
            <label for="leader">Leader</label>
            <input type="text" id="leader" v-model="form.leader" :list="form.group ? 'leader-list' : undefined" />
            <datalist id="leader-list">
              <option v-for="leader in availableLeaders" :key="leader" :value="leader"></option>
            </datalist>
          </div>
          <div class="form-group">
            <label for="coordinator">Coordinator (活動總召)</label>
            <input type="text" id="coordinator" v-model="form.coordinator" />
          </div>
          <div class="form-group">
            <label for="generalAffairs">General Affairs (活動總務)</label>
            <input type="text" id="generalAffairs" v-model="form.generalAffairs" />
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
            <label for="budgetDate">Budget Approval Date (Start - 3 days)</label>
            <input type="date" id="budgetDate" v-model="form.budgetDate" />
          </div>
          <div class="form-group">
            <label for="finalAccountDate">Final Account Date (Start + 1 day)</label>
            <input type="date" id="finalAccountDate" v-model="form.finalAccountDate" />
          </div>
        </div>
      </section>

      <!-- Files -->
      <section>
        <h2>Files</h2>
        <div class="form-group">
          <label for="files">Upload Images *</label>
          <input 
            type="file" 
            id="files" 
            @change="handleFileUpload" 
            multiple 
            accept="image/*"
            required
          />
          <p class="hint">Select one or more image files.</p>
        </div>
      </section>

      <div class="actions">
        <button type="button" @click="$router.push('/')" class="secondary">Cancel</button>
        <button type="submit" :disabled="loading">
          {{ loading ? 'Creating...' : 'Create Activity' }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'

const router = useRouter()
const loading = ref(false)
const files = ref([])

const form = reactive({
  projectId: '',
  projectName: '',
  activityId: '', // Keeping this for backward compatibility or if user wants separate field
  group: '',
  leader: '',
  coordinator: '',
  generalAffairs: '',
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

const groups = ref([])
const availableLeaders = ref([])

onMounted(async () => {
  try {
    const res = await api.listGroups()
    groups.value = res.data
  } catch(e) {
    console.error('Failed to load groups', e)
  }
})

const onGroupChange = () => {
  const selected = groups.value.find(g => g.group_name === form.group)
  const leaderNames = selected?.leader_names || []
  availableLeaders.value = leaderNames
  if (leaderNames.length > 0 && !leaderNames.includes(form.leader)) {
    form.leader = leaderNames[0]
  }
}

const handleFileUpload = (event) => {
  files.value = Array.from(event.target.files)
}

const onStartTimeChange = () => {
  if (!form.startTime) return
  
  const start = new Date(form.startTime)
  
  // Budget: Start - 3 days
  const budget = new Date(start)
  budget.setDate(start.getDate() - 3)
  form.budgetDate = budget.toISOString().split('T')[0]
  
  // Final Account: Start + 1 day
  const final = new Date(start)
  final.setDate(start.getDate() + 1)
  form.finalAccountDate = final.toISOString().split('T')[0]
}

const createProject = async () => {
  if (!form.projectId || !form.projectName || files.value.length === 0) {
    alert('Please fill in Activity ID, Activity Name, and upload at least one file.')
    return
  }

  loading.value = true
  try {
    const formData = new FormData()
    formData.append('project_id', form.projectId)
    
    // Pack metadata - projectName goes into metadata with special handling
    const metadata = {
      name: form.projectName,  // Activity Name stored as 'name' in metadata
      projectName: form.projectName,  // Keep for backward compatibility
      group: form.group,
      leader: form.leader,
      coordinator: form.coordinator,
      generalAffairs: form.generalAffairs,
      startTime: form.startTime,
      endTime: form.endTime,
      location: form.location,
      teacherCount: form.teacherCount,
      studentCount: form.studentCount,
      subsidyReason: form.subsidyReason,
      subsidyMethod: form.subsidyMethod,
      balanceHandling: form.balanceHandling,
      overdraftHandling: form.overdraftHandling,
      budgetDate: form.budgetDate,
      finalAccountDate: form.finalAccountDate
    }
    formData.append('metadata', JSON.stringify(metadata))

    files.value.forEach(file => {
      formData.append('files', file)
    })

    await api.createProject(formData)
    router.push('/')
  } catch (error) {
    console.error('Failed to create activity:', error)
    alert('Failed to create activity. See console for details.')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.create-project {
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
  color: #42b883;
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
  border-color: #42b883;
  outline: none;
}

.hint {
  font-size: 0.8rem;
  color: #888;
  margin-top: 0.5rem;
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
  background: #42b883;
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
