<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'

const route = useRoute()
const router = useRouter()
const recent = ref([])
const chain = ref(null)
const error = ref('')

const ROLE_LABEL = {
  selection_expert: '选品专家',
  pricing_expert: '定价专家',
  positioning_expert: '打法专家',
  executive_expert: '高管洞察',
}

async function loadRecent() {
  try {
    const d = await api.recentChains(20)
    recent.value = d.chains
  } catch (e) {
    error.value = e.message
  }
}

async function loadChain(id) {
  chain.value = null
  error.value = ''
  if (!id) return
  try {
    chain.value = await api.getEvidence(id)
  } catch (e) {
    error.value = e.message
  }
}

function openChain(id) {
  router.push(`/evidence/${id}`)
}

function rowKeys(rows) {
  if (!rows || !rows.length) return []
  return Object.keys(rows[0])
}

onMounted(loadRecent)
watch(() => route.params.chainId, (id) => loadChain(id), { immediate: true })
</script>

<template>
  <div class="evidence">
    <aside class="sidebar">
      <h3>最近证据链</h3>
      <div v-if="!recent.length" class="muted">暂无</div>
      <div
        v-for="c in recent"
        :key="c.chain_id"
        class="chain-item"
        :class="{ active: c.chain_id === route.params.chainId }"
        @click="openChain(c.chain_id)"
      >
        <div class="cid">{{ c.chain_id }}</div>
        <div class="q">{{ c.query }}</div>
      </div>
    </aside>

    <main class="detail">
      <div v-if="error" class="error">{{ error }}</div>
      <div v-else-if="!chain" class="muted">从左侧选择一条证据链查看</div>

      <template v-else>
        <div class="head">
          <h2>{{ chain.chain_id }}</h2>
          <div class="meta">查询：{{ chain.query }} · 时间：{{ chain.created_at }}</div>
        </div>
        <div class="entries">
          <div v-for="(e, i) in chain.entries" :key="i" class="entry">
            <div class="entry-head">
              <span class="role">{{ ROLE_LABEL[e.role] || e.role }}</span>
              <span class="op">{{ e.operator }}</span>
              <span class="ms">{{ e.elapsed_ms }}ms</span>
            </div>
            <pre class="sql">{{ e.sql }}</pre>
            <div class="params">参数：{{ JSON.stringify(e.params) }}</div>
            <table v-if="rowKeys(e.rows).length" class="rows">
              <thead>
                <tr><th v-for="k in rowKeys(e.rows)" :key="k">{{ k }}</th></tr>
              </thead>
              <tbody>
                <tr v-for="(r, ri) in e.rows.slice(0, 20)" :key="ri">
                  <td v-for="k in rowKeys(e.rows)" :key="k">{{ r[k] }}</td>
                </tr>
              </tbody>
            </table>
            <div class="count" v-else>结果：0 行</div>
          </div>
        </div>
      </template>
    </main>
  </div>
</template>

<style scoped>
.evidence { display: flex; height: 100%; }
.sidebar {
  width: 280px; border-right: 1px solid var(--border); padding: 16px; overflow-y: auto;
}
.sidebar h3 { margin-top: 0; }
.chain-item { padding: 10px; border-radius: 8px; cursor: pointer; margin-bottom: 6px; }
.chain-item:hover { background: #22304c; }
.chain-item.active { background: #22304c; border: 1px solid var(--accent); }
.cid { font-size: 12px; color: var(--accent); font-family: monospace; }
.q { font-size: 13px; color: var(--text); margin-top: 4px; }
.detail { flex: 1; overflow-y: auto; padding: 20px; }
.head .meta { color: var(--muted); font-size: 13px; margin-top: 4px; }
.entries { margin-top: 16px; display: flex; flex-direction: column; gap: 16px; }
.entry { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 14px; }
.entry-head { display: flex; gap: 10px; align-items: center; margin-bottom: 10px; }
.role { color: var(--accent); font-weight: 600; }
.op { font-family: monospace; color: var(--text); }
.ms { margin-left: auto; color: var(--muted); font-size: 12px; }
.sql {
  background: var(--bg); padding: 10px; border-radius: 6px; overflow-x: auto;
  color: #a5b4cb; font-size: 12px; line-height: 1.5;
}
.params { color: var(--muted); font-size: 12px; margin-top: 8px; }
.rows { width: 100%; margin-top: 8px; border-collapse: collapse; font-size: 12px; }
.rows th, .rows td { border: 1px solid var(--border); padding: 4px 8px; text-align: left; }
.rows th { color: var(--muted); background: #22304c; }
.count { color: var(--muted); font-size: 12px; margin-top: 8px; }
.error { color: var(--warn); }
.muted { color: var(--muted); }
</style>
