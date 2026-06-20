<template>
  <div class="pipeline-panel">
    <div class="pipeline-header">
      <div class="pl-header-left">
        <div class="pl-icon-box">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
        </div>
        <div>
          <div class="pl-title">数据流水线</div>
          <div class="pl-subtitle">{{ doneCount }}/{{ steps.length }} 阶段已完成</div>
        </div>
      </div>
      <div class="pl-badge">
        <span class="pl-badge-dot" />
        <span class="pl-badge-text">{{ doneCount }}/{{ steps.length }}</span>
      </div>
    </div>

    <div class="pipeline-scroll">
      <div class="pipeline-flow">
        <div
          v-for="(step, i) in steps"
          :key="step.phase"
          class="pipeline-step"
          :class="step.status"
        >
          <div class="step-indicator">
            <div class="step-dot" :class="step.status">
              <span v-if="step.status === 'done'" class="dot-check">✓</span>
              <span v-else-if="step.status === 'active'" class="dot-spin">⟳</span>
              <span v-else class="dot-pending">○</span>
            </div>
            <div v-if="i < steps.length - 1" class="step-line" :class="step.status" />
          </div>
          <div class="step-content" :class="{ 'step-active': step.status === 'active' }">
            <div class="sc-top">
              <div class="step-phase">{{ step.phase }}</div>
              <div v-if="step.status === 'active'" class="step-progress-tag">{{ step.progress }}%</div>
            </div>
            <div class="step-label">{{ step.label }}</div>
            <div class="step-desc">{{ step.desc }}</div>
            <div v-if="step.status === 'active'" class="step-progress-bar">
              <div class="sp-fill" :style="{ width: step.progress + '%' }" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

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
  { phase: 'Phase G', label: '回测校验', desc: '手写轮动策略 + 9 项绩效指标', status: 'done', progress: 100 },
  { phase: 'Phase H', label: '前端可视化', desc: '7 页面机构工作流全链路闭环', status: 'done', progress: 100 },
  { phase: 'Phase K', label: '占位页面填充', desc: 'Alpha/ModelFactory/Portfolio', status: 'done', progress: 100 },
  { phase: 'Phase I', label: '基本面接入', desc: 'akshare PE/PB/ROE/北向资金', status: 'pending', progress: 0 },
  { phase: 'Phase J', label: '回测框架升级', desc: '手写 → backtrader', status: 'pending', progress: 0 },
]

const doneCount = computed(() => steps.filter(s => s.status === 'done').length)
</script>

<style scoped>
.pipeline-panel {
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.03);
  height: 100%;
}

/* ── Header ── */
.pipeline-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

.pl-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pl-icon-box {
  width: 38px;
  height: 38px;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 6px rgba(59,130,246,0.25);
}

.pl-title {
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
  line-height: 1.3;
}

.pl-subtitle {
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.3;
}

.pl-badge {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 20px;
}

.pl-badge-dot {
  width: 6px;
  height: 6px;
  background: #22c55e;
  border-radius: 50%;
}

.pl-badge-text {
  font-size: 11px;
  font-weight: 600;
  color: #16a34a;
}

/* ── Scroll Container ── */
.pipeline-scroll {
  max-height: 420px;
  overflow-y: auto;
  padding-right: 4px;
}

.pipeline-scroll::-webkit-scrollbar {
  width: 3px;
}

.pipeline-scroll::-webkit-scrollbar-thumb {
  background: #e2e8f0;
  border-radius: 2px;
}

/* ── Flow ── */
.pipeline-flow {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.pipeline-step {
  display: flex;
  gap: 14px;
  min-height: 52px;
}

/* ── Indicator ── */
.step-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 30px;
  flex-shrink: 0;
}

.step-dot {
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  border-radius: 50%;
  flex-shrink: 0;
  transition: all 0.3s;
}

.step-dot.done {
  background: #dcfce7;
  color: #16a34a;
  border: 2px solid #86efac;
}

.step-dot.active {
  background: #eff6ff;
  color: #3b82f6;
  border: 2px solid #93c5fd;
  animation: dot-pulse 2s ease-in-out infinite;
}

.step-dot.pending {
  background: #f8fafc;
  color: #cbd5e1;
  border: 2px solid #e2e8f0;
}

@keyframes dot-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(59,130,246,0.3); }
  50% { box-shadow: 0 0 0 5px rgba(59,130,246,0.05); }
}

.dot-check { font-size: 13px; }
.dot-spin { font-size: 14px; animation: spin 1.5s linear infinite; display: inline-block; }
.dot-pending { font-size: 14px; }

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.step-line {
  width: 2px;
  flex: 1;
  min-height: 18px;
}

.step-line.done {
  background: linear-gradient(180deg, #86efac, #bbf7d0);
}

.step-line.active {
  background: linear-gradient(180deg, #93c5fd, #bfdbfe);
}

.step-line.pending {
  background: #e2e8f0;
}

/* ── Content ── */
.step-content {
  flex: 1;
  padding-bottom: 16px;
  min-width: 0;
  padding: 6px 10px;
  border-radius: 8px;
  transition: background 0.2s;
}

.step-content.step-active {
  background: #f8faff;
}

.sc-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1px;
}

.step-phase {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.pipeline-step.done .step-phase { color: #16a34a; }
.pipeline-step.active .step-phase { color: #2563eb; }
.pipeline-step.pending .step-phase { color: #94a3b8; }

.step-progress-tag {
  font-size: 10px;
  font-weight: 700;
  color: #3b82f6;
  background: #eff6ff;
  padding: 1px 6px;
  border-radius: 4px;
}

.step-label {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  line-height: 1.4;
  margin-bottom: 1px;
}

.step-desc {
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── Active progress bar ── */
.step-progress-bar {
  margin-top: 6px;
  height: 4px;
  background: #e2e8f0;
  border-radius: 2px;
  overflow: hidden;
}

.sp-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
  border-radius: 2px;
  transition: width 0.5s ease;
}
</style>
