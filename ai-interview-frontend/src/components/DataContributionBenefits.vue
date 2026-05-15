<template>
  <div :class="['benefit-box', { compact }]">
    <p class="benefit-title">授权后可帮助我们定向升级：</p>
    <ul>
      <li>修正简历解析遗漏和岗位画像偏差</li>
      <li>优化面试追问策略，让追问更贴近真实岗位</li>
      <li>校准 AI 评分与人工评分差异</li>
      <li>改进报告建议和学习任务，让训练路径更可执行</li>
    </ul>
  </div>
</template>

<script setup>
defineProps({
  compact: {
    type: Boolean,
    default: false
  }
})
</script>

<style scoped>
.benefit-box {
  margin-top: 10px;
  padding: 10px 12px;
  border: 1px solid #d1fae5;
  border-radius: 8px;
  background: #f0fdf4;
}

.benefit-box.compact {
  padding: 9px 10px;
}

.benefit-title {
  margin: 0 0 6px;
  color: #065f46;
  font-size: 12px;
  font-weight: 700;
}

ul {
  margin: 0;
  padding-left: 18px;
  color: #166534;
  font-size: 12px;
  line-height: 1.7;
}
</style>
