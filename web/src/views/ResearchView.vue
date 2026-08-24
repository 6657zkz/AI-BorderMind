<script setup>
import { ref, nextTick, onBeforeUnmount, watch } from 'vue'
import { useAppStore } from '../store/app'
import { api } from '../api/client'
import { streamChat } from '../api/sse'
import ConclusionCard from '../components/ConclusionCard.vue'
import TrendChart from '../components/TrendChart.vue'

const IDLE_TIMEOUT_MS = 45_000
const TOTAL_TIMEOUT_MS = 240_000

const store = useAppStore()
const input = ref('')
const sending = ref(false)
const scroller = ref(null)
const elapsed = ref(0)
let timer = null
let controller = null
let idleTimeout = null
let totalTimeout = null
let pollTimer = null
let requestSessionId = null

const ROLE_LABEL = {
  demand_researcher: '需求趋势研究员',
  competitive_analyst: '竞争格局分析师',
  price_band_analyst: '价格带分析师',
  feedback_analyst: '差评机会分析师',
  selection_score: '选品综合评分',
  cost_modeler: '成本建模专家',
  competitor_benchmark: '竞品对标分析师',
  pricing_optimizer: '定价决策专家',
  selling_point_analyst: '卖点对比分析师',
  search_gap_analyst: '搜索词空白分析师',
  strategy_node: '打法策略',
  executive_expert: '决策整合',
}

const SUGGESTIONS = [
  '这个品类值得做吗？给个选品建议',
  '帮我看看定价，给个价格策略',
  '分析一下竞争格局和打法',
]

function expertLabel(role) {
  return ROLE_LABEL[role] || role
}

function buildTabs(final) {
  const tabs = [{ key: '__summary__', label: '总结', kind: 'summary' }]
  for (const role of final.roles || []) {
    if (role === 'executive_expert') continue
    if (final.sections && final.sections[role]) {
      tabs.push({ key: role, label: expertLabel(role), kind: 'expert', data: final.sections[role] })
    }
  }
  return tabs
}

function setTab(msg, key) {
  msg.activeTab = key
}

function upsertExpert(msg, role, patch) {
  const idx = msg.experts.findIndex((e) => e.role === role)
  if (idx === -1) msg.experts.push({ role, label: expertLabel(role), status: 'working', error: null, ...patch })
  else Object.assign(msg.experts[idx], patch)
}

function startTimer(startedAt = Date.now()) {
  if (timer) return
  elapsed.value = Math.max(0, Math.floor((Date.now() - startedAt) / 1_000))
  timer = setInterval(() => elapsed.value++, 1000)
}

function stopTimer() {
  if (timer) clearInterval(timer)
  timer = null
}

function clearRequestTimeouts() {
  if (idleTimeout) clearTimeout(idleTimeout)
  if (totalTimeout) clearTimeout(totalTimeout)
  idleTimeout = null
  totalTimeout = null
}

function stopPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = null
}

function hasStreamingMessage() {
  return store.messages.some((message) => message.role === 'assistant' && message.streaming)
}

function parseStoredMessage(content) {
  try {
    const data = JSON.parse(content)
    if (data.kind === 'loading' || data.kind === 'error') return { role: 'assistant', ...data }
    if (data.clarification) return { role: 'assistant', kind: 'clarification', clarification: data.clarification }
    if (data.mode === 'research') return { role: 'assistant', kind: 'research', final: data, chainId: data.chain_id, activeTab: '__summary__' }
    if (data.mode === 'chat') return { role: 'assistant', kind: 'chat', final: data }
  } catch {
    return { role: 'assistant', kind: 'chat', final: { answer: content } }
  }
  return { role: 'assistant', kind: 'error', error: '未知消息' }
}

function startPolling(sessionId) {
  stopPolling()
  if (!hasStreamingMessage()) return
  pollTimer = setInterval(async () => {
    if (store.sessionId !== sessionId) return
    const data = await api.listMessages(sessionId)
    if (store.sessionId !== sessionId) return
    store.messages = data.messages.map((message) =>
      message.role === 'user' ? { role: 'user', content: message.content } : parseStoredMessage(message.content),
    )
    if (!hasStreamingMessage()) stopPolling()
  }, 2_000)
}

async function scrollBottom(sessionId = store.sessionId) {
  await nextTick()
  if (sessionId === store.sessionId && scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
}

function extractTrend(final) {
  const rows = []
  for (const role of Object.keys(final.sections || {})) {
    for (const ev of final.sections[role].evidence || []) {
      if (ev.operator === 'search_volume_trend') rows.push(...ev.rows)
    }
  }
  return rows
}

async function send(text) {
  const msg = (text ?? input.value).trim()
  if (!msg || sending.value || !store.ready || !store.sessionId) return

  const sessionId = store.sessionId
  const requestController = new AbortController()
  requestSessionId = sessionId
  let timeoutMessage = ''
  const markTimedOut = (message) => {
    timeoutMessage = message
    requestController.abort()
  }
  const resetIdleTimeout = () => {
    if (idleTimeout) clearTimeout(idleTimeout)
    idleTimeout = setTimeout(() => markTimedOut('响应长时间未返回，请重试'), IDLE_TIMEOUT_MS)
  }

  input.value = ''
  store.messages.push({ role: 'user', content: msg })
  store.suggestSessionName(msg)
  const assistant = {
    role: 'assistant',
    kind: 'loading',
    experts: [],
    final: null,
    chainId: null,
    startedAt: Date.now(),
    streaming: true,
  }
  store.messages.push(assistant)
  sending.value = true
  controller = requestController
  startTimer()
  resetIdleTimeout()
  totalTimeout = setTimeout(() => markTimedOut('本次研判超时，请缩小问题范围后重试'), TOTAL_TIMEOUT_MS)
  scrollBottom(sessionId)

  try {
    await streamChat({ session_id: sessionId, message: msg }, {
      expert_start: (data) => {
        upsertExpert(assistant, data.role, { label: data.label, status: 'working', error: null })
        scrollBottom(sessionId)
      },
      expert_done: (data) => {
        upsertExpert(assistant, data.role, { status: 'done', error: data.error })
        scrollBottom(sessionId)
      },
      clarification: (data) => {
        assistant.kind = 'clarification'
        assistant.clarification = data.message
        assistant.streaming = false
        scrollBottom(sessionId)
      },
      result: (data) => {
        assistant.kind = data.mode || 'research'
        assistant.final = data
        assistant.chainId = data.chain_id
        assistant.activeTab = '__summary__'
        assistant.streaming = false
        scrollBottom(sessionId)
      },
      error: (data) => {
        assistant.kind = 'error'
        assistant.error = data.message
        assistant.streaming = false
        scrollBottom(sessionId)
      },
    }, { signal: requestController.signal, onActivity: resetIdleTimeout })
  } catch (e) {
    if (store.sessionId === sessionId || e.name !== 'AbortError') {
      assistant.kind = 'error'
      assistant.error = timeoutMessage || `请求失败：${e.message}（后端是否已启动？）`
      assistant.streaming = false
    }
  } finally {
    if (assistant.streaming && store.sessionId === sessionId) {
      assistant.streaming = false
      assistant.kind = 'error'
      assistant.error = '流式响应异常中断，请重试'
    }
    if (controller === requestController) {
      controller = null
      requestSessionId = null
      clearRequestTimeouts()
      sending.value = false
      stopTimer()
    }
    if (store.sessionId === sessionId && assistant.streaming) startPolling(sessionId)
    scrollBottom(sessionId)
  }
}

watch(
  () => store.sessionId,
  (sessionId, previousSessionId) => {
    if (previousSessionId && requestSessionId === previousSessionId) controller?.abort()
    stopPolling()
    stopTimer()
    if (hasStreamingMessage() && sessionId) {
      const running = store.messages.find((message) => message.role === 'assistant' && message.streaming)
      startTimer(running?.startedAt)
      startPolling(sessionId)
    }
  },
)

watch(
  () => store.messages,
  () => {
    if (!controller && hasStreamingMessage() && store.sessionId) {
      const running = store.messages.find((message) => message.role === 'assistant' && message.streaming)
      startTimer(running?.startedAt)
      startPolling(store.sessionId)
    }
  },
  { deep: true },
)

onBeforeUnmount(() => {
  controller?.abort()
  stopPolling()
  clearRequestTimeouts()
  stopTimer()
})
</script>

<template>
  <div class="research">
    <div class="scope-bar" v-if="store.project">
      <span class="dot" :class="{ ok: store.ready }"></span>
      <span>后端已连接</span>
      <span class="divider">·</span>
      <span class="muted">项目：{{ store.project.name }}</span>
      <span class="divider">·</span>
      <span class="muted" :class="{ warn: !store.project.category_id }">
        {{ store.project.category_id ? `范围：${store.project.category_id} / ${store.project.market_code}` : '范围待定（在会话中确认）' }}
      </span>
    </div>

    <div class="chat" ref="scroller">
      <div class="empty-hint" v-if="store.ready && !sending && !store.messages.length">
        <h2>出海参谋</h2>
        <p>数据驱动，替你把跨境决策算出来。新会话从零开始，首次提问会先确认研判范围。试试：</p>
        <button v-for="s in SUGGESTIONS" :key="s" class="suggest" :disabled="sending || !store.ready" @click="send(s)">{{ s }}</button>
      </div>

      <div v-for="(m, i) in store.messages" :key="i" class="row" :class="m.role">
        <div v-if="m.role === 'user'" class="bubble user">{{ m.content }}</div>

        <div v-else class="bubble assistant">
          <div v-if="m.streaming" class="progress-line">
            <span class="live-dot"></span> 推理中… 已运行 {{ elapsed }}s
          </div>
          <div v-if="m.experts && m.experts.length" class="experts">
            <span
              v-for="e in m.experts"
              :key="e.role"
              class="chip"
              :class="{ working: e.status === 'working', done: e.status === 'done', err: e.error }"
            >
              {{ e.label }}{{ e.status === 'done' ? (e.error ? ' ⚠' : ' ✓') : ' …' }}
            </span>
          </div>

          <div v-if="m.kind === 'clarification'" class="clarify">{{ m.clarification }}</div>
          <div v-else-if="m.kind === 'error'" class="error">{{ m.error }}</div>
          <div v-else-if="m.kind === 'chat'" class="chat-text">{{ m.final?.answer }}</div>
          <template v-else-if="m.final && m.kind === 'research'">
            <div class="result-card">
              <div class="tabs" v-if="buildTabs(m.final).length > 1">
                <button
                  v-for="t in buildTabs(m.final)"
                  :key="t.key"
                  class="tab"
                  :class="{ active: m.activeTab === t.key }"
                  @click="setTab(m, t.key)"
                >
                  {{ t.label }}
                </button>
              </div>

              <!-- 主 tab：总结 -->
              <div class="tab-body" v-if="m.activeTab === '__summary__'">
                <div class="rewritten" v-if="m.final.rewritten">{{ m.final.rewritten }}</div>
                <ConclusionCard title="决策摘要" :conclusion="m.final.answer || {}" :accent="true" />
                <TrendChart v-if="extractTrend(m.final).length" :data="extractTrend(m.final)" title="类目搜索量趋势" />
                <router-link v-if="m.chainId" class="evidence-link" :to="`/evidence/${m.chainId}`">
                  查看证据链 →
                </router-link>
              </div>

              <!-- 子 tab：各节点结果 -->
              <div
                v-for="t in buildTabs(m.final)"
                :key="t.key"
                class="tab-body"
                v-if="t.key !== '__summary__' && m.activeTab === t.key"
              >
                <div class="rewritten" v-if="m.final.rewritten">{{ m.final.rewritten }}</div>
                <ConclusionCard :title="t.label" :conclusion="t.data.conclusion || {}" />
                <div class="muted note" v-if="t.data.error">异常：{{ t.data.error }}</div>
                <div class="muted note" v-else-if="t.data.skipped && t.data.skipped.length">
                  跳过 {{ t.data.skipped.length }} 个数据项（{{ t.data.skipped.map((s) => s.operator).join('、') }}）
                </div>
              </div>
            </div>
          </template>
          <div v-else-if="!m.streaming && m.kind === 'loading'" class="error">（加载中…）</div>
        </div>
      </div>
    </div>

    <div class="input-bar">
      <input
        v-model="input"
        placeholder="输入你的研判问题，例如：这个品类值得做吗？"
        @keyup.enter="send()"
        :disabled="sending || !store.ready"
      />
      <button @click="send()" :disabled="sending || !store.ready || !input.trim()">发送</button>
    </div>
  </div>
</template>

<style scoped>
.research { display: flex; flex-direction: column; height: 100%; }
.scope-bar {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 20px; border-bottom: 1px solid var(--border);
  background: var(--panel); font-size: 12px; color: var(--text); flex-shrink: 0;
}
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--muted); }
.dot.ok { background: var(--ok); }
.divider { color: var(--muted); }
.muted { color: var(--muted); }
.warn { color: var(--warn); }
.chat { flex: 1; overflow-y: auto; padding: 20px; }
.empty-hint { text-align: center; margin-top: 60px; color: var(--muted); }
.empty-hint h2 { color: var(--text); }
.suggest {
  display: block; margin: 8px auto; padding: 10px 18px;
  background: var(--panel); border: 1px solid var(--border); border-radius: 20px;
  color: var(--text); cursor: pointer;
}
.suggest:hover { border-color: var(--accent); }
.row { margin-bottom: 16px; }
.bubble { max-width: 82%; }
.bubble.user { margin-left: auto; background: var(--accent); padding: 10px 14px; border-radius: 14px; }
.bubble.assistant { margin-right: auto; }
.progress-line { display: flex; align-items: center; gap: 6px; color: var(--muted); font-size: 13px; }
.live-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--warn); animation: pulse 1.2s infinite; }
.experts { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.chip { font-size: 12px; padding: 3px 10px; border-radius: 12px; background: #22304c; }
.chip.working { color: var(--warn); }
.chip.done { color: var(--ok); }
.chip.err { color: var(--warn); }
@keyframes pulse { 50% { opacity: 0.4; } }
.clarify { padding: 12px; background: var(--panel); border: 1px solid var(--warn); border-radius: 10px; }
.error { color: var(--warn); }
.chat-text { line-height: 1.7; }
.result-card { margin-top: 8px; }
.tabs { display: flex; flex-wrap: wrap; gap: 4px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
.tab {
  border: 1px solid var(--border); background: transparent; color: var(--muted);
  padding: 4px 12px; border-radius: 14px; cursor: pointer; font-size: 12px;
}
.tab.active { color: var(--text); background: #22304c; border-color: var(--accent); }
.tab-body { margin-top: 10px; }
.rewritten {
  color: var(--accent); font-weight: 600; font-size: 13px; margin-bottom: 8px;
}
.note { color: var(--warn); font-size: 12px; margin-top: 8px; }
.muted { color: var(--muted); font-size: 12px; }
.evidence-link { display: inline-block; margin-top: 12px; color: var(--accent); text-decoration: none; }
.input-bar { display: flex; gap: 10px; padding: 14px 20px; border-top: 1px solid var(--border); background: var(--panel); flex-shrink: 0; }
.input-bar input {
  flex: 1; padding: 12px 14px; border-radius: 10px; border: 1px solid var(--border);
  background: var(--bg); color: var(--text); outline: none;
}
.input-bar button {
  padding: 0 20px; border: none; border-radius: 10px; background: var(--accent);
  color: #fff; cursor: pointer; font-weight: 600;
}
.input-bar button:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
