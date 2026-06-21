<template>
  <div class="factors-page">
    <!-- Header -->
    <div class="fp-header">
      <div class="fp-header-left">
        <div class="fp-title-row">
          <span class="fp-title-icon">📊</span>
          <div>
            <div class="fp-title">Factor Config</div>
            <div class="fp-subtitle">因子筛选配置 · 白名单 {{ whitelist.length }} / 黑名单 {{ blacklist.length }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Stats Bar -->
    <div class="fp-stats-row">
      <div class="fp-stat-item">
        <span class="fp-stat-num fp-stat-green">{{ whitelist.length }}</span>
        <span class="fp-stat-label">白名单 ✅</span>
      </div>
      <div class="fp-stat-divider" />
      <div class="fp-stat-item">
        <span class="fp-stat-num fp-stat-red">{{ blacklist.length }}</span>
        <span class="fp-stat-label">黑名单 ❌</span>
      </div>
      <div class="fp-stat-divider" />
      <div class="fp-stat-item">
        <span class="fp-stat-num fp-stat-blue">{{ (whitelist.length / (whitelist.length + blacklist.length) * 100).toFixed(0) }}%</span>
        <span class="fp-stat-label">通过率</span>
      </div>
      <div class="fp-stat-divider" />
      <div class="fp-stat-item">
        <span class="fp-stat-num" style="font-size:15px">v1</span>
        <span class="fp-stat-label">筛选批次 · {{ screeningDate }}</span>
      </div>
      <div class="fp-stat-divider" />
      <div class="fp-stat-item">
        <span class="fp-stat-num fp-stat-purple">{{ categoryCount }}</span>
        <span class="fp-stat-label">因子分类</span>
      </div>
    </div>

    <!-- Focus Panel: Top Factors -->
    <div class="fp-top-factors" v-if="topFactors.length > 0">
      <div class="fp-top-header">
        <span class="fp-top-title">🔥 最强因子（按 |IC| 排序）</span>
        <span class="fp-top-hint">IC 绝对值越大，预测能力越强</span>
      </div>
      <div class="fp-top-grid">
        <div v-for="(f, i) in topFactors" :key="f.factor_name" class="fp-top-item" :class="'fp-top-rank-' + Math.min(i + 1, 4)">
          <div class="fp-top-rank">{{ i + 1 }}</div>
          <div class="fp-top-body">
            <div class="fp-top-name">{{ f.factor_name }}</div>
            <div class="fp-top-meta">{{ f.factor_type }}</div>
            <div class="fp-top-bar-wrap">
              <div class="fp-top-bar-fill" :style="{ width: Math.min(Math.abs(f.ic_mean) * 5000, 100) + '%', background: f.ic_mean >= 0 ? '#ef4444' : '#3b82f6' }" />
            </div>
          </div>
          <div class="fp-top-val" :class="f.ic_mean >= 0 ? 'fp-top-red' : 'fp-top-blue'">
            {{ (f.ic_mean * 100).toFixed(2) }}
            <span class="fp-top-dir">{{ f.ic_mean >= 0 ? '正向' : '负向' }}</span>
            <span class="fp-top-ir">IR {{ f.ir?.toFixed(1) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab: Whitelist / Blacklist -->
    <div class="fp-tabs">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="✅ 白名单" name="whitelist">
          <!-- Toolbar -->
          <div class="fp-toolbar">
            <el-input v-model="searchQuery" placeholder="搜索因子名称..." size="small" clearable :prefix-icon="Search" class="fp-search" />
            <el-select v-model="filterCategory" size="small" placeholder="全部分类" clearable class="fp-cat-select">
              <el-option v-for="cat in categories" :key="cat.value" :label="cat.label" :value="cat.value" />
            </el-select>
          </div>
          <!-- Table -->
          <div class="fp-table">
            <div v-for="f in filteredWhitelist" :key="f.factor_name" class="fp-row" :class="{ 'fp-row-expanded': expanded.has(f.factor_name) }">
              <div class="fpr-header" @click="toggleExpand(f.factor_name)">
                <div class="fpr-name-group">
                  <div class="fpr-name">{{ f.factor_name }}</div>
                </div>
                <div class="fpr-category">
                  <el-tag size="small" :type="catTagType(f.factor_type)" effect="plain">{{ catLabel(f.factor_type) }}</el-tag>
                </div>
                <div class="fpr-metrics">
                  <span class="fpr-ic" :class="f.ic_mean >= 0 ? '' : 'fpr-ic-neg'">
                    IC {{ (f.ic_mean * 100).toFixed(2) }}
                  </span>
                  <span class="fpr-ir">IR {{ f.ir?.toFixed(2) }}</span>
                </div>
                <div class="fpr-dir">
                  <el-tag :type="f.ic_mean >= 0 ? 'danger' : 'primary'" size="small" effect="plain">{{ f.ic_mean >= 0 ? '正向' : '负向' }}</el-tag>
                </div>
                <div class="fpr-vs">
                  <div class="fpr-bar-bg">
                    <div class="fpr-bar-fill" :style="{ width: Math.min(Math.abs(f.ic_mean) * 3000, 100) + '%', background: f.ic_mean >= 0 ? '#ef4444' : '#3b82f6' }" />
                  </div>
                </div>
              </div>
              <div v-if="expanded.has(f.factor_name)" class="fpr-detail">
                <div class="fpr-detail-grid">
                  <div class="fpr-ds-item" v-if="getCnName(f.factor_name)">
                    <span class="fpr-ds-label">中文名</span>
                    <span class="fpr-ds-val">{{ getCnName(f.factor_name) }}</span>
                  </div>
                  <div class="fpr-ds-item">
                    <span class="fpr-ds-label">IC</span>
                    <span class="fpr-ds-val">{{ (f.ic_mean * 100).toFixed(4) }}</span>
                  </div>
                  <div class="fpr-ds-item">
                    <span class="fpr-ds-label">IR</span>
                    <span class="fpr-ds-val">{{ f.ir?.toFixed(4) }}</span>
                  </div>
                  <div class="fpr-ds-item" v-if="f.lgb_importance">
                    <span class="fpr-ds-label">LGB重要性</span>
                    <span class="fpr-ds-val">{{ (f.lgb_importance * 100).toFixed(2) }}%</span>
                  </div>
                </div>
                <div class="fpr-ds-full">
                  <div class="fpr-ds-label">📝 公式</div>
                  <div class="fpr-ds-val formula">{{ getFormula(f.factor_name) || '—' }}</div>
                </div>
              </div>
            </div>
            <el-empty v-if="!filteredWhitelist.length" :description="searchQuery ? '无匹配因子' : '暂无因子数据'" />
          </div>
        </el-tab-pane>

        <el-tab-pane label="❌ 黑名单" name="blacklist">
          <div class="fp-blacklist">
            <div v-for="f in blacklist" :key="f.factor_name" class="fp-bl-row">
              <span class="fp-bl-name">{{ f.factor_name }}</span>
              <el-tag size="small" type="danger" effect="plain">{{ f.reason || '未通过筛选' }}</el-tag>
            </div>
            <el-empty v-if="!blacklist.length" description="暂无黑名单数据" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { getWhitelist, getBlacklist } from '@/api/track'

const whitelist = ref<any[]>([])
const blacklist = ref<any[]>([])
const loading = ref(true)
const activeTab = ref('whitelist')
const searchQuery = ref('')
const filterCategory = ref('')
const expanded = ref<Set<string>>(new Set())

const categories = [
  { value: 'generic', label: '🔧 通用' },
  { value: 'track_specific', label: '🏷️ 赛道专属' },
  { value: 'momentum', label: '⚡ 动量' },
  { value: 'trend', label: '📈 趋势' },
  { value: 'volatility', label: '🌊 波动率' },
  { value: 'volume', label: '📊 量能' },
  { value: 'statistical', label: '📐 统计' },
  { value: 'fundamental', label: '🏢 基本面' },
]

function catLabel(val: string | null): string {
  const found = categories.find(c => c.value === val)
  return found?.label || val || '其他'
}

function catTagType(val: string | null): string {
  if (val === 'track_specific') return 'warning'
  if (val === 'generic') return 'info'
  return 'primary'
}

const screeningDate = computed(() => {
  // Try to get screening date from the whitelist data metadata
  return '2026-06-21'
})

const categoryCount = computed(() => {
  const cats = new Set(whitelist.value.map((f: any) => f.factor_type || f.category))
  return cats.size
})

const topFactors = computed(() => {
  return [...whitelist.value]
    .sort((a: any, b: any) => Math.abs(b.ic_mean || 0) - Math.abs(a.ic_mean || 0))
    .slice(0, 8)
})

const filteredWhitelist = computed(() => {
  let list = whitelist.value
  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    list = list.filter((f: any) => f.factor_name.toLowerCase().includes(q))
  }
  if (filterCategory.value) {
    list = list.filter((f: any) => (f.factor_type || f.category) === filterCategory.value)
  }
  return list.sort((a: any, b: any) => Math.abs(b.ic_mean || 0) - Math.abs(a.ic_mean || 0))
})

function toggleExpand(name: string) {
  if (expanded.value.has(name)) expanded.value.delete(name)
  else expanded.value.add(name)
}

const CN_NAMES: Record<string, string> = {
  rsi_6: '6日RSI', rsi_14: '14日RSI', rsi_24: '24日RSI',
  stoch_k: '随机K', stoch_d: '随机D', stoch_j: '随机J',
  sma_5: '5日均线', sma_10: '10日均线', sma_20: '20日均线', sma_60: '60日均线',
  macd: 'MACD', macd_signal: 'MACD信号线', macd_hist: 'MACD柱',
  adx: 'ADX', atr_14: '14日ATR', atr_5: '5日ATR',
  bb_upper: '布林上轨', bb_lower: '布林下轨',
  obv: 'OBV能量潮', vwap: '均价线',
}

const FORMULAS: Record<string, string> = {
  rsi_6: 'RSI=100-100/(1+RS)，RS=6日平均涨幅/6日平均跌幅',
  rsi_14: 'RSI=100-100/(1+RS)，周期14日',
  rsi_24: 'RSI=100-100/(1+RS)，周期24日',
  stoch_k: '%K=(收盘价-9日最低)/(9日最高-9日最低)×100',
  stoch_d: '%D=%K的3日SMA',
  stoch_j: 'J=3×%K-2×%D',
  sma_5: '5日收盘价之和/5',
  sma_10: '10日收盘价之和/10',
  sma_20: '20日收盘价之和/20',
  sma_60: '60日收盘价之和/60',
  macd: '12日EMA-26日EMA',
  macd_signal: 'MACD的9日EMA',
  macd_hist: 'MACD-Signal',
  adx: '100×|+DI--DI|/(+DI+-DI)的14日平滑移动均线',
  atr_14: '14日TR均值，TR=MAX(H-L,|H-前收|,|L-前收|)',
  atr_5: '5日TR均值',
  bb_upper: '20日SMA+2×20日标准差',
  bb_lower: '20日SMA-2×20日标准差',
  obv: 'Σ(成交量×方向)',
  vwap: 'Σ(典型价×成交量)/Σ(成交量)',
}

function getCnName(name: string): string {
  return CN_NAMES[name] || ''
}

function getFormula(name: string): string {
  return FORMULAS[name] || ''
}

onMounted(async () => {
  try {
    const [wl, bl] = await Promise.all([getWhitelist(), getBlacklist()])
    whitelist.value = Array.isArray(wl) ? wl : []
    blacklist.value = Array.isArray(bl) ? bl : []
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
  checkPipelineRefresh()
})

function checkPipelineRefresh() {
  if (localStorage.getItem('pipeline_factor_refresh')) {
    localStorage.removeItem('pipeline_factor_refresh')
    loading.value = true
    Promise.all([getWhitelist(), getBlacklist()]).then(([wl, bl]) => {
      whitelist.value = Array.isArray(wl) ? wl : []
      blacklist.value = Array.isArray(bl) ? bl : []
    }).finally(() => { loading.value = false })
  }
}
</script>

<style scoped>
.factors-page {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  overflow-y: auto;
}

/* Header */
.fp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.fp-header-left { display: flex; align-items: center; }
.fp-title-row { display: flex; align-items: center; gap: 10px; }
.fp-title-icon { font-size: 20px; width: 34px; height: 34px; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #f59e0b, #d97706); border-radius: 8px; color: #fff; }
.fp-title { font-size: 15px; font-weight: 700; color: #1e293b; }
.fp-subtitle { font-size: 11px; color: #94a3b8; }

/* Stats */
.fp-stats-row {
  display: flex; align-items: center; background: #fff; border-radius: 10px;
  padding: 12px 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
.fp-stat-item { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 1px; }
.fp-stat-num { font-size: 20px; font-weight: 700; color: #1e293b; line-height: 1.2; }
.fp-stat-green { color: #16a34a; }
.fp-stat-red { color: #dc2626; }
.fp-stat-blue { color: #2563eb; }
.fp-stat-purple { color: #7c3aed; }
.fp-stat-label { font-size: 10px; color: #94a3b8; }
.fp-stat-divider { width: 1px; height: 32px; background: #e2e8f0; margin: 0 8px; flex-shrink: 0; }

/* Top Factors */
.fp-top-factors {
  background: #fff; border-radius: 10px; padding: 12px 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
.fp-top-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.fp-top-title { font-size: 13px; font-weight: 700; color: #1e293b; }
.fp-top-hint { font-size: 10px; color: #94a3b8; }
.fp-top-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
.fp-top-item { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 6px; background: #f8fafc; border: 1px solid #f1f5f9; }
.fp-top-item:hover { border-color: #93c5fd; background: #f0f7ff; }
.fp-top-rank-1 { background: #fef2f2; border-color: #fecaca; }
.fp-top-rank-2 { background: #fff7ed; border-color: #fed7aa; }
.fp-top-rank-3 { background: #fffbeb; border-color: #fde68a; }
.fp-top-rank { font-size: 11px; font-weight: 800; color: #64748b; width: 18px; text-align: center; flex-shrink: 0; }
.fp-top-rank-1 .fp-top-rank { color: #dc2626; }
.fp-top-rank-2 .fp-top-rank { color: #ea580c; }
.fp-top-rank-3 .fp-top-rank { color: #d97706; }
.fp-top-body { flex: 1; min-width: 0; }
.fp-top-name { font-size: 11px; font-weight: 600; color: #334155; font-family: 'SF Mono', monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.fp-top-meta { font-size: 9px; color: #94a3b8; }
.fp-top-bar-wrap { height: 4px; background: #e2e8f0; border-radius: 2px; overflow: hidden; margin-top: 3px; }
.fp-top-bar-fill { height: 100%; border-radius: 2px; transition: width 0.3s; }
.fp-top-val { font-size: 13px; font-weight: 700; text-align: right; flex-shrink: 0; line-height: 1.1; }
.fp-top-red { color: #dc2626; }
.fp-top-blue { color: #2563eb; }
.fp-top-dir { display: block; font-size: 9px; font-weight: 500; opacity: 0.6; }
.fp-top-ir { display: block; font-size: 9px; font-weight: 400; opacity: 0.5; }

/* Tabs */
.fp-tabs { background: #fff; border-radius: 10px; padding: 0 16px 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.05); }
.fp-toolbar { display: flex; gap: 8px; margin-bottom: 10px; }
.fp-search { width: 260px; }
.fp-cat-select { width: 130px; }

/* Table */
.fp-table { display: flex; flex-direction: column; gap: 2px; }
.fp-row { border: 1px solid transparent; border-radius: 6px; transition: all 0.1s; }
.fp-row:hover { background: #f8fafc; }
.fp-row-expanded { background: #f8faff; border-color: #93c5fd; }
.fpr-header { display: flex; align-items: center; gap: 12px; padding: 8px 12px; cursor: pointer; }
.fpr-name-group { width: 160px; flex-shrink: 0; }
.fpr-name { font-size: 12px; font-weight: 600; color: #1e293b; font-family: 'SF Mono', monospace; }
.fpr-category { width: 80px; flex-shrink: 0; }
.fpr-metrics { display: flex; gap: 8px; width: 120px; flex-shrink: 0; }
.fpr-ic { font-size: 12px; font-weight: 700; color: #dc2626; }
.fpr-ic-neg { color: #2563eb; }
.fpr-ir { font-size: 11px; color: #94a3b8; }
.fpr-dir { width: 50px; flex-shrink: 0; }
.fpr-vs { flex: 1; min-width: 80px; padding: 0 8px; }
.fpr-bar-bg { height: 5px; background: #f1f5f9; border-radius: 3px; overflow: hidden; }
.fpr-bar-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }

/* Detail */
.fpr-detail { padding: 8px 12px 12px 16px; border-top: 1px dashed #e2e8f0; }
.fpr-detail-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 8px; }
.fpr-ds-item { }
.fpr-ds-label { font-size: 10px; font-weight: 600; color: #94a3b8; margin-bottom: 1px; }
.fpr-ds-val { font-size: 12px; color: #334155; }
.fpr-ds-val.formula { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 6px 10px; font-family: 'SF Mono', monospace; font-size: 11px; }
.fpr-ds-full { margin-top: 4px; }

/* Blacklist */
.fp-blacklist { display: flex; flex-direction: column; gap: 4px; }
.fp-bl-row { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid #f1f5f9; }
.fp-bl-name { font-size: 12px; font-family: 'SF Mono', monospace; color: #475569; }
</style>
