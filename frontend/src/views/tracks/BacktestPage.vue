<template>
  <div class="strategy-lab">
    <div class="page-header">
      <div class="ph-left">
        <div class="ph-icon">🔬</div>
        <div>
          <div class="ph-title">策略实验室</div>
          <div class="ph-sub">选策略 · 多策略对比 · 看交易拆解 · 沉淀实验记录</div>
        </div>
      </div>
      <div class="ph-actions">
        <el-radio-group v-model="mode" size="small" @change="onModeChange">
          <el-radio-button value="compare">策略对比</el-radio-button>
          <el-radio-button value="single">个股回测</el-radio-button>
        </el-radio-group>
        <el-button size="small" @click="showGuide = !showGuide" plain style="margin-left:8px">
          {{ showGuide ? '收起指南' : '📖 使用指南' }}
        </el-button>
      </div>
    </div>

    <!-- ── 使用指南 ── -->
    <div v-if="showGuide" class="guide-card">
      <div class="guide-grid">
        <div class="guide-item"><strong>①</strong> 左侧勾选想对比的策略（建议 2-4 个）</div>
        <div class="guide-item"><strong>②</strong> 选择赛道，调参数</div>
        <div class="guide-item"><strong>③</strong> 点击「一键对比」跑回测</div>
        <div class="guide-item"><strong>④</strong> 看净值曲线叠加、比指标、拆交易流水</div>
        <div class="guide-item"><strong>⑤</strong> 历史记录自动保存，随时回溯</div>
      </div>
    </div>

    <!-- ── 配置区 ── -->
    <div class="section-card">
      <div class="section-body">
        <div class="config-grid">
          <div v-if="mode === 'compare'" class="config-main">
            <div class="config-group">
              <label class="config-label">策略（多选）</label>
              <div class="strategy-checklist">
                <div v-for="g in strategyGroups" :key="g.label" class="strat-group">
                  <div class="strat-group-label">{{ g.label }}</div>
                  <el-checkbox-group v-model="selectedStrategies" class="strat-check-group">
                    <div v-for="s in g.strategies" :key="s.key" class="strat-check-item">
                      <el-checkbox :value="s.key" :label="s.name" size="small" />
                      <el-tooltip :content="s.description" placement="right">
                        <span class="label-help">?</span>
                      </el-tooltip>
                      <el-button text size="small" class="strat-detail-btn" @click="showStrategyDetail(s)">详情</el-button>
                    </div>
                  </el-checkbox-group>
                </div>
              </div>
            </div>
            <div class="config-group">
              <label class="config-label">赛道</label>
              <el-select v-model="selectedTrack" filterable placeholder="选择赛道" size="default" style="width:100%">
                <el-option v-for="t in trackList" :key="t.name" :label="t.display_name" :value="t.name" />
              </el-select>
            </div>
          </div>
          <div v-if="mode === 'single'" class="config-main">
            <div class="config-group">
              <label class="config-label">股票</label>
              <el-select v-model="singleStock" filterable placeholder="搜索股票..." size="default" style="width:100%">
                <el-option v-for="s in stockList" :key="s.code" :label="`${s.name} (${s.code})`" :value="s.code" />
              </el-select>
            </div>
            <div class="config-group">
              <label class="config-label">策略</label>
              <el-select v-model="selectedStrategy" filterable placeholder="选择策略" size="default" style="width:100%" @change="onStrategyChange">
                <el-option-group v-for="g in strategyGroups" :key="g.label" :label="g.label">
                  <el-option v-for="s in g.strategies" :key="s.key" :label="s.name" :value="s.key">
                    <span>{{ s.name }}</span>
                    <span class="strat-desc">{{ s.description }}</span>
                  </el-option>
                </el-option-group>
              </el-select>
            </div>
            <div class="config-group" v-if="selectedStrategy && !selectedStrategy.startsWith('equal_weight') && !selectedStrategy.startsWith('ai_scoring')">
              <label class="config-label config-check">
                <el-switch v-model="useAi" size="small" />
                <span>AI 增强</span>
                <el-tooltip content="用 AI 模型打分对策略选股结果二次排序" placement="top">
                  <span class="label-help">?</span>
                </el-tooltip>
                <el-tag v-if="useAi" size="small" type="primary" effect="light" style="margin-left:6px">推荐</el-tag>
              </label>
            </div>
          </div>

          <!-- 右侧：参数 -->
          <div class="config-params">
            <div class="param-row">
              <div class="param-item">
                <label class="param-label">
                  Top-N
                  <el-tooltip content="每次调仓买入几只" placement="top"><span class="label-help">?</span></el-tooltip>
                </label>
                <el-input-number v-model="params.topN" :min="1" :max="10" size="default" style="width:100%" />
              </div>
              <div class="param-item">
                <label class="param-label">调仓频率</label>
                <el-radio-group v-model="params.freq" size="small" style="width:100%">
                  <el-radio-button value="W">周频</el-radio-button>
                  <el-radio-button value="M">月频</el-radio-button>
                </el-radio-group>
              </div>
            </div>
            <div class="param-row">
              <div class="param-item">
                <label class="param-label">初始资金</label>
                <el-input-number v-model="params.capital" :min="10000" :max="10000000" :step="50000" size="default" style="width:100%" />
              </div>
              <div class="param-item">
                <label class="param-label">
                  止损%
                  <el-tooltip content="0=不止损" placement="top"><span class="label-help">?</span></el-tooltip>
                </label>
                <el-input-number v-model="params.stopLoss" :min="0" :max="30" :step="5" size="default" style="width:100%" />
              </div>
            </div>
            <div class="param-row">
              <div class="param-item">
                <label class="param-label">单票上限</label>
                <el-slider v-model="params.singleStockLimit" :min="5" :max="50" :step="5" show-input size="small" />
              </div>
              <div class="param-item">
                <label class="param-label">单赛道上限</label>
                <el-slider v-model="params.trackLimit" :min="10" :max="80" :step="10" show-input size="small" />
              </div>
            </div>
          </div>
        </div>

        <!-- 操作栏 -->
        <div class="action-bar">
          <div class="locked-info">
            <el-tag size="small" type="warning" effect="plain">锁定</el-tag>
            <span>滑点 0.1% · 手续费万三 · 涨跌停限制</span>
            <el-tag v-if="selectedStrategies.length" size="small" type="primary" effect="plain">
              已选 {{ selectedStrategies.length }} 个策略
            </el-tag>
          </div>
          <el-button
            type="primary"
            size="large"
            @click="mode === 'compare' ? runComparison() : runSingleStock()"
            :loading="running"
            :disabled="mode === 'compare' && selectedStrategies.length < 1"
            class="run-btn"
          >
            {{ running ? '回测中...' : mode === 'compare' ? '▶ 一键对比' : '▶ 开始回测' }}
          </el-button>
        </div>
      </div>
    </div>

    <!-- ── 进度/错误 ── -->
    <div v-if="error" class="error-card">
      <el-alert :title="error" type="error" :closable="false" show-icon />
    </div>
    <div v-if="running" class="progress-card">
      <el-progress :percentage="progressPct" :stroke-width="6" striped striped-flow :duration="6" />
      <div class="progress-text">正在运行 {{ progressStep }}...</div>
    </div>

    <!-- ── 对比结果（策略对比模式）── -->
    <div v-if="result && !running && mode === 'compare'">
      <!-- 净值曲线叠加 -->
      <div class="section-card">
        <div class="section-header">
          <div class="sh-left">
            <div class="sh-icon" style="background:linear-gradient(135deg,#10b981,#059669)">📈</div>
            <div>
              <div class="sh-title">净值曲线对比</div>
              <div class="sh-sub">{{ selectedTrackName }} · {{ result.stock_count }} 只股票</div>
            </div>
          </div>
          <el-tag size="small" type="info" effect="plain">{{ totalEquityPoints }} 个交易日</el-tag>
        </div>
        <StrategyComparisonChart
          :curves="equityCurves"
          :benchmark-curve="result.benchmark_curve"
        />
      </div>

      <!-- 指标对比排行榜 -->
      <div class="section-card">
        <div class="section-header">
          <div class="sh-left">
            <div class="sh-icon" style="background:linear-gradient(135deg,#3b82f6,#2563eb)">🏆</div>
            <div>
              <div class="sh-title">指标排行榜</div>
              <div class="sh-sub">按夏普比率降序 · 🥇最佳 / 🥈优秀 / 🥉一般</div>
            </div>
          </div>
        </div>
        <div class="rank-table-wrap">
          <table class="rank-table">
            <thead>
              <tr>
                <th>排名</th>
                <th>策略</th>
                <th>夏普比率</th>
                <th>总收益</th>
                <th>年化收益</th>
                <th>最大回撤</th>
                <th>胜率</th>
                <th>交易笔数</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in rankedStrategies" :key="r.key"
                  :class="{ 'rank-gold': i === 0, 'rank-silver': i === 1, 'rank-bronze': i === 2 }">
                <td class="td-rank">{{ ['🥇','🥈','🥉'][i] || i + 1 }}</td>
                <td class="td-name">{{ r.name }}</td>
                <td class="td-num" :class="sharpeClass(r.metrics.sharpe_ratio)">{{ r.metrics.sharpe_ratio?.toFixed(3) || '-' }}</td>
                <td class="td-num" :class="r.metrics.total_return >= 0 ? 'up' : 'down'">{{ r.metrics.total_return?.toFixed(1) }}%</td>
                <td class="td-num">{{ r.metrics.annual_return?.toFixed(1) }}%</td>
                <td class="td-num down">{{ r.metrics.max_drawdown?.toFixed(1) }}%</td>
                <td class="td-num">{{ r.metrics.win_rate?.toFixed(0) }}%</td>
                <td class="td-num">{{ r.metrics.buy_count || r.metrics.total_trades || '-' }}</td>
                <td>
                  <el-button size="small" text @click="toggleTradeDetail(r.key)">
                    {{ expandedTrade === r.key ? '收起' : '交易流水' }}
                  </el-button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 交易拆解 (按策略展开) -->
      <div v-for="r in rankedStrategies" :key="r.key">
        <div v-if="expandedTrade === r.key && r.trades?.length" class="section-card trade-detail-section">
          <TradeBreakdownChart :strategy-name="r.name" :trades="r.trades" />
        </div>
      </div>

      <!-- 策略学习要点 -->
      <div class="section-card" v-if="rankedStrategies.length >= 2">
        <div class="section-header">
          <div class="sh-left">
            <div class="sh-icon" style="background:linear-gradient(135deg,#8b5cf6,#7c3aed)">💡</div>
            <div>
              <div class="sh-title">学习要点</div>
              <div class="sh-sub">从这次对比中你学到了什么？</div>
            </div>
          </div>
        </div>
        <div class="learn-points">
          <div class="learn-point" v-if="bestSharpe > worstSharpeThreshold">
            <span class="lp-tag best">最佳策略</span>
            <span><strong>{{ bestStrategyName }}</strong> 夏普 {{ bestSharpe.toFixed(3) }}，是本轮表现最好的策略</span>
          </div>
          <div class="learn-point" v-if="aiVsTraditional">
            <span class="lp-tag insight">AI 对比</span>
            <span>{{ aiVsTraditional }}</span>
          </div>
          <div class="learn-point">
            <span class="lp-tag tip">提示</span>
            <span>不同策略在不同市场阶段表现不同。多次对比才能找到适合当前赛道的策略组合。</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ── 个股回测结果 ── -->
    <div v-if="result && !running && mode === 'single'">
      <!-- 核心指标卡 -->
      <div class="section-card" style="border-left:3px solid #3b82f6">
        <div class="section-header">
          <div class="sh-left">
            <div class="sh-icon" style="background:linear-gradient(135deg,#3b82f6,#2563eb)">📊</div>
            <div>
              <div class="sh-title">绩效指标</div>
              <div class="sh-sub">{{ singleStock }} · {{ strategyName }}</div>
            </div>
          </div>
          <el-tag v-if="result.metrics?.sharpe_ratio >= 1.5" size="small" type="success" effect="dark">优秀</el-tag>
          <el-tag v-else-if="result.metrics?.sharpe_ratio >= 1" size="small" type="warning" effect="dark">一般</el-tag>
          <el-tag v-else size="small" type="danger" effect="dark">待优化</el-tag>
        </div>

        <div class="metrics-grid">
          <div class="metric-card" v-for="m in singleMetrics" :key="m.label">
            <div class="metric-value" :style="{ color: m.color }">{{ m.value }}</div>
            <div class="metric-label">{{ m.label }}</div>
            <div class="metric-tip" v-if="m.tip">{{ m.tip }}</div>
          </div>
        </div>
      </div>

      <!-- 权益曲线 -->
      <div class="section-card" v-if="result.equity?.length">
        <div class="section-header">
          <div class="sh-left">
            <div class="sh-icon" style="background:linear-gradient(135deg,#10b981,#059669)">📈</div>
            <div>
              <div class="sh-title">权益曲线</div>
              <div class="sh-sub">策略 vs 买入持有</div>
            </div>
          </div>
          <el-tag size="small" type="info" effect="plain">{{ result.equity?.length }} 个交易日</el-tag>
        </div>
        <StrategyComparisonChart
          :curves="{ [strategyName]: result.equity }"
          :benchmark-curve="result.buy_hold_equity"
        />
      </div>

      <!-- AI 置信度 -->
      <div class="section-card" v-if="result.ai_confidence" style="border-left:3px solid #8b5cf6">
        <div class="section-header">
          <div class="sh-left">
            <div class="sh-icon" style="background:linear-gradient(135deg,#8b5cf6,#7c3aed)">🤖</div>
            <div>
              <div class="sh-title">AI 信号分析</div>
              <div class="sh-sub">AI 打分置信度分布与仓位建议</div>
            </div>
          </div>
        </div>
        <div class="ai-grid">
          <div class="ai-card">
            <div class="ai-value">{{ result.ai_confidence.mean_score?.toFixed(3) }}</div>
            <div class="ai-label">平均 AI 打分</div>
          </div>
          <div class="ai-card">
            <div class="ai-value">{{ (result.ai_confidence.mean_confidence * 100).toFixed(0) }}%</div>
            <div class="ai-label">平均置信度</div>
          </div>
          <div class="ai-card">
            <div class="ai-value" style="color:#16a34a">{{ result.ai_confidence.high_conf_count }}</div>
            <div class="ai-label">高置信信号 (&gt;60%)</div>
          </div>
          <div class="ai-card">
            <div class="ai-value" style="color:#e6a23c">{{ result.ai_confidence.med_conf_count }}</div>
            <div class="ai-label">中置信信号 (20~60%)</div>
          </div>
          <div class="ai-card">
            <div class="ai-value" style="color:#94a3b8">{{ result.ai_confidence.low_conf_count }}</div>
            <div class="ai-label">低置信信号 (&lt;20%)</div>
          </div>
          <div class="ai-card">
            <div class="ai-value" style="color:#16a34a">{{ result.ai_confidence.strong_buy }}</div>
            <div class="ai-label">强买入信号(重仓)</div>
          </div>
        </div>
      </div>

      <!-- 基准对比 -->
      <div class="section-card" v-if="result.benchmark && !result.benchmark.error">
        <div class="section-header">
          <div class="sh-left">
            <div class="sh-icon" style="background:linear-gradient(135deg,#f59e0b,#d97706)">🏆</div>
            <div>
              <div class="sh-title">基准对比</div>
              <div class="sh-sub">vs 买入持有</div>
            </div>
          </div>
        </div>
        <div class="benchmark-grid">
          <div class="bm-card" v-for="m in singleBenchmarkMetrics" :key="m.label">
            <div class="bm-value" :class="m.good ? (m.good(m.value) ? 'good' : 'bad') : ''">{{ m.display }}</div>
            <div class="bm-label">{{ m.label }}</div>
          </div>
        </div>
      </div>

      <!-- 交易记录 -->
      <div class="section-card" v-if="result.trades?.length">
        <TradeBreakdownChart :strategy-name="strategyName" :trades="result.trades" />
      </div>
    </div>

    <!-- ── 空状态 ── -->
    <div v-if="!result && !running && !error" class="empty-card">
      <el-empty :description="mode === 'compare' ? '勾选策略，点击「一键对比」开始实验' : '选择股票和策略，点击「开始回测」'">
        <el-button v-if="mode === 'compare'" type="primary" size="default" @click="selectDefaultStrategies">
          快速选择默认策略
        </el-button>
      </el-empty>
    </div>

    <!-- ── 策略详情弹窗 ── -->
    <el-dialog v-model="detailDialogVisible" :title="detailStrategy?.name || '策略详情'" width="600px" :close-on-click-modal="true">
      <div v-if="detailStrategy" class="strategy-detail-body">
        <div class="detail-section">
          <div class="detail-label">简介</div>
          <div class="detail-value">{{ detailStrategy.description }}</div>
        </div>
        <div class="detail-section" v-if="detailStrategy.mechanism">
          <div class="detail-label">📌 运行机制</div>
          <div class="detail-value">{{ detailStrategy.mechanism }}</div>
        </div>
        <div class="detail-section" v-if="detailStrategy.market_condition">
          <div class="detail-label">🌤️ 适用行情</div>
          <div class="detail-value">{{ detailStrategy.market_condition }}</div>
        </div>
        <div class="detail-section" v-if="detailStrategy.expected_effect">
          <div class="detail-label">📈 预期效果</div>
          <div class="detail-value">{{ detailStrategy.expected_effect }}</div>
        </div>
        <div class="detail-section" v-if="detailStrategy.limitations">
          <div class="detail-label">⚠️ 注意事项</div>
          <div class="detail-value">{{ detailStrategy.limitations }}</div>
        </div>
        <div class="detail-section" v-if="Object.keys(detailStrategy.params_detail || {}).length">
          <div class="detail-label">🔧 参数说明</div>
          <div class="params-table">
            <div v-for="(desc, param) in detailStrategy.params_detail" :key="param" class="param-row-detail">
              <code class="param-name">{{ param }}</code>
              <span class="param-arrow">→</span>
              <span class="param-desc">{{ desc }}</span>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- ── 策略对比指南 ── -->
    <div v-if="mode === 'compare' && allStrategies.length && !result" class="section-card">
      <div class="section-header">
        <div class="sh-left">
          <div class="sh-icon" style="background:linear-gradient(135deg,#06b6d4,#0891b2)">🧭</div>
          <div>
            <div class="sh-title">策略选择指南</div>
            <div class="sh-sub">根据当前市场行情或你的交易风格选择合适的策略</div>
          </div>
        </div>
      </div>
      <div class="guide-scenario-grid">
        <div class="scenario-card" v-for="sg in scenarioGuide" :key="sg.scenario">
          <div class="scenario-icon">{{ sg.icon }}</div>
          <div class="scenario-name">{{ sg.scenario }}</div>
          <div class="scenario-strategies">
            <el-tag v-for="s in sg.strategies" :key="s.key" size="small"
              :type="sg.type || 'info'" effect="plain"
              style="cursor:pointer" @click="showStrategyDetail(s)">
              {{ s.name }}
            </el-tag>
          </div>
        </div>
      </div>
    </div>

    <!-- ── 运行历史 ── -->
    <div style="margin-top:16px">
      <HistoryPanel @select="onHistorySelect" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import {
  listTracks, listStrategies, compareStrategies,
  getPipelineRuns, getBacktestDetail, getLearningStats,
  runSingleStockBacktest,
} from '@/api/track'
import StrategyComparisonChart from '@/components/trade/StrategyComparisonChart.vue'
import TradeBreakdownChart from '@/components/trade/TradeBreakdownChart.vue'
import HistoryPanel from '@/components/trade/HistoryPanel.vue'

// ── 状态 ──
const mode = ref<'compare' | 'single'>('compare')
const showGuide = ref(false)
const running = ref(false)
const error = ref('')
const result = ref<any>(null)
const progressPct = ref(0)
const progressStep = ref('')
const expandedTrade = ref<string | null>(null)

// 策略
const allStrategies = ref<any[]>([])
const selectedStrategies = ref<string[]>([])

// 个股回测
const stockList = ref<any[]>([])
const singleStock = ref('')
const selectedStrategy = ref('momentum_20d')
const useAi = ref(false)

// 策略详情
const detailDialogVisible = ref(false)
const detailStrategy = ref<any>(null)

function showStrategyDetail(s: any) {
  detailStrategy.value = s
  detailDialogVisible.value = true
}

// ── 策略选择指南 ──
const scenarioGuide = computed(() => {
  const s = allStrategies.value
  return [
    {
      icon: '📈',
      scenario: '上涨趋势市',
      type: 'success',
      strategies: s.filter(x => ['momentum_20d', 'momentum_60d', 'momentum_20d_vol', 'ma_cross', 'breakout'].includes(x.key)),
    },
    {
      icon: '📊',
      scenario: '震荡整理市',
      type: 'warning',
      strategies: s.filter(x => ['rsi_reversal', 'bollinger_reversal', 'kdj_oversold', 'bollinger_squeeze'].includes(x.key)),
    },
    {
      icon: '🚀',
      scenario: '强势突破市',
      type: 'danger',
      strategies: s.filter(x => ['volume_breakout', 'turtle', 'bollinger_squeeze', 'triple_ma'].includes(x.key)),
    },
    {
      icon: '🤖',
      scenario: 'AI 驱动（全自动）',
      type: 'primary',
      strategies: s.filter(x => ['ai_scoring', 'ai_confidence', 'multi_vote'].includes(x.key)),
    },
    {
      icon: '🧪',
      scenario: 'AI 增强版（传统+AI）',
      type: 'info',
      strategies: s.filter(x => x.key.endsWith('_ai') || x.key === 'ma_cross_ai'),
    },
  ]
})

// 赛道
const trackList = ref<any[]>([])
const selectedTrack = ref('semiconductor')

// 参数
const params = reactive({
  topN: 3,
  freq: 'W' as 'W' | 'M',
  capital: 100000,
  stopLoss: 15,
  singleStockLimit: 20,
  trackLimit: 50,
})

// ── 计算属性 ──
const selectedTrackName = computed(() => {
  const t = trackList.value.find(t => t.name === selectedTrack.value)
  return t?.display_name || selectedTrack.value
})

const strategyGroups = computed(() => {
  const types: Record<string, string> = {
    baseline: '基线策略',
    momentum: '动量策略',
    technical: '技术指标策略',
    mean_reversion: '均值回归策略',
    volatility: '波动率策略',
    trend: '趋势跟踪策略',
    composite: '复合策略 (AI投票)',
    ai: 'AI 策略',
  }
  const groups: { label: string; strategies: any[] }[] = []
  for (const [type, label] of Object.entries(types)) {
    const ss = allStrategies.value.filter(s => s.type === type)
    if (ss.length) groups.push({ label: `── ${label} ──`, strategies: ss })
  }
  return groups
})

const equityCurves = computed(() => {
  if (!result.value?.strategies) return {}
  const curves: Record<string, any[]> = {}
  for (const [key, s] of Object.entries(result.value.strategies) as [string, any][]) {
    if (s.equity_curve?.length) {
      curves[s.name || key] = s.equity_curve
    }
  }
  return curves
})

const rankedStrategies = computed(() => {
  if (!result.value?.strategies) return []
  const entries = Object.entries(result.value.strategies) as [string, any][]
  const valid = entries
    .filter(([_, s]) => s.metrics && !s.error)
    .map(([key, s]) => ({
      key,
      name: s.name || key,
      metrics: s.metrics,
      trades: s.trades || [],
    }))
  valid.sort((a, b) => (b.metrics.sharpe_ratio || 0) - (a.metrics.sharpe_ratio || 0))
  return valid
})

const totalEquityPoints = computed(() => {
  const curves = Object.values(equityCurves.value)
  return curves[0]?.length || 0
})

const bestSharpe = computed(() => rankedStrategies.value[0]?.metrics.sharpe_ratio || 0)
const bestStrategyName = computed(() => rankedStrategies.value[0]?.name || '')
const worstSharpeThreshold = 0.3

const aiVsTraditional = computed(() => {
  const aiStrat = rankedStrategies.value.find(s => s.key.includes('ai') || s.key === 'multi_vote')
  const tradStrat = rankedStrategies.value.find(s => !s.key.includes('ai') && s.key !== 'multi_vote' && s.key !== 'equal_weight')
  if (aiStrat && tradStrat) {
    const aiSharpe = aiStrat.metrics.sharpe_ratio || 0
    const tradSharpe = tradStrat.metrics.sharpe_ratio || 0
    if (aiSharpe > tradSharpe * 1.1) {
      return `AI 策略 ${aiStrat.name}（夏普 ${aiSharpe.toFixed(3)}）优于 ${tradStrat.name}（夏普 ${tradSharpe.toFixed(3)}），AI 加分效果明显`
    } else if (tradSharpe > aiSharpe * 1.1) {
      return `传统策略 ${tradStrat.name}（夏普 ${tradSharpe.toFixed(3)}）优于 ${aiStrat.name}（夏普 ${aiSharpe.toFixed(3)}），当前市场可能更适合技术指标`
    }
    return `AI 与传统策略差距不大，建议多时段对比确认`
  }
  return ''
})

function sharpeClass(v: number) {
  if (!v) return ''
  if (v >= 1.5) return 'up'
  if (v >= 1.0) return ''
  return 'down'
}

// ── 个股回测计算属性 ──
const strategyName = computed(() => {
  const s = allStrategies.value.find((s: any) => s.key === selectedStrategy.value)
  return s?.name || selectedStrategy.value
})

const singleMetrics = computed(() => {
  if (!result.value?.metrics) return []
  const m = result.value.metrics
  return [
    { label: '夏普比率', value: m.sharpe_ratio?.toFixed(3) || '-', color: (m.sharpe_ratio || 0) >= 1.2 ? '#16a34a' : '#dc2626', tip: (m.sharpe_ratio || 0) >= 1.2 ? '达标' : '偏低' },
    { label: '总收益', value: `${m.total_return?.toFixed(1)}%`, color: (m.total_return || 0) >= 0 ? '#16a34a' : '#dc2626', tip: (m.total_return || 0) >= 0 ? '盈利' : '亏损' },
    { label: '年化收益', value: `${m.annual_return?.toFixed(1)}%`, color: (m.annual_return || 0) >= 10 ? '#16a34a' : '#e6a23c' },
    { label: '最大回撤', value: `${m.max_drawdown?.toFixed(1)}%`, color: (m.max_drawdown || 100) < 25 ? '#16a34a' : '#dc2626', tip: (m.max_drawdown || 100) < 25 ? '可控' : '偏高' },
    { label: '胜率', value: `${m.win_rate?.toFixed(1)}%`, color: (m.win_rate || 0) >= 50 ? '#16a34a' : '#dc2626' },
    { label: '交易次数', value: m.total_trades || m.buy_count || 0, color: '#64748b' },
  ]
})

const singleBenchmarkMetrics = computed(() => {
  if (!result.value?.benchmark || result.value.benchmark.error) return []
  const b = result.value.benchmark
  return [
    { label: '超额收益', display: `${b.excess_return?.toFixed(1)}%`, value: b.excess_return, good: (v: number) => v > 0 },
    { label: 'Alpha', display: `${b.alpha?.toFixed(2)}%`, value: b.alpha, good: (v: number) => v > 0 },
    { label: 'Beta', display: b.beta?.toFixed(3), value: b.beta, good: (v: number) => v < 1 },
    { label: '信息比率', display: b.information_ratio?.toFixed(3), value: b.information_ratio, good: (v: number) => v > 0.5 },
    { label: '跟踪误差', display: `${b.tracking_error?.toFixed(1)}%`, value: b.tracking_error },
    { label: '相关性', display: b.correlation?.toFixed(3), value: b.correlation },
  ]
})

// ── 模式切换 ──
function onModeChange() {
  result.value = null
  error.value = ''
}

function onStrategyChange() {
  result.value = null
  error.value = ''
}

// ── 操作 ──

function selectDefaultStrategies() {
  selectedStrategies.value = ['momentum_20d', 'ma_cross', 'rsi_reversal', 'ai_scoring']
}

function toggleTradeDetail(key: string) {
  expandedTrade.value = expandedTrade.value === key ? null : key
}

function onHistorySelect(run: any) {
  ElMessage.info(`已选择回测记录 #${run.id}，详情加载中...`)
}

// ── 个股回测 ──
async function runSingleStock() {
  if (!singleStock.value) {
    ElMessage.warning('请选择股票')
    return
  }
  running.value = true
  error.value = ''
  result.value = null

  try {
    const res: any = await runSingleStockBacktest(
      singleStock.value,
      selectedStrategy.value,
      params.topN,
      params.stopLoss,
      useAi.value,
    )
    result.value = res
    ElMessage.success('个股回测完成')
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '回测失败'
  } finally {
    running.value = false
  }
}

// ── 加载数据 ──
async function loadData() {
  try {
    allStrategies.value = await listStrategies() as any
  } catch { /* ignore */ }
  try {
    const res: any = await listTracks()
    trackList.value = (res?.items || res || []).filter((t: any) => t.is_active)
    // 构建股票列表
    const stocks: any[] = []
    const seen = new Set<string>()
    for (const track of (res?.items || res || [])) {
      for (const s of track.stocks || []) {
        if (!seen.has(s.code)) {
          seen.add(s.code)
          stocks.push(s)
        }
      }
    }
    stockList.value = stocks
    if (stocks.length && !singleStock.value) {
      singleStock.value = stocks[0].code
    }
    if (trackList.value.length && !selectedStrategies.value.length) {
      selectDefaultStrategies()
    }
  } catch { /* ignore */ }
}

// ── 一键对比 ──
async function runComparison() {
  if (!selectedStrategies.value.length) {
    ElMessage.warning('请至少选择一个策略')
    return
  }

  running.value = true
  error.value = ''
  result.value = null
  expandedTrade.value = null

  // 模拟进度
  progressPct.value = 0
  progressStep.value = '初始化...'
  const progTimer = setInterval(() => {
    if (progressPct.value < 90) {
      progressPct.value += Math.random() * 15
      if (progressPct.value > 90) progressPct.value = 90
    }
  }, 800)

  try {
    progressStep.value = '运行回测...'
    const res: any = await compareStrategies({
      strategies: selectedStrategies.value,
      track_name: selectedTrack.value,
      initial_capital: params.capital,
      top_n: params.topN,
      rebalance_freq: params.freq,
      max_single_stock: params.singleStockLimit / 100,
      max_single_track: params.trackLimit / 100,
      stop_loss_pct: -Math.abs(params.stopLoss) / 100,
      take_profit_pct: 0.30,
    })
    result.value = res
    progressPct.value = 100
    progressStep.value = '完成!'

    const count = Object.keys(res.strategies || {}).length
    const successCount = Object.values(res.strategies || {}).filter((s: any) => !s.error).length
    ElMessage.success(`${successCount}/${count} 个策略回测完成`)
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '回测失败'
  } finally {
    clearInterval(progTimer)
    running.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.strategy-lab {
  min-height: 100%;
  padding: 24px 32px;
  background: #f5f7fa;
}

/* ── 页面标题 ── */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.ph-left { display: flex; align-items: center; gap: 12px; }
.ph-icon {
  width: 44px; height: 44px;
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px;
  box-shadow: 0 2px 8px rgba(99,102,241,0.25);
}
.ph-title { font-size: 22px; font-weight: 700; color: #1e293b; }
.ph-sub { font-size: 12px; color: #94a3b8; margin-top: 2px; }

/* ── 指南 ── */
.guide-card {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  padding: 8px 14px;
  margin-bottom: 8px;
}

.guide-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
}

.guide-item {
  font-size: 12px;
  color: #1e40af;
}

.guide-item strong {
  color: #2563eb;
  margin-right: 3px;
}

/* ── 卡片通用 ── */
.section-card {
  background: #fff;
  border-radius: 10px;
  padding: 14px 18px;
  box-shadow: 0 1px 6px rgba(0,0,0,0.05);
  margin-bottom: 10px;
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.sh-left { display: flex; align-items: center; gap: 12px; }
.sh-icon {
  width: 40px; height: 40px;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px;
}
.sh-title { font-size: 16px; font-weight: 700; color: #1e293b; }
.sh-sub { font-size: 12px; color: #94a3b8; margin-top: 1px; }

/* ── 配置 ── */
.config-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 14px;
  margin-bottom: 10px;
}

.config-main { display: flex; flex-direction: column; gap: 8px; }
.config-group { display: flex; flex-direction: column; gap: 4px; }
.config-label { font-size: 11px; font-weight: 600; color: #475569; }

.strategy-checklist {
  max-height: 260px;
  overflow-y: auto;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 6px 10px;
}

.strat-group { margin-bottom: 4px; }
.strat-group-label {
  font-size: 10px;
  color: #94a3b8;
  font-weight: 600;
  margin-bottom: 2px;
  padding-left: 2px;
}

.strat-check-group { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; }

.strat-check-item {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 12px;
}

.strat-check-item:hover {
  background: #f1f5f9;
}

.config-params { display: flex; flex-direction: column; gap: 10px; }
.param-row { display: flex; gap: 10px; }
.param-item { flex: 1; display: flex; flex-direction: column; gap: 4px; }
.param-label { font-size: 11px; font-weight: 500; color: #64748b; display: flex; align-items: center; gap: 4px; }

.label-help {
  display: inline-flex; align-items: center; justify-content: center;
  width: 14px; height: 14px; border-radius: 50%;
  background: #e2e8f0; color: #64748b;
  font-size: 10px; font-weight: 700; cursor: help;
}

/* ── 操作栏 ── */
.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 14px;
  background: #f8fafc;
  border-radius: 6px;
}

.locked-info {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #94a3b8;
}

.run-btn {
  padding: 8px 24px;
  font-size: 14px;
  font-weight: 600;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(59,130,246,0.25);
}

/* ── 进度 ── */
.progress-card {
  background: #fff;
  border-radius: 10px;
  padding: 20px 24px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.progress-text {
  font-size: 13px;
  color: #64748b;
  margin-top: 8px;
  text-align: center;
}

/* ── 排行榜 ── */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}

.metric-card {
  background: #f8fafc;
  border-radius: 10px;
  padding: 14px 12px;
  text-align: center;
}

.metric-value { font-size: 22px; font-weight: 700; line-height: 1.2; }
.metric-label { font-size: 11px; color: #909399; margin-top: 2px; }
.metric-tip { font-size: 10px; margin-top: 2px; opacity: 0.6; }

.ai-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}

.ai-card {
  background: #f8fafc;
  border-radius: 10px;
  padding: 14px 12px;
  text-align: center;
}

.ai-value { font-size: 20px; font-weight: 700; color: #1e293b; }
.ai-label { font-size: 11px; color: #909399; margin-top: 2px; }

.benchmark-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}

.bm-card {
  background: #f8fafc;
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}

.bm-value { font-size: 18px; font-weight: 700; }
.bm-value.good { color: #16a34a; }
.bm-value.bad { color: #dc2626; }
.bm-label { font-size: 11px; color: #909399; margin-top: 2px; }

.strat-desc {
  display: block;
  font-size: 11px;
  color: #94a3b8;
  margin-top: 1px;
}

/* ── 策略详情 ── */
.strategy-detail-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.detail-section {
  border-left: 3px solid #e2e8f0;
  padding-left: 12px;
}
.detail-label {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  margin-bottom: 4px;
}
.detail-value {
  font-size: 14px;
  color: #1e293b;
  line-height: 1.6;
}
.params-table {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.param-row-detail {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 13px;
}
.param-name {
  font-size: 12px;
  padding: 1px 6px;
  background: #f1f5f9;
  border-radius: 4px;
  color: #475569;
}
.param-arrow {
  color: #94a3b8;
}
.param-desc {
  color: #475569;
}

/* ── 策略选择指南 ── */
.guide-scenario-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}
.scenario-card {
  background: #f8fafc;
  border-radius: 10px;
  padding: 14px;
  border: 1px solid #e2e8f0;
}
.scenario-icon {
  font-size: 24px;
  margin-bottom: 4px;
}
.scenario-name {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 8px;
}
.scenario-strategies {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.strat-detail-btn {
  font-size: 11px;
  color: #3b82f6 !important;
  padding: 0 4px !important;
  margin-left: 2px;
}

.trade-detail-section {
  padding: 0;
  overflow: hidden;
}

.rank-table-wrap {
  overflow-x: auto;
}

.rank-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.rank-table th {
  text-align: left;
  padding: 10px 12px;
  background: #f8fafc;
  color: #64748b;
  font-weight: 600;
  font-size: 11px;
  border-bottom: 2px solid #e2e8f0;
  white-space: nowrap;
}

.rank-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #f1f5f9;
  color: #334155;
}

.rank-gold { background: #fffbeb; }
.rank-silver { background: #f8fafc; }
.rank-bronze { background: #fefce8; }

.td-rank { font-size: 18px; text-align: center; }
.td-name { font-weight: 600; }
.td-num { font-family: monospace; font-weight: 600; }
.up { color: #16a34a; }
.down { color: #dc2626; }

/* ── 学习要点 ── */
.learn-points {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.learn-point {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 13px;
  color: #475569;
  line-height: 1.5;
}

.lp-tag {
  flex-shrink: 0;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
}

.lp-tag.best { background: #dcfce7; color: #16a34a; }
.lp-tag.insight { background: #ede9fe; color: #7c3aed; }
.lp-tag.tip { background: #e0f2fe; color: #0284c7; }

/* ── 错误/空 ── */
.error-card, .empty-card {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  margin-bottom: 16px;
}

.trade-detail-section {
  padding: 0;
  overflow: hidden;
}

@media (max-width: 860px) {
  .config-grid { grid-template-columns: 1fr; }
  .strategy-lab { padding: 16px; }
}
</style>
