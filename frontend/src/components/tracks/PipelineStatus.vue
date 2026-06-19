<template>
  <div class="pipeline-panel">
    <div class="pipeline-title">
      <span class="title-icon">🔧</span>
      <span>数据流水线</span>
    </div>

    <div class="pipeline-flow">
      <div
        v-for="(step, i) in steps"
        :key="step.phase"
        class="pipeline-step"
        :class="step.status"
      >
        <div class="step-indicator">
          <div class="step-dot">{{ step.status === 'done' ? '✅' : step.status === 'active' ? '🔄' : '⏳' }}</div>
          <div v-if="i < steps.length - 1" class="step-line" :class="step.status" />
        </div>
        <div class="step-content">
          <div class="step-phase">{{ step.phase }}</div>
          <div class="step-desc">{{ step.label }}</div>
          <div v-if="step.status === 'active'" class="step-progress">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: step.progress + '%' }" />
            </div>
            <span class="progress-text">{{ step.progress }}%</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Step {
  phase: string
  label: string
  desc: string
  status: 'done' | 'active' | 'pending'
  progress: number
}

const steps: Step[] = [
  { phase: 'Phase A', label: '数据流水线', desc: 'baostock 取数→清洗→落库→标签', status: 'done', progress: 100 },
  { phase: 'Phase B', label: '特征工程', desc: 'ta 库 93 通用 + 18 赛道特征', status: 'done', progress: 100 },
  { phase: 'Phase C', label: '因子筛选', desc: 'Alphalens 池化IC → 75白/72黑', status: 'done', progress: 100 },
  { phase: 'Phase D', label: '特征预处理', desc: '标准化 + 去共线 + 时序分割', status: 'done', progress: 100 },
  { phase: 'Phase E', label: '模型训练', desc: '4 赛道 LightGBM 时间滚动训练', status: 'done', progress: 100 },
  { phase: 'Phase F', label: '打分 API', desc: '个股强弱分 + 赛道景气度', status: 'done', progress: 100 },
  { phase: 'Phase G', label: '回测校验', desc: '轮动策略 + 夏普/回撤评估', status: 'pending', progress: 0 },
  { phase: 'Phase H', label: '前端可视化', desc: 'K线 + 因子 + 排名 + 景气度', status: 'active', progress: 85 },
]
</script>

<style scoped>
.pipeline-panel {
  background: #fff;
  border-radius: 10px;
  padding: 16px 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

.pipeline-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 16px;
}

.title-icon {
  font-size: 18px;
}

.pipeline-flow {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.pipeline-step {
  display: flex;
  gap: 12px;
  min-height: 48px;
}

.step-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 28px;
  flex-shrink: 0;
}

.step-dot {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  border-radius: 50%;
  flex-shrink: 0;
}

.step-line {
  width: 2px;
  flex: 1;
  min-height: 16px;
}

.step-line.done {
  background: linear-gradient(180deg, #67c23a, #95de64);
}

.step-line.active {
  background: linear-gradient(180deg, #409eff, #79bbff);
}

.step-line.pending {
  background: #e4e7ed;
}

.step-content {
  flex: 1;
  padding-bottom: 14px;
  min-width: 0;
}

.step-phase {
  font-size: 11px;
  font-weight: 600;
  color: #909399;
  margin-bottom: 1px;
}

.step-desc {
  font-size: 13px;
  color: #606266;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 状态颜色 */
.pipeline-step.done .step-phase { color: #67c23a; }
.pipeline-step.active .step-phase { color: #409eff; }
.pipeline-step.pending .step-phase { color: #c0c4cc; }

.step-progress {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
}

.progress-bar {
  flex: 1;
  height: 4px;
  background: #f0f2f5;
  border-radius: 2px;
  overflow: hidden;
  max-width: 80px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #409eff, #79bbff);
  border-radius: 2px;
  transition: width 0.5s;
}

.progress-text {
  font-size: 11px;
  color: #909399;
}
</style>
