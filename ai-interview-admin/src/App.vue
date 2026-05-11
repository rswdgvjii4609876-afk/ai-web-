<template>
  <div class="admin-layout" v-if="authStore.isLoggedIn">
    <aside class="sidebar">
      <div class="sidebar-logo"><span class="logo-text">职启智评</span></div>
      <div class="sidebar-subtitle">管理后台</div>
      <nav class="sidebar-nav">
        <router-link to="/" exact-active-class="active">
          <span class="nav-icon">📊</span> 数据概览
        </router-link>
        <router-link to="/users" active-class="active">
          <span class="nav-icon">👥</span> 用户管理
        </router-link>
        <router-link to="/knowledge-bases" active-class="active">
          <span class="nav-icon">🧠</span> 公共岗位画像
        </router-link>
        <router-link to="/knowledge-package" active-class="active">
          <span class="nav-icon">▤</span> 资料包预检
        </router-link>
        <router-link to="/learning-routes" active-class="active">
          <span class="nav-icon">▣</span> 学习路线管理
        </router-link>
        <router-link to="/cases" active-class="active">
          <span class="nav-icon">□</span> 案例标注
        </router-link>
        <router-link to="/evaluation-datasets" active-class="active">
          <span class="nav-icon">🧪</span> 评测样本
        </router-link>
        <router-link to="/interviews" active-class="active">
          <span class="nav-icon">🎤</span> 面试记录
        </router-link>
      </nav>
      <div class="sidebar-footer">
        <span>{{ authStore.email }}</span>
        <button class="logout-btn" @click="logout">退出登录</button>
      </div>
    </aside>
    <main class="main-content">
      <router-view />
      <footer class="icp-footer" aria-label="ICP备案信息">
        <a href="https://beian.miit.gov.cn/" target="_blank" rel="noreferrer noopener">
          粤ICP备2026047626号
        </a>
      </footer>
    </main>
  </div>
  <div v-else class="public-shell">
    <router-view />
    <footer class="icp-footer" aria-label="ICP备案信息">
      <a href="https://beian.miit.gov.cn/" target="_blank" rel="noreferrer noopener">
        粤ICP备2026047626号
      </a>
    </footer>
  </div>
</template>

<script setup>
import { useAuthStore } from './stores/auth'
import { useRouter } from 'vue-router'
const authStore = useAuthStore()
const router = useRouter()
function logout() { authStore.logout(); router.push('/login') }
</script>

<style scoped>
.admin-layout { display: flex; min-height: 100vh; }

.sidebar {
  width: 230px;
  background: #111827;
  color: white;
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  position: fixed;
  top: 0; left: 0; bottom: 0;
  overflow: auto;
}

.sidebar-logo {
  font-size: 22px;
  font-weight: 700;
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
}

.logo-icon {
  -webkit-text-fill-color: initial;
}

.logo-text {
  color: #ffffff;
}

.sidebar-subtitle {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 32px;
  position: relative;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  position: relative;
}

.sidebar-nav a {
  padding: 11px 14px;
  border-radius: 10px;
  color: #94a3b8;
  font-size: 14px;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  gap: 10px;
}

.sidebar-nav a:hover {
  background: #1f2937;
  color: #ffffff;
}

.sidebar-nav a.active {
  background: #ffffff;
  color: #111827;
  box-shadow: none;
}

.nav-icon { font-size: 16px; }

.sidebar-footer {
  font-size: 12px;
  color: #9ca3af;
  border-top: 1px solid #374151;
  padding-top: 16px;
  position: relative;
}

.logout-btn {
  display: block;
  width: 100%;
  margin-top: 10px;
  padding: 8px;
  border-radius: 8px;
  font-size: 13px;
  background: #1f2937;
  color: #f9fafb;
  border: 1px solid #374151;
  cursor: pointer;
  transition: all 0.3s;
}

.logout-btn:hover {
  background: #374151;
  color: #ffffff;
  border-color: #4b5563;
}

.main-content {
  margin-left: 230px;
  flex: 1;
  padding: 28px;
  background: #f8fafc;
}

.public-shell {
  min-height: 100vh;
  background: #f8fafc;
}

.icp-footer {
  padding: 18px 20px 28px;
  text-align: center;
  color: #64748b;
  font-size: 12px;
}

.icp-footer a {
  color: inherit;
  font-weight: 600;
}

.icp-footer a:hover {
  color: #111827;
}
</style>
