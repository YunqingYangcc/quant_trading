<template>
  <div class="factor-panel">
    <!-- 头部：搜索 -->
    <div class="panel-header">
      <div class="header-left">
        <span class="panel-title">有效因子</span>
        <el-tag size="small" type="success" round>{{ filteredFactors.length }}</el-tag>
      </div>
      <el-tooltip content="IC=信息系数(预测力)  IR=信息比率(稳定性)" placement="left">
        <el-icon class="help-icon"><QuestionFilled /></el-icon>
      </el-tooltip>
    </div>

    <div class="search-bar">
      <el-input
        v-model="searchQuery"
        placeholder="搜索因子名称..."
        size="small"
        clearable
        :prefix-icon="Search"
      />
    </div>

    <!-- 因子列表 -->
    <div class="factor-list">
      <div v-for="group in filteredGroups" :key="group.category" class="factor-group">
        <div class="group-header" @click="toggleGroup(group.category)">
          <span class="group-title">{{ group.label }}</span>
          <div class="group-meta">
            <el-tag size="small" round>{{ group.items.length }}</el-tag>
            <el-icon :class="{ rotated: !collapsedGroups.has(group.category) }">
              <ArrowRight />
            </el-icon>
          </div>
        </div>

        <div v-if="!collapsedGroups.has(group.category)">
          <div
            v-for="f in group.items"
            :key="f.factor_name"
            class="factor-card"
            @click="toggleExpand(f.factor_name)"
          >
            <!-- 因子名 + IC -->
            <div class="card-row">
              <div class="factor-info">
                <span class="factor-cn-name">{{ getCnName(f.factor_name) }}</span>
                <span class="factor-en-name">{{ f.factor_name }}</span>
              </div>
              <div class="factor-metrics">
                <el-tag size="small" :type="f.ic_mean >= 0 ? 'success' : 'danger'" effect="dark" round>
                  {{ (f.ic_mean * 100).toFixed(1) }}
                </el-tag>
                <span class="metric-ir">IR {{ f.ir?.toFixed(2) }}</span>
              </div>
            </div>
            <!-- 强度条 -->
            <div class="strength-bar">
              <div class="strength-fill" :class="f.ic_mean >= 0 ? 'pos' : 'neg'"
                :style="{ width: Math.min(Math.abs(f.ic_mean) * 3000, 100) + '%' }" />
            </div>
            <!-- 展开后的解读 -->
            <div v-if="expanded.has(f.factor_name)" class="factor-interpret">
              <div class="interpret-line">{{ getInterpret(f.factor_name) }}</div>
            </div>
          </div>
        </div>
      </div>

      <el-empty v-if="!filteredGroups.length" :description="searchQuery ? '无匹配因子' : '暂无有效因子'" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Search, QuestionFilled, ArrowRight } from '@element-plus/icons-vue'

const props = defineProps<{ factors: any[] }>()

const searchQuery = ref('')
const collapsedGroups = ref<Set<string>>(new Set())

function toggleGroup(cat: string) {
  if (collapsedGroups.value.has(cat)) collapsedGroups.value.delete(cat)
  else collapsedGroups.value.add(cat)
}

const totalFactors = computed(() => filteredFactors.value.length)

const filteredFactors = computed(() => {
  if (!searchQuery.value.trim()) return props.factors
  const q = searchQuery.value.trim().toLowerCase()
  return props.factors.filter(f =>
    f.factor_name.toLowerCase().includes(q) ||
    getCnName(f.factor_name).includes(q)
  )
})

const categoryLabels: Record<string, string> = {
  track_specific: '🏷️ 赛道专属',
  momentum: '⚡ 动量类',
  trend: '📈 趋势类',
  volatility: '🌊 波动率类',
  volume: '📊 量能类',
  statistical: '📐 统计类',
}

const categoryOrder = ['track_specific', 'momentum', 'trend', 'volatility', 'volume', 'statistical']

const filteredGroups = computed(() => {
  const groups: Record<string, any[]> = {}
  for (const f of filteredFactors.value) {
    const cat = f.category || f.factor_type || 'other'
    if (!groups[cat]) groups[cat] = []
    groups[cat].push(f)
  }
  return Object.entries(groups)
    .sort(([a], [b]) => categoryOrder.indexOf(a) - categoryOrder.indexOf(b))
    .map(([cat, items]) => ({
      category: cat,
      label: categoryLabels[cat] || cat,
      items: items.sort((a: any, b: any) => Math.abs(b.ic_mean) - Math.abs(a.ic_mean)),
    }))
})

// ── 因子中文名映射 ──
const CN_NAMES: Record<string, string> = {
  rsi_6: '6日RSI', rsi_24: '24日RSI',
  stoch_k: '随机指标K', stoch_d: '随机指标D', stoch_j: '随机指标J',
  willr_14: '威廉指标', roc_20: '20日变动率', roc_60: '60日变动率',
  ao: '动量震荡', ppo: 'PPO', ppo_signal: 'PPO信号',
  sma_5: '5日均线', sma_10: '10日均线', sma_20: '20日均线', sma_60: '60日均线',
  sma_dev_5: '5日偏离度', sma_dev_20: '20日偏离度',
  ema_20: '20日指数均线', ema_60: '60日指数均线',
  ema_20_dev: '20日指数偏离', ema_60_dev: '60日指数偏离',
  macd: 'MACD快线', macd_signal: 'MACD信号线', macd_diff: 'MACD柱',
  adx: 'ADX趋势', adx_pos: '+DI', adx_neg: '-DI',
  aroon_up: '阿隆上升', aroon_down: '阿隆下降',
  cci_20: '20日CCI', cci_60: '60日CCI', trix: 'TRIX',
  atr_5: '5日ATR', atr_14: '14日ATR', atr_5_pct: 'ATR百分比',
  bb_upper_20: '布林上轨', bb_lower_20: '布林下轨',
  bb_width_20: '布林带宽', bb_position_20: '布林位置',
  donchian_upper_20: '通道上轨', donchian_lower_20: '通道下轨',
  donchian_width_20: '通道宽度', ulcer: 'Ulcer回撤',
  obv: 'OBV能量潮', ad: 'A/D资金流', cmf_20: '资金流指标',
  emv: '简易波动', fi: '力量指数', mfi: '资金流量',
  vpt: '量价趋势', vwap: '均价线',
  volume_5d_ma: '5日均量', volume_ratio_5d: '5日量比',
  volume_20d_ma: '20日均量', volume_ratio_20d: '20日量比',
  amount_5d_ma: '5日均额', amount_ratio_5d: '5日额比',
  ret_skew_20: '收益偏度', ret_kurt_20: '收益峰度',
  ret_quantile_80: '80%分位', ret_quantile_20: '20%分位',
  consec_up: '连涨天数', consec_down: '连跌天数',
  sharpe_20: '夏普比', vp_corr_20: '量价相关',
  price_pos_20d: '价格位置', high_pct_20d: '距高点比例',
  track_semiconductor_mom_5d: '半导体动量5', track_semiconductor_mom_20d: '半导体动量20',
  track_semiconductor_trend_20d: '半导体趋势20', track_semiconductor_trend_60d: '半导体趋势60',
  track_semiconductor_volatility_20d: '半导体波动', track_semiconductor_volume_ratio_20d: '半导体量比',
  track_semiconductor_amihud_illiq: '半导体非流动性', track_semiconductor_money_flow_5d: '半导体资金5',
  track_semiconductor_money_flow_20d: '半导体资金20', track_semiconductor_money_flow_ratio_5d: '半导体资金比5',
}

function getCnName(name: string): string {
  return CN_NAMES[name] || name.replace(/track_/g, '').replace(/_/g, ' ')
}

// ── 因子描述映射 ──
const FACTOR_DESC: Record<string, string> = {
  rsi_6: 'RSI>70超买(可能回调)，RSI<30超卖(可能反弹)',
  stoch_k: '%K线追踪收盘价在近期高低区间位置，>80超买',
  willr_14: '值<-80超卖，>-20超买，威廉经典反转指标',
  roc_20: '(今收-20日前收)/20日前收×100，价格变化速度',
  sma_5: '最近5日收盘价均值，超短期趋势参考',
  sma_dev_5: '(收盘-5日均线)/5日均线，偏离>10%可能回归',
  macd: '12EMA-26EMA，>0多头趋势，金叉买入信号',
  adx: '>25趋势强劲，<20震荡盘整',
  cci_20: '>100超买，<-100超卖，统计偏离度',
  atr_14: '标准ATR周期，越大波动越大，常用止损倍数参考',
  bb_upper_20: '20均线+2σ，触及上轨可能超买回调',
  bb_lower_20: '20均线-2σ，触及下轨可能超卖反弹',
  obv: '累计成交量，OBV创新高确认上涨趋势',
  mfi: '类似RSI但考虑成交量，>80超买<20超卖',
  vwap: '成交量加权均价，机构交易成本参考线',
  ret_skew_20: '正偏=大涨概率>大跌概率，负偏相反',
  sharpe_20: '(收益-无风险)/波动，>1良好>2优秀',
}

function getFactorDesc(name: string): string {
  return FACTOR_DESC[name] || 'Alphalens筛选通过的有效预测因子，点击查看详情'
}

const INTERPRET: Record<string, string> = {
  rsi_6: 'RSI>70超买(谨慎追高)，RSI<30超卖(关注买入)',
  stoch_k: '%K线>80超买，<20超卖，金叉买入信号',
  willr_14: '值>-20短期见顶，值<-80短期见底',
  roc_20: '上穿0轴加速上涨，下穿0轴空头信号',
  sma_5: '收盘>5MA短期强势，收盘<5MA短期弱势',
  sma_dev_5: '偏离+5%以上可能回调，-5%以下可能反弹',
  macd: 'MACD>0多头市场，金叉买入信号',
  adx: 'ADX>25趋势行情顺势交易，<20震荡高抛低吸',
  cci_20: '>+100超买回调，<-100超卖反弹',
  atr_14: 'ATR越大波动越剧烈，越小行情越平淡',
  bb_upper_20: '触及上轨超买压力，可能回调至中轨',
  bb_lower_20: '触及下轨超卖支撑，可能反弹至中轨',
  obv: 'OBV与价格同步上涨=趋势健康，背离=趋势反转',
  mfi: '>80超买回调风险，<20超卖反弹机会',
  vwap: '价格>VWAP多头主导，<VWAP空头主导',
}

function getInterpret(name: string): string {
  return INTERPRET[name] || getFactorDesc(name)
}
</script>

<style scoped>
.factor-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fafbfc;
  border-left: 1px solid #ebedf0;
  width: 300px;
  flex-shrink: 0;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px 6px;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.help-icon {
  font-size: 14px;
  color: #c0c4cc;
  cursor: help;
}

.search-bar {
  padding: 0 12px 6px;
  flex-shrink: 0;
}

.factor-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 0 8px;
}

.factor-group {
  margin-bottom: 2px;
}

.group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  cursor: pointer;
  transition: background 0.15s;
  border-bottom: 1px solid #f0f2f5;
  position: sticky;
  top: 0;
  background: #fafbfc;
  z-index: 1;
}

.group-header:hover {
  background: #f0f2f5;
}

.group-title {
  font-size: 11px;
  font-weight: 600;
  color: #909399;
}

.group-meta {
  display: flex;
  align-items: center;
  gap: 4px;
}

.group-meta .el-icon {
  font-size: 12px;
  transition: transform 0.2s;
  color: #c0c4cc;
}

.group-meta .rotated {
  transform: rotate(90deg);
}

.factor-card {
  padding: 5px 12px 5px 16px;
  border-bottom: 1px solid #f5f6f7;
  transition: background 0.1s;
}

.factor-card:hover {
  background: #f0f2f5;
}

.card-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
}

.factor-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.factor-cn-name {
  font-size: 12px;
  font-weight: 500;
  color: #303133;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.factor-en-name {
  font-size: 10px;
  color: #c0c4cc;
  font-family: 'SF Mono', 'Menlo', monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.factor-metrics {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.metric-ir {
  font-size: 10px;
  color: #909399;
  white-space: nowrap;
  min-width: 36px;
}

.strength-bar {
  margin-top: 2px;
  height: 3px;
  background: #f0f2f5;
  border-radius: 2px;
  overflow: hidden;
}

.strength-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s;
}

.strength-fill.pos {
  background: linear-gradient(90deg, #67c23a, #95de64);
}

.strength-fill.neg {
  background: linear-gradient(90deg, #f56c6c, #ff7875);
}

.factor-interpret {
  margin-top: 3px;
  padding: 4px 6px;
  background: #f8f9fa;
  border-radius: 4px;
  border-left: 2px solid #409eff;
}

.interpret-line {
  font-size: 11px;
  color: #606266;
  line-height: 1.5;
}

</style>
