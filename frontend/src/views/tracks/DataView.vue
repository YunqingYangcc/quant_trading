<template>
  <div class="data-view">
    <!-- 流水线控制台 -->
    <div class="pipeline-runner">
      <div class="pr-header">
        <div class="pr-title-row">
          <span class="pr-title-icon">⚙</span>
          <span class="pr-title">Pipeline Runner</span>
          <span class="pr-subtitle">量化流水线控制台</span>
        </div>
        <el-button type="primary" size="small" @click="runPipeline('all')" :loading="running === 'all'" :icon="CaretRight">
          {{ running === 'all' ? '运行中...' : '▶ 一键跑全部' }}
        </el-button>
      </div>
      <div class="pr-steps">
        <div v-for="s in pipelineSteps" :key="s.key" class="pr-step" :class="stepClass(s.key)">
          <div class="pr-step-indicator">
            <span v-if="pipelineStatus[s.key] === 'done'" class="pr-dot pr-dot-done">✓</span>
            <span v-else-if="pipelineStatus[s.key] === 'running'" class="pr-dot pr-dot-running">⟳</span>
            <span v-else class="pr-dot pr-dot-idle">○</span>
          </div>
          <div class="pr-step-info">
            <div class="pr-step-name">{{ s.label }}</div>
            <div class="pr-step-desc">{{ s.desc }}</div>
          </div>
          <div class="pr-step-action">
            <el-button v-if="pipelineStatus[s.key] !== 'running'" size="small" text @click="runPipeline(s.key)" :loading="running === s.key">
              {{ s.action }}
            </el-button>
            <el-tag v-else size="small" type="warning" effect="dark">运行中...</el-tag>
          </div>
        </div>
      </div>
      <div v-if="pipelineLog" class="pr-log">
        <pre>{{ pipelineLog }}</pre>
      </div>
    </div>

    <!-- 流水线运行日志 -->
    <div class="pipeline-logs">
      <div class="pl-header">
        <span class="pl-title">流水线日志</span>
        <el-button size="small" text @click="loadPipelineRuns">刷新</el-button>
      </div>
      <div v-if="pipelineRuns.length === 0" class="pl-empty">暂无运行记录</div>
      <div v-for="run in pipelineRuns" :key="run.id" class="pl-item">
        <div class="pl-item-header">
          <el-tag :type="run.run_type === 'train' ? 'primary' : 'success'" size="small" effect="dark">
            {{ run.run_type === 'train' ? '训练' : '回测' }}
          </el-tag>
          <span class="pl-item-time">{{ formatTime(run.created_at) }}</span>
          <span v-if="run.feature_count" class="pl-item-info">{{ run.feature_count }} 个特征</span>
          <span v-if="run.git_commit_hash" class="pl-item-hash">#{{ run.git_commit_hash }}</span>
        </div>
        <div v-if="run.results_summary" class="pl-item-body">
          <template v-if="run.run_type === 'train'">
            <span v-for="(v, k) in run.results_summary" :key="k" class="pl-metric">
              {{ k }}: acc={{ (v.val_acc * 100).toFixed(1) }}%
              <el-tag v-if="v.overfitting" size="small" type="danger" effect="plain">过拟合</el-tag>
            </span>
          </template>
          <template v-else>
            <span v-for="(v, k) in run.results_summary" :key="k" class="pl-metric">
              {{ k }}: 夏普={{ v.sharpe_ratio.toFixed(2) }} 收益={{ (v.total_return).toFixed(1) }}%
            </span>
          </template>
        </div>
      </div>
    </div>

    <!-- 顶部统计卡片（动态数据） -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-value">{{ stats.stocks }}</div>
        <div class="stat-label">自选股</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">111</div>
        <div class="stat-label">原始特征</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.whitelist }}</div>
        <div class="stat-label">白名单✅</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.blacklist }}</div>
        <div class="stat-label">黑名单❌</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.finalFeatures }}</div>
        <div class="stat-label">最终特征</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.models }}</div>
        <div class="stat-label">赛道模型</div>
      </div>
    </div>

    <!-- 筛选标准 -->
    <div class="content-row">
      <div class="factor-col">
        <div class="criteria-card">
          <div class="criteria-title">🔬 因子筛选流程</div>
          <div class="criteria-flow">
            <div class="c-step">
              <span class="c-num">1</span>
              <div class="c-body">
                <strong>Alphalens 池化 IC 检验</strong>
                <span>计算每个因子与未来20日收益的 Spearman 秩相关系数，要求 |IC| ≥ 0.01</span>
              </div>
            </div>
            <div class="c-step">
              <span class="c-num">2</span>
              <div class="c-body">
                <strong>IR 稳定性检验</strong>
                <span>计算 IC 时序均值/标准差的比率，要求 |IR| ≥ 0.05，确保因子表现稳定</span>
              </div>
            </div>
            <div class="c-step">
              <span class="c-num">3</span>
              <div class="c-body">
                <strong>10 层分组单调性</strong>
                <span>按因子值分成10组，检查各组收益是否单调递增/递减</span>
              </div>
            </div>
            <div class="c-step">
              <span class="c-num">4</span>
              <div class="c-body">
                <strong>去共线 (|corr| &lt; 0.95)</strong>
                <span>剔除相关性超过0.95的高相关特征对，75 → 54 个最终特征</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 黑名单 -->
    <div class="content-row" v-if="blacklistFactors.length">
      <div class="factor-col">
        <div class="blacklist-card">
          <div class="bl-header" @click="showBlacklist = !showBlacklist" style="cursor:pointer">
            <span class="bl-title">❌ 黑名单因子（{{ blacklistFactors.length }} 个）</span>
            <el-tag size="small" type="danger">未通过筛选</el-tag>
            <el-icon :class="{ rot: showBlacklist }"><ArrowRight /></el-icon>
          </div>
          <div v-if="showBlacklist" class="bl-body">
            <div v-for="f in blacklistFactors" :key="f.factor_name" class="bl-row">
              <span class="bl-name">{{ f.factor_name }}</span>
              <el-tag size="small" type="danger" effect="plain">{{ f.reason || '未通过筛选' }}</el-tag>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 最终特征 -->
    <div class="content-row">
      <div class="factor-col">
        <div class="criteria-card">
          <div class="criteria-title">📊 最终特征（54 个）</div>
          <div class="criteria-desc">
            <p>从 75 个白名单因子中剔除 21 对高度相关特征 (|corr| &gt; 0.95) 后保留。例如：</p>
            <ul>
              <li><code>sma_5</code> 与 <code>ema_5</code> 高度相关 → 仅保留 <code>sma_5</code></li>
              <li><code>atr_5</code> 与 <code>atr_14</code> 高度相关 → 仅保留 <code>atr_14</code></li>
              <li>同类趋势指标中保留 IC 最高者，去除冗余</li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <!-- 因子详情（全宽） -->
    <div class="content-row">
      <div class="factor-col">
        <div class="factor-detail-panel">
          <div class="section-header">
            <span class="section-title">📖 因子完全手册</span>
            <el-tag size="small" type="info">共 75 个有效因子</el-tag>
          </div>

          <!-- 搜索 + 分类筛选 -->
          <div class="factor-toolbar">
            <el-input
              v-model="searchQuery"
              placeholder="搜索因子名称..."
              size="small"
              clearable
              :prefix-icon="Search"
              class="factor-search"
            />
            <el-select v-model="selectedCategory" size="small" placeholder="全部分类" clearable class="category-select">
              <el-option v-for="cat in categories" :key="cat.value" :label="cat.label" :value="cat.value" />
            </el-select>
          </div>

          <!-- 因子卡片列表（带完整释义） -->
          <div class="factor-grid">
            <div
              v-for="f in filteredFactors"
              :key="f.factor_name"
              class="factor-detail-card"
              @click="toggleDetail(f.factor_name)"
            >
              <div class="card-head">
                <div class="card-info">
                  <span class="card-cn-name">{{ getCnName(f.factor_name) }}</span>
                  <span class="card-en-name">{{ f.factor_name }}</span>
                </div>
                <div class="card-metrics-top">
                  <el-tag size="small" :type="f.ic_mean >= 0 ? 'success' : 'danger'" round effect="dark">
                    IC {{ (f.ic_mean * 100).toFixed(2) }}
                  </el-tag>
                  <span class="card-ir">IR {{ f.ir?.toFixed(2) }}</span>
                </div>
              </div>

              <!-- 展开后的完整释义 -->
              <div v-if="expanded.has(f.factor_name)" class="card-detail">
                <div class="detail-section">
                  <div class="detail-label">📐 计算公式</div>
                  <div class="detail-value formula-box">{{ getFormula(f.factor_name) }}</div>
                </div>
                <div class="detail-section">
                  <div class="detail-label">💡 解读方法</div>
                  <div class="detail-value">{{ getInterpretation(f.factor_name) }}</div>
                </div>
                <div class="detail-section">
                  <div class="detail-label">📊 IC 表现</div>
                  <div class="detail-value">
                    IC={{ (f.ic_mean * 100).toFixed(2) }}, IR={{ f.ir?.toFixed(2) }}，
                    {{ f.ic_mean >= 0 ? '正向因子（值越大越好）' : '负向因子（值越小越好）' }}
                    <div class="ic-bar-bg">
                      <div class="ic-bar-fill" :style="{ width: Math.min(Math.abs(f.ic_mean) * 3000, 100) + '%', background: f.ic_mean >= 0 ? '#67c23a' : '#f56c6c' }" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <el-empty v-if="!filteredFactors.length" :description="searchQuery ? '无匹配因子' : '暂无因子数据'" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { Search, ArrowRight, CaretRight } from '@element-plus/icons-vue'
import { getWhitelist, getBlacklist, listTracks, runPipeline as runPipelineApi, getPipelineRuns } from '@/api/track'
import { ElMessage } from 'element-plus'

const factors = ref<any[]>([])
const blacklistFactors = ref<any[]>([])
const searchQuery = ref('')
const selectedCategory = ref('')
const expanded = ref<Set<string>>(new Set())
const showBlacklist = ref(false)
const stats = ref({
  stocks: 23,
  whitelist: 75,
  blacklist: 72,
  finalFeatures: 54,
  models: 4,
})

// ── 流水线运行日志 ──
const pipelineRuns = ref<any[]>([])

function formatTime(ts: string) {
  return ts?.replace('T', ' ').slice(0, 19) || ''
}

async function loadPipelineRuns() {
  try {
    const res: any = await getPipelineRuns(10)
    pipelineRuns.value = Array.isArray(res) ? res : (res?.data || [])
  } catch { /* ignore */ }
}

onMounted(() => {
  loadPipelineRuns()
})

// ── Pipeline Runner ──
const running = ref<string | null>(null)
const pipelineLog = ref('')
const pipelineStatus = reactive<Record<string, string>>({
  compute: 'idle',
  screen: 'idle',
  preprocess: 'idle',
  train: 'idle',
  backtest: 'idle',
})

const pipelineSteps = [
  { key: 'compute', label: '特征计算', desc: '93通用+18赛道特征', action: '计算' },
  { key: 'incremental_compute', label: '增量特征追加', desc: '仅新增交易日', action: '增量' },
  { key: 'screen', label: '因子筛选', desc: 'Alphalens 白/黑名单', action: '筛选' },
  { key: 'preprocess', label: '特征预处理', desc: '标准化+去共线+时序分割', action: '预处理' },
  { key: 'train', label: '模型训练', desc: '6 赛道 LightGBM', action: '训练' },
]

function stepClass(key: string) {
  const s = pipelineStatus[key]
  return {
    'pr-step-done': s === 'done',
    'pr-step-running': s === 'running',
  }
}

async function runPipeline(step: string) {
  running.value = step
  pipelineLog.value = ''

  const steps = step === 'all' ? ['compute', 'screen', 'preprocess', 'train'] : [step]

  for (const s of steps) {
    pipelineStatus[s] = 'running'
    try {
      let res: any
      if (s === 'incremental_compute') {
        const { incrementalCompute } = await import('@/api/track')
        res = await incrementalCompute()
      } else {
        res = await runPipelineApi(s)
      }
      if (step === 'all' && res?.steps?.[s]?.status === 'failed') {
        pipelineStatus[s] = 'failed'
        ElMessage.warning(`${s} 失败: ${res.steps[s].error}`)
        break
      }
      pipelineStatus[s] = 'done'
      if (res?.steps?.[s]?.log) {
        pipelineLog.value += `[${s}] ${res.steps[s].log.slice(0, 200)}\n`
      }
      if (res?.status === 'success') {
        pipelineLog.value += `[${s}] ${JSON.stringify(res)}\n`
      }
      ElMessage.success(`${s} 完成`)
    } catch (e: any) {
      pipelineStatus[s] = 'failed'
      ElMessage.error(`${s} 失败: ${e.message || ''}`)
      if (step !== 'all') break
    }
  }

  running.value = null
  // 完成后刷新统计
  refreshStats()
}

async function refreshStats() {
  try {
    const [wl, tr] = await Promise.all([getWhitelist(), listTracks()])
    const wlCount = Array.isArray(wl) ? wl.length : 0
    const trackItems = tr?.items || []
    stats.value.stocks = trackItems.reduce((s: number, t: any) => s + (t.stock_count || 0), 0)
    stats.value.whitelist = wlCount
    stats.value.models = trackItems.length || 0
  } catch {}
}

function toggleDetail(name: string) {
  if (expanded.value.has(name)) expanded.value.delete(name)
  else expanded.value.add(name)
}

// ── 中文名映射 ──
const CN_NAMES: Record<string, string> = {
  rsi_6: '6日RSI', rsi_24: '24日RSI', stoch_k: '随机K', stoch_d: '随机D', stoch_j: '随机J',
  willr_14: '威廉指标', roc_20: '20日变动率', roc_60: '60日变动率',
  ao: '动量震荡', ppo: 'PPO', ppo_signal: 'PPO信号',
  sma_5: '5日均线', sma_10: '10日均线', sma_20: '20日均线', sma_60: '60日均线',
  sma_dev_5: '5日偏离度', sma_dev_20: '20日偏离度',
  ema_20: '20日指数均线', ema_60: '60日指数均线',
  ema_20_dev: '20日指数偏离', ema_60_dev: '60日指数偏离',
  macd: 'MACD快线', macd_signal: 'MACD信号线', macd_diff: 'MACD柱',
  adx: 'ADX趋势强度', adx_pos: '+DI', adx_neg: '-DI',
  aroon_up: '阿隆上升', aroon_down: '阿隆下降',
  cci_20: '20日CCI', cci_60: '60日CCI', trix: 'TRIX',
  atr_5: '5日ATR', atr_14: '14日ATR', atr_5_pct: 'ATR百分比',
  bb_upper_20: '布林上轨', bb_lower_20: '布林下轨', bb_width_20: '布林带宽', bb_position_20: '布林位置',
  donchian_upper_20: '通道上轨', donchian_lower_20: '通道下轨', donchian_width_20: '通道宽度',
  ulcer: 'Ulcer回撤',
  obv: 'OBV能量潮', ad: 'A/D资金流', cmf_20: '资金流指标',
  emv: '简易波动', fi: '力量指数', mfi: '资金流量',
  vpt: '量价趋势', vwap: '均价线',
  volume_5d_ma: '5日均量', volume_ratio_5d: '5日量比', volume_20d_ma: '20日均量', volume_ratio_20d: '20日量比',
  amount_5d_ma: '5日均额', amount_ratio_5d: '5日额比',
  ret_skew_20: '收益偏度', ret_kurt_20: '收益峰度', ret_quantile_80: '80%分位', ret_quantile_20: '20%分位',
  consec_up: '连涨天数', consec_down: '连跌天数',
  sharpe_20: '20日夏普比', vp_corr_20: '量价相关',
  price_pos_20d: '价格位置', high_pct_20d: '距高点比例',
}

function getCnName(name: string): string {
  return CN_NAMES[name] || name
}

// ── 计算公式 ──
const FORMULAS: Record<string, string> = {
  rsi_6: 'RSI = 100 - 100/(1 + RS)，其中 RS = 6日内平均涨幅/6日内平均跌幅',
  rsi_24: 'RSI = 100 - 100/(1 + RS)，24日周期，比6日RSI更平滑',
  stoch_k: '%K = (收盘价 - 9日最低) / (9日最高 - 9日最低) × 100',
  stoch_d: '%D = %K的3日简单移动平均（%K的平滑线）',
  stoch_j: 'J = 3×%K - 2×%D，超买>100，超卖<0',
  willr_14: '%R = (14日最高 - 收盘) / (14日最高 - 14日最低) × -100',
  roc_20: 'ROC = (今收 / 20日前收盘 - 1) × 100',
  roc_60: 'ROC = (今收 / 60日前收盘 - 1) × 100',
  sma_5: 'SMA = 最近5日收盘价之和 / 5',
  sma_10: 'SMA = 最近10日收盘价之和 / 10',
  sma_20: 'SMA = 最近20日收盘价之和 / 20',
  sma_60: 'SMA = 最近60日收盘价之和 / 60',
  sma_dev_5: '(收盘价 - 5日均线) / 5日均线 × 100%',
  macd: 'MACD = 12日EMA - 26日EMA（指数移动平均）',
  macd_signal: 'MACD信号线 = MACD的9日EMA',
  adx: 'ADX = 100 × |+DI - -DI| / (+DI + -DI) 的14日平滑移动平均',
  cci_20: 'CCI = (TP - TP的20日SMA) / (0.015 × TP的平均绝对偏差)，TP = (H+L+C)/3',
  atr_14: 'ATR = 14日真实波幅均值，真实波幅=MAX(H-L, |H-前收|, |L-前收|)',
  bb_upper_20: '上轨 = 20日均线 + 2 × 20日标准差',
  bb_lower_20: '下轨 = 20日均线 - 2 × 20日标准差',
  obv: 'OBV = 累计(成交量 × 方向)，方向=今收>昨收?+1:-1',
  mfi: 'MFI = 100 - 100/(1 + 正资金流/负资金流)，14日周期',
  vwap: 'VWAP = Σ(成交价 × 成交量) / Σ(成交量)',
}

// ── 解读方法 ──
const INTERPRET: Record<string, string> = {
  rsi_6: 'RSI>70 → 超买，可能回调，谨慎追高。RSI<30 → 超卖，可能反弹，关注买入机会',
  rsi_24: '比6日RSI更平滑，适合判断中期趋势方向。>70超买<30超卖',
  stoch_k: 'K线向下突破80 → 卖出信号。K线向上突破20 → 买入信号',
  stoch_d: 'D线>80并拐头向下 → 卖出。D线<20并拐头向上 → 买入',
  willr_14: '值>-20 → 超买（短期见顶风险）。值<-80 → 超卖（短期见底机会）',
  roc_20: 'ROC上穿0轴 → 价格加速上涨，多头信号。ROC下穿0轴 → 空头信号',
  sma_5: '超短期趋势线。收盘>5MA → 短期强势。收盘<5MA → 短期弱势',
  sma_dev_5: '偏离>+5% → 可能回调。偏离<-5% → 可能反弹。偏离越大回归概率越大',
  macd: 'MACD>0 → 多头市场。MACD<0 → 空头市场。MACD向上突破信号线=金叉买入',
  adx: 'ADX>25 → 趋势行情（顺势交易）。ADX<20 → 震荡行情（高抛低吸）',
  cci_20: 'CCI>+100 → 超买，可能回调。CCI<-100 → 超卖，可能反弹',
  atr_14: 'ATR越大 → 波动越剧烈，适合设宽止损。ATR越小 → 行情平淡',
  bb_upper_20: '价格触及上轨 → 超买压力，可能回调至中轨',
  bb_lower_20: '价格触及下轨 → 超卖支撑，可能反弹至中轨',
  obv: 'OBV与价格同步新高 → 上涨趋势健康。OBV背离价格 → 趋势可能反转',
  mfi: 'MFI>80 → 超买（回调风险）。MFI<20 → 超卖（反弹机会）',
  vwap: '价格>VWAP → 多头主导。价格<VWAP → 空头主导。机构大单多参考VWAP',
}

function getFormula(name: string): string {
  return FORMULAS[name] || '来自 Alphalens 筛选出的有效预测因子'
}

function getInterpretation(name: string): string {
  return INTERPRET[name] || 'IC值为正: 因子值越大，未来收益越高。IC值为负: 因子值越小，未来收益越高'
}

// ── 分类 ──
const categories = [
  { value: 'momentum', label: '⚡ 动量类' },
  { value: 'trend', label: '📈 趋势类' },
  { value: 'volatility', label: '🌊 波动率类' },
  { value: 'volume', label: '📊 量能类' },
  { value: 'statistical', label: '📐 统计类' },
  { value: 'track_specific', label: '🏷️ 赛道专属' },
]

const filteredFactors = computed(() => {
  let list = factors.value
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    list = list.filter(f => f.factor_name.toLowerCase().includes(q) || getCnName(f.factor_name).includes(q))
  }
  if (selectedCategory.value) {
    list = list.filter(f => (f.category || f.factor_type) === selectedCategory.value)
  }
  return list.sort((a, b) => Math.abs(b.ic_mean) - Math.abs(a.ic_mean))
})

onMounted(async () => {
  // 加载因子数据
  try {
    const res = await getWhitelist()
    factors.value = Array.isArray(res) ? res : []
  } catch {
    factors.value = []
  }

  // 加载黑名单
  try {
    const res = await getBlacklist()
    blacklistFactors.value = Array.isArray(res) ? res : []
  } catch {
    blacklistFactors.value = []
  }

  // 加载统计
  try {
    const [wl, bl, tr] = await Promise.all([
      getWhitelist(),
      getBlacklist(),
      listTracks(),
    ])
    const wlCount = Array.isArray(wl) ? wl.length : 0
    const blCount = Array.isArray(bl) ? bl.length : 0
    const trackItems = tr?.items || []
    const stockCount = trackItems.reduce((s: number, t: any) => s + (t.stock_count || 0), 0)
    stats.value = {
      stocks: stockCount || 23,
      whitelist: wlCount || 75,
      blacklist: blCount || 72,
      finalFeatures: 54,
      models: trackItems.length || 4,
    }
  } catch {
    // fallback 使用默认值
  }
})
</script>

<style scoped>
.data-view {
  padding: 16px;
  min-height: 100%;
  background: #f5f7fa;
}

/* ── Pipeline Runner ── */
.pipeline-runner {
  background: #fff;
  border-radius: 10px;
  padding: 16px 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  margin-bottom: 16px;
}

.pr-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.pr-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pr-title-icon {
  font-size: 18px;
}

.pr-title {
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
}

.pr-subtitle {
  font-size: 11px;
  color: #94a3b8;
}

.pr-steps {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.pr-step {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-radius: 6px;
  transition: background 0.15s;
}

.pr-step:hover {
  background: #f8fafc;
}

.pr-step.pr-step-running {
  background: #eff6ff;
}

.pr-step.pr-step-done {
  background: #f0fdf4;
}

.pr-step-indicator {
  width: 24px;
  text-align: center;
  flex-shrink: 0;
}

.pr-dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
}

.pr-dot-idle {
  background: #f1f5f9;
  color: #cbd5e1;
  border: 1px solid #e2e8f0;
}

.pr-dot-running {
  background: #eff6ff;
  color: #3b82f6;
  border: 1px solid #93c5fd;
  animation: spin 1.2s linear infinite;
}

.pr-dot-done {
  background: #dcfce7;
  color: #16a34a;
  border: 1px solid #86efac;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.pr-step-info {
  flex: 1;
  min-width: 0;
}

.pr-step-name {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.pr-step-desc {
  font-size: 11px;
  color: #94a3b8;
}

.pr-step-action {
  flex-shrink: 0;
}

.pr-log {
  margin-top: 10px;
  padding: 10px 14px;
  background: #1e293b;
  border-radius: 6px;
  max-height: 120px;
  overflow-y: auto;
}

.pr-log pre {
  margin: 0;
  font-size: 11px;
  color: #e2e8f0;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'SF Mono', monospace;
  line-height: 1.5;
}

/* ── 流水线日志 ── */
.pipeline-logs {
  margin-bottom: 16px;
  background: #fff;
  border-radius: 8px;
  padding: 14px 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.pl-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.pl-title {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}

.pl-empty {
  color: #909399;
  font-size: 12px;
  text-align: center;
  padding: 12px 0;
}

.pl-item {
  border-bottom: 1px solid #f0f0f0;
  padding: 8px 0;
}

.pl-item:last-child {
  border-bottom: none;
}

.pl-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.pl-item-time {
  color: #909399;
  font-size: 11px;
}

.pl-item-info {
  color: #909399;
  font-size: 11px;
}

.pl-item-hash {
  color: #909399;
  font-size: 11px;
  font-family: 'SF Mono', monospace;
  margin-left: auto;
}

.pl-item-body {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding-left: 4px;
}

.pl-metric {
  font-size: 12px;
  color: #606266;
  background: #f5f7fa;
  padding: 2px 8px;
  border-radius: 4px;
  white-space: nowrap;
}

/* ── 统计卡片行 ── */
.stats-row {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  flex: 1;
  background: #fff;
  border-radius: 8px;
  padding: 14px 16px;
  text-align: center;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #303133;
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

/* ── 两栏布局 ── */
.content-row {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.pipeline-col {
  width: 260px;
  flex-shrink: 0;
}

.factor-col {
  flex: 1;
  min-width: 0;
}

/* ── 因子详情面板 ── */
.factor-detail-panel {
  background: #fff;
  border-radius: 10px;
  padding: 16px 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.factor-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.factor-search {
  flex: 1;
}

.category-select {
  width: 140px;
}

/* ── 因子网格 ── */
.factor-grid {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.factor-detail-card {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 8px 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.factor-detail-card:hover {
  border-color: #409eff;
  box-shadow: 0 1px 4px rgba(64,158,255,0.1);
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-info {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
}

.card-cn-name {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
}

.card-en-name {
  font-size: 11px;
  color: #c0c4cc;
  font-family: 'SF Mono', monospace;
}

.card-metrics-top {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.card-ir {
  font-size: 11px;
  color: #909399;
}

/* ── 展开详情 ── */
.card-detail {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #ebeef5;
}

.detail-section {
  margin-bottom: 6px;
}

.detail-label {
  font-size: 11px;
  font-weight: 600;
  color: #909399;
  margin-bottom: 2px;
}

.detail-value {
  font-size: 12px;
  color: #606266;
  line-height: 1.5;
}

.formula-box {
  background: #f8f9fa;
  border: 1px solid #eee;
  border-radius: 4px;
  padding: 6px 8px;
  font-family: 'SF Mono', monospace;
  font-size: 11px;
  color: #303133;
}

.ic-bar-bg {
  margin-top: 4px;
  height: 5px;
  background: #f0f2f5;
  border-radius: 3px;
  overflow: hidden;
}

.ic-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s;
}

/* ── 筛选流程 ── */
.criteria-card {
  background: #fff;
  border-radius: 10px;
  padding: 20px 24px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  margin-bottom: 16px;
}

.criteria-title {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 14px;
}

.criteria-flow { display: flex; flex-direction: column; gap: 10px; }

.c-step {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.c-num {
  width: 24px; height: 24px;
  background: #3b82f6; color: #fff;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700;
  flex-shrink: 0;
}

.c-body { flex: 1; }
.c-body strong { font-size: 13px; color: #1e293b; display: block; margin-bottom: 2px; }
.c-body span { font-size: 12px; color: #64748b; line-height: 1.5; }

.criteria-desc {
  font-size: 13px;
  color: #475569;
  line-height: 1.6;
}

.criteria-desc p { margin: 0 0 8px; }
.criteria-desc ul { margin: 0; padding-left: 20px; }
.criteria-desc li { margin-bottom: 4px; }
.criteria-desc code {
  font-size: 11px;
  background: #f1f5f9;
  padding: 1px 5px;
  border-radius: 3px;
  font-family: 'SF Mono', monospace;
}

/* ── 黑名单 ── */
.blacklist-card {
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  overflow: hidden;
  margin-bottom: 16px;
}

.bl-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 20px;
  border-bottom: 1px solid #f1f5f9;
}

.bl-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  flex: 1;
}

.bl-header .el-icon {
  font-size: 14px;
  color: #94a3b8;
  transition: transform 0.2s;
}

.bl-header .rot { transform: rotate(90deg); }

.bl-body {
  padding: 8px 16px;
  max-height: 400px;
  overflow-y: auto;
}

.bl-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  border-bottom: 1px solid #f8fafc;
}

.bl-name {
  font-size: 12px;
  font-family: 'SF Mono', monospace;
  color: #475569;
}
</style>
