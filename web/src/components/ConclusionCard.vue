<script setup>
const props = defineProps({
  title: { type: String, default: '' },
  conclusion: { type: Object, default: () => ({}) },
  accent: { type: Boolean, default: false },
})
</script>

<template>
  <div class="conclusion" :class="{ accent }">
    <div class="conclusion-title" v-if="title">{{ title }}</div>
    <div class="summary" v-if="conclusion.summary">{{ conclusion.summary }}</div>
    <ul class="args" v-if="conclusion.arguments && conclusion.arguments.length">
      <li v-for="(a, i) in conclusion.arguments" :key="i">{{ a }}</li>
    </ul>
    <div class="reco" v-if="conclusion.recommendation">
      <span class="label">建议</span>{{ conclusion.recommendation }}
    </div>
    <div class="risks" v-if="conclusion.risks && conclusion.risks.length">
      <span class="label">风险</span>
      <ul><li v-for="(r, i) in conclusion.risks" :key="i">{{ r }}</li></ul>
    </div>
    <div class="empty" v-if="!conclusion.summary && !conclusion.arguments && !conclusion.recommendation">
      无结论
    </div>
  </div>
</template>

<style scoped>
.conclusion {
  background: var(--panel); border: 1px solid var(--border);
  border-radius: 10px; padding: 14px 16px; margin-top: 10px;
}
.conclusion.accent { border-color: var(--accent); }
.conclusion-title { font-weight: 600; color: var(--accent); margin-bottom: 8px; }
.summary { font-weight: 600; line-height: 1.6; }
.args { margin: 8px 0; padding-left: 18px; color: var(--text); }
.args li { margin: 4px 0; line-height: 1.5; }
.reco, .risks { margin-top: 8px; color: var(--text); line-height: 1.6; }
.label { display: inline-block; color: var(--muted); font-size: 12px; margin-right: 8px; }
.risks ul { margin: 4px 0 0; padding-left: 18px; }
.risks li { color: var(--warn); margin: 3px 0; }
.empty { color: var(--muted); }
</style>
