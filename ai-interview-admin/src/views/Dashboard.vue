<template>
  <div>
    <h1 style="font-size:22px;margin-bottom:24px;color:#1e293b">📊 数据概览</h1>
    <div class="stats-grid">
      <div class="stat-card" v-for="(s, i) in statCards" :key="i">
        <div class="stat-icon">{{ s.icon }}</div>
        <div class="stat-num">{{ stats[s.key] }}</div>
        <div class="stat-label">{{ s.label }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { userApi } from '../api'

const stats = ref({ user_count: 0, resume_count: 0, interview_count: 0, completed_interview_count: 0 })

const statCards = [
  { key: 'user_count', label: '注册用户', icon: '👥' },
  { key: 'resume_count', label: '上传简历', icon: '📄' },
  { key: 'interview_count', label: '面试总数', icon: '🎤' },
  { key: 'completed_interview_count', label: '已完成面试', icon: '✅' }
]

onMounted(async () => {
  try { stats.value = await userApi.stats() } catch (e) { console.error(e) }
})
</script>

<style scoped>
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }

.stat-card {
  background: white;
  border-radius: 14px;
  padding: 28px 24px;
  text-align: center;
  position: relative;
  overflow: hidden;
  transition: all 0.3s;
  border: 1px solid #f1f5f9;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.stat-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: #111827;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px rgba(17,24,39,0.08);
}

.stat-icon { font-size: 32px; margin-bottom: 8px; }
.stat-num { font-size: 40px; font-weight: 700; color: #111827; }
.stat-label { font-size: 14px; color: #6b7280; margin-top: 4px; }
</style>
