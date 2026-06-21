<template>
  <div class="trade-breakdown">
    <div class="tb-header">
      <div class="tb-title">{{ strategyName }} — 交易流水 ({{ trades.length }} 笔)</div>
      <div class="tb-summary">
        <span class="tb-sum-good">盈利 {{ profitCount }} 笔</span>
        <span class="tb-sum-divider">|</span>
        <span class="tb-sum-bad">亏损 {{ lossCount }} 笔</span>
        <span class="tb-sum-divider">|</span>
        <span>总盈亏 ¥{{ totalPnl.toFixed(2) }}</span>
      </div>
    </div>

    <div class="tb-table-wrap" ref="scrollRef">
      <table class="tb-table">
        <thead>
          <tr>
            <th>日期</th>
            <th>代码</th>
            <th>操作</th>
            <th>价格</th>
            <th>数量</th>
            <th>金额</th>
            <th>盈亏</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in sortedTrades" :key="t.date + t.type + t.code"
              :class="{ 'row-profit': t.profit > 0, 'row-loss': t.profit < 0 }">
            <td class="td-date">{{ t.date }}</td>
            <td class="td-code">{{ t.code }}</td>
            <td>
              <el-tag :type="tagType(t.type)" size="small" effect="plain">{{ tagLabel(t.type) }}</el-tag>
            </td>
            <td class="td-num">¥{{ t.price }}</td>
            <td class="td-num">{{ t.shares || '-' }}</td>
            <td class="td-num">{{ formatMoney(t) }}</td>
            <td class="td-pnl">
              <span v-if="t.profit !== undefined" :class="t.profit >= 0 ? 'pnl-up' : 'pnl-down'">
                {{ t.profit >= 0 ? '+' : '' }}¥{{ t.profit.toFixed(2) }}
              </span>
              <span v-else>-</span>
            </td>
            <td class="td-reason">{{ t.reason || '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  strategyName: string
  trades: any[]
}>()

const sortedTrades = computed(() => {
  return [...(props.trades || [])].sort((a, b) => {
    if (a.date !== b.date) return b.date.localeCompare(a.date)
    return a.code?.localeCompare(b.code || '') || 0
  })
})

const profitCount = computed(() => props.trades?.filter(t => (t.profit || 0) > 0).length || 0)
const lossCount = computed(() => props.trades?.filter(t => (t.profit || 0) < 0).length || 0)
const totalPnl = computed(() => props.trades?.reduce((s, t) => s + (t.profit || 0), 0) || 0)

function tagType(t: string) {
  if (t === 'buy') return 'success'
  if (t === 'sell' || t === 'stop_loss') return 'danger'
  if (t === 'take_profit') return 'info'
  return ''
}

function tagLabel(t: string) {
  const map: Record<string, string> = { buy: '买入', sell: '卖出', stop_loss: '止损', take_profit: '止盈' }
  return map[t] || t
}

function formatMoney(t: any) {
  if (t.cost) return `¥${t.cost.toLocaleString()}`
  if (t.proceeds) return `¥${t.proceeds.toLocaleString()}`
  return '-'
}
</script>

<style scoped>
.trade-breakdown {
  background: #fff;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
}

.tb-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

.tb-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.tb-summary {
  font-size: 12px;
  color: #64748b;
}

.tb-sum-good { color: #16a34a; font-weight: 600; }
.tb-sum-bad { color: #dc2626; font-weight: 600; }
.tb-sum-divider { margin: 0 8px; color: #cbd5e1; }

.tb-table-wrap {
  max-height: 360px;
  overflow-y: auto;
}

.tb-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.tb-table th {
  text-align: left;
  padding: 6px 10px;
  background: #f8fafc;
  color: #64748b;
  font-weight: 600;
  font-size: 11px;
  border-bottom: 2px solid #e2e8f0;
  position: sticky;
  top: 0;
  z-index: 1;
}

.tb-table td {
  padding: 5px 10px;
  border-bottom: 1px solid #f1f5f9;
  color: #334155;
}

.row-profit { background: #f0fdf4; }
.row-loss { background: #fef2f2; }

.td-date { color: #94a3b8; font-family: monospace; font-size: 11px; white-space: nowrap; }
.td-code { font-family: monospace; font-weight: 600; }
.td-num { font-family: monospace; }
.td-pnl { font-family: monospace; font-weight: 600; }
.pnl-up { color: #16a34a; }
.pnl-down { color: #dc2626; }
.td-reason { color: #e6a23c; font-size: 11px; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
