<template>
  <div class="prosperity-panel">
    <div class="panel-header">
      <span class="panel-title">赛道景气度</span>
      <el-tag v-if="loading" size="small" type="info" effect="plain">加载中...</el-tag>
    </div>

    <div class="prosperity-list">
      <div
        v-for="track in sortedTracks"
        :key="track.name"
        class="prosperity-row"
        :class="{ active: activeTrack === track.name }"
        @click="$emit('switch-track', track.name)"
      >
        <span class="track-name">{{ track.displayName || track.name }}</span>
        <div class="prosperity-meter">
          <div
            class="prosperity-bar"
            :style="{ width: (track.prosperity || 0) + '%', background: prosperityColor(track.prosperity || 0) }"
          />
        </div>
        <span class="prosperity-value" :style="{ color: prosperityColor(track.prosperity || 0) }">
          {{ track.prosperity || '-' }}
        </span>
      </div>
    </div>

    <div v-if="!tracks.length && !sortedTracks.length" class="empty-state">
      <el-alert title="加载赛道数据..." type="info" :closable="false" show-icon size="small" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getAllTrackScores } from '@/api/track'

const props = defineProps<{
  tracks: { name: string; displayName?: string; prosperity?: number }[]
  activeTrack?: string
}>()
defineEmits<{ 'switch-track': [name: string] }>()

const loading = ref(false)
const apiScores = ref<Record<string, any>>({})

const sortedTracks = computed(() => {
  const entries = Object.entries(apiScores.value)
  const apiList = entries
    .filter(([_, v]) => v && typeof v.track_sentiment === 'number')
    .map(([name, v]) => ({
      name,
      displayName: v.display_name || name,
      prosperity: Math.round(v.track_sentiment),
    }))
    .sort((a, b) => (b.prosperity || 0) - (a.prosperity || 0))

  // 有 API 数据用 API，没有用 props
  return apiList.length ? apiList : props.tracks
})

async function loadProsperity() {
  loading.value = true
  try {
    const res = await getAllTrackScores()
    apiScores.value = res || {}
  } catch {
    apiScores.value = {}
  } finally {
    loading.value = false
  }
}

onMounted(loadProsperity)

function prosperityColor(val: number): string {
  if (val >= 60) return '#67c23a'
  if (val >= 40) return '#e6a23c'
  return '#f56c6c'
}
</script>

<style scoped>
.prosperity-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fafbfc;
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

.prosperity-list {
  padding: 8px 12px;
  flex: 1;
}

.prosperity-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 4px;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.15s;
}

.prosperity-row:hover {
  background: #f0f2f5;
}

.prosperity-row.active {
  background: #ecf5ff;
}

.track-name {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
  min-width: 48px;
  flex-shrink: 0;
}

.prosperity-meter {
  flex: 1;
  height: 8px;
  background: #f0f2f5;
  border-radius: 4px;
  overflow: hidden;
}

.prosperity-bar {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.prosperity-value {
  font-size: 13px;
  font-weight: 600;
  min-width: 28px;
  text-align: right;
}

.empty-state {
  padding: 8px 12px;
}
</style>
