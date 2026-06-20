<template>
  <div class="portfolio-page">
    <div class="page-header">
      <h2>📊 Portfolio Monitor</h2>
      <el-button size="small" @click="loadData" :loading="loading">重新加载</el-button>
    </div>

    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="3" animated />
    </div>

    <template v-else>
      <div class="two-col">
        <!-- 左列：赛道权重 -->
        <div class="left-col">
          <div class="section-card">
            <div class="section-title">🎯 赛道权重分配（按景气度）</div>
            <div ref="pieChartRef" class="chart-box-sm" />
            <div class="weight-table">
              <div v-for="t in portfolio?.tracks || []" :key="t.name" class="weight-row">
                <span class="w-name" :style="{ color: trackColor(t.name) }">{{ t.display_name }}</span>
                <div class="w-bar-bg">
                  <div class="w-bar-fill" :style="{ width: t.weight + '%', background: trackColor(t.name) }" />
                </div>
                <span class="w-value">{{ t.weight.toFixed(1) }}%</span>
                <span class="w-sentiment">
                  <el-tag :type="t.sentiment >= 60 ? 'success' : t.sentiment >= 40 ? 'warning' : 'danger'" size="small" effect="plain">
                    {{ t.sentiment.toFixed(0) }}
                  </el-tag>
                </span>
              </div>
            </div>
          </div>

          <!-- 风险监控 -->
          <div class="section-card">
            <div class="section-title">⚠️ 风险敞口监控</div>
            <div class="risk-grid">
              <div v-for="r in riskItems" :key="r.label" class="risk-item">
                <div class="risk-label">{{ r.label }}</div>
                <div class="risk-value" :style="{ color: r.color }">{{ r.value }}</div>
                <div class="risk-bar">
                  <div class="risk-fill" :style="{ width: r.pct + '%', background: r.color }" />
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 右列：个股持仓 -->
        <div class="right-col">
          <div class="section-card">
            <div class="section-title">
              💼 个股持仓比例
              <span class="section-sub">按赛道分组</span>
            </div>
            <div v-for="t in portfolio?.tracks || []" :key="t.name" class="track-positions">
              <div class="tp-header" :style="{ color: trackColor(t.name) }">
                {{ t.display_name }}
                <span class="tp-weight">{{ t.weight.toFixed(1) }}%</span>
              </div>
              <div v-for="s in (t.stocks || [])" :key="s.stock_code" class="position-row">
                <div class="p-info">
                  <span class="p-name">{{ s.stock_name || s.stock_code }}</span>
                  <span v-if="s.stock_name" class="p-code-sm">{{ s.stock_code }}</span>
                </div>
                <div class="p-bar-bg">
                  <div class="p-bar-fill" :style="{ width: scoreToPct(s.score) + '%', background: s.score > 0 ? '#67c23a' : '#f56c6c' }" />
                </div>
                <span class="p-score">{{ (s.score * 100).toFixed(2) }}</span>
                <span class="p-rank">#{{ s.rank }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 调仓时间线 -->
      <div class="section-card">
        <div class="section-title">📅 调仓时间线</div>
        <div ref="timelineChartRef" class="chart-box" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { getPortfolioSummary, getBacktestEquity } from '@/api/track'
import * as echarts from 'echarts'

const loading = ref(true)
const portfolio = ref<any>(null)
const equityData = ref<any[]>([])
const pieChartRef = ref<HTMLElement>()
const timelineChartRef = ref<HTMLElement>()

const trackColors: Record<string, string> = {
  semiconductor: '#3b82f6',
  ai: '#f59e0b',
  robot: '#10b981',
  storage: '#8b5cf6',
}
function trackColor(name: string) { return trackColors[name] || '#909399' }

const riskItems = computed(() => {
  const r = portfolio.value?.risk_metrics || {}
  const items = [
    { label: '总收益', value: (r.total_return || 0).toFixed(1) + '%', color: (r.total_return || 0) >= 0 ? '#67c23a' : '#f56c6c', pct: Math.min(100, Math.abs(r.total_return || 0)) },
    { label: '年化波动', value: (r.annual_volatility || 0).toFixed(1) + '%', color: (r.annual_volatility || 0) > 30 ? '#f56c6c' : '#e6a23c', pct: Math.min(100, (r.annual_volatility || 0)) },
    { label: '最大回撤', value: (r.max_drawdown || 0).toFixed(1) + '%', color: Math.abs(r.max_drawdown || 0) > 25 ? '#f56c6c' : '#67c23a', pct: Math.min(100, Math.abs(r.max_drawdown || 0)) },
    { label: '夏普比率', value: (r.sharpe_ratio || 0).toFixed(3), color: (r.sharpe_ratio || 0) >= 1.2 ? '#67c23a' : '#e6a23c', pct: Math.min(100, ((r.sharpe_ratio || 0) + 2) * 25) },
    { label: '胜率', value: (r.win_rate || 0).toFixed(0) + '%', color: (r.win_rate || 0) >= 50 ? '#67c23a' : '#e6a23c', pct: r.win_rate || 0 },
    { label: '交易次数', value: String(r.total_trades || 0), color: '#909399', pct: Math.min(100, (r.total_trades || 0) / 3) },
  ]
  return items
})

function scoreToPct(score: number): number {
  return Math.min(95, Math.max(5, (score + 0.02) * 2000))
}

function renderCharts() {
  nextTick(() => {
    // Pie chart
    if (pieChartRef.value && portfolio.value?.tracks) {
      const chart = echarts.init(pieChartRef.value)
      chart.setOption({
        tooltip: { formatter: (p: any) => `${p.name}: ${p.percent}%` },
        series: [{
          type: 'pie',
          radius: ['40%', '70%'],
          center: ['50%', '50%'],
          data: portfolio.value.tracks.map((t: any) => ({
            name: t.display_name,
            value: t.weight,
            itemStyle: { color: trackColor(t.name) },
          })),
          label: { show: true, formatter: '{b}\n{d}%', fontSize: 11 },
          emphasis: { scale: true },
        }],
      })
    }

    // Timeline chart
    if (timelineChartRef.value && equityData.value.length > 0) {
      const chart = echarts.init(timelineChartRef.value)
      const dates = equityData.value.map((d: any) => d.date || '')
      const nav = equityData.value.map((d: any) => parseFloat(d.total_value || '1'))
      const benchmark = equityData.value.map((d: any) => parseFloat(d.benchmark || '1'))

      chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['Portfolio NAV', 'Benchmark'], top: 0, textStyle: { fontSize: 11 } },
        grid: { left: 50, right: 20, top: 35, bottom: 30 },
        xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10, rotate: 45 } },
        yAxis: { type: 'value', axisLabel: { formatter: (v: number) => v.toFixed(2) } },
        series: [
          { name: 'Portfolio NAV', type: 'line', data: nav, smooth: true, lineStyle: { color: '#3b82f6', width: 1.5 }, symbol: 'none', areaStyle: { color: 'rgba(59,130,246,0.08)' } },
          { name: 'Benchmark', type: 'line', data: benchmark, smooth: true, lineStyle: { color: '#909399', width: 1, type: 'dashed' }, symbol: 'none' },
        ],
      })
    }
  })
}

async function loadData() {
  loading.value = true
  try {
    const [pf, eq] = await Promise.all([
      getPortfolioSummary(),
      getBacktestEquity().catch(() => ({ data: [] })),
    ])
    portfolio.value = pf as any
    equityData.value = ((eq as any)?.data) || []
  } catch (e) {
    console.error('Portfolio data load failed', e)
  }
  loading.value = false
  renderCharts()
}

onMounted(loadData)
</script>

<style scoped>
.portfolio-page {
  min-height: 100%;
  padding: 24px 32px;
  background: #f5f7fa;
}
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; font-size: 22px; color: #1e293b; }
.loading-state { padding: 40px; background: #fff; border-radius: 10px; }

.two-col { display: flex; gap: 16px; margin-bottom: 16px; }
.left-col { flex: 1; display: flex; flex-direction: column; gap: 16px; }
.right-col { flex: 1; }

.section-card { background: #fff; border-radius: 8px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom: 16px; }
.section-title { font-size: 14px; font-weight: 600; color: #303133; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }
.section-sub { font-size: 11px; color: #c0c4cc; font-weight: 400; }
.chart-box { width: 100%; height: 320px; }
.chart-box-sm { width: 100%; height: 240px; }

/* Weight table */
.weight-table { margin-top: 8px; }
.weight-row { display: flex; align-items: center; gap: 8px; padding: 5px 0; }
.w-name { font-size: 12px; font-weight: 600; min-width: 80px; }
.w-bar-bg { flex: 1; height: 8px; background: #f0f2f5; border-radius: 4px; overflow: hidden; }
.w-bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s; }
.w-value { font-size: 12px; font-weight: 600; min-width: 48px; text-align: right; color: #303133; }
.w-sentiment { min-width: 36px; }

/* Risk grid */
.risk-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.risk-item { text-align: center; padding: 8px; background: #f8fafc; border-radius: 6px; }
.risk-label { font-size: 11px; color: #909399; margin-bottom: 4px; }
.risk-value { font-size: 18px; font-weight: 700; }
.risk-bar { height: 3px; background: #f0f2f5; border-radius: 2px; margin-top: 4px; overflow: hidden; }
.risk-fill { height: 100%; border-radius: 2px; }

/* Positions */
.track-positions { margin-bottom: 12px; }
.tp-header { font-size: 13px; font-weight: 600; margin-bottom: 6px; display: flex; align-items: center; gap: 8px; }
.tp-weight { font-size: 11px; color: #909399; }
.position-row { display: flex; align-items: center; gap: 6px; padding: 3px 0 3px 12px; }
.p-code { font-size: 11px; font-family: 'SF Mono', monospace; color: #606266; min-width: 80px; }
.p-info { display: flex; flex-direction: column; min-width: 0; }
.p-name { font-size: 12px; font-weight: 600; color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.p-code-sm { font-size: 10px; color: #c0c4cc; font-family: 'SF Mono', monospace; }
.p-bar-bg { flex: 1; height: 4px; background: #f0f2f5; border-radius: 2px; overflow: hidden; }
.p-bar-fill { height: 100%; border-radius: 2px; }
.p-score { font-size: 11px; font-weight: 600; min-width: 42px; text-align: right; color: #606266; }
.p-rank { font-size: 10px; color: #c0c4cc; min-width: 24px; text-align: right; }
</style>
