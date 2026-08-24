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
const composer = ref(null)
let controller = null

const suggestions = [
  '这个品类值得做吗？给个选品建议',
  '帮我看看定价，给个价格策略',
  '分析一下竞争格局和打法',
]

const scope = computed(() => {
  if (!store.project?.category_id) return '范围待确认'
  return `${store.project.category_id} · ${store.project.market_code || '市场待确认'}`
})

function upsertNode(role, patch) {
  if (!runStore.snapshot) return
  const node = runStore.snapshot.nodes?.find((item) => item.role === role)
  if (node) Object.assign(node, patch)
}

async function send(text) {
  const message = (text ?? input.value).trim()
  if (!message || sending.value || !store.sessionId) return
  input.value = ''
  sending.value = true
  controller = new AbortController()
  store.suggestSessionName(message)
  try {
    await streamChat({ session_id: store.sessionId, message }, {
      run_created: async ({ run_id: runId }) => {
        await runStore.attach(runId)
      },
      expert_start: ({ role }) => upsertNode(role, { status: 'running' }),
      expert_done: ({ role, error }) => upsertNode(role, { status: error ? 'failed' : 'succeeded', error }),
      node_progress: ({ role, stage, elapsed_ms: elapsedMs }) => upsertNode(role, { stage, elapsed_ms: elapsedMs }),
      clarification: async (data) => {
        if (runStore.runId) await runStore.hydrate(runStore.runId)
        else runStore.snapshot = { status: 'waiting_clarification', query: message, clarifications: data.clarifications || [] }
      },
      result: async (data) => {
        if (runStore.runId) await runStore.hydrate(runStore.runId)
        else runStore.snapshot = { status: 'succeeded', query: message, final: data, nodes: [], execution_plan: data.execution_plan }
        await store.selectSession(store.sessionId)
      },
      error: (data) => { runStore.error = data.message },
    }, { signal: controller.signal })
  } catch (error) {
    if (error.name !== 'AbortError') runStore.error = error.message
  } finally {
    controller = null
    sending.value = false
  }
}

watch(
  () => store.sessionId,
  async () => {
    runStore.disconnect()
    const latest = [...store.messages].reverse().find((message) => message.final?.run_id || message.runId)
    const runId = latest?.final?.run_id || latest?.runId
    if (runId) {
      try { await runStore.attach(runId) } catch { /* A historical chat-only entry may not have a persisted run. */ }
    }
  },
)

onBeforeUnmount(() => {
  controller?.abort()
  runStore.disconnect()
})
</script>

<template>
  <div class="research-shell">
    <section class="canvas">
      <header class="scope-bar">
        <div class="scope-label"><span class="live"></span><span>{{ store.project?.name || '加载项目中' }}</span><span class="separator">/</span><span>{{ scope }}</span></div>
        <span class="connection" :class="{ degraded: runStore.error }">{{ runStore.error || '受控数据研判' }}</span>
      </header>

      <div class="canvas-scroll">
        <DecisionWorkspace :run="runStore.snapshot" />
      </div>

      <form ref="composer" class="composer" @submit.prevent="send()">
        <input v-model="input" :disabled="sending" placeholder="提出一个跨境经营问题，例如：美国站 TWS 耳机怎样定价？" />
        <button type="submit" :disabled="sending || !input.trim()">{{ sending ? '运行中' : '开始研判' }}</button>
      </form>
      <div class="suggestions" v-if="!runStore.snapshot">
        <button v-for="item in suggestions" :key="item" :disabled="sending" @click="send(item)">{{ item }}</button>
      </div>
    </section>

    <aside class="inspector">
      <RunTimeline
        :nodes="runStore.planNodes"
        :run-nodes="runStore.snapshot?.nodes || []"
        :status="runStore.snapshot?.status"
      />
      <div v-if="runStore.isRunning" class="inspector-actions">
        <span>{{ runStore.connected ? '已连接运行事件' : '正在重连运行事件' }}</span>
        <button @click="runStore.cancel">取消本次运行</button>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.research-shell { height: 100%; display: grid; grid-template-columns: minmax(0, 1fr) 330px; overflow: hidden; background: radial-gradient(circle at 42% -20%, #1c3267 0, transparent 38%), #0b101b; }
.canvas { min-width: 0; display: flex; flex-direction: column; border-right: 1px solid #26324a; }.scope-bar { padding: 14px 22px; min-height: 52px; display: flex; align-items: center; justify-content: space-between; gap: 12px; border-bottom: 1px solid #26324a; color: #9caac4; font-size: 12px; }.scope-label { display: flex; align-items: center; gap: 8px; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }.live { width: 7px; height: 7px; border-radius: 50%; background: #4ade80; box-shadow: 0 0 0 4px rgba(74,222,128,.08); }.separator { color: #4c5d7c; }.connection { color: #6f84af; white-space: nowrap; }.connection.degraded { color: #fbbf24; }.canvas-scroll { flex: 1; overflow-y: auto; padding: clamp(16px, 3vw, 36px); }.composer { display: flex; gap: 9px; margin: 0 22px 10px; padding: 7px; background: rgba(24, 33, 52, .85); border: 1px solid #314261; border-radius: 14px; box-shadow: 0 -12px 50px rgba(2,6,15,.2); }.composer input { flex: 1; min-width: 0; border: 0; outline: 0; color: #edf3ff; background: transparent; padding: 8px 10px; font: inherit; }.composer input::placeholder { color: #71809c; }.composer button { border: 0; border-radius: 9px; background: linear-gradient(135deg, #4f8cff, #6e5eff); color: white; padding: 0 14px; font-weight: 650; cursor: pointer; }.composer button:disabled { opacity: .5; cursor: not-allowed; }.suggestions { display: flex; flex-wrap: wrap; gap: 7px; padding: 0 26px 16px; }.suggestions button { background: transparent; color: #8ea8dd; border: 1px solid #334666; border-radius: 999px; padding: 5px 10px; cursor: pointer; font-size: 11px; }.suggestions button:hover { border-color: #759df8; color: #c7d8ff; }
.inspector { overflow-y: auto; padding: 20px 16px; background: rgba(13, 19, 31, .88); }.inspector-actions { position: sticky; bottom: -20px; display: flex; flex-direction: column; gap: 9px; padding: 16px 0 0; margin-top: 16px; background: linear-gradient(to top, #0d131f 72%, transparent); color: #71809c; font-size: 11px; }.inspector-actions button { border: 1px solid #674137; background: #2b1c1a; color: #fbbf24; padding: 8px; border-radius: 8px; cursor: pointer; }
@media (max-width: 1120px) { .research-shell { grid-template-columns: minmax(0, 1fr) 280px; } }.inspector { padding: 16px 12px; }
@media (max-width: 820px) { .research-shell { display: flex; flex-direction: column; overflow: auto; }.canvas { min-height: 74vh; border-right: 0; }.inspector { border-top: 1px solid #26324a; overflow: visible; }.scope-bar { padding: 12px 16px; }.connection { display: none; }.composer { margin: 0 16px 9px; }.suggestions { padding: 0 18px 14px; } }
</style>
