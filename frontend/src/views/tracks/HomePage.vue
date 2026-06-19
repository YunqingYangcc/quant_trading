<template>
  <div class="home-page">
    <!-- 顶部标题 -->
    <div class="hero-section">
      <div class="hero-text">
        <h1>赛道量化终端</h1>
        <p>AI 驱动的个人散户投资决策系统</p>
      </div>
      <div class="hero-badges">
        <el-tag size="large" type="success" effect="dark" round>Phase A-D ✅</el-tag>
        <el-tag size="large" type="warning" effect="dark" round>Phase E-F 🔄</el-tag>
        <el-tag size="large" type="info" effect="dark" round>Phase G-H ⏳</el-tag>
      </div>
    </div>

    <!-- 4 赛道卡片 -->
    <div class="track-grid">
      <div
        v-for="track in tracksWithProsperity"
        :key="track.name"
        class="track-card"
        :style="{ borderTop: `4px solid ${track.color}` }"
        @click="goToTrack(track.name)"
      >
        <div class="card-header">
          <span class="card-name">{{ track.displayName }}</span>
          <div class="card-prosperity">
            <div class="prosperity-ring" :style="{ borderColor: prosperityColor(track.prosperity) }">
              {{ track.prosperity ?? '-' }}
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
            <span class="stock-empty-text">暂无数据，请先训练模型</span>
          </div>
        </div>

        <div class="card-footer">
          <span class="footer-count">{{ track.stockCount }} 只成分股</span>
          <el-tag size="small" :type="track.prosperity && track.prosperity >= 40 ? 'success' : 'danger'" round effect="plain">
            {{ track.prosperity && track.prosperity >= 40 ? '可持仓' : '谨慎观望' }}
          </el-tag>
        </div>
      </div>
    </div>

    <!-- 底部区域：流水线 + 排行榜 -->
    <div class="bottom-section">
      <div class="pipeline-wrapper">
        <PipelineStatus />
      </div>
      <div class="leaderboard-wrapper">
        <div class="leaderboard-card">
          <div class="lb-header">
            <span class="lb-title">🏆 全市场 Top Picks</span>
            <el-tag size="small" type="warning" round>AI 推荐</el-tag>
          </div>
          <div class="lb-list">
            <div v-for="(item, i) in topPicks" :key="i" class="lb-row" @click="goToTrack(item.track)">
              <span class="lb-rank">{{ ['🥇','🥈','🥉'][i] || i+1 }}</span>
              <span class="lb-code">{{ item.code }}</span>
              <span class="lb-track">{{ item.trackName }}</span>
              <div class="lb-score-bar">
                <div class="lb-score-fill" :style="{ width: item.scorePct + '%' }" />
              </div>
              <span class="lb-score">{{ item.score }}</span>
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
const prosperityMap = ref<Record<string, any>>({})
const trackScores = ref<Record<string, any[]>>({})

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
  } catch {}
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

.pipeline-wrapper {
  width: 280px;
  flex-shrink: 0;
}

.leaderboard-wrapper {
  flex: 1;
}

.leaderboard-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  height: 100%;
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
