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
      path: '/stamps',
      name: 'stamps-management',
      component: () => import('../views/StampsManagementView.vue')
    },
    {
      path: '/persons',
      name: 'persons-management',
      component: () => import('../views/PersonsManagementView.vue')
    },
    {
      path: '/stamp-zones',
      name: 'stamp-zones-config',
      component: () => import('../views/StampZoneConfigView.vue')
    },
    {
      path: '/stamps/upload',
      name: 'stamp-source-upload',
      component: () => import('../views/StampSourceUploadView.vue')
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
    },
    {
      path: '/voucher-template-config',
      name: 'voucher-template-config',
      component: () => import('../views/VoucherTemplateConfigView.vue')
    }
  ]
})

export default router
