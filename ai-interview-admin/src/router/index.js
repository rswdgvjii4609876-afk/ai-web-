import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { authApi } from '../api'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue') },
  { path: '/', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { auth: true } },
  { path: '/users', name: 'Users', component: () => import('../views/Users.vue'), meta: { auth: true } },
  { path: '/admins', name: 'Admins', component: () => import('../views/Admins.vue'), meta: { auth: true, manageAdmins: true } },
  { path: '/account', name: 'AccountSettings', component: () => import('../views/AccountSettings.vue'), meta: { auth: true } },
  { path: '/knowledge-bases', name: 'KnowledgeBases', component: () => import('../views/KnowledgeBases.vue'), meta: { auth: true } },
  { path: '/interview-experiences', name: 'InterviewExperiences', component: () => import('../views/InterviewExperiences.vue'), meta: { auth: true } },
  { path: '/knowledge-package', name: 'KnowledgePackage', component: () => import('../views/KnowledgePackage.vue'), meta: { auth: true } },
  { path: '/learning-routes', name: 'LearningRoutes', component: () => import('../views/LearningRoutes.vue'), meta: { auth: true } },
  { path: '/cases', name: 'Cases', component: () => import('../views/Cases.vue'), meta: { auth: true } },
  { path: '/evaluation-datasets', name: 'EvaluationDatasets', component: () => import('../views/EvaluationDatasets.vue'), meta: { auth: true } },
  { path: '/interviews', name: 'Interviews', component: () => import('../views/Interviews.vue'), meta: { auth: true } },
  { path: '/interviews/:id', name: 'InterviewDetail', component: () => import('../views/InterviewDetail.vue'), meta: { auth: true } }
]

const router = createRouter({ history: createWebHistory(import.meta.env.BASE_URL), routes })

router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  if (to.meta.auth && !authStore.isLoggedIn) return next('/login')

  if (
    to.meta.auth &&
    authStore.isLoggedIn &&
    (!authStore.id || (to.meta.manageAdmins && !authStore.canManageAdmins))
  ) {
    try {
      const me = await authApi.me()
      authStore.setAdminInfo(me)
    } catch (error) {
      authStore.logout()
      return next('/login')
    }
  }

  if (to.meta.manageAdmins && !authStore.canManageAdmins) return next('/')
  next()
})

export default router
