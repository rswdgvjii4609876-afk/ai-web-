<template>
  <div class="app-shell" :class="{ 'signed-in': authStore.token, 'interview-focus': isInterview }">
    <a class="skip-link" href="#page-content">跳到主要内容</a>
    <nav class="navbar" v-if="authStore.token">
      <div class="nav-content">
        <router-link to="/dashboard" class="nav-logo">职启智评</router-link>
        <button ref="menuButton" class="mobile-menu-button btn-secondary" type="button" :aria-expanded="menuOpen" aria-controls="primary-links" @click="menuOpen = !menuOpen">{{ menuOpen ? '收起菜单' : '更多功能' }}</button>
        <div id="primary-links" class="nav-links" :class="{ 'is-open': menuOpen }" @click="closeMenu" @keydown.esc="closeMenu(true)">
          <router-link to="/resume-polish">简历润色</router-link>
          <router-link to="/dashboard">工作台</router-link>
          <router-link to="/knowledge-base">岗位画像库</router-link>
          <router-link to="/ability-diagnosis">能力诊断</router-link>
          <router-link to="/learning-tasks">学习任务</router-link>
          <router-link to="/training-review">训练复盘</router-link>
          <router-link to="/resume/upload">新建面试</router-link>
          <router-link to="/feedback">留言反馈</router-link>
          <router-link to="/profile" class="nav-user-link">
            <img v-if="authStore.userAvatar && !avatarError" :src="authStore.userAvatar" class="nav-avatar" alt="avatar" @error="avatarError = true" />
            <span v-else class="nav-avatar-placeholder">👤</span>
            <span>{{ authStore.userName || '个人设置' }}</span>
          </router-link>
          <button class="btn-secondary" @click="logout" style="padding:6px 14px;font-size:13px">退出</button>
        </div>
      </div>
    </nav>
    <main id="page-content" tabindex="-1"><router-view /></main>
    <nav v-if="authStore.token && !isInterview" class="mobile-tabs" aria-label="手机主导航">
      <router-link to="/dashboard"><span aria-hidden="true">⌂</span>工作台</router-link>
      <router-link to="/resume/upload"><span aria-hidden="true">◇</span>面试</router-link>
      <router-link to="/learning-tasks" :class="{ 'router-link-active': route.path === '/training-review' }"><span aria-hidden="true">▤</span>学习</router-link>
      <router-link to="/profile" :class="{ 'router-link-active': route.path === '/feedback' }"><span aria-hidden="true">○</span>我的</router-link>
    </nav>
    <footer class="icp-footer" aria-label="ICP备案信息">
      <a href="https://beian.miit.gov.cn/" target="_blank" rel="noreferrer noopener">
        粤ICP备2026047626号
      </a>
    </footer>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useAuthStore } from './stores/auth'
import { useRoute, useRouter } from 'vue-router'
import { getProfile } from './api/user'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()
const menuOpen = ref(false)
const menuButton = ref(null)
const isInterview = computed(() => route.name === 'Interview')
function closeMenu(restoreFocus = false) {
  menuOpen.value = false
  if (restoreFocus === true) menuButton.value?.focus()
}
watch(() => route.fullPath, () => closeMenu())
function updateViewportHeight() {
  document.documentElement.style.setProperty('--visual-viewport-height', `${window.visualViewport?.height || window.innerHeight}px`)
}
onMounted(() => {
  updateViewportHeight()
  window.visualViewport?.addEventListener('resize', updateViewportHeight)
  window.addEventListener('resize', updateViewportHeight)
})
onUnmounted(() => {
  window.visualViewport?.removeEventListener('resize', updateViewportHeight)
  window.removeEventListener('resize', updateViewportHeight)
  document.documentElement.style.removeProperty('--visual-viewport-height')
})
const avatarError = ref(false)

onMounted(async () => {
  if (authStore.token) {
    try {
      const data = await getProfile()
      authStore.setUserInfo(data)
      avatarError.value = false
    } catch (e) {
      // 忽略
    }
  }
})

function logout() {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.mobile-menu-button, .mobile-tabs { display: none; }
.skip-link { position: fixed; top: -80px; left: 12px; z-index: 1000; padding: 12px; background: white; }
.skip-link:focus { top: 8px; }
.navbar {
  background: white;
  border-bottom: 1px solid #e5e7eb;
  padding: 0 20px;
  position: sticky;
  top: 0;
  z-index: 100;
}
.nav-content {
  max-width: 1080px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 56px;
  padding: 8px 0;
  gap: 14px;
}
.nav-logo {
  font-size: 18px;
  font-weight: 700;
  color: #4f46e5;
}
.nav-links {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  flex-wrap: wrap;
}
.nav-links a.router-link-active {
  color: #4f46e5;
  font-weight: 600;
}
.nav-user {
  color: #6b7280;
  font-size: 13px;
}
.nav-user-link {
  color: #6b7280;
  font-size: 13px;
  transition: color 0.2s;
  display: flex;
  align-items: center;
  gap: 6px;
}
.nav-user-link:hover {
  color: #4f46e5;
}
.nav-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  object-fit: cover;
}
.nav-avatar-placeholder {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}
.icp-footer {
  padding: 18px 20px 28px;
  text-align: center;
  color: #6b7280;
  font-size: 12px;
}
.icp-footer a {
  color: inherit;
  font-weight: 600;
}
.icp-footer a:hover {
  color: #4f46e5;
}

@media (max-width: 860px) {
  .signed-in { padding-bottom: calc(68px + env(safe-area-inset-bottom, 0px)); }
  .interview-focus { padding-bottom: 0; }
  .navbar { padding: 0 16px; }
  .nav-content {
    display: flex;
    flex-wrap: wrap;
    min-height: 64px;
    gap: 0;
  }
  .nav-logo {
    display: inline-block;
    margin-bottom: 0;
  }
  .mobile-menu-button { display: block; min-height: 44px; }
  .nav-links {
    display: none;
    width: 100%;
    max-height: calc(100dvh - 144px);
    overflow-y: auto;
    padding: 12px 0;
    white-space: normal;
    gap: 8px;
  }
  .nav-links.is-open { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .nav-links > * {
    display: flex; align-items: center; min-height: 44px; padding: 8px; overflow-wrap: anywhere;
  }
  .mobile-tabs { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); position: fixed; bottom: 0; left: 0; right: 0; z-index: 110; padding-bottom: env(safe-area-inset-bottom, 0px); background: white; border-top: 1px solid #e5e7eb; }
  .mobile-tabs a { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 64px; gap: 3px; color: #475569; font-size: 13px; }
  .mobile-tabs a span { font-size: 22px; line-height: 24px; }
  .mobile-tabs a.router-link-active { color: #4f46e5; font-weight: 700; background: #f5f3ff; }
  .interview-focus .icp-footer { display: none; }
}
</style>
