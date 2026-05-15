<template>
  <section class="case-consent-card">
    <div class="case-consent-copy">
      <div class="case-consent-head">
        <p class="eyebrow">推荐开启数据贡献计划</p>
        <span :class="['consent-chip', consented ? 'chip-on' : 'chip-off']">
          {{ consented ? '可进入人工评分沉淀' : '未进入评测库' }}
        </span>
      </div>
      <h3>把本次去标识化训练记录加入评测库</h3>
      <p>
        授权后，本次简历解析、学校/专业/项目或实习经历、目标岗位、面试问答、报告和人工评分可用于系统评测、
        比赛材料、质量改进和数据集沉淀。真实案例越多，我们越能定位简历解析遗漏、岗位画像不贴合、
        追问不够深入、评分与人工判断不一致、报告建议空泛、学习任务不可执行等问题，并针对性升级项目。
      </p>
      <ul class="upgrade-list">
        <li>优化岗位画像：补强同岗位常见能力、场景题和表达要求。</li>
        <li>优化面试追问：让问题更贴合你的简历证据和岗位短板。</li>
        <li>优化评分与报告：校准 AI 分数、人工评分和后续提升建议。</li>
        <li>优化学习任务：减少空泛任务，生成更具体的材料、练习和验收方式。</li>
      </ul>
      <p class="case-consent-note">
        我们会删除或遮挡姓名、手机号、邮箱、证件号、学号、详细住址和文件名个人标识；为保证诊断质量，
        可能保留学校、专业、教育/实习/项目经历、技能、岗位、问答和评分。不同意不影响报告、复盘和继续训练。
      </p>
      <DataContributionBenefits />
      <p v-if="message" class="case-consent-message">{{ message }}</p>
    </div>
    <div class="case-consent-actions">
      <button
        v-if="!consented"
        type="button"
        class="btn-primary consent-primary"
        :disabled="saving"
        @click="$emit('set-consent', true)"
      >
        {{ saving ? '记录中...' : '同意加入本次案例评测库' }}
      </button>
      <button
        v-else
        type="button"
        class="btn-secondary consent-secondary"
        :disabled="saving"
        @click="$emit('set-consent', false)"
      >
        {{ saving ? '处理中...' : '撤回本次案例授权' }}
      </button>
      <router-link to="/privacy" target="_blank" class="privacy-link">查看处理说明</router-link>
    </div>
  </section>
</template>

<script setup>
import DataContributionBenefits from './DataContributionBenefits.vue'

defineProps({
  consented: {
    type: Boolean,
    default: false
  },
  saving: {
    type: Boolean,
    default: false
  },
  message: {
    type: String,
    default: ''
  }
})

defineEmits(['set-consent'])
</script>

<style scoped>
.case-consent-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-top: 16px;
  padding: 16px;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
  background: linear-gradient(135deg, #f0fdf4, #f8fafc);
}

.case-consent-copy {
  min-width: 0;
}

.case-consent-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}

.eyebrow {
  margin: 0;
  color: #047857;
  font-size: 12px;
  font-weight: 700;
}

.consent-chip {
  flex-shrink: 0;
  padding: 4px 9px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.chip-on {
  background: #dcfce7;
  color: #166534;
}

.chip-off {
  background: #f3f4f6;
  color: #6b7280;
}

h3 {
  margin: 0 0 6px;
  color: #111827;
  font-size: 17px;
}

p {
  margin: 0;
  color: #374151;
  font-size: 13px;
  line-height: 1.7;
}

.upgrade-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 12px;
  margin: 10px 0 0;
  padding-left: 18px;
  color: #166534;
  font-size: 13px;
  line-height: 1.6;
}

.case-consent-note {
  margin-top: 8px;
  color: #64748b;
}

.case-consent-message {
  margin-top: 8px;
  color: #047857;
  font-weight: 600;
}

.case-consent-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  min-width: 190px;
}

.consent-primary,
.consent-secondary {
  width: 100%;
  padding: 9px 12px;
  border-radius: 8px;
}

.privacy-link {
  color: #2563eb;
  font-size: 13px;
  font-weight: 600;
}

@media (max-width: 720px) {
  .case-consent-card,
  .case-consent-head,
  .upgrade-list {
    flex-direction: column;
    align-items: stretch;
  }

  .upgrade-list {
    display: block;
  }

  .case-consent-actions {
    align-items: stretch;
    min-width: 0;
  }
}
</style>
