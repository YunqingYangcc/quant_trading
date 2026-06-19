<template>
  <div class="backtest-page">
    <div class="page-header">
      <h2>📊 回测绩效</h2>
      <el-button size="small" @click="loadBacktest" :loading="loading">重新加载</el-button>
    </div>

    <div v-if="error" class="error-card">
      <el-alert :title="error" type="warning" :closable="false" show-icon />
      <div class="run-hint">
        <p>请先运行回测：</p>
        <code>cd backend && python3 scripts/run_backtest.py</code>
      </div>
    </div>

    <template v-if="report">
      <!-- 关键指标 -->
      <div class="metrics-row">
        <div class="metric-card" v-for="m in metrics" :key="m.label">
          <div class="metric-value" :style="{ color: m.color }">{{ m.value }}</div>
          <div class="metric-label">{{ m.label }}</div>
          <div class="metric-pass" v-if="m.pass !== undefined">
            <el-tag :type="m.pass ? 'success' : 'danger'" size="small" effect="plain">
              {{ m.pass ? '✅ 达标' : '❌ 未达标' }}
            </el-tag>
          </div>
        </div>
      </div>

      <!-- 参数 -->
      <div class="section-card">
        <div class="section-title">⚙️ 回测参数（锁定）</div>
        <div class="params-grid">
          <div v-for="(v,k) in report.params || {}" :key="k" class="param-item">
            <span class="param-key">{{ k }}</span>
            <span class="param-val">{{ v }}</span>
          </div>
        </div>
      </div>
    </template>

    <div v-if="!report && !loading && !error" class="empty-card">
      <el-empty description="暂无回测数据" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

const loading = ref(false)
const error = ref('')
const report = ref<any>(null)

const metrics = computed(() => {
  if (!report.value) return []
  const r = report.value
  return [
    { label: '初始资金', value: `¥${(r.initial_capital || 100000).toLocaleString()}`, color: '#909399' },
    { label: '最终净值', value: `¥${(r.final_value || 0).toLocaleString()}`, color: r.total_return >= 0 ? '#67c23a' : '#f56c6c' },
    { label: '总收益', value: `${r.total_return || 0}%`, color: (r.total_return || 0) >= 0 ? '#67c23a' : '#f56c6c' },
    { label: '年化收益', value: `${r.annual_return || 0}%`, color: (r.annual_return || 0) >= 0 ? '#67c23a' : '#f56c6c' },
    { label: '夏普比率', value: r.sharpe_ratio?.toFixed(3) || '-', color: (r.sharpe_ratio || 0) >= 1.2 ? '#67c23a' : '#f56c6c', pass: (r.sharpe_ratio || 0) >= 1.2 },
    { label: '年化波动', value: `${r.annual_volatility || 0}%`, color: '#e6a23c' },
    { label: '最大回撤', value: `${r.max_drawdown || 0}%`, color: (r.max_drawdown || 100) < 25 ? '#67c23a' : '#f56c6c', pass: (r.max_drawdown || 100) < 25 },
    { label: '胜率', value: `${r.win_rate || 0}%`, color: (r.win_rate || 0) >= 50 ? '#67c23a' : '#e6a23c' },
    { label: '交易次数', value: r.total_trades || 0, color: '#909399' },
  ]
})

async function loadBacktest() {
  loading.value = true
  error.value = ''
  try {
    // 读取后端生成的回测报告 JSON
    const resp = await fetch('http://localhost:8000/api/v1/backtest/report')
    if (!resp.ok) throw new Error('回测报告未生成')
    report.value = await resp.json()
  } catch (e: any) {
    error.value = e.message || '加载失败'
    report.value = null
  } finally {
    loading.value = false
  }
}

onMounted(loadBacktest)
</script>

<style scoped>
.backtest-page {
  height: calc(100vh - 52px);
  overflow-y: auto;
  padding: 24px 32px;
  background: #f5f7fa;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 22px;
  color: #1e293b;
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.metric-card {
  background: #fff;
  border-radius: 8px;
  padding: 14px 12px;
  text-align: center;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.metric-value {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.2;
}

.metric-label {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}

.metric-pass {
  margin-top: 4px;
}

.section-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  margin-bottom: 16px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 10px;
}

.params-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 6px;
}

.param-item {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  border-bottom: 1px solid #f5f5f5;
  font-size: 12px;
}

.param-key {
  color: #909399;
}

.param-val {
  color: #303133;
  font-weight: 500;
}

.error-card, .empty-card {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.run-hint {
  margin-top: 12px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 6px;
}

.run-hint p { margin: 0 0 6px; font-size: 13px; color: #606266; }
.run-hint code {
  font-size: 12px;
  background: #1e293b;
  color: #e2e8f0;
  padding: 4px 8px;
  border-radius: 4px;
}
</style>
