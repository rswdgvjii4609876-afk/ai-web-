<template>
  <div class="container feedback-page">
    <div class="feedback-heading"><div><h1>留言反馈</h1><p>留言仅你和管理员可见，回复后可在这里查看。</p></div><router-link to="/profile">返回我的</router-link></div>
    <form class="card feedback-form" @submit.prevent="submit">
      <h2>提交使用反馈</h2>
      <label for="feedback-category">问题类型</label>
      <select id="feedback-category" v-model="form.category" :disabled="sending"><option value="issue">使用问题</option><option value="suggestion">功能建议</option><option value="other">其他</option></select>
      <label for="feedback-title">标题</label>
      <input id="feedback-title" v-model="form.title" :disabled="sending" maxlength="80" required placeholder="简要描述遇到的问题" />
      <label for="feedback-content">详细说明</label>
      <textarea id="feedback-content" v-model="form.content" :disabled="sending" rows="6" maxlength="2000" required aria-describedby="feedback-help" placeholder="请描述操作步骤、设备和实际情况"></textarea>
      <div class="feedback-hint"><span id="feedback-help">请勿填写密码、API密钥或完整简历。</span><span>{{ form.content.length }} / 2000</span></div>
      <p v-if="submitError" class="feedback-error" role="alert">{{ submitError }}</p>
      <p v-if="success" class="feedback-success" role="status">{{ success }}</p>
      <button class="btn-primary" type="submit" :disabled="sending || loading || !form.title.trim() || !form.content.trim()">{{ sending ? '提交中…' : '提交留言' }}</button>
    </form>
    <section aria-labelledby="feedback-history">
      <div class="feedback-heading"><h2 id="feedback-history">我的留言</h2><button class="btn-secondary" type="button" :disabled="loading || sending" @click="load(false)">刷新</button></div>
      <p v-if="loadError" class="feedback-error" role="alert">{{ loadError }} <button type="button" class="btn-secondary" :disabled="loading || sending" @click="load(false)">重试</button></p>
      <p v-if="loading" role="status">正在读取留言…</p>
      <p v-else-if="!items.length && !loadError" class="card">还没有留言。使用中遇到的问题或建议都可以在上方提交。</p>
      <article v-for="item in items" :key="item.id" class="card feedback-item">
        <div class="feedback-heading"><h3>{{ item.title }}</h3><span class="feedback-status">{{ statuses[item.status] || item.status }}</span></div>
        <p class="feedback-time">{{ categories[item.category] }} · {{ formatDate(item.created_at) }}</p>
        <p class="feedback-text">{{ item.content }}</p>
        <div v-if="item.reply" class="feedback-reply"><strong>管理员回复</strong><p class="feedback-text">{{ item.reply }}</p><p class="feedback-time">{{ formatDate(item.updated_at) }}</p></div>
        <p v-else class="feedback-time">{{ item.status === 'closed' ? '这条留言已关闭。' : '已收到留言，请稍后在这里查看回复。' }}</p>
      </article>
      <button v-if="hasMore" type="button" class="btn-secondary" :disabled="loading || sending" @click="load(true)">加载更多</button>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { createFeedback, listFeedback } from '../api/feedback'
const form = reactive({ category: 'issue', title: '', content: '' })
const items = ref([]), loading = ref(false), sending = ref(false), hasMore = ref(false)
const loadError = ref(''), submitError = ref(''), success = ref('')
const statuses = { pending: '待处理', replied: '已回复', closed: '已关闭' }
const categories = { issue: '使用问题', suggestion: '功能建议', other: '其他' }
const formatDate = value => value ? new Date(value).toLocaleString('zh-CN') : ''
async function load(append = false) {
  if (loading.value || sending.value) return
  loading.value = true; loadError.value = ''
  try {
    const data = await listFeedback(append ? items.value.length : 0)
    items.value = append ? [...items.value, ...data.items] : data.items
    hasMore.value = data.has_more
  } catch (e) { loadError.value = e.message || '留言读取失败，请重试' }
  finally { loading.value = false }
}
async function submit() {
  if (sending.value || loading.value || !form.title.trim() || !form.content.trim()) return
  sending.value = true; submitError.value = ''; success.value = ''
  try {
    const item = await createFeedback({ category: form.category, title: form.title.trim(), content: form.content.trim() })
    items.value = [item, ...items.value]
    form.title = ''; form.content = ''
    success.value = '留言已提交，可在下方查看处理状态。'
  } catch (e) { submitError.value = e.message || '提交失败，内容已保留，请重试' }
  finally { sending.value = false }
}
onMounted(() => load())
</script>

<style scoped>
.feedback-page { max-width: 760px; }
.feedback-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: 18px 0; flex-wrap: wrap; }
.feedback-heading p, .feedback-time { color: #64748b; font-size: 14px; line-height: 1.6; }
.feedback-form { display: grid; gap: 12px; margin-bottom: 28px; }
.feedback-form label { margin-top: 6px; font-weight: 600; }
.feedback-form textarea { resize: vertical; }
.feedback-hint { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; font-size: 12px; color: #64748b; }
.feedback-error { color: #b91c1c; line-height: 1.6; }
.feedback-success { color: #047857; }
.feedback-item { margin: 12px 0; }
.feedback-item .feedback-heading { margin-top: 0; }
.feedback-status { color: #4338ca; background: #eef2ff; padding: 5px 10px; border-radius: 6px; white-space: nowrap; font-size: 13px; }
.feedback-text { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.7; margin: 12px 0; }
.feedback-reply { padding: 14px; background: #f8fafc; border-left: 3px solid #818cf8; margin-top: 16px; }
</style>
