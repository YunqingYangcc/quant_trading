<template>
  <div class="track-dashboard">
    <div class="page-header">
      <h2>赛道量化终端</h2>
      <el-button type="primary" size="small" @click="refreshData" :loading="loading">
        刷新数据
      </el-button>
    </div>

    <!-- 赛道 Tab -->
    <el-tabs v-model="activeTrack" @tab-change="onTrackChange">
      <el-tab-pane
        v-for="track in tracks"
        :key="track.id"
        :label="`${track.display_name} (${track.stock_count})`"
        :name="track.name"
      >
        <template #label>
          <span class="track-tab-label">
            {{ track.display_name }}
            <el-tag size="small" type="info">{{ track.stock_count }}</el-tag>
          </span>
        </template>
      </el-tab-pane>
    </el-tabs>

    <el-row :gutter="16" class="dashboard-content">
      <!-- 左侧：个股排名 -->
      <el-col :span="8">
        <el-card shadow="never" class="stock-rank-card">
          <template #header>
            <span>个股 AI 强弱排名</span>
          </template>
          <div v-if="scoreResult?.scores?.length">
            <div
              v-for="(s, i) in scoreResult.scores"
              :key="s.stock_code"
              class="stock-rank-item"
              :class="{ active: selectedStock === s.stock_code }"
              @click="selectStock(s.stock_code)"
            >
              <span class="rank-num">#{{ s.rank }}</span>
              <span class="stock-name">{{ getStockName(s.stock_code) || s.stock_code }}</span>
              <el-tag
                :type="s.score > 0 ? 'success' : 'danger'"
                size="small"
              >
                {{ s.score.toFixed(3) }}
              </el-tag>
            </div>
          </div>
          <el-empty v-else description="暂无评分数据" />
        </el-card>
      </el-col>

      <!-- 中间：K 线 + 特征 -->
      <el-col :span="10">
        <el-card shadow="never" class="kline-card">
          <template #header>
            <span>{{ selectedStockName || '选择一只股票' }}</span>
          </template>
          <div ref="klineRef" class="kline-container"></div>
          <el-empty v-if="!selectedStock" description="请在左侧选择股票" />
        </el-card>
      </el-col>

      <!-- 右侧：赛道景气 + 因子 -->
      <el-col :span="6">
        <el-card shadow="never" class="sentiment-card">
          <template #header>
            <span>赛道景气度</span>
          </template>
          <div class="sentiment-gauge">
            <div class="gauge-value" :style="{ color: sentimentColor }">
              {{ scoreResult?.track_sentiment ?? '--' }}
            </div>
            <div class="gauge-label">分</div>
            <el-progress
              :percentage="scoreResult?.track_sentiment ?? 0"
              :color="sentimentColor"
              :stroke-width="12"
            />
          </div>
        </el-card>

        <el-card shadow="never" class="factors-card" style="margin-top: 16px">
          <template #header>
            <span>有效因子 ({{ whitelist.length }})</span>
          </template>
          <div v-for="f in whitelist.slice(0, 15)" :key="f.factor_name" class="factor-item">
            <el-tooltip :content="`IC: ${f.ic_mean} | IR: ${f.ir}`" placement="left">
              <span class="factor-name">{{ f.factor_name }}</span>
            </el-tooltip>
            <el-tag size="small" type="success">{{ f.category || f.factor_type }}</el-tag>
          </div>
          <el-empty v-if="!whitelist.length" description="暂无因子" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import {
  listTracks,
  listStocks,
  getTrackScore,
  getWhitelist,
  getLabels,
  type Track,
  type TrackStock,
} from '@/api/track'

const loading = ref(false)
const activeTrack = ref('')
const tracks = ref<Track[]>([])
const stocks = ref<TrackStock[]>([])
const selectedStock = ref('')
const scoreResult = ref<any>(null)
const whitelist = ref<any[]>([])
const labels = ref<any[]>([])
const klineRef = ref<HTMLElement | null>(null)
let klineChart: echarts.ECharts | null = null

const selectedStockName = computed(() => {
  const s = stocks.value.find(x => x.code === selectedStock.value)
  return s ? `${s.name} (${s.code})` : selectedStock.value
})

const sentimentColor = computed(() => {
  const v = scoreResult.value?.track_sentiment ?? 0
  if (v >= 70) return '#67c23a'
  if (v >= 40) return '#e6a23c'
  return '#f56c6c'
})

function getStockName(code: string): string | undefined {
  return stocks.value.find(s => s.code === code)?.name
}

async function refreshData() {
  loading.value = true
  try {
    const [trackRes, wlRes] = await Promise.all([listTracks(), getWhitelist()])
    tracks.value = trackRes.items || []
    whitelist.value = Array.isArray(wlRes) ? wlRes : []

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
  const track = tracks.value.find(t => t.name === trackName)
  if (!track) return

  try {
    // 获取该赛道股票
    const stockRes = await listTracks()
    stocks.value = track.stocks || []

    // 获取 AI 评分
    try {
      const scoreRes = await getTrackScore(trackName)
      scoreResult.value = scoreRes
    } catch {
      scoreResult.value = null
    }

    // 默认选中第一只
    if (stocks.value.length) {
      selectedStock.value = stocks.value[0].code
      await loadKline(selectedStock.value)
    }
  } catch (e: any) {
    ElMessage.error('赛道加载失败')
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
      { left: '10%', right: '10%', top: 60, height: '55%' },
      { left: '10%', right: '10%', top: '78%', height: '15%' },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, axisLabel: { rotate: 45 } },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } },
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, scale: true },
      { type: 'value', gridIndex: 1, scale: true },
    ],
    dataZoom: [{ type: 'inside', xAxisIndex: [0, 1], start: 50, end: 100 }],
    series: [
      {
        name: 'K线', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0,
        data: prices,
        itemStyle: { color: '#f56c6c', color0: '#67c23a' },
      },
      {
        name: 'MA5', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
        data: ma5, smooth: true, symbol: 'none', lineStyle: { width: 1 },
      },
      {
        name: 'MA20', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
        data: ma20, smooth: true, symbol: 'none', lineStyle: { width: 1 },
      },
      {
        name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
        data: volumes,
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
.track-dashboard { padding: 16px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 20px; }
.track-tab-label { display: flex; align-items: center; gap: 6px; }
.stock-rank-card .stock-rank-item {
  display: flex; align-items: center; gap: 8px; padding: 8px 12px;
  cursor: pointer; border-radius: 4px; transition: background 0.2s;
}
.stock-rank-item:hover { background: #f5f7fa; }
.stock-rank-item.active { background: #ecf5ff; }
.rank-num { width: 28px; font-size: 12px; color: #909399; }
.stock-name { flex: 1; font-size: 14px; }
.kline-container { width: 100%; height: 420px; }
.sentiment-gauge { text-align: center; padding: 16px 0; }
.gauge-value { font-size: 48px; font-weight: bold; }
.gauge-label { font-size: 14px; color: #909399; margin-bottom: 8px; }
.factor-item { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; font-size: 12px; }
.factor-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 140px; }
</style>
