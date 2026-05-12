import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue') },
  { path: '/register', name: 'Register', component: () => import('../views/Register.vue') },
  { path: '/dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { auth: true } },
  { path: '/competition-demo', redirect: '/dashboard' },
  { path: '/knowledge-base', name: 'KnowledgeBase', component: () => import('../views/KnowledgeBase.vue'), meta: { auth: true } },
  { path: '/ability-diagnosis', name: 'AbilityDiagnosis', component: () => import('../views/AbilityDiagnosis.vue'), meta: { auth: true } },
  { path: '/learning-tasks', name: 'LearningTasks', component: () => import('../views/LearningTasks.vue'), meta: { auth: true } },
  { path: '/training-review', name: 'TrainingReview', component: () => import('../views/TrainingReview.vue'), meta: { auth: true } },
  { path: '/resume-polish', name: 'ResumePolish', component: () => import('../views/ResumePolish.vue'), meta: { auth: true } },
  { path: '/resume/upload', name: 'ResumeUpload', component: () => import('../views/ResumeUpload.vue'), meta: { auth: true } },
  { path: '/interview/:id', name: 'Interview', component: () => import('../views/Interview.vue'), meta: { auth: true } },
  { path: '/interview/:id/report', name: 'Report', component: () => import('../views/Report.vue'), meta: { auth: true } },
  { path: '/profile', name: 'Profile', component: () => import('../views/Profile.vue'), meta: { auth: true } },
  { path: '/', redirect: '/dashboard' }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  if (to.meta.auth && !authStore.isLoggedIn) {
    next('/login')
  } else {
    next()
  }
})

export default router
