<template>
  <div class="rank-panel">
    <div class="panel-header">
      <span class="panel-title">AI 强弱排名</span>
      <el-tag v-if="loading" size="small" type="info" effect="plain">加载中...</el-tag>
      <el-tag v-else size="small" type="success" effect="plain" v-text="trackName" />
    </div>

    <div class="rank-list" v-if="sortedScores.length">
      <div
        v-for="(s, i) in sortedScores"
        :key="s.stock_code"
        class="rank-row"
        :class="{ selected: selectedCode === s.stock_code, top: i === 0 }"
        @click="onSelect(s.stock_code)"
      >
        <div class="rank-position" :class="{ medal: i < 3 }">
          <span v-if="i === 0">🥇</span>
          <span v-else-if="i === 1">🥈</span>
          <span v-else-if="i === 2">🥉</span>
          <span v-else>{{ i + 1 }}</span>
        </div>
        <div class="rank-info">
          <span class="rank-name">{{ s.stock_code }}</span>
        </div>
        <div class="rank-score">
          <div
            class="score-bar"
            :style="{ width: scorePct(s.score) + '%', background: scoreColor(s.score) }"
          />
          <span class="score-value">{{ (s.score * 100).toFixed(2) }}</span>
        </div>
      </div>
    </div>

    <div v-else class="rank-list">
      <div v-for="(stock, i) in mockRanks" :key="stock.code" class="rank-row" @click="onSelect(stock.code)">
        <div class="rank-position"><span>{{ i + 1 }}</span></div>
        <div class="rank-info"><span class="rank-name">{{ stock.name }}</span></div>
        <div class="rank-score">
          <div class="score-value" style="color:#909399;font-size:10px">Mock</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { getTrackScore } from '@/api/track'

const props = defineProps<{ selectedCode?: string; trackName?: string }>()
const emit = defineEmits<{ select: [code: string] }>()

const loading = ref(false)
const scores = ref<any[]>([])

const sortedScores = computed(() =>
  [...scores.value].sort((a, b) => b.score - a.score)
)

function onSelect(code: string) {
  emit('select', code)
}

function scorePct(score: number): number {
  // 映射到 10-95% 范围
  return Math.min(95, Math.max(10, (score + 0.02) * 2000))
}

function scoreColor(score: number): string {
  if (score > 0.01) return '#67c23a'
  if (score > 0) return '#e6a23c'
  return '#f56c6c'
}

async function loadScores(track: string) {
  if (!track) return
  loading.value = true
  try {
    const res = await getTrackScore(track)
    scores.value = res?.scores || []
  } catch {
    scores.value = []
  } finally {
    loading.value = false
  }
}

watch(() => props.trackName, (val) => { loadScores(val!) }, { immediate: true })

const mockRanks = [
  { code: '688041.SH', name: '海光信息', score: 92 },
  { code: '300502.SZ', name: '新易盛', score: 85 },
  { code: '002281.SZ', name: '光迅科技', score: 78 },
  { code: '300308.SZ', name: '中际旭创', score: 72 },
  { code: '601138.SH', name: '工业富联', score: 65 },
]
</script>

<style scoped>
.rank-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fafbfc;
  border-right: 1px solid #ebedf0;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid #ebedf0;
  flex-shrink: 0;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.rank-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.rank-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  cursor: pointer;
  transition: background 0.15s;
}

.rank-row:hover {
  background: #f0f2f5;
}

.rank-row.selected {
  background: #ecf5ff;
}

.rank-row.top {
  background: linear-gradient(90deg, #f0f9eb 0%, transparent 100%);
}

.rank-position {
  width: 24px;
  text-align: center;
  font-size: 13px;
  font-weight: 600;
  color: #909399;
  flex-shrink: 0;
}

.rank-position.medal {
  font-size: 16px;
}

.rank-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.rank-name {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rank-code {
  font-size: 11px;
  color: #909399;
}

.rank-score {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  width: 80px;
}

.score-bar {
  height: 6px;
  border-radius: 3px;
  flex: 1;
  min-width: 20px;
}

.score-value {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  min-width: 24px;
  text-align: right;
}

.mock-notice {
  padding: 8px 12px;
  flex-shrink: 0;
}
</style>
