/**
 * 流水线运行状态管理（跨页面持久化）
 */
import { reactive } from 'vue'

export interface PipelineTask {
  taskId: string
  status: 'idle' | 'running' | 'completed' | 'failed' | 'cancelled'
  step: string
  logs: string[]
  steps: Record<string, any>
  startedAt: string
  finishedAt?: string
  pollingTimer: number | null
}

const state = reactive<{
  currentTask: PipelineTask | null
  history: PipelineTask[]
}>({
  currentTask: null,
  history: [],
})

const STEP_NAMES: Record<string, string> = {
  compute: '特征计算',
  screen: '因子筛选',
  preprocess: '特征预处理',
  train: '模型训练',
  incremental_compute: '增量特征追加',
}

const STEP_DESCS: Record<string, string> = {
  compute: 'ta库 93通用+18赛道特征 → FeatureStore',
  screen: 'Alphalens 池化IC筛选 → 白/黑名单',
  preprocess: '标准化+去共线+时序分割 → parquet',
  train: '6赛道 LightGBM 二分类训练',
  backtest: 'AI打分轮动策略 + 绩效报告',
  incremental_compute: '仅补算 FeatureStore 中缺失的交易日',
}

export function usePipelineRunner() {
  /** 启动流水线 */
  async function startPipeline(step: string, trackName: string | null = null): Promise<string | null> {
    try {
      const { default: request } = await import('@/api/index')
      const params: Record<string, any> = { step }
      if (trackName) params.track_name = trackName
      const res: any = await request.post('/ml/run-pipeline', null, { params })
      const taskId = res.task_id

      state.currentTask = {
        taskId,
        status: 'running',
        step: '',
        logs: [`[启动] task_id=${taskId} step=${step}`],
        steps: {},
        startedAt: new Date().toISOString(),
        pollingTimer: null,
      }

      // 开始轮询
      startPolling(taskId)
      return taskId
    } catch (e: any) {
      console.error('启动流水线失败:', e)
      return null
    }
  }

  /** 轮询任务状态 */
  function startPolling(taskId: string) {
    const timer = window.setInterval(async () => {
      try {
        const { default: request } = await import('@/api/index')
        const res: any = await request.get(`/ml/pipeline-status/${taskId}`)
        if (!state.currentTask || state.currentTask.taskId !== taskId) {
          clearInterval(timer)
          return
        }
        state.currentTask.status = res.status
        state.currentTask.step = res.step
        state.currentTask.logs = res.logs
        state.currentTask.steps = res.steps
        state.currentTask.finishedAt = res.finished_at

        if (res.status !== 'running') {
          clearInterval(timer)
          state.currentTask.pollingTimer = null
          // 移入历史
          if (state.currentTask) {
            state.history.unshift({ ...state.currentTask })
            if (state.history.length > 20) state.history.pop()
          }
        }
      } catch {
        // 轮询失败忽略
      }
    }, 1500) // 1.5s 轮询

    if (state.currentTask) {
      state.currentTask.pollingTimer = timer
    }
  }

  /** 取消流水线 */
  async function cancelPipeline() {
    if (!state.currentTask) return
    try {
      const { default: request } = await import('@/api/index')
      await request.post(`/ml/pipeline-cancel/${state.currentTask.taskId}`)
    } catch (e) {
      console.error('取消失败:', e)
    }
  }

  /** 获取步骤中文名 */
  function getStepName(key: string) {
    return STEP_NAMES[key] || key
  }

  /** 获取步骤描述 */
  function getStepDesc(key: string) {
    return STEP_DESCS[key] || ''
  }

  /** 获取所有步骤 */
  function getAllSteps() {
    return ['compute', 'screen', 'preprocess', 'train']
  }

  return {
    state,
    startPipeline,
    cancelPipeline,
    getStepName,
    getStepDesc,
    getAllSteps,
  }
}
