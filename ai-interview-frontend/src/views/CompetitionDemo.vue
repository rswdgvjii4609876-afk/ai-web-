<template>
  <div class="container">
    <div class="demo-header">
      <div>
        <p class="eyebrow">参赛演示</p>
        <h1>{{ assets.title || '职启智评' }}</h1>
        <p class="lead">
          在原有多岗位模拟面试主流程之上，展示岗位画像、轻量匹配评分、技术深度路线、演示案例和人工评分对比。这里的数据是固定样例，用于答辩和离线演示。
        </p>
      </div>
      <router-link to="/resume/upload" class="btn-primary start-link">开始完整流程</router-link>
    </div>

    <div class="claim-card card">
      <strong>边界说明</strong>
      <p>{{ assets.claim_boundary }}</p>
    </div>

    <section class="section">
      <div class="section-head">
        <h2>技术深度路线</h2>
        <span>ML + LLM + 微调准备</span>
      </div>
      <div class="depth-grid">
        <article v-for="(items, key) in assets.technical_depth_route || {}" :key="key" class="card depth-card">
          <h3>{{ depthTitleMap[key] || key }}</h3>
          <ul>
            <li v-for="item in items" :key="item">{{ item }}</li>
          </ul>
        </article>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <h2>岗位画像库</h2>
        <span>{{ assets.position_profiles?.length || 0 }} 个默认岗位</span>
      </div>
      <div class="profile-grid">
        <article v-for="profile in assets.position_profiles || []" :key="profile.job_id" class="card profile-card">
          <h3>{{ profile.job_name }}</h3>
          <p class="muted">核心能力：{{ profile.core_skills.join('、') }}</p>
          <p class="muted">典型任务：{{ profile.typical_tasks.join('、') }}</p>
          <div class="tag-row">
            <span v-for="kw in profile.keywords.slice(0, 5)" :key="kw" class="tag">{{ kw }}</span>
          </div>
        </article>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <h2>评分规则</h2>
        <span>总分 {{ assets.scoring_rules?.total_score || 100 }}</span>
      </div>
      <div class="rule-grid">
        <div v-for="item in assets.scoring_rules?.dimensions || []" :key="item.name" class="card rule-card">
          <div class="rule-top">
            <strong>{{ item.name }}</strong>
            <span>{{ item.weight }}%</span>
          </div>
          <p>{{ item.description }}</p>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <h2>AI 与人工评分对比</h2>
        <span>演示样本 {{ assets.demo_cases?.length || 0 }} 组</span>
      </div>
      <div class="case-list">
        <article v-for="item in assets.demo_cases || []" :key="item.case_id" class="card case-card">
          <div class="case-main">
            <strong>案例 {{ item.case_id }}：{{ item.target_position }}</strong>
            <p>{{ item.profile }}</p>
            <p class="suggestion">{{ item.suggestion }}</p>
          </div>
          <div class="score-strip">
            <span>AI {{ item.ai_score }}</span>
            <span>人工 {{ item.human_score_avg }}</span>
            <span :class="Math.abs(item.delta) <= 3 ? 'delta-ok' : 'delta-warn'">差值 {{ item.delta }}</span>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getCompetitionDemoAssets } from '../api/demo'

const assets = ref({})
const depthTitleMap = {
  machine_learning: '机器学习层',
  deep_learning: '深度学习应用层',
  fine_tuning_preparation: '微调准备层'
}

onMounted(async () => {
  try {
    assets.value = await getCompetitionDemoAssets()
  } catch (error) {
    console.error('加载参赛演示数据失败', error)
  }
})
</script>

<style scoped>
.demo-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  margin: 24px 0 16px;
}
.eyebrow {
  color: #0f766e;
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 6px;
}
.demo-header h1 {
  font-size: 28px;
  line-height: 1.35;
  color: #111827;
  max-width: 760px;
}
.lead {
  margin-top: 10px;
  max-width: 760px;
  color: #4b5563;
  line-height: 1.8;
}
.start-link {
  flex-shrink: 0;
  display: inline-block;
  border-radius: 8px;
  color: white;
}
.claim-card {
  margin-bottom: 24px;
  border-left: 4px solid #0f766e;
}
.claim-card p {
  margin-top: 8px;
  color: #4b5563;
  line-height: 1.7;
}
.section {
  margin-bottom: 24px;
}
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.section-head h2 {
  font-size: 20px;
}
.section-head span {
  color: #6b7280;
  font-size: 13px;
}
.profile-grid,
.rule-grid,
.depth-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
}
.depth-card h3 {
  margin-bottom: 10px;
  color: #111827;
}
.depth-card ul {
  margin: 0;
  padding-left: 18px;
  color: #4b5563;
  font-size: 13px;
  line-height: 1.8;
}
.profile-card h3 {
  margin-bottom: 10px;
  color: #111827;
}
.muted {
  color: #4b5563;
  font-size: 13px;
  line-height: 1.7;
  margin-bottom: 8px;
}
.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
.tag {
  padding: 4px 10px;
  border-radius: 999px;
  background: #ecfeff;
  color: #0f766e;
  font-size: 12px;
}
.rule-card {
  padding: 18px;
}
.rule-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.rule-top span {
  color: #0f766e;
  font-weight: 700;
}
.rule-card p {
  color: #4b5563;
  font-size: 13px;
  line-height: 1.7;
}
.case-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.case-card {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}
.case-main p {
  margin-top: 8px;
  color: #4b5563;
  line-height: 1.7;
}
.suggestion {
  color: #0f766e !important;
}
.score-strip {
  min-width: 190px;
  display: grid;
  gap: 8px;
}
.score-strip span {
  border-radius: 8px;
  background: #f3f4f6;
  padding: 8px 10px;
  font-size: 13px;
  font-weight: 600;
}
.delta-ok {
  color: #047857;
  background: #d1fae5 !important;
}
.delta-warn {
  color: #b45309;
  background: #fef3c7 !important;
}
@media (max-width: 700px) {
  .demo-header,
  .case-card {
    flex-direction: column;
  }
  .score-strip {
    width: 100%;
    min-width: 0;
  }
}
</style>
