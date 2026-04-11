<template>
  <div class="home-container">
    <div class="header">
      <h1>活動列表</h1>
      <div class="header-actions">
        <button @click="$router.push('/stamps')" class="stamps-btn">🖋 印章管理</button>
        <button @click="$router.push('/kanban')" class="kanban-btn">📊 PDF 看板</button>
        <button @click="$router.push('/create')" class="create-btn">+ 新增活動</button>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading activities...</div>
    
    <div v-else class="projects-table-container">
      <table class="projects-table">
        <thead>
          <tr>
            <th>活動名稱</th>
            <th>活動編號</th>
            <th>狀態</th>
            <th>最後更新</th>
            <th>操作</th>
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
              <button class="text-btn" @click="goToProject(project.project_id)">管理發票</button>
              <button class="text-btn edit" @click="editProject(project)">預算與報表</button>
              <button class="icon-btn delete" @click="deleteProject(project)" title="Delete">🗑</button>
            </td>
          </tr>
          <tr v-if="projects.length === 0">
            <td colspan="5" class="empty-state">尚無活動紀錄。請建立新的活動。</td>
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

.header-actions {
  display: flex;
  gap: 1rem;
}

.stamps-btn {
  background-color: #0f766e;
  color: white;
  border: none;
  padding: 0.8rem 1.5rem;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s;
}

.stamps-btn:hover {
  background-color: #115e59;
}

.kanban-btn {
  background-color: #3b82f6;
  color: white;
  border: none;
  padding: 0.8rem 1.5rem;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s;
}

.kanban-btn:hover {
  background-color: #2563eb;
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

.icon-btn.delete { color: #ef4444; }

.text-btn {
  background: #333;
  color: #ddd;
  border: 1px solid #555;
  padding: 0.3rem 0.6rem;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 0.85rem;
}
.text-btn:hover { background: #444; }
.text-btn.edit { border-color: #60a5fa; color: #60a5fa; background: transparent; }
.text-btn.edit:hover { background: rgba(96, 165, 250, 0.1); }

.empty-state {
  text-align: center;
  padding: 3rem;
  color: #666;
}
</style>
