<template>
  <div class="fp">
    <div class="fp-head">
      <div class="fp-head-left">
        <span class="fp-title">因子监控</span>
        <span class="fp-count">{{ filteredFactors.length }}</span>
      </div>
      <el-tooltip content="IC=信息系数(预测力) IR=信息比率(稳定性)" placement="left">
        <el-icon class="fp-help"><QuestionFilled /></el-icon>
      </el-tooltip>
    </div>

    <div class="fp-search">
      <el-input v-model="q" placeholder="Search factors..." size="small" clearable :prefix-icon="Search" />
    </div>

    <div class="fp-body">
      <div v-for="g in groups" :key="g.key" class="fp-cat">
        <div class="fp-cat-head" @click="toggle(g.key)">
          <div class="fp-cat-left">
            <span class="fp-cat-icon">{{ g.icon }}</span>
            <span class="fp-cat-name">{{ g.label }}</span>
          </div>
          <div class="fp-cat-right">
            <span class="fp-cat-best">best IC {{ g.bestIc }}</span>
            <span class="fp-cat-n">{{ g.items.length }}</span>
            <el-icon :class="{ rot: !collapsed.has(g.key) }"><ArrowRight /></el-icon>
          </div>
        </div>

        <div v-if="!collapsed.has(g.key)" class="fp-items">
          <div v-for="f in g.items" :key="f.factor_name" class="fp-item" @click="expand(f.factor_name)">
            <div class="fp-item-row">
              <div class="fp-item-info">
                <span class="fp-item-cn">{{ cn(f.factor_name) }}</span>
                <span class="fp-item-en">{{ f.factor_name }}</span>
              </div>
              <div class="fp-item-metrics">
                <span class="fp-item-ic" :class="f.ic_mean >= 0 ? 'ic-p' : 'ic-n'">
                  {{ (f.ic_mean * 100).toFixed(1) }}
                </span>
                <span class="fp-item-ir">IR {{ f.ir?.toFixed(2) }}</span>
              </div>
            </div>
            <div class="fp-item-bar">
              <div class="fp-bar-fill" :class="f.ic_mean >= 0 ? 'bp' : 'bn'"
                :style="{ width: Math.min(Math.abs(f.ic_mean) * 3000, 100) + '%' }" />
            </div>
            <div v-if="expanded.has(f.factor_name)" class="fp-item-desc">
              <div class="fp-desc-text">{{ interpret(f.factor_name) }}</div>
            </div>
          </div>
        </div>
      </div>

      <el-empty v-if="!groups.length" :description="q ? 'No match' : 'No factors'" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Search, QuestionFilled, ArrowRight } from '@element-plus/icons-vue'

const props = defineProps<{ factors: any[] }>()
const q = ref('')
const collapsed = ref<Set<string>>(new Set())
const expanded = ref<Set<string>>(new Set())

function toggle(k: string) {
  if (collapsed.value.has(k)) collapsed.value.delete(k)
  else collapsed.value.add(k)
}
function expand(n: string) {
  if (expanded.value.has(n)) expanded.value.delete(n)
  else expanded.value.add(n)
}

const catMeta: Record<string, { icon: string; label: string }> = {
  track_specific: { icon: '🏷️', label: 'Track-Specific' },
  momentum: { icon: '⚡', label: 'Momentum' },
  trend: { icon: '📈', label: 'Trend' },
  volatility: { icon: '🌊', label: 'Volatility' },
  volume: { icon: '📊', label: 'Volume' },
  statistical: { icon: '📐', label: 'Statistical' },
}
const catOrder = ['track_specific', 'momentum', 'trend', 'volatility', 'volume', 'statistical']

const filtered = computed(() => {
  if (!q.value.trim()) return props.factors
  const s = q.value.trim().toLowerCase()
  return props.factors.filter(f =>
    f.factor_name.toLowerCase().includes(s) || cn(f.factor_name).includes(s)
  )
})

const groups = computed(() => {
  const map: Record<string, any[]> = {}
  for (const f of filtered.value) {
    const k = f.category || f.factor_type || 'other'
    if (!map[k]) map[k] = []
    map[k].push(f)
  }
  return Object.entries(map)
    .sort(([a], [b]) => catOrder.indexOf(a) - catOrder.indexOf(b))
    .map(([key, items]) => {
      const sorted = items.sort((a: any, b: any) => Math.abs(b.ic_mean) - Math.abs(a.ic_mean))
      const bestIc = ((sorted[0]?.ic_mean || 0) * 100).toFixed(1)
      return {
        key,
        icon: catMeta[key]?.icon || '📋',
        label: catMeta[key]?.label || key,
        items: sorted,
        bestIc,
      }
    })
})

// ── Name mapping ──
const CN: Record<string, string> = {
  rsi_6: '6日RSI', rsi_24: '24日RSI', stoch_k: '随机K', stoch_d: '随机D', stoch_j: '随机J',
  willr_14: '威廉指标', roc_20: '20日变动率', roc_60: '60日变动率',
  ao: '动量震荡', ppo: 'PPO', ppo_signal: 'PPO信号',
  sma_5: '5日均线', sma_10: '10日均线', sma_20: '20日均线', sma_60: '60日均线',
  sma_dev_5: '5日偏离度', sma_dev_20: '20日偏离度',
  ema_20: '20日指数均线', ema_60: '60日指数均线', ema_20_dev: '20日指数偏离', ema_60_dev: '60日指数偏离',
  macd: 'MACD快线', macd_signal: 'MACD信号线', macd_diff: 'MACD柱',
  adx: 'ADX趋势', adx_pos: '+DI', adx_neg: '-DI',
  aroon_up: '阿隆上升', aroon_down: '阿隆下降',
  cci_20: '20日CCI', cci_60: '60日CCI', trix: 'TRIX',
  atr_5: '5日ATR', atr_14: '14日ATR', atr_5_pct: 'ATR百分比',
  bb_upper_20: '布林上轨', bb_lower_20: '布林下轨', bb_width_20: '布林带宽', bb_position_20: '布林位置',
  donchian_upper_20: '通道上轨', donchian_lower_20: '通道下轨', donchian_width_20: '通道宽度', ulcer: 'Ulcer回撤',
  obv: 'OBV能量潮', ad: 'A/D资金流', cmf_20: '资金流指标',
  emv: '简易波动', fi: '力量指数', mfi: '资金流量', vpt: '量价趋势', vwap: '均价线',
  volume_5d_ma: '5日均量', volume_ratio_5d: '5日量比', volume_20d_ma: '20日均量', volume_ratio_20d: '20日量比',
  amount_5d_ma: '5日均额', amount_ratio_5d: '5日额比',
  ret_skew_20: '收益偏度', ret_kurt_20: '收益峰度', ret_quantile_80: '80%分位', ret_quantile_20: '20%分位',
  consec_up: '连涨天数', consec_down: '连跌天数', sharpe_20: '夏普比', vp_corr_20: '量价相关',
  price_pos_20d: '价格位置', high_pct_20d: '距高点比例',
}
function cn(name: string): string { return CN[name] || name }

// ── Interpret ──
const INTERP: Record<string, string> = {
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
function interpret(name: string): string {
  return INTERP[name] || 'Alphalens筛选通过的有效预测因子'
}
</script>

<style scoped>
.fp {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-left: 1px solid #e8ecf0;
  width: 310px;
  flex-shrink: 0;
}

/* Header */
.fp-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 8px;
  flex-shrink: 0;
}
.fp-head-left { display: flex; align-items: center; gap: 8px; }
.fp-title { font-size: 13px; font-weight: 600; color: #1e293b; letter-spacing: 0.2px; }
.fp-count {
  font-size: 10px; font-weight: 600; color: #fff; background: #3b82f6;
  padding: 1px 7px; border-radius: 8px; line-height: 16px;
}
.fp-help { font-size: 13px; color: #c0c4cc; cursor: help; }

/* Search */
.fp-search { padding: 0 16px 8px; flex-shrink: 0; }

/* Body */
.fp-body { flex: 1; overflow-y: auto; padding: 0 0 8px; }

/* Category */
.fp-cat { margin-bottom: 1px; }
.fp-cat-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 16px; cursor: pointer; transition: background 0.1s;
  border-bottom: 1px solid #f0f2f5;
  position: sticky; top: 0; background: #fff; z-index: 1;
}
.fp-cat-head:hover { background: #f8fafc; }
.fp-cat-left { display: flex; align-items: center; gap: 6px; }
.fp-cat-icon { font-size: 14px; }
.fp-cat-name { font-size: 11px; font-weight: 600; color: #475569; text-transform: uppercase; letter-spacing: 0.5px; }
.fp-cat-right { display: flex; align-items: center; gap: 6px; }
.fp-cat-best { font-size: 10px; color: #94a3b8; }
.fp-cat-n {
  font-size: 10px; font-weight: 600; color: #64748b; background: #f1f5f9;
  padding: 0 6px; border-radius: 6px; line-height: 18px; min-width: 20px; text-align: center;
}
.fp-cat-right .el-icon { font-size: 12px; color: #cbd5e1; transition: transform 0.2s; }
.fp-cat-right .rot { transform: rotate(90deg); }

/* Factor item */
.fp-items { padding: 0; }
.fp-item { padding: 6px 16px 6px 22px; border-bottom: 1px solid #f8f9fa; cursor: pointer; transition: background 0.1s; }
.fp-item:hover { background: #f1f5f9; }
.fp-item-row { display: flex; align-items: center; justify-content: space-between; gap: 4px; }
.fp-item-info { flex: 1; min-width: 0; }
.fp-item-cn { font-size: 12px; font-weight: 500; color: #1e293b; line-height: 1.3; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fp-item-en { font-size: 10px; color: #94a3b8; font-family: 'SF Mono', monospace; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fp-item-metrics { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.fp-item-ic {
  font-size: 11px; font-weight: 700; padding: 1px 6px; border-radius: 4px; min-width: 36px; text-align: right;
}
.ic-p { color: #059669; background: #ecfdf5; }
.ic-n { color: #dc2626; background: #fef2f2; }
.fp-item-ir { font-size: 10px; color: #94a3b8; min-width: 32px; text-align: right; }

/* Bar */
.fp-item-bar { margin-top: 3px; height: 3px; background: #f1f5f9; border-radius: 2px; overflow: hidden; }
.fp-bar-fill { height: 100%; border-radius: 2px; transition: width 0.3s; }
.bp { background: linear-gradient(90deg, #10b981, #34d399); }
.bn { background: linear-gradient(90deg, #ef4444, #f87171); }

/* Desc */
.fp-item-desc { margin-top: 4px; padding: 5px 8px; background: #f8fafc; border-radius: 4px; border-left: 2px solid #3b82f6; }
.fp-desc-text { font-size: 11px; color: #475569; line-height: 1.5; }
</style>
