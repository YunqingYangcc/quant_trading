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

    <!-- 主 K 线图区域 -->
    <div class="kline-main">
      <div class="kline-header">
        <span class="kline-title">{{ selectedStockName || '选择一只股票' }}</span>
        <el-button size="small" @click="refreshData" :loading="loading" text>
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>
      <div ref="klineRef" class="kline-chart"></div>
    </div>

    <!-- 底部预留区（后续 Phase 填充：因子/回测等） -->
    <div class="bottom-reserved">
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import * as echarts from 'echarts/core'
import { CandlestickChart, LineChart, BarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import {
  listTracks,
  getLabels,
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

async function refreshData() {
  loading.value = true
  try {
    const trackRes = await listTracks()
    tracks.value = trackRes.items || []

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
  const prices = data.map(d => [d.open_px, d.close_px, d.low_px, d.high_px])
  const volumes = data.map(d => d.volume)
  const ma5 = calcMA(prices.map(p => p[1]), 5)
  const ma20 = calcMA(prices.map(p => p[1]), 20)

  const option = {
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['K线', 'MA5', 'MA20'], top: 0 },
    grid: [
      { left: 60, right: 20, top: 36, bottom: '32%' },
      { left: 60, right: 20, top: '73%', bottom: 36 },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, axisLabel: { rotate: 45, fontSize: 11 } },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } },
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, scale: true, splitLine: { lineStyle: { type: 'dashed' } } },
      { type: 'value', gridIndex: 1, scale: true, splitLine: { show: false } },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 70, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], start: 70, end: 100, bottom: 6, height: 18, borderColor: 'transparent', backgroundColor: '#f5f7fa', fillerColor: 'rgba(59,130,246,0.08)', handleStyle: { color: '#3b82f6' } },
    ],
    series: [
      {
        name: 'K线', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0,
        data: prices,
        itemStyle: { color: '#f56c6c', color0: '#67c23a', borderColor: '#f56c6c', borderColor0: '#67c23a' },
      },
      {
        name: 'MA5', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
        data: ma5, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#e6a23c' },
      },
      {
        name: 'MA20', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
        data: ma20, smooth: true, symbol: 'none', lineStyle: { width: 1, color: '#409eff' },
      },
      {
        name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
        data: volumes,
        itemStyle: { color: '#c0c4cc' },
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

onMounted(() => {
  refreshData()
  window.addEventListener('resize', () => klineChart?.resize())
})
</script>

<style scoped>
.track-dashboard {
  height: calc(100vh - 52px);
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
.kline-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin: 0;
  background: #fff;
  overflow: hidden;
  min-height: 0;
}

.kline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  border-bottom: 1px solid #f0f2f5;
  flex-shrink: 0;
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

/* 底部预留 */
.bottom-reserved {
  flex-shrink: 0;
}
</style>
