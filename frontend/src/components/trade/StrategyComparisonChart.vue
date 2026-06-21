<template>
  <div ref="chartRef" class="comparison-chart" style="width:100%;height:380px"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  curves: Record<string, Array<{ date: string; total_value: number }>>
  benchmarkCurve?: Array<{ date: string; total_value: number }>
}>()

const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

const COLORS = [
  '#3b82f6', '#ef4444', '#10b981', '#f59e0b',
  '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16',
]

function render() {
  if (!chartRef.value) return
  chart?.dispose()
  chart = null

  const curves = props.curves
  const curveKeys = Object.keys(curves)
  if (!curveKeys.length && !props.benchmarkCurve?.length) return

  try {
    chart = echarts.init(chartRef.value)
    const dateSet = new Set<string>()
    for (const key of curveKeys) {
      const curve = curves[key]
      if (curve?.length) for (const pt of curve) if (pt.date) dateSet.add(pt.date)
    }
    if (props.benchmarkCurve) {
      for (const pt of props.benchmarkCurve) if (pt.date) dateSet.add(pt.date)
    }
    const dates = Array.from(dateSet).sort()
    if (!dates.length) return

    const series: any[] = []
    const legendData: string[] = []
    let colorIdx = 0

    for (const key of curveKeys) {
      const curve = curves[key]
      if (!curve?.length) continue
      const map = new Map(curve.map(c => [c.date, c.total_value]))
      const data = dates.map(d => map.get(d) ?? null)
      const color = COLORS[colorIdx++ % COLORS.length]
      legendData.push(key)
      series.push({
        name: key, type: 'line', data, smooth: true, showSymbol: false,
        lineStyle: { width: 2, color },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: color + '22' }, { offset: 1, color: color + '04' },
        ])},
      })
    }

    if (props.benchmarkCurve?.length) {
      const map = new Map(props.benchmarkCurve.map(c => [c.date, c.total_value]))
      const data = dates.map(d => map.get(d) ?? null)
      legendData.push('基准(等权持有)')
      series.push({
        name: '基准(等权持有)', type: 'line', data, smooth: true, showSymbol: false,
        lineStyle: { width: 1.5, color: '#94a3b8', type: 'dashed' },
      })
    }

    chart.setOption({
      tooltip: {
        trigger: 'axis', backgroundColor: 'rgba(255,255,255,0.96)', borderWidth: 0, textStyle: { fontSize: 12 },
        formatter: (params: any[]) => {
          let s = `<div style="font-weight:600;margin-bottom:4px">${params[0].axisValue}</div>`
          for (const p of params) {
            const v = p.value
            if (v === null || v === undefined) continue
            s += `<div style="display:flex;justify-content:space-between;gap:16px"><span style="color:${p.color}">●</span> ${p.seriesName}<span style="font-weight:600">¥${Number(v).toLocaleString()}</span></div>`
          }
          return s
        },
      },
      legend: { data: legendData, bottom: 0, textStyle: { fontSize: 11, color: '#64748b' }},
      grid: { left: 60, right: 20, top: 16, bottom: 36 },
      xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10, color: '#94a3b8' }, axisLine: { show: false }, axisTick: { show: false }},
      yAxis: { type: 'value', axisLabel: { fontSize: 10, color: '#94a3b8', formatter: (v: number) => `¥${(v / 10000).toFixed(0)}万` }, splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' }}},
      series,
    }, true)
  } catch (e) { console.error('ECharts error:', e) }
}

function scheduleRender() {
  if (Object.keys(props.curves).length > 0 || (props.benchmarkCurve?.length ?? 0) > 0) {
    if (chartRef.value) render()
    else nextTick(() => { if (chartRef.value) render() })
  }
}

watch(() => props.curves, scheduleRender, { deep: true, immediate: true })
watch(() => props.benchmarkCurve, scheduleRender, { deep: true, immediate: true })

onMounted(() => {
  window.addEventListener('resize', () => chart?.resize())
  scheduleRender()
})

onUnmounted(() => {
  chart?.dispose()
  chart = null
})
</script>
