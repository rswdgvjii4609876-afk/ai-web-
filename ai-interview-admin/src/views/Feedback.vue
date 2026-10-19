<template>
  <div>
    <h1>留言反馈</h1>
    <p class="intro">查看用户私有留言，回复使用问题并更新处理状态。</p>
    <div class="toolbar"><label for="feedback-filter">处理状态</label><select id="feedback-filter" v-model="filter" :disabled="loading || !!savingId" @change="load(false)"><option value="">全部</option><option value="pending">待处理</option><option value="replied">已回复</option><option value="closed">已关闭</option></select><button :disabled="loading || !!savingId" @click="load(false)">刷新</button></div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <p v-if="loading" role="status">正在读取留言…</p>
    <p v-else-if="!items.length && !error">当前没有符合条件的留言。</p>
    <article v-for="item in items" :key="item.id" class="feedback-card">
      <div class="heading"><h2>{{ item.title }}</h2><span>{{ statuses[item.status] }}</span></div>
      <p class="meta">编号 {{ item.id }} · 用户 {{ item.user_id }} · {{ categories[item.category] }} · {{ formatDate(item.created_at) }}</p>
      <p class="content">{{ item.content }}</p>
      <label :for="`reply-${item.id}`">回复内容</label>
      <textarea :id="`reply-${item.id}`" v-model="drafts[item.id]" maxlength="2000" rows="4" :disabled="loading || !!savingId" placeholder="填写用户可见的回复"></textarea>
      <div class="actions"><button class="btn-primary" :disabled="loading || !!savingId || !drafts[item.id]?.trim()" @click="save(item, 'replied')">{{ savingId === item.id ? '保存中…' : '保存回复' }}</button><button :disabled="loading || !!savingId || item.status === 'closed'" @click="save(item, 'closed')">关闭留言</button></div>
    </article>
    <button v-if="hasMore" :disabled="loading || !!savingId" @click="load(true)">加载更多</button>
  </div>
</template>
<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '../api/request'
const items = ref([]), filter = ref(''), loading = ref(false), savingId = ref(null), hasMore = ref(false), error = ref(''), notice = ref('')
const drafts = reactive({})
const statuses = { pending: '待处理', replied: '已回复', closed: '已关闭' }
const categories = { issue: '使用问题', suggestion: '功能建议', other: '其他' }
const formatDate = value => value ? new Date(value).toLocaleString('zh-CN') : ''
async function load(append = false) {
  if (loading.value) return
  loading.value = true; error.value = ''
  try {
    const data = await api.get('/feedback', { params: { status: filter.value || undefined, offset: append ? items.value.length : 0, limit: 20 } })
    items.value = append ? [...items.value, ...data.items] : data.items
    for (const item of data.items) drafts[item.id] = item.reply || ''
    hasMore.value = data.has_more
  } catch (e) { error.value = e.message || '留言读取失败' }
  finally { loading.value = false }
}
async function save(item, status) {
  if (savingId.value || loading.value) return
  savingId.value = item.id; error.value = ''; notice.value = ''
  try {
    const updated = await api.patch(`/feedback/${item.id}`, { status, reply: drafts[item.id]?.trim() || null })
    Object.assign(item, updated); drafts[item.id] = updated.reply || ''
    notice.value = '处理结果已保存。'
    if (filter.value && filter.value !== updated.status) await load(false)
  } catch (e) { error.value = e.message || '保存失败，回复内容已保留' }
  finally { savingId.value = null }
}
onMounted(() => load())
</script>
<style scoped>
.intro,.meta { color:#64748b; margin:12px 0; }
.toolbar,.heading,.actions { display:flex; flex-wrap:wrap; align-items:center; gap:12px; margin:16px 0; }
.heading { justify-content:space-between; }
.toolbar select { width:auto; }
.feedback-card { background:white; border:1px solid #e2e8f0; border-radius:12px; padding:24px; margin:16px 0; }
.content { white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.7; margin:20px 0; }
textarea { width:100%; margin-top:10px; font:inherit; padding:12px; border:1px solid #cbd5e1; border-radius:8px; }
.error { color:#b91c1c; }
</style>
