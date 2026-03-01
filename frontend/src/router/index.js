import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView
    },
    {
      path: '/create',
      name: 'create',
      component: () => import('../views/CreateProjectView.vue')
    },
    {
      path: '/project/:id',
      name: 'project-detail',
      component: () => import('../views/ProjectDetailView.vue')
    },
    {
      path: '/edit/:id',
      name: 'edit-project',
      component: () => import('../views/EditProjectView.vue')
    },
    {
      path: '/project/:id/edit-job',
      name: 'job-editor',
      component: () => import('../views/JobEditorView.vue')
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/SettingsView.vue')
    },
    {
      path: '/project/:id/pdf-editor',
      name: 'pdf-editor',
      component: () => import('../views/PdfEditorView.vue')
    },
    {
      path: '/kanban',
      name: 'kanban',
      component: () => import('../views/KanbanView.vue')
    }
  ]
})

export default router
