<template>
  <div class="alpha-page">
    <div class="page-header">
      <h2>📈 Alpha Research</h2>
      <el-button size="small" @click="loadData" :loading="loading">重新加载</el-button>
    </div>

    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="3" animated />
    </div>

    <template v-else>
      <!-- 赛道选择 -->
      <div class="filter-row">
        <el-select v-model="selectedTrack" placeholder="选择赛道" size="small" @change="loadData" clearable>
          <el-option v-for="t in tracks" :key="t.name" :label="t.display_name" :value="t.name" />
        </el-select>
        <el-select v-model="selectedFactor" placeholder="选择因子" size="small" clearable filterable>
          <el-option v-for="f in factorNames" :key="f" :label="f" :value="f" />
        </el-select>
        <span class="filter-hint">
          {{ rows.length }} 行 · {{ factorNames.length }} 因子
        </span>
      </div>

      <!-- 因子IC时序 -->
      <div class="section-card" v-if="icTimeSeries.length > 0">
        <div class="section-title">📊 因子IC时序（{{ selectedFactor || '平均IC' }}）</div>
        <div ref="icChartRef" class="chart-box" />
      </div>

      <!-- 相关性热力图 -->
      <div class="section-card">
        <div class="section-title">🔥 因子相关性热力图（Top 20 因子）</div>
        <div ref="corrChartRef" class="chart-box" />
      </div>

      <!-- 分位数组合收益 -->
      <div class="section-card">
        <div class="section-title">📦 分位数组合累计收益</div>
        <div ref="quintileChartRef" class="chart-box" />
      </div>

      <!-- 因子IC统计表 -->
      <div class="section-card">
        <div class="section-title">📋 因子IC统计</div>
        <el-table :data="factorIcStats" size="small" stripe max-height="360" style="width:100%">
          <el-table-column prop="name" label="因子" min-width="160" />
          <el-table-column prop="mean_ic" label="Mean IC" width="100" align="right">
            <template #default="{ row }">
              <span :style="{ color: row.mean_ic > 0 ? '#67c23a' : '#f56c6c' }">{{ row.mean_ic.toFixed(4) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="std_ic" label="Std IC" width="100" align="right" />
          <el-table-column prop="ir" label="IR" width="100" align="right">
            <template #default="{ row }">
              <span :style="{ color: row.ir > 0.5 ? '#67c23a' : row.ir < -0.5 ? '#f56c6c' : '#909399' }">{{ row.ir.toFixed(3) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="ic_positive_pct" label="IC>0%" width="100" align="right">
            <template #default="{ row }">{{ (row.ic_positive_pct * 100).toFixed(0) }}%</template>
          </el-table-column>
        </el-table>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { getFactorData, listTracks, getWhitelist } from '@/api/track'
import * as echarts from 'echarts'

const loading = ref(true)
const tracks = ref<any[]>([])
const selectedTrack = ref('')
const selectedFactor = ref('')
const rawData = ref<{ columns: string[]; rows: number[][]; feature_cols: string[] }>({ columns: [], rows: [], feature_cols: [] })
const icChartRef = ref<HTMLElement>()
const corrChartRef = ref<HTMLElement>()
const quintileChartRef = ref<HTMLElement>()

const factorNames = computed(() => rawData.value.feature_cols || [])
const rows = computed(() => {
  const data = rawData.value
  if (!data.rows || !data.columns) return []
  const feats = data.feature_cols || []
  const dateIdx = data.columns.indexOf('date')
  const targetIdx = data.columns.indexOf('target')
  const stockIdx = data.columns.indexOf('stock_code')

  return data.rows.map((r: any[]) => {
    const row: Record<string, any> = {}
    data.columns.forEach((c, i) => { row[c] = r[i] })
    return row
  })
})

// ── IC 时序 ──
const icTimeSeries = computed(() => {
  const data = rows.value
  if (data.length < 10) return []

  const feats = factorNames.value
  const selected = selectedFactor.value
  const factors = selected ? [selected] : feats.slice(0, 5)

  // Group by date
  const dateMap: Record<string, { factors: number[][]; returns: number[] }> = {}
  for (const row of data) {
    const date = String(row.date).slice(0, 10)
    if (!dateMap[date]) dateMap[date] = { factors: [], returns: [] }
    const vals = factors.map(f => row[f] ?? 0)
    dateMap[date].factors.push(vals)
    dateMap[date].returns.push(row.target ?? 0)
  }

  // Compute cross-sectional IC per date
  const icByDate: { date: string; ic: number }[] = []
  for (const [date, group] of Object.entries(dateMap)) {
    const n = group.returns.length
    if (n < 5) continue
    let totalIc = 0
    for (let fi = 0; fi < factors.length; fi++) {
      const fv = group.factors.map(r => r[fi])
      const ret = group.returns
      const meanF = fv.reduce((a, b) => a + b, 0) / n
      const meanR = ret.reduce((a, b) => a + b, 0) / n
      let num = 0, denF = 0, denR = 0
      for (let i = 0; i < n; i++) {
        num += (fv[i] - meanF) * (ret[i] - meanR)
        denF += (fv[i] - meanF) ** 2
        denR += (ret[i] - meanR) ** 2
      }
      const corr = Math.sqrt(denF * denR) > 1e-10 ? num / Math.sqrt(denF * denR) : 0
      totalIc += corr
    }
    icByDate.push({ date, ic: totalIc / factors.length })
  }

  return icByDate.sort((a, b) => a.date.localeCompare(b.date))
})

// ── 因子IC统计 ──
const factorIcStats = computed(() => {
  const data = rows.value
  if (data.length < 10) return []

  const feats = factorNames.value.slice(0, 20)

  // Group by date
  const dateMap: Record<string, any[]> = {}
  for (const row of data) {
    const date = String(row.date).slice(0, 10)
    if (!dateMap[date]) dateMap[date] = []
    dateMap[date].push(row)
  }

  const dates = Object.keys(dateMap).sort()
  return feats.map(name => {
    const ics: number[] = []
    for (const date of dates) {
      const group = dateMap[date]
      if (group.length < 5) continue
      const fv = group.map(r => r[name] ?? 0)
      const ret = group.map(r => r.target ?? 0)
      const n = fv.length
      const mf = fv.reduce((a, b) => a + b, 0) / n
      const mr = ret.reduce((a, b) => a + b, 0) / n
      let num = 0, df = 0, dr = 0
      for (let i = 0; i < n; i++) {
        num += (fv[i] - mf) * (ret[i] - mr)
        df += (fv[i] - mf) ** 2
        dr += (ret[i] - mr) ** 2
      }
      const corr = Math.sqrt(df * dr) > 1e-10 ? num / Math.sqrt(df * dr) : 0
      ics.push(corr)
    }
    const mean = ics.reduce((a, b) => a + b, 0) / ics.length
    const std = Math.sqrt(ics.reduce((s, v) => s + (v - mean) ** 2, 0) / ics.length)
    const positive = ics.filter(v => v > 0).length / ics.length
    return {
      name,
      mean_ic: mean,
      std_ic: std,
      ir: std > 1e-10 ? mean / std : 0,
      ic_positive_pct: positive,
    }
  })
})

// ── 相关性矩阵（Top 20） ──
const corrMatrix = computed(() => {
  const data = rows.value
  if (data.length < 10) return { names: [], matrix: [] }
  const feats = factorNames.value.slice(0, 20)
  const n = feats.length
  const vals: number[][] = feats.map(f => data.map(r => r[f] ?? 0))
  const matrix: number[][] = []
  for (let i = 0; i < n; i++) {
    matrix[i] = []
    for (let j = 0; j < n; j++) {
      const vi = vals[i]!
      const vj = vals[j]!
      const m = vi.length
      const mi = vi.reduce((a, b) => a + b, 0) / m
      const mj = vj.reduce((a, b) => a + b, 0) / m
      let num = 0, di = 0, dj = 0
      for (let k = 0; k < m; k++) {
        num += (vi[k] - mi) * (vj[k] - mj)
        di += (vi[k] - mi) ** 2
        dj += (vj[k] - mj) ** 2
      }
      matrix[i][j] = Math.sqrt(di * dj) > 1e-10 ? num / Math.sqrt(di * dj) : 0
    }
  }
  return { names: feats, matrix }
})

// ── 分位数组合收益 ──
const quintileReturns = computed(() => {
  const data = rows.value
  if (data.length < 10) return []
  const feats = factorNames.value.slice(0, 5)
  const quintileLabels = ['Q1 (Low)', 'Q2', 'Q3', 'Q4', 'Q5 (High)']

  return feats.map(fname => {
    const sorted = [...data].sort((a, b) => (a[fname] ?? 0) - (b[fname] ?? 0))
    const perGroup = Math.floor(sorted.length / 5)
    const groups: number[][] = []
    for (let q = 0; q < 5; q++) {
      const start = q * perGroup
      const end = q === 4 ? sorted.length : start + perGroup
      const avgRet = sorted.slice(start, end).reduce((s, r) => s + (r.target ?? 0), 0) / (end - start)
      groups.push(Array.from({ length: 10 }, (_, i) => avgRet * (i + 1)))
    }
    return { name: fname, groups, labels: quintileLabels }
  })
})

function renderCharts() {
  nextTick(() => {
    // IC 时序
    if (icChartRef.value && icTimeSeries.value.length > 0) {
      const chart = echarts.init(icChartRef.value)
      chart.setOption({
        tooltip: { trigger: 'axis' },
        grid: { left: 50, right: 20, top: 30, bottom: 30 },
        xAxis: { type: 'category', data: icTimeSeries.value.map(d => d.date), axisLabel: { rotate: 45, fontSize: 10 } },
        yAxis: { type: 'value', axisLabel: { formatter: (v: number) => v.toFixed(3) } },
        series: [{
          type: 'line',
          data: icTimeSeries.value.map(d => d.ic),
          smooth: true,
          lineStyle: { color: '#3b82f6', width: 1.5 },
          areaStyle: { color: 'rgba(59,130,246,0.1)' },
          symbol: 'none',
        }],
      })
    }

    // 相关性热力图
    if (corrChartRef.value) {
      const { names, matrix } = corrMatrix.value
      if (names.length > 0) {
        const chart = echarts.init(corrChartRef.value)
        chart.setOption({
          tooltip: {
            formatter: (p: any) => `${names[p.data[0]]} × ${names[p.data[1]]}<br/>Corr: ${p.data[2].toFixed(4)}`,
          },
          grid: { left: 120, right: 30, top: 20, bottom: 80 },
          xAxis: { type: 'category', data: names, axisLabel: { rotate: 45, fontSize: 10 } },
          yAxis: { type: 'category', data: names, axisLabel: { fontSize: 10 } },
          visualMap: { min: -1, max: 1, inRange: { color: ['#f56c6c', '#fff', '#67c23a'] }, calculable: true, orient: 'horizontal', left: 'center', bottom: 10 },
          series: [{
            type: 'heatmap',
            data: matrix.flatMap((row, i) => row.map((v, j) => [i, j, +v.toFixed(4)])),
            label: { show: true, fontSize: 9, color: '#333', formatter: (p: any) => {
              const v = matrix[p.data[0]]?.[p.data[1]]
              return v != null ? v.toFixed(2) : '0'
            } },
            emphasis: { itemStyle: { shadowBlur: 10 } },
          }],
        })
      }
    }

    // 分位数收益
    if (quintileChartRef.value && quintileReturns.value.length > 0) {
      const chart = echarts.init(quintileChartRef.value)
      const first = quintileReturns.value[0]
      if (!first) return
      chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: first.labels, top: 0, textStyle: { fontSize: 11 } },
        grid: { left: 50, right: 20, top: 40, bottom: 30 },
        xAxis: { type: 'category', data: Array.from({ length: 10 }, (_, i) => `T+${i + 1}`) },
        yAxis: { type: 'value', axisLabel: { formatter: (v: number) => (v * 100).toFixed(1) + '%' } },
        series: first.labels.map((label: string, qi: number) => ({
          name: label,
          type: 'line',
          data: first.groups[qi],
          smooth: true,
          symbol: 'none',
        })),
      })
    }
  })
}

watch([icTimeSeries, corrMatrix, quintileReturns], renderCharts, { deep: true })

async function loadData() {
  loading.value = true
  try {
    const trackRes = await listTracks()
    tracks.value = (trackRes as any)?.items || []

    const factorData = await getFactorData({ track_name: selectedTrack.value || undefined, max_rows: 3000 })
    rawData.value = factorData as any
  } catch (e) {
    console.error('Alpha Research data load failed', e)
  }
  loading.value = false
  nextTick(renderCharts)
}

onMounted(loadData)
</script>

<style scoped>
.alpha-page {
  min-height: 100%;
  padding: 24px 32px;
  background: #f5f7fa;
}
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; font-size: 22px; color: #1e293b; }
.filter-row { display: flex; gap: 8px; align-items: center; margin-bottom: 16px; }
.filter-hint { font-size: 12px; color: #909399; margin-left: auto; }
.section-card { background: #fff; border-radius: 8px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom: 16px; }
.section-title { font-size: 14px; font-weight: 600; color: #303133; margin-bottom: 12px; }
.chart-box { width: 100%; height: 320px; }
.loading-state { padding: 40px; background: #fff; border-radius: 10px; }
</style>
