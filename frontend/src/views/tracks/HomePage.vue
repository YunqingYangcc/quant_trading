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
            <div class="stock-info">
              <span class="stock-name">{{ s.stock_name || s.stock_code }}</span>
              <span v-if="s.stock_name" class="stock-code-sm">{{ s.stock_code }}</span>
            </div>
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

    <!-- 底部区域：数据流水线 + Quick Stats -->
    <div class="bottom-section">
      <div class="bs-left">
        <PipelineStatus />
      </div>
      <div class="bs-right">
        <div class="quick-stats-card">
          <div class="qs-header">
            <div class="qs-header-left">
              <div class="qs-icon-box">⚡</div>
              <div>
                <div class="qs-title">Quick Stats</div>
                <div class="qs-subtitle">全系统关键指标速览</div>
              </div>
            </div>
            <div class="qs-live-dot">
              <span class="live-indicator" />
              <span class="live-text">Live</span>
            </div>
          </div>
          <div class="qs-divider" />
          <div class="qs-grid">
            <div class="qs-item">
              <div class="qs-item-top">
                <span class="qs-item-icon">📈</span>
                <span class="qs-value">{{ stats.stocks }}</span>
              </div>
              <span class="qs-label">跟踪标的</span>
              <div class="qs-bar">
                <div class="qs-bar-fill" style="width:45%;background:#3b82f6" />
              </div>
            </div>
            <div class="qs-item">
              <div class="qs-item-top">
                <span class="qs-item-icon">🧪</span>
                <span class="qs-value">{{ stats.whitelist }}</span>
              </div>
              <span class="qs-label">有效因子</span>
              <div class="qs-bar">
                <div class="qs-bar-fill" style="width:72%;background:#10b981" />
              </div>
            </div>
            <div class="qs-item">
              <div class="qs-item-top">
                <span class="qs-item-icon">🤖</span>
                <span class="qs-value">{{ stats.models }}</span>
              </div>
              <span class="qs-label">赛道模型</span>
              <div class="qs-bar">
                <div class="qs-bar-fill" style="width:60%;background:#8b5cf6" />
              </div>
            </div>
            <div class="qs-item">
              <div class="qs-item-top">
                <span class="qs-item-icon">💰</span>
                <span class="qs-value">{{ stats.backtestReturn }}</span>
              </div>
              <span class="qs-label">回测收益</span>
              <div class="qs-bar">
                <div class="qs-bar-fill" :style="{ width:'80%', background: backtestReturnColor }" />
              </div>
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
import { listTracks, getTrackScore, getAllTrackScores, getWhitelist, getBlacklist, getBacktestReport, type Track } from '@/api/track'
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

const backtestReturnColor = computed(() => {
  const val = stats.value.backtestReturn
  if (val === '-' || !val) return '#909399'
  const num = parseFloat(val)
  if (isNaN(num)) return '#909399'
  return num >= 0 ? '#f59e0b' : '#f56c6c'
})

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
      const [wl] = await Promise.all([
        getWhitelist(),
        getBlacklist(),
      ]).catch(() => [] as any)
      const wlCount = Array.isArray(wl) ? wl.length : 0
      const trackItems = trackRes?.items || []
      stats.value.stocks = trackItems.reduce((s: number, t: any) => s + (t.stock_count || 0), 0)
      stats.value.whitelist = wlCount
      stats.value.models = tracks.value.length
      // 回测收益
      try {
        const bt = await getBacktestReport()
        const m = bt?.metrics || (Array.isArray(bt) ? bt[0] : bt) || {}
        stats.value.backtestReturn = (m.total_return || 0).toFixed(1) + '%'
      } catch {}
    } catch {}
  } catch {
    // silent fail
  }
  loading.value = false
})
</script>

<style scoped>
.home-page {
  min-height: 100%;
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

.stock-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.stock-name {
  font-size: 12px;
  font-weight: 600;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stock-code-sm {
  font-size: 10px;
  color: #c0c4cc;
  font-family: 'SF Mono', monospace;
}

.stock-score-bar {
  flex: 1;
  height: 4px;
  background: #f0f2f5;
  border-radius: 2px;
  overflow: hidden;
  max-width: 80px;
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
  gap: 20px;
  margin-top: 4px;
}

.bs-left {
  flex: 1;
  min-width: 0;
  max-width: 420px;
}

.bs-right {
  flex: 1;
  min-width: 0;
}

/* ── Quick Stats 高级卡片 ── */
.quick-stats-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.03);
  height: 100%;
  transition: box-shadow 0.2s;
}

.quick-stats-card:hover {
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}

.qs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0;
}

.qs-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.qs-icon-box {
  width: 38px;
  height: 38px;
  background: linear-gradient(135deg, #fbbf24, #f59e0b);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  box-shadow: 0 2px 6px rgba(245,158,11,0.25);
}

.qs-title {
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
  line-height: 1.3;
}

.qs-subtitle {
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.3;
}

.qs-live-dot {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 20px;
}

.live-indicator {
  width: 6px;
  height: 6px;
  background: #22c55e;
  border-radius: 50%;
  animation: pulse-dot 2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(34,197,94,0.5); }
  50% { opacity: 0.7; box-shadow: 0 0 0 4px rgba(34,197,94,0); }
}

.live-text {
  font-size: 11px;
  font-weight: 600;
  color: #16a34a;
}

.qs-divider {
  height: 1px;
  background: linear-gradient(90deg, #e2e8f0 0%, #e2e8f0 60%, transparent 100%);
  margin: 14px 0 16px;
}

.qs-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.qs-item {
  padding: 14px 16px;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #f1f5f9;
  transition: all 0.2s;
}

.qs-item:hover {
  background: #fff;
  border-color: #e2e8f0;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.qs-item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.qs-item-icon {
  font-size: 16px;
  opacity: 0.8;
}

.qs-value {
  font-size: 22px;
  font-weight: 700;
  color: #1e293b;
  letter-spacing: -0.3px;
  line-height: 1;
}

.qs-label {
  display: block;
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 8px;
  font-weight: 500;
}

.qs-bar {
  height: 3px;
  background: #f0f2f5;
  border-radius: 2px;
  overflow: hidden;
}

.qs-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.6s ease;
}

.loading-state {
  padding: 40px;
  background: #fff;
  border-radius: 10px;
  margin-bottom: 20px;
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
