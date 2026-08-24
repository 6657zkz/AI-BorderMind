<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useAppStore } from '../store/app'
import { useAnalysisRunStore } from '../store/analysisRun'
import { streamChat } from '../api/sse'
import DecisionWorkspace from '../components/DecisionWorkspace.vue'
import RunTimeline from '../components/RunTimeline.vue'

const store = useAppStore()
const runStore = useAnalysisRunStore()
const input = ref('')
const sending = ref(false)
let controller = null
let requestId = 0

const suggestions = [
  '这个品类值得做吗？给个选品建议',
  '帮我看看定价，给个价格策略',
  '分析一下竞争格局和打法',
]

const scope = computed(() => {
  if (!store.project?.category_id) return '范围待确认'
  return `${store.project.category_id} · ${store.project.market_code || '市场待确认'}`
})

function isCurrent(context) {
  return context.requestId === requestId
    && context.sessionId === store.sessionId
    && context.projectId === store.projectId
}

function updateNode(nodeId, role, patch) {
  runStore.updateNode(nodeId, role, patch)
}

async function cancelRun() {
  requestId += 1
  controller?.abort()
  controller = null
  sending.value = false
  await runStore.cancel()
}

async function send(text) {
  const message = (text ?? input.value).trim()
  if (!message || sending.value || !store.sessionId) return
  const context = {
    requestId: ++requestId,
    sessionId: store.sessionId,
    projectId: store.projectId,
  }
  input.value = ''
  sending.value = true
  runStore.beginPending(message)
  controller = new AbortController()
  store.suggestSessionName(message)
  try {
    await streamChat({ session_id: context.sessionId, message }, {
      run_created: async ({ run_id: runId }) => {
        if (!isCurrent(context)) return
        await runStore.attach(runId)
      },
      expert_start: ({ node_id: nodeId, role }) => {
        if (isCurrent(context)) updateNode(nodeId, role, { status: 'running' })
      },
      expert_done: ({ node_id: nodeId, role, error }) => {
        if (isCurrent(context)) updateNode(nodeId, role, { status: error ? 'failed' : 'succeeded', error })
      },
      node_progress: ({ node_id: nodeId, role, stage, elapsed_ms: elapsedMs }) => {
        if (isCurrent(context)) updateNode(nodeId, role, { stage, elapsed_ms: elapsedMs })
      },
      clarification: async (data) => {
        if (!isCurrent(context)) return
        if (runStore.runId) await runStore.hydrate(runStore.runId)
        else runStore.snapshot = {
          status: 'waiting_clarification', query: message, clarifications: data.clarifications || [],
          nodes: [], execution_plan: data.execution_plan || { nodes: [] }, final: {},
        }
      },
      result: async (data) => {
        if (!isCurrent(context)) return
        if (runStore.runId) await runStore.hydrate(runStore.runId)
        else runStore.snapshot = { status: 'succeeded', query: message, final: data, nodes: [], execution_plan: data.execution_plan || { nodes: [] } }
        if (isCurrent(context)) await store.selectSession(context.sessionId)
      },
      error: (data) => {
        if (isCurrent(context)) runStore.error = data.message
      },
    }, { signal: controller.signal })
  } catch (error) {
    if (error.name !== 'AbortError' && isCurrent(context)) {
      runStore.error = error.message
      if (runStore.snapshot?.status === 'planning') runStore.snapshot.status = 'failed'
    }
  } finally {
    if (context.requestId === requestId) {
      controller = null
      sending.value = false
    }
  }
}

watch(
  () => `${store.projectId}:${store.sessionId}`,
  async () => {
    requestId += 1
    controller?.abort()
    controller = null
    sending.value = false
    runStore.reset()
    const latest = [...store.messages].reverse().find((message) => message.final?.run_id || message.runId)
    const runId = latest?.final?.run_id || latest?.runId
    if (runId) {
      try { await runStore.attach(runId) } catch { /* Historical chat-only entry. */ }
    }
  },
)

onBeforeUnmount(() => {
  requestId += 1
  controller?.abort()
  runStore.reset()
})
</script>

<template>
  <div class="research-shell">
    <section class="canvas">
      <header class="scope-bar">
        <div class="scope-label"><span class="live"></span><span>{{ store.project?.name || '加载项目中' }}</span><span class="separator">/</span><span>{{ scope }}</span></div>
        <span class="connection" :class="{ degraded: runStore.error }">{{ runStore.error || (sending && !runStore.runId ? '正在创建研判…' : '受控数据研判') }}</span>
      </header>

      <div class="canvas-scroll">
        <DecisionWorkspace :run="runStore.snapshot" />
      </div>

      <form class="composer" @submit.prevent="send()">
        <input v-model="input" :disabled="sending" placeholder="提出一个跨境经营问题，例如：美国站 TWS 耳机怎样定价？" />
        <button type="submit" :disabled="sending || !input.trim()">{{ sending ? (runStore.runId ? '运行中' : '创建中') : '开始研判' }}</button>
      </form>
      <div class="suggestions" v-if="!runStore.snapshot">
        <button v-for="item in suggestions" :key="item" :disabled="sending" @click="send(item)">{{ item }}</button>
      </div>
    </section>

    <aside class="inspector">
      <RunTimeline :nodes="runStore.planNodes" :run-nodes="runStore.snapshot?.nodes || []" :status="runStore.snapshot?.status" />
      <div v-if="runStore.canCancel" class="inspector-actions">
        <span>{{ runStore.isRunning ? (runStore.connected ? '已连接运行事件' : '正在连接运行事件') : '等待补充决策前提' }}</span>
        <button @click="cancelRun">取消本次运行</button>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.research-shell { height: 100%; min-height: 0; min-width: 0; display: grid; grid-template-columns: minmax(0, 1fr) 330px; overflow: hidden; background: var(--surface-subtle); }
.canvas { min-width: 0; min-height: 0; display: flex; flex-direction: column; border-right: 1px solid var(--border); }.scope-bar { padding: 14px 22px; min-height: 54px; display: flex; align-items: center; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--border); color: var(--muted); font-size: 12px; background: var(--surface); }.scope-label { display: flex; align-items: center; gap: 8px; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }.live { width: 7px; height: 7px; border-radius: 50%; background: var(--ok); box-shadow: 0 0 0 4px rgba(22, 163, 74, .12); }.separator { color: #cbd5e1; }.connection { color: var(--muted); white-space: nowrap; }.connection.degraded { color: var(--warn); }.canvas-scroll { flex: 1; min-height: 0; overflow-y: auto; padding: clamp(16px, 3vw, 36px); }.composer { flex: 0 0 auto; display: flex; gap: 9px; margin: 0 22px 10px; padding: 7px; background: var(--surface); border: 1px solid var(--border); border-radius: 14px; box-shadow: 0 -8px 24px rgba(15, 23, 42, .06); }.composer input { flex: 1; min-width: 0; border: 0; outline: 0; color: var(--text); background: transparent; padding: 8px 10px; font: inherit; }.composer input::placeholder { color: #94a3b8; }.composer button { border: 0; border-radius: 9px; background: var(--accent); color: white; padding: 0 14px; font-weight: 650; cursor: pointer; }.composer button:disabled { opacity: .5; cursor: not-allowed; }.suggestions { flex: 0 0 auto; display: flex; flex-wrap: wrap; gap: 7px; padding: 0 26px 16px; }.suggestions button { background: var(--surface); color: #3564c8; border: 1px solid #bfdbfe; border-radius: 999px; padding: 5px 10px; cursor: pointer; font-size: 11px; }.suggestions button:hover { border-color: var(--accent); color: var(--accent); }
.inspector { min-height: 0; min-width: 0; overflow-y: auto; padding: 20px 16px; background: var(--surface); }.inspector-actions { position: sticky; bottom: -20px; display: flex; flex-direction: column; gap: 9px; padding: 16px 0 0; margin-top: 16px; background: linear-gradient(to top, var(--surface) 72%, transparent); color: var(--muted); font-size: 11px; }.inspector-actions button { border: 1px solid #fecaca; background: #fff7ed; color: #b45309; padding: 8px; border-radius: 8px; cursor: pointer; }
@media (max-width: 1120px) { .research-shell { grid-template-columns: minmax(0, 1fr) 280px; } .inspector { padding: 16px 12px; } }
@media (max-width: 820px) { .research-shell { display: flex; flex-direction: column; overflow: auto; }.canvas { min-height: 74vh; border-right: 0; }.inspector { border-top: 1px solid var(--border); overflow: visible; }.scope-bar { padding: 12px 16px; }.connection { display: none; }.composer { margin: 0 16px 9px; }.suggestions { padding: 0 18px 14px; } }
</style>
