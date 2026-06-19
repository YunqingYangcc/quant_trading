<template>
  <div class="home-page">
    <!-- 顶部标题 -->
    <div class="hero-section">
      <div class="hero-text">
        <h1>量化交易跟踪系统</h1>
        <p>Quantitative Trading & Tracking System</p>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="3" animated />
    </div>

    <!-- 4 赛道卡片 -->
    <div v-else class="track-grid">
      <div
        v-for="track in tracksWithProsperity"
        :key="track.name"
        class="track-card"
        :style="{ borderTop: `4px solid ${track.color}` }"
        @click="goToTrack(track.name)"
      >
        <div class="card-header">
          <span class="card-name">{{ track.displayName }}</span>
          <div v-if="track.prosperity != null" class="card-prosperity">
            <div class="prosperity-ring" :style="{ borderColor: prosperityColor(track.prosperity) }">
              {{ track.prosperity }}
            </div>
          </div>
        </div>

        <div class="card-stocks">
          <div class="stock-row" v-for="s in track.topStocks?.slice(0, 3)" :key="s.stock_code">
            <span class="stock-code">{{ s.stock_code }}</span>
            <div class="stock-score-bar">
              <div class="score-fill" :style="{ width: scorePct(s.score) + '%', background: s.score > 0 ? '#67c23a' : '#f56c6c' }" />
            </div>
            <span class="stock-score">{{ (s.score * 100).toFixed(2) }}</span>
          </div>
          <div v-if="!track.topStocks?.length" class="stock-empty-row">
            <span class="stock-empty-text">AI scores loading...</span>
          </div>
        </div>

        <div class="card-footer">
          <span class="footer-count">{{ track.stockCount }} stocks</span>
          <el-tag v-if="track.prosperity != null" size="small"
            :type="track.prosperity >= 60 ? 'success' : track.prosperity >= 40 ? 'warning' : 'danger'"
            round effect="plain">
            {{ track.prosperity >= 60 ? 'Favorable' : track.prosperity >= 40 ? 'Neutral' : 'Caution' }}
          </el-tag>
        </div>
      </div>
    </div>

    <!-- 底部区域：流水线 -->
    <div class="bottom-section">
      <div class="pipeline-wrapper">
        <PipelineStatus />
      </div>
      <div class="pipeline-wrapper">
        <div class="quick-stats-card">
          <div class="qs-title">⚡ Quick Stats</div>
          <div class="qs-grid">
            <div class="qs-item">
              <span class="qs-value">{{ stats.stocks }}</span>
              <span class="qs-label">Stocks</span>
            </div>
            <div class="qs-item">
              <span class="qs-value">{{ stats.whitelist }}</span>
              <span class="qs-label">Factors ✅</span>
            </div>
            <div class="qs-item">
              <span class="qs-value">{{ stats.models }}</span>
              <span class="qs-label">Models</span>
            </div>
            <div class="qs-item">
              <span class="qs-value">{{ stats.backtestReturn }}</span>
              <span class="qs-label">BT Return</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listTracks, getTrackScore, getAllTrackScores, type Track } from '@/api/track'
import PipelineStatus from '@/components/tracks/PipelineStatus.vue'

const router = useRouter()
const tracks = ref<Track[]>([])
const loading = ref(true)
const prosperityMap = ref<Record<string, any>>({})
const trackScores = ref<Record<string, any[]>>({})
const stats = ref({
  stocks: 0,
  whitelist: 0,
  models: 0,
  backtestReturn: '-',
})

const trackColors: Record<string, string> = {
  semiconductor: '#3b82f6',
  ai: '#f59e0b',
  robot: '#10b981',
  storage: '#8b5cf6',
}

const tracksWithProsperity = computed(() =>
  tracks.value.map(t => {
    const p = prosperityMap.value[t.name]
    const scores = trackScores.value[t.name] || []
    return {
      name: t.name,
      displayName: t.display_name,
      stockCount: t.stock_count,
      color: trackColors[t.name] || '#909399',
      prosperity: p?.track_sentiment,
      topStocks: scores.slice(0, 3),
    }
  })
)

// ── 全市场 Top Picks ──
const topPicks = computed(() => {
  const all: { code: string; score: number; track: string; trackName: string; scorePct: number }[] = []
  for (const t of tracks.value) {
    const scores = trackScores.value[t.name] || []
    for (const s of scores.slice(0, 1)) {
      all.push({
        code: s.stock_code,
        score: parseFloat((s.score * 100).toFixed(2)),
        track: t.name,
        trackName: t.display_name,
        scorePct: Math.min(100, (s.score + 0.02) * 2000),
      })
    }
  }
  return all.sort((a, b) => b.score - a.score).slice(0, 5)
})

function prosperityColor(val: number | undefined): string {
  if (!val) return '#c0c4cc'
  if (val >= 60) return '#67c23a'
  if (val >= 40) return '#e6a23c'
  return '#f56c6c'
}

function goToTrack(name: string) {
  router.push(`/track/${name}`)
}

function scorePct(score: number): number {
  return Math.min(95, Math.max(5, (score + 0.02) * 2000))
}

onMounted(async () => {
  try {
    const trackRes = await listTracks()
    tracks.value = trackRes?.items || []

    // 加载所有赛道打分
    const allScores = await getAllTrackScores()
    if (allScores && typeof allScores === 'object') {
      for (const [name, data] of Object.entries(allScores) as [string, any][]) {
        if (data?.track_sentiment != null) {
          prosperityMap.value[name] = data
          trackScores.value[name] = data.scores || []
        }
      }
    }

    // 逐个赛道加载（fallback）
    for (const t of tracks.value) {
      if (!prosperityMap.value[t.name]) {
        try {
          const res = await getTrackScore(t.name)
          if (res?.track_sentiment != null) {
            prosperityMap.value[t.name] = res
            trackScores.value[t.name] = res.scores || []
          }
        } catch {}
      }
    }

    // 加载统计
    try {
      const [wl, tr] = await Promise.all([
        getWhitelist(),
        getBlacklist(),
      ].catch(() => []))
      const wlCount = Array.isArray(wl) ? wl.length : 0
      const trackItems = tr?.items || trackRes?.items || []
      stats.value.stocks = trackItems.reduce((s: number, t: any) => s + (t.stock_count || 0), 0)
      stats.value.whitelist = wlCount
      stats.value.models = tracks.value.length
      // 回测收益
      try {
        const btResp = await fetch('http://localhost:8000/api/v1/backtest/report')
        const bt = await btResp.json()
        stats.value.backtestReturn = (bt.total_return || 0).toFixed(1) + '%'
      } catch {}
    } catch {}
  } catch {
    // silent fail
  } finally {
    loading.value = false
  })
</script>

<style scoped>
.home-page {
  height: calc(100vh - 52px);
  overflow-y: auto;
  padding: 24px 32px;
  background: linear-gradient(135deg, #f0f4ff 0%, #f5f7fa 100%);
}

/* ── Hero ── */
.hero-section {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 24px;
}

.hero-text h1 {
  font-size: 26px;
  font-weight: 700;
  color: #1e293b;
  margin: 0;
}

.hero-text p {
  font-size: 14px;
  color: #94a3b8;
  margin: 4px 0 0;
}

.hero-badges {
  display: flex;
  gap: 6px;
}

/* ── 4 赛道网格 ── */
.track-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.track-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.25s;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.track-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.card-name {
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
}

.card-prosperity {
  display: flex;
  align-items: center;
}

.prosperity-ring {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 3px solid;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  color: #303133;
}

.card-stocks {
  margin-bottom: 12px;
}

.stock-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 0;
}

.stock-code {
  font-size: 11px;
  font-family: 'SF Mono', monospace;
  color: #606266;
  min-width: 80px;
}

.stock-score-bar {
  flex: 1;
  height: 4px;
  background: #f0f2f5;
  border-radius: 2px;
  overflow: hidden;
}

.score-fill {
  height: 100%;
  border-radius: 2px;
}

.stock-score {
  font-size: 11px;
  font-weight: 600;
  color: #606266;
  min-width: 36px;
  text-align: right;
}

.stock-empty-row {
  padding: 8px 0;
}

.stock-empty-text {
  font-size: 11px;
  color: #c0c4cc;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid #f0f2f5;
  padding-top: 10px;
}

.footer-count {
  font-size: 12px;
  color: #909399;
}

/* ── 底部 ── */
.bottom-section {
  display: flex;
  gap: 16px;
}



.quick-stats-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  height: 100%;
}

.qs-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
}

.qs-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.qs-item {
  text-align: center;
  padding: 8px;
  background: #f8fafc;
  border-radius: 6px;
}

.qs-value {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: #303133;
}

.qs-label {
  font-size: 11px;
  color: #909399;
}

.loading-state {
  padding: 40px;
  background: #fff;
  border-radius: 10px;
  margin-bottom: 20px;
}
.pipeline-wrapper {
  width: 280px;
  flex-shrink: 0;
}


.lb-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.lb-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.lb-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.lb-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.lb-row:hover {
  background: #f0f2f5;
}

.lb-rank {
  font-size: 16px;
  width: 28px;
  text-align: center;
}

.lb-code {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
  min-width: 90px;
}

.lb-track {
  font-size: 11px;
  color: #909399;
  min-width: 56px;
}

.lb-score-bar {
  flex: 1;
  height: 5px;
  background: #f0f2f5;
  border-radius: 3px;
  overflow: hidden;
  max-width: 120px;
}

.lb-score-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
  border-radius: 3px;
}

.lb-score {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  min-width: 36px;
  text-align: right;
}
</style>
