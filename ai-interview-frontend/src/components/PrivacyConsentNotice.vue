<template>
  <div :class="['privacy-notice', { compact }]">
    <div class="privacy-copy">
      <strong>{{ title }}</strong>
      <p>
        平台会为提供简历解析、能力诊断、简历润色、模拟面试、报告和训练复盘服务处理你的账号、
        简历、学校、专业、项目经历、技能、目标岗位、面试回答和安全日志，并可能调用你选择的大模型服务。
        <router-link to="/privacy" target="_blank">查看隐私协议与个人信息处理说明</router-link>
      </p>
    </div>

    <label v-if="showBaseConsent" class="privacy-check required">
      <input
        type="checkbox"
        :checked="baseAgreed"
        @change="$emit('update:baseAgreed', $event.target.checked)"
      />
      <span>我已阅读并同意《隐私协议与个人信息处理说明》</span>
    </label>

    <label v-if="showDataContribution" class="privacy-check">
      <input
        type="checkbox"
        :checked="dataContributionConsent"
        @change="$emit('update:dataContributionConsent', $event.target.checked)"
      />
      <span>
        推荐开启数据贡献计划：我同意将去标识化后的简历解析结果、学校/专业/项目或实习经历、
        目标岗位、面试问答、报告和人工评分用于系统评测、比赛材料、质量改进和数据集沉淀。
      </span>
    </label>

    <p class="privacy-note">
      数据贡献默认不勾选；不同意不影响简历解析、润色和模拟面试。授权后，我们可以基于真实使用数据
      发现简历解析、岗位画像、面试追问、评分规则、报告建议和学习任务中的问题，针对性升级项目，
      让后续诊断和训练效果更贴近真实求职场景。去标识化会去除或遮挡姓名、手机号、邮箱、证件号、
      学号、详细住址和文件名个人标识；为保证诊断质量，可能保留学校、专业、教育/实习/项目经历、
      技能和问答内容。
    </p>
    <DataContributionBenefits v-if="showDataContribution" compact />
    <p v-if="showDataContribution && dataContributionConsent" class="privacy-note privacy-note-positive">
      当前已沿用你的默认数据贡献授权；你也可以取消本次勾选，仅使用核心功能。
    </p>
  </div>
</template>

<script setup>
import DataContributionBenefits from './DataContributionBenefits.vue'

defineProps({
  title: {
    type: String,
    default: '隐私与数据使用确认'
  },
  baseAgreed: {
    type: Boolean,
    default: false
  },
  dataContributionConsent: {
    type: Boolean,
    default: false
  },
  showBaseConsent: {
    type: Boolean,
    default: false
  },
  showDataContribution: {
    type: Boolean,
    default: true
  },
  compact: {
    type: Boolean,
    default: false
  }
})

defineEmits(['update:baseAgreed', 'update:dataContributionConsent'])
</script>

<style scoped>
.privacy-notice {
  margin: 14px 0 16px;
  padding: 14px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
  color: #334155;
}

.privacy-notice.compact {
  padding: 12px;
}

.privacy-copy strong {
  display: block;
  margin-bottom: 6px;
  color: #0f172a;
  font-size: 14px;
}

.privacy-copy p,
.privacy-note {
  margin: 0;
  font-size: 12px;
  line-height: 1.7;
}

.privacy-copy a {
  color: #2563eb;
  font-weight: 600;
}

.privacy-check {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 10px;
  font-size: 13px;
  line-height: 1.6;
  color: #1f2937;
}

.privacy-check input {
  margin-top: 3px;
  flex-shrink: 0;
}

.privacy-check.required {
  font-weight: 600;
}

.privacy-note {
  margin-top: 10px;
  color: #64748b;
}

.privacy-note-positive {
  color: #047857;
  font-weight: 600;
}
</style>
