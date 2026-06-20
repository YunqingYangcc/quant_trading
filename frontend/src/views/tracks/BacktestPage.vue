<template>
  <div class="backtest-page">
    <div class="page-header">
      <h2>📊 回测绩效</h2>
      <div class="header-actions">
        <el-select v-model="selectedStrategy" size="small" placeholder="选择策略" style="width:200px;margin-right:8px" @change="onStrategyChange">
          <el-option-group label="── 基线策略 ──">
            <el-option v-for="s in baselineStrats" :key="s.key" :label="s.name" :value="s.key" />
          </el-option-group>
          <el-option-group label="── 动量策略 ──">
            <el-option v-for="s in momentumStrats" :key="s.key" :label="s.name" :value="s.key" />
          </el-option-group>
          <el-option-group label="── AI 策略 ──">
            <el-option v-for="s in aiStrats" :key="s.key" :label="s.name" :value="s.key" />
          </el-option-group>
        </el-select>
        <el-button type="primary" size="small" @click="runStrategyBt" :loading="strategyRunning">
          {{ strategyRunning ? '回测中...' : '▶ 运行策略' }}
        </el-button>
        <el-button size="small" @click="loadBacktest" :loading="loadingReport">刷新</el-button>
      </div>
    </div>

    <!-- 策略对比表 -->
    <div v-if="strategyResults.length > 0" class="section-card" style="margin-bottom:16px">
      <div class="section-header">
        <div class="sh-left">
          <div class="sh-icon">🏆</div>
          <div>
            <div class="sh-title">策略对比</div>
            <div class="sh-sub">基线 vs 所选策略</div>
          </div>
        </div>
      </div>
      <table class="compare-table">
        <thead>
          <tr>
            <th>策略</th>
            <th>类型</th>
            <th>夏普</th>
            <th>总收益</th>
            <th>年化收益</th>
            <th>最大回撤</th>
            <th>胜率</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in strategyResults" :key="i" :class="{ 'row-best': i === bestIdx }">
            <td>
              <span v-if="i === bestIdx" class="best-badge">⭐</span>
              {{ r.name }}
            </td>
            <td><el-tag size="small" :type="r.type === 'baseline' ? '' : 'primary'" effect="plain">{{ r.type }}</el-tag></td>
            <td :class="scoreClass(r.sharpe_ratio, 1.2)">{{ r.sharpe_ratio?.toFixed(3) }}</td>
            <td :class="scoreClass(r.total_return, 0)">{{ r.total_return?.toFixed(1) }}%</td>
            <td :class="scoreClass(r.annual_return, 0)">{{ r.annual_return?.toFixed(1) }}%</td>
            <td :class="scoreClass(-r.max_drawdown, -25, true)">{{ r.max_drawdown?.toFixed(1) }}%</td>
            <td>{{ r.win_rate?.toFixed(1) }}%</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 个股回测 -->
    <div class="section-card" style="border-left:3px solid #3b82f6">
      <div class="section-header">
        <div class="sh-left">
          <div class="sh-icon" style="background:linear-gradient(135deg,#3b82f6,#2563eb)">📈</div>
          <div>
            <div class="sh-title">个股回测</div>
            <div class="sh-sub">选一只股票，调参数，看胜率</div>
          </div>
        </div>
        <el-tag size="small" type="primary" effect="dark">NEW</el-tag>
      </div>

      <div class="single-bt-form">
        <div class="sbf-row">
          <div class="sbf-item">
            <label class="form-label">股票</label>
            <el-select v-model="singleStock" filterable placeholder="选股票" size="small" style="width:180px">
              <el-option v-for="s in stockList" :key="s.code" :label="`${s.name} (${s.code})`" :value="s.code" />
            </el-select>
          </div>
          <div class="sbf-item">
            <label class="form-label">策略</label>
            <el-select v-model="singleStrategy" size="small" style="width:160px">
              <el-option label="20日趋势跟踪" value="momentum_20d" />
              <el-option label="60日趋势跟踪" value="momentum_60d" />
            </el-select>
          </div>
          <div class="sbf-item">
            <label class="form-label">
              动量周期
              <el-tooltip content="趋势判断的回看天数，越长越稳定但反应越慢" placement="top">
                <span class="label-help">?</span>
              </el-tooltip>
            </label>
            <el-slider v-model="singleLookback" :min="10" :max="120" :step="10" show-input size="small" style="width:100%" />
          </div>
          <div class="sbf-item">
            <label class="form-label">
              止损%
              <el-tooltip content="单笔亏损超过此比例强制卖出。0=不止损" placement="top">
                <span class="label-help">?</span>
              </el-tooltip>
            </label>
            <el-input-number v-model="singleStopLoss" :min="0" :max="30" :step="5" size="small" style="width:90px" />
          </div>
          <div class="sbf-item sbf-action">
            <el-button type="primary" size="small" @click="runSingleBt" :loading="singleRunning">
              {{ singleRunning ? '回测中...' : '▶ 跑回测' }}
            </el-button>
          </div>
        </div>
      </div>

      <!-- 个股回测结果 -->
      <div v-if="singleResult" class="single-result">
        <div class="sr-header">
          <span class="sr-stock">{{ singleResult.metrics?.stock_code }}</span>
          <el-tag :type="winRateLevel(singleResult.metrics?.win_rate).type" size="small" effect="dark">
            {{ winRateLevel(singleResult.metrics?.win_rate).icon }}
            胜率 {{ singleResult.metrics?.win_rate?.toFixed(1) }}%
            {{ winRateLevel(singleResult.metrics?.win_rate).label }}
          </el-tag>
        </div>
        <div class="sr-metrics">
          <div class="srm-card">
            <div class="srm-value" :style="{color:winColor(singleResult.metrics?.win_rate)}">{{ singleResult.metrics?.win_rate?.toFixed(1) }}%</div>
            <div class="srm-label">胜率</div>
          </div>
          <div class="srm-card">
            <div class="srm-value" :style="{color:(singleResult.metrics?.total_return||0)>=0?'#16a34a':'#dc2626'}">{{ singleResult.metrics?.total_return?.toFixed(1) }}%</div>
            <div class="srm-label">总收益</div>
          </div>
          <div class="srm-card">
            <div class="srm-value">{{ singleResult.metrics?.sharpe?.toFixed(3) }}</div>
            <div class="srm-label">夏普</div>
          </div>
          <div class="srm-card">
            <div class="srm-value" style="color:#dc2626">{{ singleResult.metrics?.max_drawdown?.toFixed(1) }}%</div>
            <div class="srm-label">最大回撤</div>
          </div>
          <div class="srm-card">
            <div class="srm-value">{{ singleResult.metrics?.total_trades }}</div>
            <div class="srm-label">交易次数</div>
          </div>
        </div>

        <!-- 指导建议 -->
        <div class="sr-guide">
          <div class="srg-title">💡 优化建议</div>
          <div class="srg-text">{{ getGuidance(singleResult.metrics) }}</div>
        </div>

        <!-- 最近交易 -->
        <div v-if="singleResult.trades?.length" class="sr-trades">
          <div class="srt-title">最近交易</div>
          <div class="srt-row" v-for="(t,i) in singleResult.trades.slice(-10).reverse()" :key="i">
            <span class="srt-date">{{ t.date }}</span>
            <el-tag :type="t.type==='buy'?'success':'danger'" size="small" effect="plain">{{ t.type==='buy'?'买入':'卖出' }}</el-tag>
            <span class="srt-price">¥{{ t.price }}</span>
            <span v-if="t.profit" :class="t.profit>=0?'srt-profit':'srt-loss'">{{ t.profit>=0?'+':'' }}{{ t.profit.toFixed(0) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 回测参数配置 -->
    <div class="section-card">
      <div class="section-header">
        <div class="sh-left">
          <div class="sh-icon">⚙️</div>
          <div>
            <div class="sh-title">回测参数配置</div>
            <div class="sh-sub">调整策略参数后点击运行，每次运行覆盖前次结果</div>
          </div>
        </div>
        <el-tag size="small" type="info" effect="plain">可自定义</el-tag>
      </div>

      <!-- 预设方案 -->
      <div class="preset-row">
        <span class="preset-label">快速预设</span>
        <el-radio-group v-model="presetKey" size="small" @change="applyPreset">
          <el-radio-button value="conservative">🛡️ 保守</el-radio-button>
          <el-radio-button value="balanced">⚖️ 均衡</el-radio-button>
          <el-radio-button value="aggressive">🚀 激进</el-radio-button>
        </el-radio-group>
        <el-tag v-if="presetKey !== 'custom'" size="small" type="success" effect="plain" class="preset-tag">推荐</el-tag>
        <el-tag v-else size="small" type="warning" effect="plain" class="preset-tag">已修改</el-tag>
      </div>

      <div class="bt-form">
        <div class="form-grid">
          <!-- 资金 -->
          <div class="form-group">
            <div class="fg-label">💰 资金配置</div>
            <div class="fg-fields">
              <div class="form-item">
                <label class="form-label">
                  初始资金
                  <el-tooltip content="回测起点的可用资金" placement="top">
                    <span class="label-help">?</span>
                  </el-tooltip>
                </label>
                <el-input-number v-model="btParams.initial_capital" :min="10000" :step="50000" :max="10000000" controls-position="right" style="width:100%" />
              </div>
            </div>
          </div>

          <!-- 选股 -->
          <div class="form-group">
            <div class="fg-label">📋 选股策略</div>
            <div class="fg-fields">
              <div class="form-item">
                <label class="form-label">每赛道 Top-N</label>
                <el-input-number v-model="btParams.top_n" :min="1" :max="10" controls-position="right" style="width:100%" />
              </div>
              <div class="form-item">
                <label class="form-label">调仓频率</label>
                <el-radio-group v-model="btParams.rebalance_freq" class="freq-group">
                  <el-radio-button value="W">📅 周频</el-radio-button>
                  <el-radio-button value="M">📆 月频</el-radio-button>
                </el-radio-group>
              </div>
            </div>
          </div>

          <!-- 风控 -->
          <div class="form-group">
            <div class="fg-label">🛡️ 风控限制</div>
            <div class="fg-fields">
              <div class="form-item">
                <label class="form-label">单票上限</label>
                <el-slider v-model="btParams.max_single_stock" :min="5" :max="50" :step="5" show-input>
                  <template #append>%</template>
                </el-slider>
              </div>
              <div class="form-item">
                <label class="form-label">单赛道上限</label>
                <el-slider v-model="btParams.max_single_track" :min="10" :max="80" :step="5" show-input>
                  <template #append>%</template>
                </el-slider>
              </div>
            </div>
          </div>
        </div>

        <!-- 操作栏 -->
        <div class="action-bar">
          <div class="locked-hint">
            <el-tag size="small" type="warning" effect="plain">🔒 锁定</el-tag>
            <span>滑点 0.1% · 手续费万三 · 涨跌停限制</span>
          </div>
          <el-button type="primary" size="default" @click="runBacktest" :loading="running" :icon="CaretRight" class="run-btn">
            {{ running ? '回测运行中...' : '开始回测' }}
          </el-button>
        </div>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error-card">
      <el-alert :title="error" type="warning" :closable="false" show-icon />
    </div>

    <!-- 回测结果 -->
    <template v-if="report">
      <!-- 回测记录 -->
      <div class="report-header">
        <div class="rh-left">
          <div class="rh-icon">📋</div>
          <div>
            <div class="rh-title">回测记录</div>
            <div class="rh-sub">{{ report.metadata?.run_at || '' }} 执行</div>
          </div>
        </div>
        <el-tag size="small" type="success" effect="plain" v-if="report.metadata?.trade_count">
          {{ report.metadata.trade_count }} 个交易日
        </el-tag>
      </div>

      <!-- 上下文信息：参数 + 赛道 + 时间 -->
      <div class="context-grid">
        <div class="ctx-card">
          <div class="ctx-title">🎯 策略参数</div>
          <div class="ctx-rows">
            <div class="ctx-row" v-for="(v, k) in report.params || {}" :key="k">
              <span class="ctx-key">{{ k }}</span>
              <span class="ctx-val">{{ v }}</span>
            </div>
          </div>
        </div>

        <div class="ctx-card">
          <div class="ctx-title">📂 覆盖赛道</div>
          <div class="ctx-rows">
            <div v-if="report.metadata?.tracks?.length" v-for="t in report.metadata.tracks" :key="t.name" class="ctx-row">
              <span class="ctx-key">{{ t.display_name }}</span>
              <span class="ctx-val">{{ t.stock_count }} 只</span>
            </div>
            <div v-else class="ctx-row">
              <span class="ctx-val" style="color:#94a3b8">暂无赛道数据</span>
            </div>
          </div>
        </div>

        <div class="ctx-card">
          <div class="ctx-title">📅 回测区间</div>
          <div class="ctx-rows">
            <div class="ctx-row">
              <span class="ctx-key">开始</span>
              <span class="ctx-val">{{ report.metadata?.date_start || '-' }}</span>
            </div>
            <div class="ctx-row">
              <span class="ctx-key">结束</span>
              <span class="ctx-val">{{ report.metadata?.date_end || '-' }}</span>
            </div>
            <div class="ctx-row">
              <span class="ctx-key">锁定参数</span>
              <span class="ctx-val" style="font-size:11px;color:#94a3b8">
                滑点 0.1% / 万三 / 涨跌停限制
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 绩效指标 -->
      <div class="metrics-section-title">📊 绩效指标</div>
      <div class="metrics-row">
        <div class="metric-card" v-for="m in metrics" :key="m.label">
          <div class="metric-value" :style="{ color: m.color }">{{ m.value }}</div>
          <div class="metric-label">{{ m.label }}</div>
          <div class="metric-pass" v-if="m.pass !== undefined">
            <el-tag :type="m.pass ? 'success' : 'danger'" size="small" effect="plain">
              {{ m.pass ? '✅ 达标' : '❌ 未达标' }}
            </el-tag>
          </div>
        </div>
      </div>
    </template>

    <div v-if="!report && !loadingReport && !error" class="empty-card">
      <el-empty description="点击「开始回测」运行首次回测">
        <el-button type="primary" size="small" @click="runBacktest" :loading="running">
          开始回测
        </el-button>
      </el-empty>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { CaretRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getBacktestReport, runBacktest as runBacktestApi, listStrategies, runStrategyBacktest, runSingleStockBacktest, listTracks } from '@/api/track'

const loadingReport = ref(false)
const running = ref(false)
const error = ref('')
const report = ref<any>(null)

// ── 策略选择 ──
const selectedStrategy = ref('momentum_20d')
const strategyRunning = ref(false)
const allStrategies = ref<any[]>([])
const strategyResults = ref<any[]>([])

const baselineStrats = computed(() => allStrategies.value.filter(s => s.type === 'baseline'))
const momentumStrats = computed(() => allStrategies.value.filter(s => s.type === 'momentum'))
const aiStrats = computed(() => allStrategies.value.filter(s => s.type === 'ai'))

const bestIdx = computed(() => {
  if (strategyResults.value.length === 0) return -1
  return strategyResults.value.reduce((best, r, i) => (r.sharpe_ratio || 0) > (strategyResults.value[best]?.sharpe_ratio || 0) ? i : best, 0)
})

function scoreClass(value: number, threshold: number, inverted = false) {
  if (value == null || isNaN(value)) return ''
  const ok = inverted ? value > threshold : value >= threshold
  return ok ? 'score-good' : 'score-bad'
}

async function loadStrategies() {
  try {
    allStrategies.value = await listStrategies()
  } catch { /* ignore */ }
}

function onStrategyChange() {
  // 切换策略时重置结果
}

async function runStrategyBt() {
  strategyRunning.value = true
  try {
    // 跑所选策略
    const result = await runStrategyBacktest(selectedStrategy.value)
    result.type = allStrategies.value.find(s => s.key === selectedStrategy.value)?.type || 'unknown'
    
    // 跑基线
    const promises = ['equal_weight', 'momentum_20d']
      .filter(k => k !== selectedStrategy.value)
      .map(k => runStrategyBacktest(k).then(r => ({ ...r, type: allStrategies.value.find(s => s.key === k)?.type || 'baseline', isBaseline: true })))
    
    const baselines = await Promise.all(promises)
    strategyResults.value = [result, ...baselines]
      .sort((a, b) => (b.sharpe_ratio || 0) - (a.sharpe_ratio || 0))
    
    ElMessage.success('策略回测完成')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '回测失败')
  } finally {
    strategyRunning.value = false
  }
}

const btParams = reactive({
  initial_capital: 100000,
  top_n: 3,
  rebalance_freq: 'W',
  max_single_stock: 20,
  max_single_track: 50,
})

const presetKey = ref('balanced')

const PRESETS: Record<string, Partial<typeof btParams>> = {
  conservative: { initial_capital: 50000, top_n: 2, rebalance_freq: 'M', max_single_stock: 10, max_single_track: 30 },
  balanced: { initial_capital: 100000, top_n: 3, rebalance_freq: 'W', max_single_stock: 20, max_single_track: 50 },
  aggressive: { initial_capital: 200000, top_n: 5, rebalance_freq: 'W', max_single_stock: 30, max_single_track: 70 },
}

function applyPreset(key: string) {
  const p = PRESETS[key]
  if (!p) return
  Object.assign(btParams, p)
}

const metrics = computed(() => {
  if (!report.value) return []
  const r = report.value.metrics || (Array.isArray(report.value) ? report.value[0] : report.value) || {}
  const params = report.value.params || {}
  return [
    { label: '初始资金', value: `¥${(params.initial_capital || 100000).toLocaleString()}`, color: '#909399' },
    { label: '最终净值', value: `¥${(r.final_value || 0).toLocaleString()}`, color: (r.total_return || 0) >= 0 ? '#67c23a' : '#f56c6c' },
    { label: '总收益', value: `${r.total_return || 0}%`, color: (r.total_return || 0) >= 0 ? '#67c23a' : '#f56c6c' },
    { label: '年化收益', value: `${r.annual_return || 0}%`, color: (r.annual_return || 0) >= 0 ? '#67c23a' : '#f56c6c' },
    { label: '夏普比率', value: r.sharpe_ratio?.toFixed(3) || '-', color: (r.sharpe_ratio || 0) >= 1.2 ? '#67c23a' : '#f56c6c', pass: (r.sharpe_ratio || 0) >= 1.2 },
    { label: '年化波动', value: `${r.annual_volatility || 0}%`, color: '#e6a23c' },
    { label: '最大回撤', value: `${r.max_drawdown || 0}%`, color: (r.max_drawdown || 100) < 25 ? '#67c23a' : '#f56c6c', pass: (r.max_drawdown || 100) < 25 },
    { label: '胜率', value: `${r.win_rate || 0}%`, color: (r.win_rate || 0) >= 50 ? '#67c23a' : '#e6a23c' },
    { label: '交易次数', value: r.total_trades || 0, color: '#909399' },
  ]
})

async function runBacktest() {
  running.value = true
  error.value = ''
  try {
    report.value = await runBacktestApi({
      initial_capital: btParams.initial_capital,
      top_n: btParams.top_n,
      rebalance_freq: btParams.rebalance_freq,
      max_single_stock: btParams.max_single_stock / 100,
      max_single_track: btParams.max_single_track / 100,
    })
    ElMessage.success('回测完成')
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '回测执行失败'
    report.value = null
  } finally {
    running.value = false
  }
}

async function loadBacktest() {
  loadingReport.value = true
  error.value = ''
  try {
    report.value = await getBacktestReport()
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '加载失败'
    report.value = null
  } finally {
    loadingReport.value = false
  }
}

onMounted(() => { loadBacktest(); loadStrategies(); loadStockList() })

// ── 个股回测 ──
const singleStock = ref('002371.SZ')
const singleStrategy = ref('momentum_20d')
const singleLookback = ref(20)
const singleStopLoss = ref(0)
const singleRunning = ref(false)
const singleResult = ref<any>(null)
const stockList = ref<any[]>([])

async function loadStockList() {
  try {
    const res: any = await listTracks()
    const stocks: any[] = []
    const seen = new Set<string>()
    for (const track of res?.items || res || []) {
      for (const s of track.stocks || []) {
        if (!seen.has(s.code)) {
          seen.add(s.code)
          stocks.push(s)
        }
      }
    }
    stockList.value = stocks
  } catch { /* ignore */ }
}

async function runSingleBt() {
  singleRunning.value = true
  try {
    singleResult.value = await runSingleStockBacktest(singleStock.value, singleStrategy.value, singleLookback.value, singleStopLoss.value)
    ElMessage.success(`${singleStock.value} 回测完成`)
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '回测失败')
  } finally {
    singleRunning.value = false
  }
}

function winRateLevel(rate: number) {
  if (rate == null || isNaN(rate)) return { icon: '❓', label: '', type: '' as any }
  if (rate >= 60) return { icon: '🔥', label: '优秀', type: 'success' as any }
  if (rate >= 55) return { icon: '✅', label: '良好', type: 'success' as any }
  if (rate >= 50) return { icon: '⚠️', label: '接近随机', type: 'warning' as any }
  return { icon: '❌', label: '不如抛硬币', type: 'danger' as any }
}

function winColor(rate: number) {
  if (rate >= 60) return '#16a34a'
  if (rate >= 55) return '#65a30d'
  if (rate >= 50) return '#e6a23c'
  return '#dc2626'
}

function getGuidance(metrics: any) {
  if (!metrics) return '请先运行回测'
  const wr = metrics.win_rate || 0
  const dd = Math.abs(metrics.max_drawdown || 0)
  const ret = metrics.total_return || 0
  const trades = metrics.total_trades || 0
  
  // 决策树
  if (trades < 10) return '交易次数太少（<10），加长回测周期或放宽入场条件（减小动量周期）'
  if (wr < 50) return '胜率 < 50%，趋势跟踪对该股无效。建议：①换逆向策略；②换其他股票；③该股可能不适合趋势交易'
  if (wr >= 50 && wr < 55) return '胜率勉强 > 50%，但接近随机。试试加止损（-10%~-15%）过滤掉大亏交易，看胜率是否改善'
  if (wr >= 55 && dd > 30) return '胜率不错但回撤太大！加止损控制单笔亏损，建议 -10% 止损'
  if (wr >= 55 && ret < 0) return '胜率高但总收益为负？盈亏比有问题——每次赢的少亏的多。试试加止盈（+20%）锁定利润'
  if (wr >= 60) return '👏 胜率 > 60%，策略有效！下一步：①加仓（调大资金比例）；②在其他同类股票上验证是否通用'
  return '调整参数后再看'
}
</script>

<style scoped>
.backtest-page {
  min-height: 100%;
  padding: 24px 32px;
  background: #f5f7fa;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 22px;
  color: #1e293b;
}

.header-actions {
  display: flex;
  gap: 8px;
}

/* ── 配置卡片 ── */
.section-card {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.03);
  margin-bottom: 16px;
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.sh-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sh-icon {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  box-shadow: 0 2px 6px rgba(59,130,246,0.2);
}

.sh-title {
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
  line-height: 1.3;
}

.sh-sub {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.4;
  margin-top: 1px;
}

/* ── 预设 ── */
.preset-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 18px;
}

.preset-label {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  white-space: nowrap;
}

.preset-tag {
  margin-left: auto;
}

/* ── 表单网格 ── */
.bt-form {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
  margin-bottom: 18px;
}

.form-group {
  background: #fafbfc;
  border: 1px solid #eef2f6;
  border-radius: 10px;
  padding: 14px 16px;
}

.fg-label {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #eef2f6;
}

.fg-fields {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 12px;
  font-weight: 500;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 4px;
}

.label-help {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #e2e8f0;
  color: #64748b;
  font-size: 10px;
  font-weight: 700;
  cursor: help;
}

.freq-group {
  display: flex;
  width: 100%;
}

.freq-group :deep(.el-radio-button__inner) {
  width: 100%;
}

/* ── 操作栏 ── */
.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 8px;
}

.locked-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #94a3b8;
}

.run-btn {
  padding: 10px 28px;
  font-size: 14px;
  font-weight: 600;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(59,130,246,0.25);
}

/* ── 指标 ── */
.metrics-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.metric-card {
  background: #fff;
  border-radius: 8px;
  padding: 14px 12px;
  text-align: center;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.metric-value {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.2;
}

.metric-label {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}

.metric-pass {
  margin-top: 4px;
}

.error-card, .empty-card {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

/* ── 回测记录 ── */
.report-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.03);
  margin-bottom: 16px;
}

.rh-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.rh-icon {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #10b981, #059669);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  box-shadow: 0 2px 6px rgba(16,185,129,0.2);
}

.rh-title {
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
}

.rh-sub {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 1px;
}

/* ── 上下文网格 ── */
.context-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  margin-bottom: 20px;
}

.ctx-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
  border: 1px solid #f0f2f5;
}

.ctx-title {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0f2f5;
}

.ctx-rows {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ctx-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.ctx-key {
  color: #64748b;
}

.ctx-val {
  font-weight: 600;
  color: #1e293b;
}

.metrics-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 12px;
  padding-left: 4px;
}

/* ── 策略对比表 ── */
.compare-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.compare-table th {
  text-align: left;
  padding: 8px 12px;
  background: #f8fafc;
  color: #64748b;
  font-weight: 600;
  font-size: 11px;
  border-bottom: 2px solid #e2e8f0;
}

.compare-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #f1f5f9;
  color: #334155;
}

.compare-table tr.row-best {
  background: #fefce8;
}

.compare-table tr.row-best td:first-child {
  font-weight: 700;
}

.best-badge {
  margin-right: 4px;
}

.score-good {
  color: #16a34a;
  font-weight: 600;
}

.score-bad {
  color: #dc2626;
}

/* ── 个股回测 ── */
.single-bt-form { margin-bottom: 12px; }
.sbf-row {
  display: grid;
  grid-template-columns: 180px 150px 160px 100px auto;
  gap: 12px;
  align-items: end;
}

@media (max-width: 900px) {
  .sbf-row { grid-template-columns: 1fr 1fr; }
}

.sbf-item { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.sbf-action { justify-content: flex-end; }
.sbf-item :deep(.el-slider) { margin-bottom: 0; }
.sbf-item :deep(.el-slider__input) { width: 48px !important; }

.single-result { margin-top: 12px; }
.sr-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.sr-stock { font-weight: 700; font-size: 15px; color: #1e293b; }

.sr-metrics { display: flex; gap: 12px; margin-bottom: 10px; }
.srm-card { flex: 1; text-align: center; padding: 10px 8px; background: #f8fafc; border-radius: 8px; }
.srm-value { font-size: 20px; font-weight: 700; }
.srm-label { font-size: 10px; color: #94a3b8; margin-top: 2px; }

.sr-guide { background: #fefce8; border: 1px solid #fde68a; border-radius: 8px; padding: 10px 14px; margin-bottom: 10px; }
.srg-title { font-size: 13px; font-weight: 600; color: #92400e; margin-bottom: 4px; }
.srg-text { font-size: 12px; color: #78350f; line-height: 1.5; }

.sr-trades { max-height: 200px; overflow-y: auto; }
.srt-title { font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 4px; }
.srt-row { display: flex; gap: 12px; align-items: center; padding: 3px 0; font-size: 11px; border-bottom: 1px solid #f1f5f9; }
.srt-date { color: #94a3b8; width: 80px; font-family: monospace; }
.srt-price { color: #475569; }
.srt-profit { color: #16a34a; font-weight: 600; }
.srt-loss { color: #dc2626; font-weight: 600; }
</style>
