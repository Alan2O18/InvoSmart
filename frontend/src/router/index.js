import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import LandingView from '../views/LandingView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'landing',
      component: LandingView
    },
    {
      path: '/projects',
      name: 'projects',
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
      path: '/project/:id/edit-job',
      name: 'job-editor',
      component: () => import('../views/JobEditorView.vue')
    },
    {
      path: '/project/:id/budget-editor',
      name: 'budget-editor',
      component: () => import('../views/BudgetEditorView.vue')
    },
    {
      path: '/projects/overview',
      name: 'projects-overview',
      component: () => import('../views/ProjectsOverviewView.vue')
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/SettingsView.vue')
    },
    {
      path: '/voucher-template-config',
      name: 'voucher-template-config',
      component: () => import('../views/VoucherTemplateConfigView.vue')
    },
    {
      path: '/pdf-tasks',
      name: 'pdf-tasks',
      component: () => import('../views/PdfTasksView.vue')
    },
    {
      path: '/pdf-tasks/:id/editor',
      name: 'pdf-task-editor',
      component: () => import('../views/PdfTaskEditorView.vue')
    },
    {
      path: '/management',
      name: 'management',
      component: () => import('../views/StampsManagementView.vue')
    },
    {
      path: '/stamp-templates/create',
      name: 'stamp-template-create',
      component: () => import('../views/StampTemplateEditorView.vue')
    },
    {
      path: '/stamp-templates/:id/edit',
      name: 'stamp-template-edit',
      component: () => import('../views/StampTemplateEditorView.vue')
    },
    {
      path: '/project/:id/stamp-preview',
      name: 'voucher-stamp-preview',
      component: () => import('../views/VoucherStampPreviewView.vue')
    },
    {
      path: '/project/:id/voucher-editor',
      name: 'voucher-editor',
      component: () => import('../views/VoucherEditorView.vue')
    }
  ]
})

export default router

