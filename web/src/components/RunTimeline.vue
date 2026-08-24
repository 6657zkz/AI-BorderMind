<script setup>
import { computed } from 'vue'

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  runNodes: { type: Array, default: () => [] },
  status: { type: String, default: '' },
})

const runNodeMap = computed(() => Object.fromEntries(props.runNodes.map((node) => [node.node_id, node])))
const layers = computed(() => {
  const pending = new Map(props.nodes.map((node) => [node.id, node]))
  const completed = new Set()
  const result = []
  while (pending.size) {
    const ready = [...pending.values()].filter((node) => (node.depends_on || []).every((id) => completed.has(id)))
    if (!ready.length) return [...result, [...pending.values()]]
    result.push(ready)
    ready.forEach((node) => {
      pending.delete(node.id)
      completed.add(node.id)
    })
  }
  return result
})

function nodeState(node) {
  return runNodeMap.value[node.id]?.status || 'queued'
}

function nodeStage(node) {
  const item = runNodeMap.value[node.id]
  if (item?.stage === 'data_fetch_started') return '正在取证'
  if (item?.stage === 'llm_started') return '正在推理'
  if (item?.stage === 'llm_completed') return '正在整理结论'
  if (item?.status === 'succeeded') return '已完成'
  if (item?.status === 'failed') return '执行失败'
  if (item?.status === 'skipped') return '已跳过'
  if (item?.status === 'queued') return '准备执行'
  if (!item && props.status === 'succeeded') return '未收到执行记录'
  return '等待依赖'
}

function roleName(node) {
  return node.expert_role_id?.replaceAll('_', ' ') || node.id
}
</script>

<template>
  <section class="timeline" aria-label="执行计划">
    <div class="head">
      <div>
        <p class="eyebrow">EXECUTION PLAN</p>
        <h3>运行检查器</h3>
      </div>
      <span class="run-status" :class="status">{{ status || 'planning' }}</span>
    </div>

    <div v-if="!nodes.length" class="empty">{{ status === 'waiting_clarification' ? '补齐决策前提后将在这里生成执行计划。' : '计划生成后将在这里展示执行节点。' }}</div>
    <div v-for="(layer, index) in layers" :key="index" class="layer">
      <div class="layer-title">第 {{ index + 1 }} 层 <span>可并行</span></div>
      <article v-for="node in layer" :key="node.id" class="node" :class="nodeState(node)">
        <span class="status-dot"></span>
        <div class="node-content">
          <strong>{{ roleName(node) }}</strong>
          <small>{{ nodeStage(node) }}</small>
          <p v-if="node.depends_on?.length">依赖：{{ node.depends_on.join(' · ') }}</p>
          <p v-if="runNodeMap[node.id]?.error" class="error">{{ runNodeMap[node.id].error }}</p>
          <p v-else-if="runNodeMap[node.id]?.elapsed_ms">{{ runNodeMap[node.id].elapsed_ms }}ms · {{ runNodeMap[node.id].output_summary?.evidence_count || 0 }} 条证据</p>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.timeline { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.eyebrow { margin: 0 0 4px; font-size: 10px; letter-spacing: .12em; color: var(--muted); font-weight: 700; }
h3 { margin: 0; font-size: 15px; color: var(--text); }
.run-status { border: 1px solid var(--border); color: var(--muted); padding: 4px 8px; border-radius: 999px; font-size: 11px; white-space: nowrap; background: var(--surface-subtle); }
.run-status.running, .run-status.planning { color: #a16207; border-color: #fcd34d; background: #fffbeb; }.run-status.succeeded { color: #15803d; border-color: #86efac; background: #f0fdf4; }.run-status.partial_succeeded, .run-status.failed, .run-status.timed_out { color: #b45309; border-color: #fdba74; background: #fff7ed; }
.layer { display: flex; flex-direction: column; gap: 7px; }
.layer-title { color: var(--muted); font-size: 11px; font-weight: 600; }.layer-title span { margin-left: 5px; color: #94a3b8; font-weight: 400; }
.node { display: flex; gap: 9px; padding: 10px; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; }.status-dot { width: 7px; height: 7px; flex: 0 0 auto; margin-top: 5px; border-radius: 50%; background: #94a3b8; }.node.running .status-dot { background: #eab308; box-shadow: 0 0 0 4px rgba(234, 179, 8, .12); animation: breathe 1.4s infinite; }.node.succeeded .status-dot { background: var(--ok); }.node.failed .status-dot, .node.skipped .status-dot { background: #f97316; }
.node-content { min-width: 0; display: flex; flex-direction: column; gap: 3px; }.node-content strong { font-size: 12px; color: var(--text); text-transform: capitalize; }.node-content small { color: var(--muted); font-size: 11px; }.node-content p { margin: 1px 0 0; color: var(--muted); font-size: 10px; overflow-wrap: anywhere; }.node-content .error { color: #b45309; }.empty { color: var(--muted); font-size: 12px; padding: 18px 0; }
@keyframes breathe { 50% { opacity: .48; } }
</style>
