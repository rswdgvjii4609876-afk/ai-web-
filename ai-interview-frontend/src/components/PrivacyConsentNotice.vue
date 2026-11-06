<template>
  <div :class="['privacy-notice', { compact }]">
    <div class="privacy-copy">
      <strong>{{ title }}</strong>
      <p>
        平台会为提供简历解析、能力诊断、简历润色、角色、模拟面试、报告和训练复盘服务处理你的账号、简历、学校、专业、项目经历、技能、目标岗位、面试回答和安全日志，并可能调用你选择的大模型服务。
        <router-link to="/privacy" target="_blank">查看隐私协议与个人信息处理说明</router-link>
      </p>
    </div>

    <label v-if="showBaseConsent" class="privacy-check" aria-label="我已确认隐私与数据使用">
      <input
        type="checkbox"
        :checked="baseAgreed"
        @change="emit('update:baseAgreed', $event.target.checked)"
      />
      <span>我已阅读并同意基础隐私说明，以使用简历分析和面试服务。</span>
    </label>
    <label v-if="showDataContribution" class="privacy-check" aria-label="自愿贡献去标识化数据">
      <input
        type="checkbox"
        :checked="dataContributionConsent"
        @change="emit('update:dataContributionConsent', $event.target.checked)"
      />
      <span>自愿将去标识化资料用于评测、比赛材料和质量改进。不同意不影响使用，可在个人设置及案例报告中撤回。</span>
    </label>
  </div>
</template>

<script setup>
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
    default: true
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

const emit = defineEmits(['update:baseAgreed', 'update:dataContributionConsent'])

</script>

<style scoped>
.privacy-notice {
  margin: 14px 0 16px;
  padding: 12px 14px;
  border: 1px solid #bfdbfe;
  background: #f8fbff;
  color: #111827;
}

.privacy-notice.compact {
  padding: 10px 12px;
}

.privacy-copy strong {
  display: block;
  margin-bottom: 6px;
  color: #0f172a;
  font-size: 14px;
}

.privacy-copy p {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.8;
}

.privacy-copy a {
  color: #2563eb;
  font-weight: 700;
  text-decoration: none;
}

.privacy-copy a:hover {
  text-decoration: underline;
}

.privacy-check {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 8px;
  padding: 2px 0;
  border: 3px solid #e0e7ff;
  background: #f8fafc;
}

.privacy-check input {
  flex-shrink: 0;
  width: 13px;
  height: 13px;
  margin: 3px 0 0;
}
</style>
