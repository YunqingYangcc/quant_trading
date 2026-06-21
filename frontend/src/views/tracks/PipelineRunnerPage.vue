<template>
  <div class="pipeline-page">
    <div class="pp-header">
      <h2>量化流水线</h2>
      <p>特征计算 → 因子筛选 → 特征预处理 → 模型训练</p>
    </div>

    <div class="pp-steps">
      <div v-for="s in steps" :key="s.key" class="pp-step" :class="s.status">
        <div class="pps-icon">{{ iconMap[s.status] }}</div>
        <div class="pps-body">
          <div class="pps-name">{{ s.label }}</div>
          <div class="pps-desc">{{ s.desc }}</div>
        </div>
        <div v-if="s.status === 'running'" class="pps-spinner" />
        <el-button v-else-if="s.status === 'idle' || s.status === 'failed'"
          size="small" :loading="runningStep === s.key" :disabled="isRunning"
          @click="runStep(s.key)">运行</el-button>
        <el-tag v-else size="small" type="success">完成</el-tag>
      </div>
    </div>

    <div class="pp-action">
      <el-button type="primary" size="large"
        :loading="runningAll" :disabled="isRunning"
        @click="runStep('all')">▶ 一键跑全部</el-button>
      <el-button v-if="taskId" size="small" type="danger" plain
        @click="handleCancel">取消</el-button>
    </div>

    <!-- Terminal -->
    <div class="pp-terminal">
      <div class="ppt-header">
        <span class="ppt-title">▶ Terminal</span>
        <span v-if="isRunning" class="ppt-badge running">RUNNING</span>
        <span v-else-if="taskStatus === 'success'" class="ppt-badge done">DONE</span>
        <span v-else-if="taskStatus === 'failed'" class="ppt-badge fail">FAILED</span>
        <button class="ppt-clear" @click="clearLog">clear</button>
      </div>
      <div class="ppt-body" ref="terminalBodyRef">
        <div v-if="!lines.length" class="ppt-empty">
          <span class="ppt-prompt">$ _</span>
          <span class="ppt-hint">点击步骤或「一键跑全部」开始</span>
        </div>
        <div v-for="(line, i) in lines" :key="i" class="ppt-line" :class="lineClass(line)">{{ line }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { runPipeline, getPipelineStatus, cancelPipeline } from '@/api/track'

const steps = ref([
  { key: 'compute', label: '特征计算', desc: 'ta 库生成 111 个技术指标', status: 'idle' },
  { key: 'screen', label: '因子筛选', desc: 'Alphalens 池化 IC 检验', status: 'idle' },
  { key: 'preprocess', label: '特征预处理', desc: '标准化、去共线、时序分割', status: 'idle' },
  { key: 'train', label: '模型训练', desc: 'LightGBM 6 赛道独立训练', status: 'idle' },
])

const iconMap: Record<string, string> = { idle: '○', running: '⟳', done: '✓', failed: '✕' }
const runningStep = ref<string | null>(null)
const runningAll = ref(false)
const isRunning = ref(false)
const taskId = ref('')
const taskStatus = ref('')
const lines = ref<string[]>([])
const terminalBodyRef = ref<HTMLElement>()
let pollTimer: ReturnType<typeof setInterval> | null = null

function log(msg: string) {
  lines.value.push(msg)
  nextTick(() => { terminalBodyRef.value?.scrollTo(0, terminalBodyRef.value.scrollHeight) })
}

function clearLog() { lines.value = [] }

function lineClass(line: string): string {
  if (line.includes('❌') || line.includes('失败') || line.includes('异常')) return 'ppt-error'
  if (line.includes('✅')) return 'ppt-success'
  if (line.includes('⚠️')) return 'ppt-warn'
  if (line.includes('🎉')) return 'ppt-done'
  if (line.startsWith('▶') || line.startsWith('$')) return 'ppt-cmd'
  return ''
}

function startPolling(id: string) {
  taskId.value = id
  taskStatus.value = 'running'
  isRunning.value = true

  pollTimer = setInterval(async () => {
    try {
      const res = await getPipelineStatus(id)
      const data = res as any

      // 追加新日志
      const logs: string[] = data.logs || []
      const currentLen = lines.value.length
      for (let i = currentLen; i < logs.length; i++) {
        lines.value.push(logs[i])
      }
      nextTick(() => terminalBodyRef.value?.scrollTo(0, terminalBodyRef.value?.scrollHeight || 0))

      // 更新步骤状态
      const stepKey = data.step || ''
      if (stepKey) {
        runningStep.value = stepKey
        const found = steps.value.find(s => s.key === stepKey)
        if (found) found.status = 'running'
        // 其他步骤标记为 idle/done
        for (const s of steps.value) {
          if (s.key === stepKey) continue
          const stepsDone = data.steps || {}
          if (stepsDone[s.key] === 'success') s.status = 'done'
          else if (stepsDone[s.key] === 'failed') s.status = 'failed'
        }
      }

      const st = data.status
      if (st === 'success') {
        taskStatus.value = 'success'
        stopPolling()
        log('🎉 流水线全部完成')
        ElMessage.success('流水线完成')
        // 所有进行中的步骤标记完成
        for (const s of steps.value) {
          if (s.status === 'running') s.status = 'done'
        }
      } else if (st === 'failed') {
        taskStatus.value = 'failed'
        stopPolling()
        log('❌ 流水线失败')
        ElMessage.error('流水线执行出错，查看日志')
      } else if (st === 'cancelled') {
        taskStatus.value = 'cancelled'
        stopPolling()
        log('⚠️ 流水线已取消')
      }
    } catch {
      // polling failed, skip
    }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  isRunning.value = false
  runningStep.value = null
  runningAll.value = false
}

onUnmounted(() => stopPolling())

async function runStep(step: string) {
  const all = step === 'all'
  runningAll.value = all
  runningStep.value = step
  clearLog()

  // 重置步骤状态
  const stepsToRun = all ? ['compute', 'screen', 'preprocess', 'train'] : [step]
  for (const s of stepsToRun) {
    const found = steps.value.find(x => x.key === s)
    if (found) found.status = 'idle'
  }

  try {
    log(`▶ 启动 ${all ? '全流水线' : (steps.value.find(x => x.key === step)?.label || step)}...`)
    const res = await runPipeline(all ? 'all' : step) as any
    if (res?.task_id) {
      log(`  task_id: ${res.task_id}`)
      startPolling(res.task_id)
    } else {
      log('❌ 启动失败：无 task_id')
    }
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.message || '未知错误'
    log(`❌ 启动失败: ${msg}`)
    ElMessage.error(`启动失败: ${msg}`)
    isRunning.value = false
    runningStep.value = null
    runningAll.value = false
  }
}

async function handleCancel() {
  if (!taskId.value) return
  try {
    await cancelPipeline(taskId.value)
    log('⚠️ 正在取消...')
  } catch { }
}
</script>

<style scoped>
.pipeline-page { padding: 24px 32px; }
.pp-header { margin-bottom: 24px; }
.pp-header h2 { font-size: 20px; margin: 0 0 4px; }
.pp-header p { font-size: 13px; color: #94a3b8; margin: 0; }

.pp-steps { display: flex; gap: 12px; margin-bottom: 20px; }
.pp-step {
  flex: 1; display: flex; align-items: center; gap: 10px;
  padding: 14px; border-radius: 10px;
  border: 1px solid #e2e8f0; background: #fff;
}
.pp-step.failed { border-color: #fecaca; background: #fef2f2; }
.pp-step.done { border-color: #bbf7d0; background: #f0fdf4; }
.pps-icon { font-size: 18px; font-weight: 700; width: 24px; text-align: center; }
.pps-body { flex: 1; }
.pps-name { font-size: 14px; font-weight: 700; }
.pps-desc { font-size: 11px; color: #94a3b8; }
.pps-spinner { width: 16px; height: 16px; border: 2px solid #e2e8f0; border-top-color: #3b82f6; border-radius: 50%; animation: spin .6s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.pp-action { text-align: center; margin-bottom: 20px; display: flex; gap: 10px; justify-content: center; }

.pp-terminal { background: #0d1117; border-radius: 8px; overflow: hidden; }
.ppt-header {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 12px; background: #161b22; border-bottom: 1px solid #30363d;
}
.ppt-title { font-size: 11px; font-weight: 600; color: #58a6ff; font-family: monospace; }
.ppt-badge { font-size: 9px; font-weight: 700; padding: 1px 6px; border-radius: 3px; font-family: monospace; }
.ppt-badge.running { background: #1a3a5c; color: #58a6ff; }
.ppt-badge.done { background: #1a3a2c; color: #3fb950; }
.ppt-badge.fail { background: #3a1a1a; color: #f78166; }
.ppt-clear { margin-left: auto; background: none; border: none; color: #484f58; font-size: 10px; cursor: pointer; font-family: monospace; }
.ppt-clear:hover { color: #8b949e; }
.ppt-body { padding: 8px 12px; height: 240px; overflow-y: auto; font-family: monospace; font-size: 12px; line-height: 1.6; }
.ppt-body::-webkit-scrollbar { width: 4px; }
.ppt-body::-webkit-scrollbar-thumb { background: #30363d; border-radius: 2px; }
.ppt-empty { color: #8b949e; }
.ppt-prompt { color: #3fb950; margin-right: 8px; }
.ppt-hint { color: #484f58; font-size: 11px; }
.ppt-line { white-space: pre-wrap; word-break: break-all; color: #c9d1d9; }
.ppt-line.ppt-cmd { color: #58a6ff; }
.ppt-line.ppt-success { color: #3fb950; }
.ppt-line.ppt-error { color: #f78166; }
.ppt-line.ppt-warn { color: #d29922; }
.ppt-line.ppt-done { color: #7ee787; font-weight: 600; }
</style>
