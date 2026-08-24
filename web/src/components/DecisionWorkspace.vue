<script setup>
import { computed, ref } from 'vue'
import { useAnalysisRunStore } from '../store/analysisRun'
import ConclusionCard from './ConclusionCard.vue'
import TrendChart from './TrendChart.vue'

const props = defineProps({
  run: { type: Object, default: null },
})

const runStore = useAnalysisRunStore()
const answers = ref({})

const final = computed(() => props.run?.final || {})
const sections = computed(() => final.value.sections || {})
const summary = computed(() => final.value.answer || {})
const evidenceRows = computed(() => Object.values(sections.value).flatMap((section) => section.evidence || []))
const trend = computed(() => evidenceRows.value.filter((item) => item.operator === 'search_volume_trend').flatMap((item) => item.rows || []))
const completedNodes = computed(() => props.run?.nodes?.filter((item) => item.status === 'succeeded').length || 0)

function nodeTitle(nodeId, section) {
  return section.role?.replaceAll('_', ' ') || nodeId.replaceAll('_', ' ')
}

async function submit(need) {
  const value = answers.value[need.field_id]?.trim()
  if (!value) return
  await runStore.submitClarification(need.field_id, value)
}
</script>

<template>
  <section v-if="run" class="workspace" aria-live="polite">
    <header class="run-header">
      <div>
        <p class="eyebrow">ANALYSIS RUN · {{ run.run_id }}</p>
        <h1>{{ final.rewritten || run.query }}</h1>
        <p class="query">{{ run.query }}</p>
      </div>
      <div class="status-stack">
        <span class="status" :class="run.status">{{ run.status }}</span>
        <span class="meta">{{ completedNodes }} 个节点已完成</span>
      </div>
    </header>

    <div v-if="run.status === 'waiting_clarification'" class="clarification-card">
      <p class="eyebrow">INPUT REQUIRED</p>
      <h2>补齐决策前提</h2>
      <div v-for="need in run.clarifications.filter((item) => item.status === 'waiting')" :key="need.field_id" class="clarification-row">
        <label :for="need.field_id">{{ need.question }}</label>
        <div class="quick-options" v-if="need.options?.length">
          <button v-for="option in need.options" :key="option" type="button" @click="answers[need.field_id] = option">{{ option }}</button>
        </div>
        <div class="answer-box">
          <input :id="need.field_id" v-model="answers[need.field_id]" :placeholder="need.options?.[0] || '请输入答案'" @keyup.enter="submit(need)" />
          <button :disabled="!answers[need.field_id]?.trim()" @click="submit(need)">继续研判</button>
        </div>
      </div>
    </div>

    <template v-else-if="final.mode === 'research' || run.status === 'partial_succeeded' || run.status === 'succeeded'">
      <section class="decision-card">
        <div class="card-head">
          <div><p class="eyebrow">DECISION BRIEF</p><h2>经营决策摘要</h2></div>
          <router-link v-if="final.chain_id" :to="`/evidence/${final.chain_id}`" class="evidence-link">审阅证据 →</router-link>
        </div>
        <ConclusionCard :conclusion="summary" accent />
        <TrendChart v-if="trend.length" :data="trend" title="需求趋势" />
      </section>

      <section class="findings" v-if="Object.keys(sections).length">
        <div class="section-head"><p class="eyebrow">EVIDENCE-BASED FINDINGS</p><h2>专家研判</h2></div>
        <article v-for="(section, nodeId) in sections" :key="nodeId" class="finding">
          <div class="finding-label">{{ nodeTitle(nodeId, section) }}</div>
          <p>{{ section.conclusion?.summary || section.error || '暂无可展示结论' }}</p>
          <small>{{ section.evidence?.length || 0 }} 条证据 · {{ section.skipped?.length || 0 }} 项跳过</small>
        </article>
      </section>
    </template>

    <section v-else class="pending-card">
      <span class="pulse"></span>
      <div><p class="eyebrow">RUNNING WITH VERIFIED DATA</p><h2>正在执行受控研判</h2><p>数据取证、专家推理与结果落库会按右侧计划实时更新。</p></div>
    </section>

    <section v-if="run.error" class="error-card">
      <strong>运行异常</strong>
      <span>{{ run.error.message || run.error }}</span>
    </section>
  </section>

  <section v-else class="welcome">
    <p class="eyebrow">AI-BORDERMIND</p>
    <h1>从证据到跨境经营决策</h1>
    <p>提出一个品类、市场或定价问题；系统会先确认范围，再生成受控执行计划。</p>
  </section>
</template>

<style scoped>
.workspace, .welcome { display: flex; flex-direction: column; gap: 18px; min-width: 0; }
.run-header, .decision-card, .findings, .clarification-card, .pending-card, .error-card { border: 1px solid #2a3854; background: linear-gradient(140deg, rgba(25, 34, 54, .95), rgba(17, 23, 37, .88)); border-radius: 16px; }
.run-header { display: flex; justify-content: space-between; gap: 20px; padding: 22px; }
.eyebrow { margin: 0 0 5px; color: #7395df; font-size: 10px; font-weight: 750; letter-spacing: .12em; }
h1 { margin: 0; font-size: clamp(22px, 2.3vw, 34px); letter-spacing: -.03em; }
h2 { margin: 0; font-size: 17px; }
.query { margin: 9px 0 0; color: #9caac4; line-height: 1.5; }
.status-stack { display: flex; align-items: flex-end; flex-direction: column; gap: 6px; white-space: nowrap; }
.status { border: 1px solid #3c4b6c; border-radius: 99px; padding: 5px 10px; font-size: 11px; color: #aab8d2; }
.status.running, .status.planning { color: #fbbf24; border-color: #8a6618; }.status.succeeded { color: #4ade80; border-color: #176b43; }.status.partial_succeeded, .status.failed, .status.timed_out { color: #fbbf24; border-color: #8a6618; }
.meta { color: #71809c; font-size: 11px; }
.decision-card, .findings, .clarification-card { padding: 20px; }
.card-head, .section-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.evidence-link { color: #8cabff; text-decoration: none; font-size: 12px; }
.findings { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }.section-head { grid-column: 1 / -1; }
.finding { border: 1px solid #2a3854; background: rgba(9, 13, 23, .28); padding: 14px; border-radius: 12px; }.finding-label { font-size: 11px; color: #83a6ff; font-weight: 600; text-transform: capitalize; }.finding p { margin: 8px 0; line-height: 1.55; font-size: 13px; }.finding small { color: #71809c; }
.clarification-row { margin-top: 16px; display: grid; gap: 9px; }.clarification-row label { font-weight: 600; }.quick-options { display: flex; gap: 8px; flex-wrap: wrap; }.quick-options button { border: 1px solid #39548b; color: #a9c1ff; background: #18233c; border-radius: 99px; padding: 5px 11px; cursor: pointer; }.answer-box { display: flex; gap: 8px; }.answer-box input { flex: 1; min-width: 0; background: #0d1422; color: #e6ecf5; border: 1px solid #354466; border-radius: 9px; padding: 10px; }.answer-box button { border: 0; border-radius: 9px; background: #497ef0; color: white; padding: 0 14px; font-weight: 600; cursor: pointer; }.answer-box button:disabled { opacity: .4; cursor: not-allowed; }
.pending-card { padding: 30px 22px; display: flex; gap: 13px; align-items: flex-start; }.pending-card h2 { margin-bottom: 7px; }.pending-card p:not(.eyebrow) { color: #9caac4; margin: 0; line-height: 1.5; }.pulse { width: 10px; height: 10px; flex: none; margin-top: 4px; border-radius: 50%; background: #fbbf24; box-shadow: 0 0 0 6px rgba(251,191,36,.13); animation: glow 1.2s infinite; }
.error-card { padding: 14px; display: flex; gap: 10px; color: #fbbf24; flex-wrap: wrap; }.welcome { max-width: 680px; margin: 14vh auto; text-align: center; align-items: center; }.welcome > p:last-child { color: #9caac4; max-width: 540px; line-height: 1.6; }
@keyframes glow { 50% { opacity: .45; } }
@media (max-width: 720px) { .run-header { flex-direction: column; }.status-stack { align-items: flex-start; }.findings { grid-template-columns: 1fr; }.answer-box { flex-direction: column; }.answer-box button { padding: 10px; } }
</style>
