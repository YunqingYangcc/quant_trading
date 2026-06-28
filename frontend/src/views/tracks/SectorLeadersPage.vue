<template>
  <div class="biz-logic-page">
    <div class="page-header">
      <h2>业务逻辑分析</h2>
      <div class="header-right">
        <el-button size="small" type="primary" :loading="batchLoading" @click="runBatchAi">全部重新分析</el-button>
        <span class="page-date">{{ data?.date || '加载中...' }}</span>
      </div>
    </div>

    <div v-if="loading" class="loading-state"><el-skeleton :rows="5" animated /></div>

    <!-- 按赛道分组 -->
    <template v-if="stocks.length">
      <div v-for="group in trackGroups" :key="group.track" class="track-section">
        <div class="track-header">{{ group.track }} ({{ group.stocks.length }}只)</div>
        <el-table :data="group.stocks" size="small" stripe style="width:100%">
          <el-table-column prop="position" label="定位" width="60">
            <template #default="{ row }">
              <el-tag :type="row.position === '龙1' ? 'danger' : 'warning'" size="small" effect="dark">{{ row.position }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="股票" width="100" />
          <el-table-column prop="code" label="代码" width="120" />
          <el-table-column prop="segment" label="细分" width="120" />
          <el-table-column label="涨跌幅" width="100" align="right">
            <template #default="{ row }">
              <span :class="row.change_pct > 0 ? 'up' : row.change_pct < 0 ? 'down' : 'flat'" style="font-weight:700">
                {{ row.change_pct > 0 ? '+' : '' }}{{ row.change_pct.toFixed(2) }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="业务逻辑" min-width="320">
            <template #default="{ row }">
              <div v-if="row.logicSummary" class="logic-cell">
                <span class="logic-text">{{ row.logicSummary }}</span>
                <el-button size="small" text type="primary" @click="showDetail(row)">详情</el-button>
                <el-button size="small" text type="warning" @click="reAnalyze(row)">重新分析</el-button>
              </div>
              <el-button v-else size="small" type="primary" text :loading="aiLoading[row.code]" @click="runAiLogic(row)">
                {{ aiLoading[row.code] ? '分析中...' : 'AI 分析' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>

    <el-empty v-if="!loading && !stocks.length" description="加载失败" />

    <!-- 详情弹窗 -->
    <el-dialog v-model="aiVisible" :title="aiTitle" width="680px" destroy-on-close>
      <div v-if="detailStock" class="ai-result">
        <div class="ai-summary">{{ detailStock.logicSummary }}</div>
        <div v-if="detailStock.logicScore" class="ai-score-note">可验证评分 {{ detailStock.logicScore }}/12</div>
        <div v-for="dim in (detailStock.logicDims || [])" :key="dim.label" class="ai-dim">
          <div class="ai-dim-label">{{ dim.label }}</div>
          <div class="ai-dim-content">{{ dim.content }}</div>
          <div v-if="dim.sources" class="ai-dim-source">来源: {{ dim.sources }}</div>
        </div>
      </div>
      <div v-else-if="aiError" class="ai-error">{{ aiError }}</div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'

const API_BASE = 'http://localhost:8000/api/v1'
const data = ref<any>(null)
const stocks = ref<any[]>([])
const loading = ref(true)
const batchLoading = ref(false)
const aiVisible = ref(false)
const aiTitle = ref('')
const detailStock = ref<any>(null)
const aiError = ref('')
const aiLoading = ref<Record<string, boolean>>({})
const priceLoading = ref<Record<string, boolean>>({})

const trackGroups = computed(() => {
  const map: Record<string, any[]> = {}
  for (const s of stocks.value) {
    const t = s.track || '其他'
    if (!map[t]) map[t] = []
    map[t].push(s)
  }
  return Object.entries(map).map(([track, items]) => ({ track, stocks: items }))
})

onMounted(async () => {
  try {
    const resp = await fetch(`${API_BASE}/monitor/leaders`)
    data.value = await resp.json()
    const flat: any[] = []
    for (const g of data.value?.groups || []) {
      for (const s of g.stocks) {
        flat.push({ ...s, track: g.track, logicSummary: null, logicScore: null, logicDims: null, pricePlan: null })
      }
    }
    // 从 localStorage 恢复之前保存的分析结果
    const saved = localStorage.getItem('biz_logic_cache')
    if (saved) {
      const cache = JSON.parse(saved)
      for (const s of flat) {
        const c = cache[s.code]
        if (c) {
          if (c.logicSummary) { s.logicSummary = c.logicSummary; s.logicScore = c.logicScore; s.logicDims = c.logicDims }
          if (c.pricePlan) s.pricePlan = c.pricePlan
        }
      }
    }
    stocks.value = flat
  } catch { /* ignore */ }
  finally { loading.value = false }
})

function saveToCache() {
  const cache: Record<string, any> = {}
  for (const s of stocks.value) {
    cache[s.code] = { logicSummary: s.logicSummary, logicScore: s.logicScore, logicDims: s.logicDims, pricePlan: s.pricePlan }
  }
  localStorage.setItem('biz_logic_cache', JSON.stringify(cache))
}

async function runAiLogic(stock: any) {
  aiLoading.value[stock.code] = true
  try {
    const resp = await fetch(`${API_BASE}/monitor/ai-logic`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stock: { name: stock.name, code: stock.code, track: stock.track, segment: stock.segment, position: stock.position } }),
    })
    const json = await resp.json()
    if (resp.ok && json.analysis) {
      stock.logicSummary = json.analysis.summary || ''
      stock.logicScore = json.analysis.verifiable_score || 0
      stock.logicDims = json.analysis.dimensions || []
      saveToCache()
      detailStock.value = stock
      aiTitle.value = `${stock.name} (${stock.code})`
      aiVisible.value = true
    } else {
      aiError.value = json.detail || '分析失败'
      aiVisible.value = true
    }
  } catch (e: any) {
    aiError.value = e.message || '网络错误'
    aiVisible.value = true
  } finally {
    aiLoading.value[stock.code] = false
  }
}

function showDetail(stock: any) {
  detailStock.value = stock
  aiTitle.value = `${stock.name} (${stock.code})`
  aiVisible.value = true
}

function reAnalyze(stock: any) {
  stock.logicSummary = null
  stock.logicScore = null
  stock.logicDims = null
  saveToCache()
  runAiLogic(stock)
}

async function runAiPrice(stock: any) {
  priceLoading.value[stock.code] = true
  try {
    const resp = await fetch(`${API_BASE}/monitor/ai-price`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stock: { name: stock.name, code: stock.code, track: stock.track, segment: stock.segment, position: stock.position } }),
    })
    const json = await resp.json()
    if (resp.ok && json.analysis) {
      const tp = json.analysis.trade_plan || {}
      stock.pricePlan = { should_buy: tp.should_buy || '观望', buy_zone: tp.buy_zone || '', stop_loss: tp.stop_loss || '', target_1: tp.target_1 || '' }
      saveToCache()
    }
  } catch { /* ignore */ }
  finally { priceLoading.value[stock.code] = false }
}

async function runBatchAi() {
  batchLoading.value = true
  // 清除全部旧结果
  for (const s of stocks.value) {
    s.logicSummary = null
    s.logicScore = null
    s.logicDims = null
  }
  saveToCache()
  try {
    const resp = await fetch(`${API_BASE}/monitor/ai-logic/all`, { method: 'POST' })
    const json = await resp.json()
    if (resp.ok && json.results) {
      for (const r of json.results) {
        const stock = stocks.value.find(s => s.code === r.stock.code)
        if (stock && r.analysis) {
          stock.logicSummary = r.analysis.summary || ''
          stock.logicScore = r.analysis.verifiable_score || 0
          stock.logicDims = r.analysis.dimensions || []
        }
      }
    }
  } catch { /* ignore */ }
  finally { batchLoading.value = false }
}
</script>

<style scoped>
.biz-logic-page { padding: 20px 24px; max-width: 1500px; margin: 0 auto; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.page-header h2 { font-size: 20px; font-weight: 600; color: #1a1a2e; margin: 0; }
.header-right { display: flex; align-items: center; gap: 12px; }
.page-date { font-size: 12px; color: #94a3b8; white-space: nowrap; }
.up { color: #f56c6c; } .down { color: #67c23a; } .flat { color: #909399; }

.track-section { margin-bottom: 16px; }
.track-header { font-size: 13px; font-weight: 600; color: #475569; margin-bottom: 6px; padding: 4px 0; border-bottom: 2px solid #3b82f6; }

.logic-cell { display: flex; align-items: center; gap: 6px; }
.logic-text { font-size: 12px; color: #334155; line-height: 1.5; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.ai-result { line-height: 1.8; }
.ai-summary { font-size: 14px; font-weight: 600; color: #1a1a2e; padding: 10px 14px; background: #f0fdf4; border-radius: 6px; margin-bottom: 14px; border-left: 3px solid #67c23a; }
.ai-dim { margin-bottom: 12px; }
.ai-dim-label { font-size: 12px; font-weight: 600; color: #3b82f6; margin-bottom: 4px; }
.ai-dim-content { font-size: 13px; color: #475569; line-height: 1.7; }
.ai-dim-source { font-size: 10px; color: #94a3b8; margin-top: 2px; font-style: italic; }
.ai-score-note { font-size: 11px; color: #64748b; margin-bottom: 12px; padding: 6px 10px; background: #fffbeb; border-radius: 4px; }
.ai-error { color: #f56c6c; padding: 20px; text-align: center; }
</style>
