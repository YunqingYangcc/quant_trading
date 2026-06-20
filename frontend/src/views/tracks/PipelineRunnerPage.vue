<template>
  <div class="runner-page">
    <!-- 流水线控制面板 -->
    <div class="runner-control">
      <div class="rc-header">
        <div class="rc-title-row">
          <span class="rc-title-icon">⚙</span>
          <div>
            <div class="rc-title">Pipeline Runner</div>
            <div class="rc-subtitle">量化流水线控制台</div>
          </div>
        </div>
        <div class="rc-actions">
          <el-button
            v-if="isRunning"
            type="danger"
            size="small"
            @click="handleCancel"
            :loading="cancelling"
          >
            ⏹ 取消运行
          </el-button>
          <el-button
            v-else
            type="primary"
            size="small"
            @click="handleRun('all')"
            :loading="runLoading === 'all'"
          >
            ▶ 一键跑全部
          </el-button>
        </div>
      </div>

      <!-- 步骤控制 -->
      <div class="rc-steps">
        <div v-for="key in allSteps" :key="key" class="rc-step" :class="stepStatusClass(key)">
          <div class="rcs-indicator">
            <span v-if="stepStatus(key) === 'done'" class="rcs-dot done">✓</span>
            <span v-else-if="stepStatus(key) === 'running'" class="rcs-dot running">⟳</span>
            <span v-else-if="stepStatus(key) === 'failed'" class="rcs-dot failed">✕</span>
            <span v-else class="rcs-dot idle">○</span>
          </div>
          <div class="rcs-info">
            <div class="rcs-name">{{ getStepName(key) }}</div>
            <div class="rcs-desc">{{ getStepDesc(key) }}</div>
          </div>
          <div class="rcs-action">
            <el-button
              v-if="stepStatus(key) !== 'running'"
              size="small"
              text
              :disabled="isRunning"
              @click="handleRun(key)"
              :loading="runLoading === key"
            >
              运行
            </el-button>
            <el-tag v-else size="small" type="warning" effect="dark">运行中...</el-tag>
          </div>
        </div>
      </div>
    </div>

    <!-- Terminal 日志 -->
    <div class="runner-terminal" ref="terminalRef">
      <div class="rt-header">
        <span class="rt-title">▶ Terminal</span>
        <span v-if="isRunning" class="rt-badge running">RUNNING</span>
        <span v-else-if="lastStatus === 'completed'" class="rt-badge done">COMPLETED</span>
        <span v-else-if="lastStatus === 'failed'" class="rt-badge failed">FAILED</span>
        <span v-else-if="lastStatus === 'cancelled'" class="rt-badge cancelled">CANCELLED</span>
        <button class="rt-clear" @click="clearLogs">clear</button>
      </div>
      <div class="rt-body">
        <div v-if="terminalLines.length === 0" class="rt-empty">
          <span class="rt-prompt">$ _</span>
          <span class="rt-hint">点击「一键跑全部」或单独步骤开始</span>
        </div>
        <div v-for="(line, i) in terminalLines" :key="i" class="rt-line" :class="lineClass(line)">
          {{ line }}
        </div>
      </div>
    </div>

    <!-- 运行历史 -->
    <div class="runner-history">
      <div class="rh-header">
        <span class="rh-title">运行历史</span>
        <span class="rh-count">{{ history.length }} 条记录</span>
      </div>
      <div v-if="history.length === 0" class="rh-empty">暂无运行记录</div>
      <div v-for="task in history" :key="task.taskId" class="rh-item" :class="[
        'rh-' + task.status,
        { 'rh-expanded': expandedHistory.has(task.taskId) }
      ]">
        <div class="rhi-top" @click="toggleExpand(task.taskId)" style="cursor:pointer">
          <span class="rh-expand-icon">{{ expandedHistory.has(task.taskId) ? '▼' : '▶' }}</span>
          <el-tag :type="statusTagType(task.status)" size="small" effect="dark">
            {{ statusLabel(task.status) }}
          </el-tag>
          <span class="rhi-type-tag" :class="'rhi-type-' + task.runType">{{ task.runType === 'train' ? '训练' : '回测' }}</span>
          <span class="rhi-id">#{{ task.taskId }}</span>
          <span class="rhi-time">{{ formatTime(task.startedAt) }}</span>
        </div>
        <div class="rhi-steps">
          <span
            v-for="key in allSteps"
            :key="key"
            class="rhi-step-badge"
            :class="historyStepClass(task, key)"
          >
            {{ getStepName(key).replace('Phase ', '') }}
          </span>
        </div>
        <!-- 展开详情 -->
        <div v-if="expandedHistory.has(task.taskId)" class="rh-detail">
          <div v-if="task.runType === 'train'" class="rhd-section">
            <div class="rhd-section-title">训练参数</div>
            <div class="rhd-grid">
              <div v-for="(v, k) in task.params_snapshot" :key="k" class="rhd-item">
                <span class="rhd-key">{{ k }}</span>
                <span class="rhd-val">{{ typeof v === 'number' ? v.toFixed?.(4) ?? v : v }}</span>
              </div>
            </div>
            <div class="rhd-section-title">各赛道训练结果</div>
            <div v-for="(v, trackName) in task.steps.train" :key="trackName">
              <template v-if="trackName !== 'status'">
                <div class="rhd-track-header">{{ trackName }}</div>
                <div class="rhd-grid">
                  <div v-for="(mv, mk) in v" :key="mk" class="rhd-item">
                    <span class="rhd-key">{{ mk }}</span>
                    <span class="rhd-val" :class="{ 'rhd-overfit': mk === 'overfitting' && mv }">
                      {{ typeof mv === 'number' ? (mv * 100).toFixed(1) + '%' : mv === true ? '⚠ 是' : mv === false ? '否' : mv }}
                    </span>
                  </div>
                </div>
              </template>
            </div>
          </div>
          <div v-if="task.runType === 'backtest'" class="rhd-section">
            <div class="rhd-section-title">回测参数</div>
            <div class="rhd-grid">
              <div v-for="(v, k) in task.params_snapshot" :key="k" class="rhd-item">
                <span class="rhd-key">{{ k }}</span>
                <span class="rhd-val">{{ typeof v === 'number' ? (k.includes('_pct') || k === 'slippage' || k === 'commission' ? (v * 100).toFixed(2) + '%' : v.toFixed?.(4) ?? v) : String(v) }}</span>
              </div>
            </div>
            <div class="rhd-section-title">各频率回测绩效</div>
            <div v-for="(v, freqName) in task.steps.backtest" :key="freqName">
              <template v-if="freqName !== 'status'">
                <div class="rhd-track-header">{{ freqName }}</div>
                <div class="rhd-grid">
                  <div v-for="(mv, mk) in v" :key="mk" class="rhd-item">
                    <span class="rhd-key">{{ mk }}</span>
                    <span class="rhd-val" :class="{ 'rhd-negative': typeof mv === 'number' && mv < 0 }">
                      {{ typeof mv === 'number' ? mv.toFixed(2) : mv }}
                    </span>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onBeforeUnmount, onMounted } from 'vue'
import { usePipelineRunner } from '@/composables/usePipelineRunner'
import { getPipelineRuns } from '@/api/track'

const {
  state,
  startPipeline,
  cancelPipeline,
  getStepName,
  getStepDesc,
  getAllSteps,
} = usePipelineRunner()

const allSteps = getAllSteps()
const runLoading = ref<string | null>(null)
const cancelling = ref(false)
const terminalRef = ref<HTMLElement>()
const expandedHistory = ref<Set<string>>(new Set())

function toggleExpand(id: string) {
  if (expandedHistory.value.has(id)) {
    expandedHistory.value.delete(id)
  } else {
    expandedHistory.value.add(id)
  }
  // 触发响应式
  expandedHistory.value = new Set(expandedHistory.value)
}

const isRunning = computed(() => state.currentTask?.status === 'running')
const lastStatus = computed(() => state.currentTask?.status || '')
const history = computed(() => state.history)

// 合并当前任务日志和历史
const terminalLines = computed(() => {
  const lines: string[] = []
  if (state.currentTask) {
    lines.push(...state.currentTask.logs)
  }
  return lines
})

function stepStatus(key: string): string {
  if (!state.currentTask) return 'idle'
  if (state.currentTask.steps[key]?.status === 'failed') return 'failed'
  if (state.currentTask.step === key && state.currentTask.status === 'running') return 'running'
  if (state.currentTask.steps[key]?.status === 'success' || state.currentTask.steps[key]?.status) return 'done'
  return 'idle'
}

function stepStatusClass(key: string) {
  const s = stepStatus(key)
  return `rcs-${s}`
}

function historyStepClass(task: any, key: string): string {
  if (task.steps[key]?.status === 'failed') return 'rhsb-failed'
  if (task.steps[key]?.status === 'success' || task.steps[key]?.status) return 'rhsb-done'
  if (task.status === 'cancelled') return 'rhsb-cancelled'
  return 'rhsb-idle'
}

async function handleRun(step: string) {
  runLoading.value = step
  await startPipeline(step)
  runLoading.value = null
}

async function handleCancel() {
  cancelling.value = true
  await cancelPipeline()
  cancelling.value = false
}

function clearLogs() {
  if (state.currentTask) {
    state.currentTask.logs = []
  }
}

function lineClass(line: string): string {
  if (line.includes('❌') || line.includes('失败') || line.includes('异常')) return 'rt-error'
  if (line.includes('✅')) return 'rt-success'
  if (line.includes('⚠️') || line.includes('取消')) return 'rt-warn'
  if (line.includes('🎉')) return 'rt-done'
  if (line.includes('▶')) return 'rt-cmd'
  return ''
}

function statusTagType(status: string): string {
  switch (status) {
    case 'completed': return 'success'
    case 'failed': return 'danger'
    case 'cancelled': return 'info'
    case 'running': return 'warning'
    default: return ''
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case 'completed': return '完成'
    case 'failed': return '失败'
    case 'cancelled': return '已取消'
    case 'running': return '运行中'
    default: return status
  }
}

function formatTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

// 自动滚动到底部
watch(terminalLines, async () => {
  await nextTick()
  if (terminalRef.value) {
    terminalRef.value.querySelector('.rt-body')?.scrollTo({ top: 999999, behavior: 'smooth' })
  }
})

// 页面卸载时停止轮询
onBeforeUnmount(() => {
  if (state.currentTask?.pollingTimer) {
    clearInterval(state.currentTask.pollingTimer)
  }
})

// 页面挂载时从后端加载运行历史
onMounted(async () => {
  if (state.history.length > 0) return // 已有 session 内记录则不重复加载
  try {
    const res: any = await getPipelineRuns(20)
    const records = Array.isArray(res) ? res : (res?.data || [])
    state.history = records.map((r: any) => {
      // run_type → frontend step key
      const stepKey = r.run_type === 'train' ? 'train' : r.run_type === 'backtest' ? 'backtest' : r.run_type
      return {
        taskId: String(r.id),
        status: r.status === 'success' ? 'completed' : r.status === 'failed' ? 'failed' : 'completed',
        runType: r.run_type,
        params_snapshot: r.params_snapshot || {},
        steps: {
          [stepKey]: {
            status: r.status === 'success' ? 'success' : r.status,
            ...(r.results_summary || {}),
          },
        },
        startedAt: r.created_at,
        logs: [],
        pollingTimer: null,
      }
    })
  } catch {
    // ignore
  }
})
</script>

<style scoped>
.runner-page {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
  overflow-y: auto;
}

/* ═══════════ 控制面板 ═══════════ */
.runner-control {
  background: #fff;
  border-radius: 10px;
  padding: 16px 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}

.rc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.rc-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.rc-title-icon {
  font-size: 20px;
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  border-radius: 8px;
  color: white;
}

.rc-title {
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
}

.rc-subtitle {
  font-size: 11px;
  color: #94a3b8;
}

.rc-steps {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.rc-step {
  flex: 1;
  min-width: 140px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fafbfc;
  transition: all 0.2s;
}

.rc-step.rcs-running {
  border-color: #93c5fd;
  background: #eff6ff;
}

.rc-step.rcs-done {
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.rc-step.rcs-failed {
  border-color: #fecaca;
  background: #fef2f2;
}

.rcs-indicator {
  flex-shrink: 0;
}

.rcs-dot {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
}

.rcs-dot.done {
  background: #dcfce7;
  color: #16a34a;
}

.rcs-dot.running {
  background: #dbeafe;
  color: #2563eb;
  animation: spin 1.5s linear infinite;
}

.rcs-dot.failed {
  background: #fee2e2;
  color: #dc2626;
}

.rcs-dot.idle {
  background: #f1f5f9;
  color: #94a3b8;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.rcs-info {
  flex: 1;
  min-width: 0;
}

.rcs-name {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.rcs-desc {
  font-size: 10px;
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ═══════════ Terminal ═══════════ */
.runner-terminal {
  background: #0d1117;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  min-height: 200px;
  max-height: 400px;
  display: flex;
  flex-direction: column;
}

.rt-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: #161b22;
  border-bottom: 1px solid #30363d;
  flex-shrink: 0;
}

.rt-title {
  font-size: 11px;
  font-weight: 600;
  color: #58a6ff;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.rt-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
  font-family: 'SF Mono', monospace;
}

.rt-badge.running { background: #1a3a5c; color: #58a6ff; }
.rt-badge.done { background: #1a3c2a; color: #3fb950; }
.rt-badge.failed { background: #3c1a1a; color: #f78166; }
.rt-badge.cancelled { background: #2a2a1a; color: #d29922; }

.rt-clear {
  margin-left: auto;
  background: none;
  border: none;
  color: #484f58;
  font-size: 10px;
  cursor: pointer;
  font-family: 'SF Mono', monospace;
}

.rt-clear:hover { color: #8b949e; }

.rt-body {
  flex: 1;
  overflow-y: auto;
  padding: 10px 14px;
  font-family: 'SF Mono', 'Fira Code', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.7;
}

.rt-body::-webkit-scrollbar { width: 4px; }
.rt-body::-webkit-scrollbar-thumb { background: #30363d; border-radius: 2px; }

.rt-empty {
  color: #8b949e;
}

.rt-prompt {
  color: #3fb950;
  margin-right: 8px;
}

.rt-hint {
  color: #484f58;
  font-size: 11px;
}

.rt-line {
  white-space: pre-wrap;
  word-break: break-all;
  color: #c9d1d9;
}

.rt-line.rt-cmd { color: #58a6ff; }
.rt-line.rt-success { color: #3fb950; }
.rt-line.rt-error { color: #f78166; }
.rt-line.rt-warn { color: #d29922; }
.rt-line.rt-done { color: #7ee787; font-weight: 600; }

/* ═══════════ History ═══════════ */
.runner-history {
  background: #fff;
  border-radius: 10px;
  padding: 14px 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}

.rh-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.rh-title {
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
}

.rh-count {
  font-size: 11px;
  color: #94a3b8;
}

.rh-empty {
  color: #94a3b8;
  font-size: 12px;
  padding: 8px 0;
}

.rh-item {
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  margin-bottom: 8px;
}

.rh-item.rh-completed { border-left: 3px solid #22c55e; }
.rh-item.rh-failed { border-left: 3px solid #ef4444; }
.rh-item.rh-cancelled { border-left: 3px solid #94a3b8; }
.rh-item.rh-running { border-left: 3px solid #3b82f6; }

.rhi-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.rhi-id {
  font-size: 11px;
  color: #64748b;
  font-family: 'SF Mono', monospace;
}

.rhi-time {
  font-size: 11px;
  color: #94a3b8;
  margin-left: auto;
}

.rhi-steps {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.rhi-step-badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  background: #f1f5f9;
  color: #94a3b8;
}

.rhi-step-badge.rhsb-done {
  background: #dcfce7;
  color: #16a34a;
}

.rhi-step-badge.rhsb-failed {
  background: #fee2e2;
  color: #dc2626;
}

.rhi-step-badge.rhsb-cancelled {
  background: #f1f5f9;
  color: #94a3b8;
  text-decoration: line-through;
}

.rhi-step-meta {
  color: inherit;
  opacity: 0.7;
  margin-left: 2px;
}

/* ═══════════ Detail Panel ═══════════ */
.rh-expand-icon {
  font-size: 9px;
  color: #94a3b8;
  width: 14px;
  flex-shrink: 0;
  transition: transform 0.15s;
}

.rhi-type-tag {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 3px;
  font-weight: 600;
}
.rhi-type-train { background: #dbeafe; color: #2563eb; }
.rhi-type-backtest { background: #d1fae5; color: #059669; }

.rh-item.rh-expanded {
  border-color: #93c5fd;
  background: #f8faff;
}

.rh-detail {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #e2e8f0;
}

.rhd-section {
  margin-bottom: 6px;
}

.rhd-section-title {
  font-size: 12px;
  font-weight: 700;
  color: #475569;
  margin: 8px 0 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid #eef2f6;
}

.rhd-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 4px 12px;
  margin-bottom: 6px;
}

.rhd-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  line-height: 1.6;
}

.rhd-key {
  color: #94a3b8;
  font-family: 'SF Mono', 'Fira Code', monospace;
  white-space: nowrap;
}

.rhd-key::after {
  content: ':';
  margin-right: 2px;
}

.rhd-val {
  color: #1e293b;
  font-weight: 600;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.rhd-val.rhd-overfit {
  color: #dc2626;
  font-weight: 800;
}

.rhd-val.rhd-negative {
  color: #dc2626;
}

.rhd-track-header {
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  padding: 2px 0 1px 4px;
  margin-top: 2px;
  border-left: 2px solid #93c5fd;
}
</style>
