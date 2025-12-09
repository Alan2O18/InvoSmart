<template>
  <div class="home-container">
    <div class="header">
      <h1>Activities</h1>
      <button @click="$router.push('/create')" class="create-btn">+ New Activity</button>
    </div>

    <div v-if="loading" class="loading">Loading activities...</div>
    
    <div v-else class="projects-table-container">
      <table class="projects-table">
        <thead>
          <tr>
            <th>Activity Name</th>
            <th>Activity ID</th>
            <th>Status</th>
            <th>Updated</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="project in projects" :key="project.project_id" @click="goToProject(project.project_id)" class="clickable-row">
            <td>{{ project.name || project.project_id }}</td>
            <td>{{ project.project_id }}</td>
            <td>
              <span class="status-badge" :class="project.status">{{ project.status }}</span>
            </td>
            <td>{{ new Date(project.updated_at * 1000).toLocaleDateString() }}</td>
            <td class="actions-cell" @click.stop>
              <button class="icon-btn edit" @click="editProject(project)" title="Edit">✎</button>
              <button class="icon-btn delete" @click="deleteProject(project)" title="Delete">🗑</button>
            </td>
          </tr>
          <tr v-if="projects.length === 0">
            <td colspan="5" class="empty-state">No activities found. Create one to get started.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'

const router = useRouter()
const projects = ref([])
const loading = ref(true)

const fetchProjects = async () => {
  try {
    const response = await api.getProjects()
    projects.value = response.data
  } catch (error) {
    console.error('Failed to fetch projects:', error)
  } finally {
    loading.value = false
  }
}

const goToProject = (id) => {
  router.push(`/project/${id}`)
}

const editProject = (project) => {
  router.push(`/edit/${project.project_id}`)
}

const deleteProject = async (project) => {
  if (!confirm(`Are you sure you want to delete activity "${project.name}"? This cannot be undone.`)) return

  try {
    await api.deleteProject(project.project_id)
    await fetchProjects()
  } catch (error) {
    console.error('Failed to delete project:', error)
    alert('Failed to delete project.')
  }
}

onMounted(fetchProjects)
</script>

<style scoped>
.home-container {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.create-btn {
  background-color: #42b883;
  color: white;
  border: none;
  padding: 0.8rem 1.5rem;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s;
}

.create-btn:hover {
  background-color: #3aa876;
}

.projects-table-container {
  background: #2a2a2a;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #333;
}

.projects-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.projects-table th {
  background: #1a1a1a;
  padding: 1rem;
  font-weight: 600;
  color: #888;
  border-bottom: 1px solid #333;
}

.projects-table td {
  padding: 1rem;
  border-bottom: 1px solid #333;
  color: #ddd;
}

.clickable-row {
  cursor: pointer;
  transition: background-color 0.2s;
}

.clickable-row:hover {
  background-color: #333;
}

.status-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 99px;
  font-size: 0.75rem;
  background: #444;
  color: white;
}

.status-badge.NEW { background: #3b82f6; }
.status-badge.SPLIT { background: #8b5cf6; }
.status-badge.PROCESSING { background: #f59e0b; }
.status-badge.PROCESSED { background: #10b981; }
.status-badge.ARCHIVED { background: #6366f1; }
.status-badge.SEALED { background: #64748b; }

.actions-cell {
  display: flex;
  gap: 0.5rem;
}

.icon-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 1.2rem;
  padding: 0.25rem;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.icon-btn:hover {
  background-color: #444;
}

.icon-btn.edit { color: #60a5fa; }
.icon-btn.delete { color: #ef4444; }

.empty-state {
  text-align: center;
  padding: 3rem;
  color: #666;
}
</style>
