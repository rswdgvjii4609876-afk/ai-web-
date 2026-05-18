<template>
  <div v-if="hint.isAiConfigError" class="ai-config-error-notice">
    <div class="notice-marker">AI</div>
    <div class="notice-body">
      <strong>{{ hint.title }}</strong>
      <p>{{ hint.message }}</p>
      <ol>
        <li v-for="step in hint.steps" :key="step">{{ step }}</li>
      </ol>
      <div class="notice-actions">
        <router-link class="notice-action" to="/profile">去个人设置</router-link>
      </div>
      <details v-if="hint.diagnostic" class="notice-diagnostic">
        <summary>查看原始错误</summary>
        <span>{{ hint.diagnostic }}</span>
      </details>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { getAiConfigErrorHint } from '../utils/aiConfigError'

const props = defineProps({
  error: {
    type: [String, Error],
    default: ''
  }
})

const hint = computed(() => getAiConfigErrorHint(props.error))
</script>

<style scoped>
.ai-config-error-notice {
  display: grid;
  grid-template-columns: 36px 1fr;
  gap: 12px;
  margin: 12px 0 14px;
  padding: 14px;
  border: 1px solid #bfdbfe;
  border-radius: 10px;
  background: #eff6ff;
  color: #1e3a8a;
}

.notice-marker {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #dbeafe;
  color: #1d4ed8;
  font-weight: 800;
  font-size: 13px;
}

.notice-body strong {
  display: block;
  margin-bottom: 6px;
  font-size: 15px;
}

.notice-body p {
  margin: 0 0 8px;
  font-size: 13px;
  line-height: 1.7;
}

.notice-body ol {
  margin: 0 0 10px 18px;
  padding: 0;
  font-size: 13px;
  line-height: 1.7;
}

.notice-action {
  display: inline-flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 8px;
  background: #2563eb;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
}

.notice-diagnostic {
  margin-top: 10px;
  color: #475569;
  font-size: 12px;
}

.notice-diagnostic summary {
  cursor: pointer;
}
</style>
