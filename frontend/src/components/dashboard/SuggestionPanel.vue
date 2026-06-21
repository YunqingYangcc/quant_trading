<template>
  <div class="suggestion-panel">
    <div class="panel-header">
      <div class="header-left">
        <span class="header-icon">📊</span>
        <span class="header-title">每日交易建议</span>
      </div>
      <span class="header-date">{{ updatedAt }}</span>
    </div>

    <div v-if="loading" class="panel-loading">
      <el-skeleton :rows="3" animated />
    </div>

    <div v-else-if="!suggestions.length" class="panel-empty">
      暂无交易建议 — 请先在 Backtest Lab 运行回测
    </div>

    <div v-else class="suggestion-table">
      <div class="table-header">
        <span class="col-track">赛道</span>
        <span class="col-trend">趋势</span>
        <span class="col-strategy">推荐策略</span>
        <span class="col-picks">关注个股</span>
      </div>

      <div
        v-for="item in suggestions"
        :key="item.track_name"
        class="table-row"
        :class="'trend-' + item.trend"
        @click="goToTrack(item.track_name)"
      >
        <span class="col-track">
          <span class="track-name">{{ item.display_name }}</span>
        </span>

        <span class="col-trend">
          <span class="trend-badge" :class="'badge-' + item.trend">
            {{ trendIcon(item.trend) }} {{ item.trend_label }}
          </span>
        </span>

        <span class="col-strategy">
          <template v-if="item.best_strategy">
            <span class="strategy-name">{{ item.best_strategy.name }}</span>
            <span class="strategy-sharpe">夏普 {{ item.best_strategy.sharpe }}</span>
          </template>
          <span v-else class="strategy-fallback">暂无回测数据</span>
        </span>

        <span class="col-picks">
          <template v-if="item.top_picks.length">
            <span
              v-for="(pick, i) in item.top_picks.slice(0, 3)"
              :key="pick.code"
              class="pick-chip"
            >{{ pick.name || formatCode(pick.code) }}</span>
          </template>
          <span v-else class="pick-empty">—</span>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { SuggestionItem } from '@/api/track'

const props = defineProps<{
  suggestions: SuggestionItem[]
  loading: boolean
  updatedAt: string
}>()

const router = useRouter()

function goToTrack(name: string) {
  router.push(`/track/${name}`)
}

function trendIcon(trend: string): string {
  if (trend === 'up') return '↑'
  if (trend === 'down') return '↓'
  return '→'
}

function formatCode(code: string): string {
  // 688981.SH → 688981
  return code.split('.')[0] || code
}
</script>

<style scoped>
.suggestion-panel {
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  margin-bottom: 20px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid #f0f2f5;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-icon {
  font-size: 18px;
}

.header-title {
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
}

.header-date {
  font-size: 12px;
  color: #94a3b8;
}

.panel-loading,
.panel-empty {
  padding: 32px 24px;
  text-align: center;
  font-size: 13px;
  color: #94a3b8;
}

.suggestion-table {
  width: 100%;
}

.table-header {
  display: flex;
  padding: 10px 24px;
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.table-row {
  display: flex;
  align-items: center;
  padding: 12px 24px;
  cursor: pointer;
  transition: background 0.15s;
  border-top: 1px solid #f8fafc;
}

.table-row:hover {
  background: #f8fafc;
}

.table-row.trend-down:hover {
  background: #fef2f2;
}

.col-track {
  flex: 0 0 110px;
  font-size: 17px;
}

.track-name {
  font-weight: 600;
  color: #1e293b;
}

.col-trend {
  flex: 0 0 100px;
}

.trend-badge {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 600;
}

.badge-up {
  background: #f0fdf4;
  color: #16a34a;
}

.badge-neutral {
  background: #fffbeb;
  color: #d97706;
}

.badge-down {
  background: #fef2f2;
  color: #dc2626;
}

.col-strategy {
  flex: 0 0 185px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.strategy-name {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.strategy-sharpe {
  font-size: 11px;
  color: #94a3b8;
  white-space: nowrap;
}

.strategy-fallback {
  font-size: 12px;
  color: #c0c4cc;
  font-style: italic;
}

.col-picks {
  flex: 1;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.pick-chip {
  display: inline-block;
  padding: 3px 10px;
  background: #f1f5f9;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #475569;
}

.pick-empty {
  font-size: 13px;
  color: #c0c4cc;
}

.trend-down .pick-chip {
  color: #94a3b8;
}
</style>
