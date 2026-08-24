<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/client'
import { useAppStore } from '../store/app'

const store = useAppStore()
const signals = ref([])
const loading = ref(false)
const running = ref(false)
const error = ref('')

const TYPE_LABEL = {
  pricing_change: '价格变动',
  review_surge: '评论突增',
  trend_shift: '趋势转向',
  supply_disruption: '供应中断',
}

async function load() {
  loading.value = true
  try {
    const d = await api.listSignals(store.projectId)
    signals.value = d.signals
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function runMonitor() {
  running.value = true
  try {
    const d = await api.runMonitor({ project_id: store.projectId })
    alert(`巡检完成，新增 ${d.created} 条信号`)
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    running.value = false
  }
}

function fmtTs(ts) {
  if (!ts) return '-'
  return new Date(ts).toLocaleString('zh-CN')
}

onMounted(async () => {
  await store.init()
  await load()
})
</script>

<template>
  <div class="signals">
    <div class="head">
      <h2>监控信号</h2>
      <button @click="runMonitor" :disabled="running">{{ running ? '巡检中…' : '手动巡检' }}</button>
    </div>
    <div class="error" v-if="error">{{ error }}</div>
    <div class="muted" v-if="loading">加载中…</div>
    <div class="empty" v-if="!loading && !signals.length">
      暂无信号。持续监控按时间触发，或点「手动巡检」跑一次变化检测。
    </div>
    <div class="list">
      <div v-for="s in signals" :key="s.id" class="card">
        <div class="card-head">
          <span class="type">{{ TYPE_LABEL[s.signal_type] || s.signal_type }}</span>
          <span class="confidence" :class="s.confidence">{{ s.confidence }}</span>
          <span class="status" :class="s.status">{{ s.status }}</span>
        </div>
        <div class="summary">{{ s.summary }}</div>
        <div class="meta">
          <span>实体：{{ s.entity || '-' }}</span>
          <span>时间：{{ fmtTs(s.observed_at) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.signals { padding: 20px; max-width: 900px; margin: 0 auto; height: 100%; overflow-y: auto; }
.head { display: flex; justify-content: space-between; align-items: center; }
.head button {
  padding: 8px 16px; border: none; border-radius: 8px; background: var(--accent);
  color: #fff; cursor: pointer; font-weight: 600;
}
.error { color: var(--warn); }
.muted { color: var(--muted); }
.empty { color: var(--muted); margin-top: 40px; text-align: center; }
.list { margin-top: 16px; display: flex; flex-direction: column; gap: 12px; }
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }
.card-head { display: flex; gap: 10px; align-items: center; margin-bottom: 8px; }
.type { font-weight: 600; color: var(--accent); }
.confidence { font-size: 12px; padding: 2px 8px; border-radius: 10px; background: #22304c; }
.confidence.high { color: var(--warn); }
.confidence.medium { color: var(--accent); }
.confidence.low { color: var(--muted); }
.status { font-size: 12px; color: var(--muted); }
.summary { line-height: 1.6; }
.meta { margin-top: 8px; color: var(--muted); font-size: 12px; display: flex; gap: 16px; }
</style>
