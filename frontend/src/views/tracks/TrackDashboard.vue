<template>
  <div class="track-dashboard">
    <!-- 赛道 Tab -->
    <div class="track-tabs-bar">
      <div
        v-for="track in tracks"
        :key="track.id"
        class="track-tab"
        :class="{ active: activeTrack === track.name }"
        @click="onTrackChange(track.name)"
      >
        <span class="tab-name">{{ track.display_name }}</span>
        <el-tag size="small" type="info" round>{{ track.stock_count }}</el-tag>
      </div>
    </div>

    <!-- 股票选择横栏 -->
    <div class="stock-selector-bar">
      <div class="stock-search">
        <el-input
          v-model="searchQuery"
          placeholder="搜索股票"
          size="small"
          clearable
          :prefix-icon="Search"
        />
      </div>
      <div class="stock-chips">
        <div
          v-for="s in filteredStocks"
          :key="s.code"
          class="stock-chip"
          :class="{ active: selectedStock === s.code }"
          @click="selectStock(s.code)"
        >
          <span class="chip-name">{{ s.name }}</span>
          <span class="chip-code">{{ s.code }}</span>
        </div>
        <div v-if="!filteredStocks.length" class="stock-empty">
          {{ stocks.length ? '无匹配' : '暂无股票' }}
        </div>
      </div>
    </div>

    <!-- 主体三栏布局 -->
    <div class="main-body">
      <!-- 左侧 AI 排名面板 -->
      <div class="left-panel" v-if="activeTrack">
        <div class="left-panel-top">
          <RankPanel :selectedCode="selectedStock" :trackName="activeTrack" @select="selectStock" />
        </div>
      </div>

      <!-- 中间 K 线图区域 -->
      <div class="kline-main">
        <div class="kline-header">
          <div class="kline-header-left">
            <el-button size="small" text @click="goHome" class="back-btn">
              <el-icon><ArrowLeft /></el-icon> 返回
            </el-button>
            <span class="kline-title">{{ selectedStockName || '选择一只股票' }}</span>
          </div>
          <div class="kline-header-actions">
            <el-button size="small" @click="showFactors = !showFactors" text>
              <el-icon><DataAnalysis /></el-icon>
              因子列表 <el-tag size="small" type="success" round>{{ whitelist.length }}</el-tag>
            </el-button>
            <el-button size="small" @click="refreshData" :loading="loading" text>
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
          </div>
        </div>
        <div ref="klineRef" class="kline-chart"></div>
      </div>

      <!-- 右侧有效因子曲线面板 -->
      <div class="right-panel">
        <FactorChartPanel :factors="whitelist" />
      </div>
    </div>

    <!-- 因子面板 (Drawer) -->
    <el-drawer
      v-model="showFactors"
      title="因子筛选结果"
      direction="rtl"
      size="380px"
      :append-to-body="true"
    >
      <template #header>
        <div class="drawer-header">
          <span>因子筛选结果</span>
          <el-tag size="small">Phase C</el-tag>
        </div>
      </template>

      <el-tabs v-model="factorTab">
        <el-tab-pane name="whitelist">
          <template #label>
            白名单 <el-tag size="small" type="success" round>{{ whitelist.length }}</el-tag>
          </template>
          <div class="factor-list">
            <div v-for="group in groupedWhitelist" :key="group.category" class="factor-group">
              <div class="group-title">{{ group.label }} ({{ group.items.length }})</div>
              <div v-for="f in group.items" :key="f.factor_name" class="factor-row">
                <span class="factor-name">{{ f.factor_name }}</span>
                <div class="factor-metrics">
                  <el-tag size="small" :type="f.ic_mean >= 0 ? 'success' : 'danger'">
                    IC {{ f.ic_mean >= 0 ? '+' : '' }}{{ f.ic_mean.toFixed(4) }}
                  </el-tag>
                  <span class="factor-ir">IR {{ f.ir.toFixed(2) }}</span>
                </div>
              </div>
            </div>
            <el-empty v-if="!whitelist.length" description="暂无白名单因子" />
          </div>
        </el-tab-pane>

        <el-tab-pane name="blacklist">
          <template #label>
            黑名单 <el-tag size="small" type="danger" round>{{ blacklist.length }}</el-tag>
          </template>
          <div class="factor-list">
            <div v-for="f in blacklist" :key="f.factor_name" class="factor-row blacklist-row">
              <span class="factor-name">{{ f.factor_name }}</span>
              <el-tag size="small" type="info">{{ f.reason }}</el-tag>
            </div>
            <el-empty v-if="!blacklist.length" description="暂无黑名单因子" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-drawer>

    <!-- ⚙ 流水线控制（可折叠） -->
    <div class="pipeline-section" :class="{ 'ps-expanded': showPipeline }">
      <div class="ps-toggle" @click="showPipeline = !showPipeline">
        <span class="ps-toggle-arrow">{{ showPipeline ? '▼' : '▶' }}</span>
        <span class="ps-toggle-icon">⚙</span>
        <div class="ps-toggle-texts">
          <span class="ps-toggle-title">Pipeline Runner</span>
          <span class="ps-toggle-subtitle">量化流水线控制台</span>
        </div>
        <el-tag v-if="isRunning" size="small" type="warning" effect="dark" class="ps-toggle-badge">运行中</el-tag>
      </div>

      <div v-show="showPipeline" class="ps-body">
        <!-- 步骤控制 -->
        <div class="ps-actions">
          <el-button v-if="isRunning" type="danger" size="small" @click="handleCancel" :loading="cancelling">⏹ 取消</el-button>
          <el-button v-else type="primary" size="small" @click="handleRun('all')" :loading="runLoading === 'all'">▶ 一键跑全部</el-button>
        </div>
        <div class="ps-steps">
          <div v-for="key in allSteps" :key="key" class="ps-step" :class="stepCls(key)">
            <div class="pss-indicator">
              <span v-if="stepStatus(key) === 'done'" class="pss-dot done">✓</span>
              <span v-else-if="stepStatus(key) === 'running'" class="pss-dot running">⟳</span>
              <span v-else-if="stepStatus(key) === 'failed'" class="pss-dot failed">✕</span>
              <span v-else class="pss-dot idle">○</span>
            </div>
            <div class="pss-info">
              <div class="pss-name">{{ getStepName(key) }}</div>
              <div class="pss-desc">{{ getStepDesc(key) }}</div>
            </div>
            <div class="pss-action">
              <el-button v-if="stepStatus(key) !== 'running'" size="small" text :disabled="isRunning" @click="handleRun(key)" :loading="runLoading === key">运行</el-button>
              <el-tag v-else size="small" type="warning" effect="dark">运行中...</el-tag>
            </div>
          </div>
        </div>

        <!-- Terminal -->
        <div class="ps-terminal" ref="terminalRef">
          <div class="pst-header">
            <span class="pst-title">▶ Terminal</span>
            <span v-if="isRunning" class="pst-badge running">RUNNING</span>
            <button class="pst-clear" @click="clearLogs">clear</button>
          </div>
          <div class="pst-body">
            <div v-if="terminalLines.length === 0" class="pst-empty">
              <span class="pst-prompt">$ _</span>
              <span class="pst-hint">点击步骤运行开始</span>
            </div>
            <div v-for="(line, i) in terminalLines" :key="i" class="pst-line" :class="lineClass(line)">{{ line }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Search, DataAnalysis, ArrowLeft } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()

function goHome() {
  router.push('/')
}
import * as echarts from 'echarts/core'
import { CandlestickChart, LineChart, BarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import RankPanel from '@/components/tracks/RankPanel.vue'
import FactorChartPanel from '@/components/tracks/FactorChartPanel.vue'
import { usePipelineRunner } from '@/composables/usePipelineRunner'
import {
  listTracks,
  getLabels,
  getWhitelist,
  getBlacklist,
  type Track,
  type TrackStock,
} from '@/api/track'

echarts.use([
  CandlestickChart,
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  CanvasRenderer,
])

const loading = ref(false)
const activeTrack = ref('')
const tracks = ref<Track[]>([])
const stocks = ref<TrackStock[]>([])
const selectedStock = ref('')
const searchQuery = ref('')
const labels = ref<any[]>([])
const showFactors = ref(false)
const factorTab = ref('whitelist')
const whitelist = ref<any[]>([])
const blacklist = ref<any[]>([])

const categoryLabels: Record<string, string> = {
  momentum: '动量类',
  trend: '趋势类',
  volatility: '波动率类',
  volume: '量能类',
  statistical: '统计类',
  track_specific: '赛道专属',
}

const groupedWhitelist = computed(() => {
  const groups: Record<string, any[]> = {}
  for (const f of whitelist.value) {
    const cat = f.category || f.factor_type || 'other'
    if (!groups[cat]) groups[cat] = []
    groups[cat].push(f)
  }
  return Object.entries(groups)
    .sort(([a], [b]) => {
      const order = ['track_specific', 'momentum', 'trend', 'volatility', 'volume', 'statistical']
      return order.indexOf(a) - order.indexOf(b)
    })
    .map(([cat, items]) => ({
      category: cat,
      label: categoryLabels[cat] || cat,
      items: items.sort((a: any, b: any) => Math.abs(b.ic_mean) - Math.abs(a.ic_mean)),
    }))
})

const filteredStocks = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return stocks.value
  return stocks.value.filter(
    s => s.name.toLowerCase().includes(q) || s.code.toLowerCase().includes(q)
  )
})
const klineRef = ref<HTMLElement | null>(null)
let klineChart: echarts.ECharts | null = null

const selectedStockName = computed(() => {
  const s = stocks.value.find(x => x.code === selectedStock.value)
  return s ? `${s.name} (${s.code})` : ''
})

// ── Pipeline Runner ──
const showPipeline = ref(false)
const {
  state,
  startPipeline,
  cancelPipeline,
  getStepName,
  getStepDesc,
  getAllSteps,
} = usePipelineRunner()

const allSteps = getAllSteps()
const runLoading = ref<string | null>(null)
const cancelling = ref(false)
const terminalRef = ref<HTMLElement>()

const isRunning = computed(() => state.currentTask?.status === 'running')
const terminalLines = computed(() => state.currentTask?.logs || [])

function stepStatus(key: string): string {
  if (!state.currentTask) return 'idle'
  if (state.currentTask.steps[key]?.status === 'failed') return 'failed'
  if (state.currentTask.step === key && state.currentTask.status === 'running') return 'running'
  if (state.currentTask.steps[key]?.status === 'success' || state.currentTask.steps[key]?.status) return 'done'
  return 'idle'
}

function stepCls(key: string) {
  const s = stepStatus(key)
  return `pss-${s}`
}

async function handleRun(step: string) {
  runLoading.value = step
  await startPipeline(step, activeTrack.value)
  runLoading.value = null
}

async function handleCancel() {
  cancelling.value = true
  await cancelPipeline()
  cancelling.value = false
}

function clearLogs() {
  if (state.currentTask) {
    state.currentTask.logs = []
  }
}

function lineClass(line: string): string {
  if (line.includes('❌') || line.includes('失败') || line.includes('异常')) return 'pst-error'
  if (line.includes('✅')) return 'pst-success'
  if (line.includes('⚠️') || line.includes('取消')) return 'pst-warn'
  if (line.includes('🎉')) return 'pst-done'
  if (line.includes('▶')) return 'pst-cmd'
  return ''
}

// 自动滚动
watch(terminalLines, async () => {
  await nextTick()
  const body = terminalRef.value?.querySelector('.pst-body')
  if (body) body.scrollTop = body.scrollHeight
})

async function refreshData() {
  loading.value = true
  try {
    const [trackRes, wlRes, blRes] = await Promise.all([listTracks(), getWhitelist(), getBlacklist()])
    tracks.value = trackRes.items || []
    whitelist.value = Array.isArray(wlRes) ? wlRes : []
    blacklist.value = Array.isArray(blRes) ? blRes : []

    if (tracks.value.length && !activeTrack.value) {
      activeTrack.value = tracks.value[0].name
      await onTrackChange(activeTrack.value)
    }
  } catch (e: any) {
    ElMessage.error('数据加载失败: ' + (e.message || ''))
  } finally {
    loading.value = false
  }
}

async function onTrackChange(trackName: string) {
  activeTrack.value = trackName
  const track = tracks.value.find(t => t.name === trackName)
  if (!track) return

  stocks.value = track.stocks || []
  searchQuery.value = ''

  if (stocks.value.length) {
    selectedStock.value = stocks.value[0].code
    await loadKline(selectedStock.value)
  } else {
    selectedStock.value = ''
  }
}

async function selectStock(code: string) {
  selectedStock.value = code
  await loadKline(code)
}

async function loadKline(code: string) {
  try {
    const res = await getLabels(code)
    labels.value = res?.data_points || []
    renderKline()
  } catch {
    labels.value = []
  }
}

function renderKline() {
  if (!klineRef.value) return

  if (!klineChart) {
    klineChart = echarts.init(klineRef.value)
  }

  const data = labels.value
  if (!data.length) {
    klineChart.clear()
    return
  }

  const dates = data.map(d => d.trade_date)

  // ── 价格数据 ──
  const open_vals = data.map(d => d.open_px)
  const close_vals = data.map(d => d.close_px)
  const low_vals = data.map(d => d.low_px)
  const high_vals = data.map(d => d.high_px)
  const prices = data.map((d, i) => [open_vals[i], close_vals[i], low_vals[i], high_vals[i]])
  const volumes = data.map(d => d.volume)

  // ── 均线 ──
  const ma5 = calcMA(close_vals, 5)
  const ma20 = calcMA(close_vals, 20)
  const ma60 = calcMA(close_vals, 60)

  // ── 布林带 ──
  const bb20 = calcBollinger(close_vals, 20)
  const bb_upper = bb20.map(v => v?.upper ?? null)
  const bb_mid = bb20.map(v => v?.mid ?? null)
  const bb_lower = bb20.map(v => v?.lower ?? null)

  // ── RSI ──
  const rsi14 = calcRSI(close_vals, 14)

  // ── ATR ──
  const atr14 = calcATR(high_vals, low_vals, close_vals, 14)

  // ── 赛道景气模拟（用 RSI 替代，等 Phase F 接入真实数据） ──
  const mockProsperity = rsi14.map(v => v != null ? +(v * 0.8 + 20).toFixed(1) : null)

  // ── 趋势线（线性回归） ──
  const trendLine = calcLinearReg(close_vals, 60)

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: {
      data: ['K线', 'MA5', 'MA20', 'MA60', '布林上轨', '布林下轨', '趋势线', 'RSI', 'ATR', '赛道景气'],
      top: 0,
      selected: {
        'MA5': true, 'MA20': true, 'MA60': true,
        '布林上轨': true, '布林下轨': true,
        '趋势线': true,
        'RSI': true, 'ATR': true,
        '赛道景气': true,
      },
    },
    grid: [
      // 0: K线主图（占30%高度）
      { left: 50, right: 16, top: '4%', height: '30%' },
      // 1: 成交量（占10%，留2%间距）
      { left: 50, right: 16, top: '36%', height: '10%' },
      // 2: RSI（占16%）
      { left: 50, right: 16, top: '48%', height: '16%' },
      // 3: ATR（占16%）
      { left: 50, right: 16, top: '66%', height: '16%' },
      // 4: 赛道景气（占16% + 底部留白）
      { left: 50, right: 16, top: '84%', height: '16%' },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 2, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 3, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 4, axisLabel: { rotate: 45, fontSize: 10 } },
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, scale: true, splitLine: { lineStyle: { type: 'dashed' } } },
      { type: 'value', gridIndex: 1, scale: true, splitLine: { show: false } },
      { type: 'value', gridIndex: 2, scale: true, splitLine: { show: false }, min: 0, max: 100 },
      { type: 'value', gridIndex: 3, scale: true, splitLine: { show: false } },
      { type: 'value', gridIndex: 4, scale: true, splitLine: { show: false }, min: 0, max: 100 },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1, 2, 3, 4], start: 70, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1, 2, 3, 4], start: 70, end: 100, bottom: 4, height: 14, borderColor: 'transparent', backgroundColor: '#f5f7fa', fillerColor: 'rgba(59,130,246,0.08)', handleStyle: { color: '#3b82f6' } },
    ],
    series: [
      // ── K线 ──
      {
        name: 'K线', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0,
        data: prices,
        itemStyle: { color: '#f56c6c', color0: '#67c23a', borderColor: '#f56c6c', borderColor0: '#67c23a' },
      },
      // ── 均线 ──
      {
        name: 'MA5', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
        data: ma5, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#e6a23c' },
      },
      {
        name: 'MA20', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
        data: ma20, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#409eff' },
      },
      {
        name: 'MA60', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
        data: ma60, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#909399', type: 'dashed' },
      },
      // ── 趋势线 ──
      {
        name: '趋势线', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
        data: trendLine, smooth: true, symbol: 'none', lineStyle: { width: 2, color: '#409eff', type: 'solid' },
      },
      // ── 布林带 ──
      {
        name: '布林上轨', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
        data: bb_upper, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#b37feb', type: 'dashed' },
      },
      {
        name: '布林下轨', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
        data: bb_lower, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#b37feb', type: 'dashed' },
        areaStyle: { color: 'rgba(179,127,235,0.05)' },
      },
      // ── 成交量 ──
      {
        name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
        data: volumes,
        itemStyle: { color: '#c0c4cc' },
      },
      // ── RSI ──
      {
        name: 'RSI', type: 'line', xAxisIndex: 2, yAxisIndex: 2,
        data: rsi14, smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: '#f56c6c' },
        markLine: {
          silent: true,
          data: [
            { yAxis: 70, label: { formatter: '70 超买', color: '#909399', fontSize: 10 }, lineStyle: { color: '#dcdfe6', type: 'dashed' } },
            { yAxis: 30, label: { formatter: '30 超卖', color: '#909399', fontSize: 10 }, lineStyle: { color: '#dcdfe6', type: 'dashed' } },
          ],
        },
      },
      // ── ATR ──
      {
        name: 'ATR', type: 'line', xAxisIndex: 3, yAxisIndex: 3,
        data: atr14, smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: '#409eff' },
      },
      // ── 赛道景气 ──
      {
        name: '赛道景气', type: 'line', xAxisIndex: 4, yAxisIndex: 4,
        data: mockProsperity, smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: '#67c23a' },
        markLine: {
          silent: true,
          data: [
            { yAxis: 60, label: { formatter: '60 景气', color: '#909399', fontSize: 10 }, lineStyle: { color: '#dcdfe6', type: 'dashed' } },
            { yAxis: 40, label: { formatter: '40 不景气', color: '#909399', fontSize: 10 }, lineStyle: { color: '#dcdfe6', type: 'dashed' } },
          ],
        },
      },
    ],
  }
  klineChart.setOption(option, true)
  klineChart.resize()
}

function calcMA(data: number[], period: number): (number | null)[] {
  const result: (number | null)[] = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) { result.push(null); continue }
    let sum = 0
    for (let j = i - period + 1; j <= i; j++) sum += data[j]
    result.push(+(sum / period).toFixed(2))
  }
  return result
}

function calcBollinger(data: number[], period: number): ({ upper: number; mid: number; lower: number } | null)[] {
  const result: ({ upper: number; mid: number; lower: number } | null)[] = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) { result.push(null); continue }
    const slice = data.slice(i - period + 1, i + 1)
    const ma = slice.reduce((a, b) => a + b, 0) / period
    const std = Math.sqrt(slice.reduce((sq, v) => sq + (v - ma) ** 2, 0) / period)
    result.push({
      upper: +(ma + 2 * std).toFixed(2),
      mid: +ma.toFixed(2),
      lower: +(ma - 2 * std).toFixed(2),
    })
  }
  return result
}

function calcRSI(data: number[], period: number): (number | null)[] {
  const result: (number | null)[] = [null]
  let avgGain = 0
  let avgLoss = 0
  for (let i = 1; i < data.length; i++) {
    const diff = data[i] - data[i - 1]
    const gain = diff > 0 ? diff : 0
    const loss = diff < 0 ? -diff : 0
    if (i < period) {
      avgGain += gain
      avgLoss += loss
      if (i === period - 1) {
        avgGain /= period
        avgLoss /= period
        const rs = avgGain / (avgLoss + 1e-10)
        result.push(+(100 - 100 / (1 + rs)).toFixed(1))
      } else {
        result.push(null)
      }
    } else {
      avgGain = (avgGain * (period - 1) + gain) / period
      avgLoss = (avgLoss * (period - 1) + loss) / period
      const rs = avgGain / (avgLoss + 1e-10)
      result.push(+(100 - 100 / (1 + rs)).toFixed(1))
    }
  }
  return result
}

function calcATR(high: number[], low: number[], close: number[], period: number): (number | null)[] {
  const tr: number[] = [0]
  for (let i = 1; i < high.length; i++) {
    const hl = high[i] - low[i]
    const hc = Math.abs(high[i] - close[i - 1])
    const lc = Math.abs(low[i] - close[i - 1])
    tr.push(Math.max(hl, hc, lc))
  }
  return calcMA(tr, period)
}

function calcLinearReg(data: number[], period: number): (number | null)[] {
  /* 滚动线性回归趋势线 */
  const result: (number | null)[] = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) { result.push(null); continue }
    const slice = data.slice(i - period + 1, i + 1)
    const n = slice.length
    const xSum = (n * (n - 1)) / 2
    const x2Sum = ((n - 1) * n * (2 * n - 1)) / 6
    const ySum = slice.reduce((a, b) => a + b, 0)
    const xySum = slice.reduce((sum, y, j) => sum + j * y, 0)
    const slope = (n * xySum - xSum * ySum) / (n * x2Sum - xSum * xSum)
    const intercept = (ySum - slope * xSum) / n
    result.push(+(slope * (n - 1) + intercept).toFixed(2))
  }
  return result
}

onMounted(() => {
  refreshData()
  window.addEventListener('resize', () => klineChart?.resize())
})

// 监听路由参数变化（从首页点击赛道进入）
watch(() => route.params.name, (name) => {
  if (name && tracks.value.length) {
    const match = tracks.value.find(t => t.name === name)
    if (match && match.name !== activeTrack.value) {
      onTrackChange(name as string)
    }
  }
})
</script>

<style scoped>
.track-dashboard {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
}

/* 赛道 Tab 栏 */
.track-tabs-bar {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 6px 12px;
  background: #fafbfc;
  border-bottom: 1px solid #ebedf0;
  flex-shrink: 0;
}

.track-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
  color: #606266;
}

.track-tab:hover {
  background: #f0f2f5;
}

.track-tab.active {
  background: #ecf5ff;
  color: #409eff;
  font-weight: 600;
}

.tab-name {
  white-space: nowrap;
}

/* 股票选择横栏 */
.stock-selector-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 12px;
  background: #fff;
  border-bottom: 1px solid #ebedf0;
  flex-shrink: 0;
}

.stock-search {
  flex-shrink: 0;
  width: 160px;
}

.stock-search :deep(.el-input__wrapper) {
  border-radius: 6px;
}

.stock-chips {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow-x: auto;
  flex: 1;
}

.stock-chips::-webkit-scrollbar {
  height: 3px;
}

.stock-chips::-webkit-scrollbar-thumb {
  background: #dcdfe6;
  border-radius: 2px;
}

.stock-chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 4px 14px;
  border-radius: 6px;
  border: 1px solid #e4e7ed;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
  min-width: 80px;
}

.stock-chip:hover {
  border-color: #409eff;
  background: #f5f7fa;
}

.stock-chip.active {
  border-color: #409eff;
  background: #ecf5ff;
}

.chip-name {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
  white-space: nowrap;
}

.chip-code {
  font-size: 11px;
  color: #909399;
  margin-top: 1px;
}

.stock-chip.active .chip-name {
  color: #409eff;
}

.stock-empty {
  color: #c0c4cc;
  font-size: 13px;
  padding: 8px;
}

/* K 线主区域 */
.main-body {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

.left-panel {
  width: 220px;
  flex-shrink: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.left-panel-top {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.kline-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin: 0;
  background: #fff;
  overflow: hidden;
  min-width: 0;
}

.right-panel {
  flex-shrink: 0;
  overflow: hidden;
}

.kline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  border-bottom: 1px solid #f0f2f5;
  flex-shrink: 0;
}

.kline-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.kline-header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.kline-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.kline-chart {
  flex: 1;
  min-height: 0;
  padding: 0 8px 8px;
}

/* 因子面板 */
.drawer-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
}

.factor-list {
  padding: 0 4px;
}

.factor-group {
  margin-bottom: 16px;
}

.group-title {
  font-size: 12px;
  font-weight: 600;
  color: #909399;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid #f0f2f5;
}

.factor-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 5px 8px;
  border-radius: 4px;
  transition: background 0.15s;
}

.factor-row:hover {
  background: #f5f7fa;
}

.factor-row .factor-name {
  font-size: 13px;
  color: #303133;
  font-family: 'SF Mono', 'Menlo', monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 160px;
}

.factor-metrics {
  display: flex;
  align-items: center;
  gap: 6px;
}

.factor-ir {
  font-size: 11px;
  color: #909399;
  white-space: nowrap;
}

.blacklist-row .factor-name {
  color: #909399;
  text-decoration: line-through;
}

/* ═══════════ Pipeline Runner 嵌入式（可折叠） ═══════════ */
.pipeline-section {
  border-top: 1px solid #ebedf0;
  background: #fff;
  flex-shrink: 0;
}

.pipeline-section.ps-expanded {
  box-shadow: 0 -2px 12px rgba(0,0,0,0.04);
}

.ps-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}

.ps-toggle:hover {
  background: #f8fafc;
}

.ps-toggle-arrow {
  font-size: 10px;
  color: #94a3b8;
  width: 14px;
}

.ps-toggle-icon {
  font-size: 16px;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  border-radius: 6px;
  color: white;
  flex-shrink: 0;
}

.ps-toggle-texts {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.ps-toggle-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.ps-toggle-subtitle {
  font-size: 10px;
  color: #94a3b8;
}

.ps-toggle-badge {
  margin-left: auto;
}

.ps-body {
  padding: 0 16px 14px;
}

.ps-actions {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 10px;
}

.ps-steps {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.ps-step {
  flex: 1;
  min-width: 130px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fafbfc;
  transition: all 0.2s;
}

.ps-step.pss-running {
  border-color: #93c5fd;
  background: #eff6ff;
}

.ps-step.pss-done {
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.ps-step.pss-failed {
  border-color: #fecaca;
  background: #fef2f2;
}

.pss-indicator {
  flex-shrink: 0;
}

.pss-dot {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 10px;
  font-weight: 700;
}

.pss-dot.done {
  background: #dcfce7;
  color: #16a34a;
}

.pss-dot.running {
  background: #dbeafe;
  color: #2563eb;
  animation: pss-spin 1.5s linear infinite;
}

.pss-dot.failed {
  background: #fee2e2;
  color: #dc2626;
}

.pss-dot.idle {
  background: #f1f5f9;
  color: #94a3b8;
}

@keyframes pss-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.pss-info {
  flex: 1;
  min-width: 0;
}

.pss-name {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.pss-desc {
  font-size: 10px;
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── Terminal ── */
.ps-terminal {
  background: #0d1117;
  border-radius: 8px;
  overflow: hidden;
  max-height: 240px;
  display: flex;
  flex-direction: column;
}

.pst-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: #161b22;
  border-bottom: 1px solid #30363d;
  flex-shrink: 0;
}

.pst-title {
  font-size: 11px;
  font-weight: 600;
  color: #58a6ff;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.pst-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
  font-family: 'SF Mono', monospace;
  background: #1a3a5c;
  color: #58a6ff;
}

.pst-clear {
  margin-left: auto;
  background: none;
  border: none;
  color: #484f58;
  font-size: 10px;
  cursor: pointer;
  font-family: 'SF Mono', monospace;
}

.pst-clear:hover { color: #8b949e; }

.pst-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
  font-family: 'SF Mono', 'Fira Code', 'Courier New', monospace;
  font-size: 11px;
  line-height: 1.6;
  max-height: 180px;
}

.pst-body::-webkit-scrollbar { width: 4px; }
.pst-body::-webkit-scrollbar-thumb { background: #30363d; border-radius: 2px; }

.pst-empty {
  color: #8b949e;
}

.pst-prompt {
  color: #3fb950;
  margin-right: 8px;
}

.pst-hint {
  color: #484f58;
  font-size: 11px;
}

.pst-line {
  white-space: pre-wrap;
  word-break: break-all;
  color: #c9d1d9;
  font-size: 11px;
}

.pst-line.pst-cmd { color: #58a6ff; }
.pst-line.pst-success { color: #3fb950; }
.pst-line.pst-error { color: #f78166; }
.pst-line.pst-warn { color: #d29922; }
.pst-line.pst-done { color: #7ee787; font-weight: 600; }
</style>
