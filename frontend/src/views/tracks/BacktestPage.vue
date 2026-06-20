<template>
  <div class="backtest-page">
    <div class="page-header">
      <h2>📊 回测绩效</h2>
      <div class="header-actions">
        <el-button size="small" @click="loadBacktest" :loading="loadingReport">重新加载</el-button>
      </div>
    </div>

    <!-- 回测参数配置 -->
    <div class="section-card">
      <div class="section-header">
        <div class="sh-left">
          <div class="sh-icon">⚙️</div>
          <div>
            <div class="sh-title">回测参数配置</div>
            <div class="sh-sub">调整策略参数后点击运行，每次运行覆盖前次结果</div>
          </div>
        </div>
        <el-tag size="small" type="info" effect="plain">可自定义</el-tag>
      </div>

      <!-- 预设方案 -->
      <div class="preset-row">
        <span class="preset-label">快速预设</span>
        <el-radio-group v-model="presetKey" size="small" @change="applyPreset">
          <el-radio-button value="conservative">🛡️ 保守</el-radio-button>
          <el-radio-button value="balanced">⚖️ 均衡</el-radio-button>
          <el-radio-button value="aggressive">🚀 激进</el-radio-button>
        </el-radio-group>
        <el-tag v-if="presetKey !== 'custom'" size="small" type="success" effect="plain" class="preset-tag">推荐</el-tag>
        <el-tag v-else size="small" type="warning" effect="plain" class="preset-tag">已修改</el-tag>
      </div>

      <div class="bt-form">
        <div class="form-grid">
          <!-- 资金 -->
          <div class="form-group">
            <div class="fg-label">💰 资金配置</div>
            <div class="fg-fields">
              <div class="form-item">
                <label class="form-label">
                  初始资金
                  <el-tooltip content="回测起点的可用资金" placement="top">
                    <span class="label-help">?</span>
                  </el-tooltip>
                </label>
                <el-input-number v-model="btParams.initial_capital" :min="10000" :step="50000" :max="10000000" controls-position="right" style="width:100%" />
              </div>
            </div>
          </div>

          <!-- 选股 -->
          <div class="form-group">
            <div class="fg-label">📋 选股策略</div>
            <div class="fg-fields">
              <div class="form-item">
                <label class="form-label">每赛道 Top-N</label>
                <el-input-number v-model="btParams.top_n" :min="1" :max="10" controls-position="right" style="width:100%" />
              </div>
              <div class="form-item">
                <label class="form-label">调仓频率</label>
                <el-radio-group v-model="btParams.rebalance_freq" class="freq-group">
                  <el-radio-button value="W">📅 周频</el-radio-button>
                  <el-radio-button value="M">📆 月频</el-radio-button>
                </el-radio-group>
              </div>
            </div>
          </div>

          <!-- 风控 -->
          <div class="form-group">
            <div class="fg-label">🛡️ 风控限制</div>
            <div class="fg-fields">
              <div class="form-item">
                <label class="form-label">单票上限</label>
                <el-slider v-model="btParams.max_single_stock" :min="5" :max="50" :step="5" show-input>
                  <template #append>%</template>
                </el-slider>
              </div>
              <div class="form-item">
                <label class="form-label">单赛道上限</label>
                <el-slider v-model="btParams.max_single_track" :min="10" :max="80" :step="5" show-input>
                  <template #append>%</template>
                </el-slider>
              </div>
            </div>
          </div>
        </div>

        <!-- 操作栏 -->
        <div class="action-bar">
          <div class="locked-hint">
            <el-tag size="small" type="warning" effect="plain">🔒 锁定</el-tag>
            <span>滑点 0.1% · 手续费万三 · 涨跌停限制</span>
          </div>
          <el-button type="primary" size="default" @click="runBacktest" :loading="running" :icon="CaretRight" class="run-btn">
            {{ running ? '回测运行中...' : '开始回测' }}
          </el-button>
        </div>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error-card">
      <el-alert :title="error" type="warning" :closable="false" show-icon />
    </div>

    <!-- 回测结果 -->
    <template v-if="report">
      <!-- 回测记录 -->
      <div class="report-header">
        <div class="rh-left">
          <div class="rh-icon">📋</div>
          <div>
            <div class="rh-title">回测记录</div>
            <div class="rh-sub">{{ report.metadata?.run_at || '' }} 执行</div>
          </div>
        </div>
        <el-tag size="small" type="success" effect="plain" v-if="report.metadata?.trade_count">
          {{ report.metadata.trade_count }} 个交易日
        </el-tag>
      </div>

      <!-- 上下文信息：参数 + 赛道 + 时间 -->
      <div class="context-grid">
        <div class="ctx-card">
          <div class="ctx-title">🎯 策略参数</div>
          <div class="ctx-rows">
            <div class="ctx-row" v-for="(v, k) in report.params || {}" :key="k">
              <span class="ctx-key">{{ k }}</span>
              <span class="ctx-val">{{ v }}</span>
            </div>
          </div>
        </div>

        <div class="ctx-card">
          <div class="ctx-title">📂 覆盖赛道</div>
          <div class="ctx-rows">
            <div v-if="report.metadata?.tracks?.length" v-for="t in report.metadata.tracks" :key="t.name" class="ctx-row">
              <span class="ctx-key">{{ t.display_name }}</span>
              <span class="ctx-val">{{ t.stock_count }} 只</span>
            </div>
            <div v-else class="ctx-row">
              <span class="ctx-val" style="color:#94a3b8">暂无赛道数据</span>
            </div>
          </div>
        </div>

        <div class="ctx-card">
          <div class="ctx-title">📅 回测区间</div>
          <div class="ctx-rows">
            <div class="ctx-row">
              <span class="ctx-key">开始</span>
              <span class="ctx-val">{{ report.metadata?.date_start || '-' }}</span>
            </div>
            <div class="ctx-row">
              <span class="ctx-key">结束</span>
              <span class="ctx-val">{{ report.metadata?.date_end || '-' }}</span>
            </div>
            <div class="ctx-row">
              <span class="ctx-key">锁定参数</span>
              <span class="ctx-val" style="font-size:11px;color:#94a3b8">
                滑点 0.1% / 万三 / 涨跌停限制
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 绩效指标 -->
      <div class="metrics-section-title">📊 绩效指标</div>
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
    </template>

    <div v-if="!report && !loadingReport && !error" class="empty-card">
      <el-empty description="点击「开始回测」运行首次回测">
        <el-button type="primary" size="small" @click="runBacktest" :loading="running">
          开始回测
        </el-button>
      </el-empty>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { CaretRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getBacktestReport, runBacktest as runBacktestApi } from '@/api/track'

const loadingReport = ref(false)
const running = ref(false)
const error = ref('')
const report = ref<any>(null)

const btParams = reactive({
  initial_capital: 100000,
  top_n: 3,
  rebalance_freq: 'W',
  max_single_stock: 20,
  max_single_track: 50,
})

const presetKey = ref('balanced')

const PRESETS: Record<string, Partial<typeof btParams>> = {
  conservative: { initial_capital: 50000, top_n: 2, rebalance_freq: 'M', max_single_stock: 10, max_single_track: 30 },
  balanced: { initial_capital: 100000, top_n: 3, rebalance_freq: 'W', max_single_stock: 20, max_single_track: 50 },
  aggressive: { initial_capital: 200000, top_n: 5, rebalance_freq: 'W', max_single_stock: 30, max_single_track: 70 },
}

function applyPreset(key: string) {
  const p = PRESETS[key]
  if (!p) return
  Object.assign(btParams, p)
}

const metrics = computed(() => {
  if (!report.value) return []
  const r = report.value.metrics || (Array.isArray(report.value) ? report.value[0] : report.value) || {}
  const params = report.value.params || {}
  return [
    { label: '初始资金', value: `¥${(params.initial_capital || 100000).toLocaleString()}`, color: '#909399' },
    { label: '最终净值', value: `¥${(r.final_value || 0).toLocaleString()}`, color: (r.total_return || 0) >= 0 ? '#67c23a' : '#f56c6c' },
    { label: '总收益', value: `${r.total_return || 0}%`, color: (r.total_return || 0) >= 0 ? '#67c23a' : '#f56c6c' },
    { label: '年化收益', value: `${r.annual_return || 0}%`, color: (r.annual_return || 0) >= 0 ? '#67c23a' : '#f56c6c' },
    { label: '夏普比率', value: r.sharpe_ratio?.toFixed(3) || '-', color: (r.sharpe_ratio || 0) >= 1.2 ? '#67c23a' : '#f56c6c', pass: (r.sharpe_ratio || 0) >= 1.2 },
    { label: '年化波动', value: `${r.annual_volatility || 0}%`, color: '#e6a23c' },
    { label: '最大回撤', value: `${r.max_drawdown || 0}%`, color: (r.max_drawdown || 100) < 25 ? '#67c23a' : '#f56c6c', pass: (r.max_drawdown || 100) < 25 },
    { label: '胜率', value: `${r.win_rate || 0}%`, color: (r.win_rate || 0) >= 50 ? '#67c23a' : '#e6a23c' },
    { label: '交易次数', value: r.total_trades || 0, color: '#909399' },
  ]
})

async function runBacktest() {
  running.value = true
  error.value = ''
  try {
    report.value = await runBacktestApi({
      initial_capital: btParams.initial_capital,
      top_n: btParams.top_n,
      rebalance_freq: btParams.rebalance_freq,
      max_single_stock: btParams.max_single_stock / 100,
      max_single_track: btParams.max_single_track / 100,
    })
    ElMessage.success('回测完成')
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '回测执行失败'
    report.value = null
  } finally {
    running.value = false
  }
}

async function loadBacktest() {
  loadingReport.value = true
  error.value = ''
  try {
    report.value = await getBacktestReport()
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '加载失败'
    report.value = null
  } finally {
    loadingReport.value = false
  }
}

onMounted(loadBacktest)
</script>

<style scoped>
.backtest-page {
  min-height: 100%;
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

.header-actions {
  display: flex;
  gap: 8px;
}

/* ── 配置卡片 ── */
.section-card {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.03);
  margin-bottom: 16px;
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.sh-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sh-icon {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  box-shadow: 0 2px 6px rgba(59,130,246,0.2);
}

.sh-title {
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
  line-height: 1.3;
}

.sh-sub {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.4;
  margin-top: 1px;
}

/* ── 预设 ── */
.preset-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 18px;
}

.preset-label {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  white-space: nowrap;
}

.preset-tag {
  margin-left: auto;
}

/* ── 表单网格 ── */
.bt-form {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
  margin-bottom: 18px;
}

.form-group {
  background: #fafbfc;
  border: 1px solid #eef2f6;
  border-radius: 10px;
  padding: 14px 16px;
}

.fg-label {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #eef2f6;
}

.fg-fields {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 12px;
  font-weight: 500;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 4px;
}

.label-help {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #e2e8f0;
  color: #64748b;
  font-size: 10px;
  font-weight: 700;
  cursor: help;
}

.freq-group {
  display: flex;
  width: 100%;
}

.freq-group :deep(.el-radio-button__inner) {
  width: 100%;
}

/* ── 操作栏 ── */
.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 8px;
}

.locked-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #94a3b8;
}

.run-btn {
  padding: 10px 28px;
  font-size: 14px;
  font-weight: 600;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(59,130,246,0.25);
}

/* ── 指标 ── */
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

.error-card, .empty-card {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

/* ── 回测记录 ── */
.report-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.03);
  margin-bottom: 16px;
}

.rh-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.rh-icon {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #10b981, #059669);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  box-shadow: 0 2px 6px rgba(16,185,129,0.2);
}

.rh-title {
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
}

.rh-sub {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 1px;
}

/* ── 上下文网格 ── */
.context-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  margin-bottom: 20px;
}

.ctx-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
  border: 1px solid #f0f2f5;
}

.ctx-title {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0f2f5;
}

.ctx-rows {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ctx-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.ctx-key {
  color: #64748b;
}

.ctx-val {
  font-weight: 600;
  color: #1e293b;
}

.metrics-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 12px;
  padding-left: 4px;
}
</style>
