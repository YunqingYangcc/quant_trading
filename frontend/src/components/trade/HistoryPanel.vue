<template>
  <div class="history-panel">
    <div class="hp-header" @click="expanded = !expanded">
      <div class="hp-left">
        <span class="hp-icon">📋</span>
        <span class="hp-title">回测实验记录</span>
        <el-tag size="small" type="info" effect="plain">{{ history.length }} 次</el-tag>
      </div>
      <el-icon :class="{ 'hp-rotate': expanded }">
        <ArrowDownBold />
      </el-icon>
    </div>

    <template v-if="expanded">
      <div v-if="loading" class="hp-loading">加载中...</div>
      <div v-else-if="!history.length" class="hp-empty">
        <el-empty description="暂无回测记录，跑一次回测就会出现在这里" :image-size="80" />
      </div>
      <div v-else class="hp-list">
        <div v-for="r in history" :key="r.id" class="hp-item" @click="$emit('select', r)">
          <div class="hp-item-top">
            <span class="hp-item-time">{{ formatTime(r.created_at) }}</span>
            <el-tag :type="r.status === 'success' ? 'success' : 'danger'" size="small" effect="plain">
              {{ r.status }}
            </el-tag>
          </div>
          <div class="hp-item-body" v-if="r.results_summary">
            <span class="hp-item-stat" v-for="(v, k) in topResults(r.results_summary)" :key="k">
              {{ k }}: 夏普 {{ v.sharpe_ratio }}
            </span>
          </div>
          <div class="hp-item-meta">
            <span>ID #{{ r.id }}</span>
            <span v-if="r.duration_seconds">{{ r.duration_seconds.toFixed(0) }}s</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ArrowDownBold } from '@element-plus/icons-vue'
import { getPipelineRuns } from '@/api/track'

defineEmits<{
  select: [run: any]
}>()

const expanded = ref(false)
const loading = ref(false)
const history = ref<any[]>([])

async function loadHistory() {
  loading.value = true
  try {
    history.value = await getPipelineRuns(20, 'backtest') as any
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

function formatTime(t: string) {
  if (!t) return ''
  const d = new Date(t)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

function topResults(summary: Record<string, any>) {
  if (!summary || typeof summary !== 'object') return {}
  const entries = Object.entries(summary).slice(0, 3)
  return Object.fromEntries(entries)
}

onMounted(() => {
  if (expanded.value) loadHistory()
})

// 展开时自动加载
import { watch } from 'vue'
watch(expanded, (v) => {
  if (v && !history.value.length) loadHistory()
})
</script>

<style scoped>
.history-panel {
  background: #fff;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
}

.hp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}

.hp-header:hover {
  background: #f8fafc;
}

.hp-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hp-icon { font-size: 16px; }
.hp-title { font-size: 14px; font-weight: 700; color: #1e293b; }

.hp-rotate {
  transform: rotate(180deg);
  transition: transform 0.2s;
}

.hp-loading {
  padding: 24px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
}

.hp-empty {
  padding: 16px;
}

.hp-list {
  max-height: 400px;
  overflow-y: auto;
}

.hp-item {
  padding: 12px 16px;
  border-top: 1px solid #f1f5f9;
  cursor: pointer;
  transition: background 0.15s;
}

.hp-item:hover {
  background: #f1f5f9;
}

.hp-item-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.hp-item-time {
  font-size: 12px;
  color: #94a3b8;
  font-family: monospace;
}

.hp-item-body {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 4px;
}

.hp-item-stat {
  font-size: 11px;
  color: #64748b;
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 4px;
}

.hp-item-meta {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #94a3b8;
}
</style>
