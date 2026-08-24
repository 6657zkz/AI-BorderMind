<script setup>
import { onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  data: { type: Array, default: () => [] },
  title: { type: String, default: '' },
})

const el = ref(null)
let chart = null

function render() {
  if (!el.value || !props.data.length) return
  if (!chart) chart = echarts.init(el.value)
  const xs = props.data.map((d) => new Date(d.ts).toLocaleDateString('zh-CN'))
  const ys = props.data.map((d) => d.volume ?? d.value)
  chart.setOption({
    title: { text: props.title, left: 'center', textStyle: { color: '#8b98ad', fontSize: 12 } },
    grid: { left: 48, right: 16, top: 36, bottom: 28 },
    xAxis: { type: 'category', data: xs, axisLabel: { color: '#8b98ad', fontSize: 10 } },
    yAxis: { type: 'value', axisLabel: { color: '#8b98ad', fontSize: 10 }, splitLine: { lineStyle: { color: '#26324a' } } },
    series: [
      {
        type: 'line', data: ys, smooth: true,
        areaStyle: { opacity: 0.12 }, lineStyle: { color: '#3b82f6' }, itemStyle: { color: '#3b82f6' },
      },
    ],
    tooltip: { trigger: 'axis' },
  })
}

onMounted(render)
watch(() => props.data, render, { deep: true })
</script>

<template>
  <div ref="el" style="height: 200px; width: 100%"></div>
</template>
