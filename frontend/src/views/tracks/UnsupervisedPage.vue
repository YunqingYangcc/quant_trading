<template>
  <div class="unsupervised-page">
    <div class="page-header">
      <h2>智能分析</h2>
      <span class="page-subtitle">基于无监督学习的市场洞察</span>
    </div>

    <el-tabs v-model="activeTab" class="analysis-tabs">
      <!-- ═══════════════ Tab 1: 市场状态 ═══════════════ -->
      <el-tab-pane label="市场状态" name="regime">
        <div class="tab-toolbar">
          <el-button type="primary" :loading="loading.regime" @click="runRegime">
            {{ loading.regime ? '分析中...' : '运行分析' }}
          </el-button>
          <span v-if="regimeUpdated" class="update-hint">上次更新: {{ regimeUpdated }}</span>
        </div>

        <template v-if="regimeData">
          <!-- 当前状态大卡片 -->
          <div class="regime-card" :style="{ borderLeftColor: regimeData.summary.regime_meta?.[regimeData.summary.current_regime]?.color }">
            <div class="regime-current">
              <div class="regime-badge" :style="{ background: regimeData.summary.regime_meta?.[regimeData.summary.current_regime]?.color }">
                {{ regimeData.summary.current_label }}
              </div>
              <div class="regime-desc">
                {{ regimeData.summary.regime_meta?.[regimeData.summary.current_regime]?.description || '' }}
              </div>
            </div>
          </div>

          <!-- 统计信息 -->
          <el-row :gutter="16" class="stat-row">
            <el-col :span="8">
              <div class="stat-card">
                <div class="stat-label">分析天数</div>
                <div class="stat-value">{{ regimeData.summary.total_dates }}</div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="stat-card">
                <div class="stat-label">状态切换</div>
                <div class="stat-value">{{ regimeData.summary.num_transitions }} 次</div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="stat-card">
                <div class="stat-label">分布</div>
                <div class="stat-value small">
                  <span v-for="(v, k) in regimeData.summary.regime_distribution" :key="k">
                    {{ k }}: {{ v }}
                  </span>
                </div>
              </div>
            </el-col>
          </el-row>

          <!-- 历史状态变迁图 -->
          <div class="chart-container">
            <div class="chart-title">状态历史变迁</div>
            <div ref="regimeChartRef" class="chart-box"></div>
          </div>
        </template>

        <el-empty v-else-if="!loading.regime" description="点击「运行分析」查看市场状态" />
      </el-tab-pane>

      <!-- ═══════════════ Tab 2: 因子降维 ═══════════════ -->
      <el-tab-pane label="因子降维" name="pca">
        <div class="tab-toolbar">
          <el-button type="primary" :loading="loading.pca" @click="runPCA">
            {{ loading.pca ? '分析中...' : '运行分析' }}
          </el-button>
          <span v-if="pcaUpdated" class="update-hint">上次更新: {{ pcaUpdated }}</span>
        </div>

        <template v-if="pcaData">
          <!-- 解释方差 -->
          <el-row :gutter="16" class="stat-row">
            <el-col :span="6">
              <div class="stat-card">
                <div class="stat-label">PC1 解释方差</div>
                <div class="stat-value">{{ (pcaData.explained_variance_ratio[0] * 100).toFixed(1) }}%</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-card">
                <div class="stat-label">PC2 解释方差</div>
                <div class="stat-value">{{ (pcaData.explained_variance_ratio[1] * 100).toFixed(1) }}%</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-card">
                <div class="stat-label">累计解释方差</div>
                <div class="stat-value">{{ (pcaData.cumulative_variance * 100).toFixed(1) }}%</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-card">
                <div class="stat-label">特征总数</div>
                <div class="stat-value">{{ pcaData.total_features }}</div>
              </div>
            </el-col>
          </el-row>

          <!-- PCA 散点图 -->
          <div class="chart-container">
            <div class="chart-title">因子 PCA 投影</div>
            <div ref="pcaChartRef" class="chart-box"></div>
          </div>

          <!-- 因子载荷表 -->
          <div class="chart-container">
            <div class="chart-title">因子载荷 (Top 20)</div>
            <el-table :data="topLoadings" size="small" stripe max-height="400">
              <el-table-column prop="feature" label="因子" min-width="180" />
              <el-table-column prop="category" label="分类" width="100">
                <template #default="{ row }">
                  <el-tag :type="tagType(row.category)" size="small">{{ row.category }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="pc1" label="PC1 载荷" width="120" align="right">
                <template #default="{ row }"><span :style="{ color: row.pc1 > 0 ? '#f56c6c' : '#67c23a' }">{{ row.pc1.toFixed(3) }}</span></template>
              </el-table-column>
              <el-table-column prop="pc2" label="PC2 载荷" width="120" align="right">
                <template #default="{ row }"><span :style="{ color: row.pc2 > 0 ? '#f56c6c' : '#67c23a' }">{{ row.pc2.toFixed(3) }}</span></template>
              </el-table-column>
            </el-table>
          </div>
        </template>

        <el-empty v-else-if="!loading.pca" description="点击「运行分析」查看因子结构" />
      </el-tab-pane>

      <!-- ═══════════════ Tab 3: 异动检测 ═══════════════ -->
      <el-tab-pane label="异动检测" name="anomaly">
        <div class="tab-toolbar">
          <el-button type="primary" :loading="loading.anomaly" @click="runAnomaly">
            {{ loading.anomaly ? '分析中...' : '运行分析' }}
          </el-button>
          <span v-if="anomalyUpdated" class="update-hint">上次更新: {{ anomalyUpdated }}</span>
        </div>

        <template v-if="anomalyData">
          <!-- 统计信息 -->
          <el-row :gutter="16" class="stat-row">
            <el-col :span="8">
              <div class="stat-card">
                <div class="stat-label">分析股票</div>
                <div class="stat-value">{{ anomalyData.summary.total_stocks }} 只</div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="stat-card">
                <div class="stat-label">异常记录</div>
                <div class="stat-value">{{ anomalyData.summary.total_anomalies }} 条</div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="stat-card">
                <div class="stat-label">平均异常率</div>
                <div class="stat-value">{{ (anomalyData.summary.avg_anomaly_ratio * 100).toFixed(1) }}%</div>
              </div>
            </el-col>
          </el-row>

          <!-- 异常列表 -->
          <div class="chart-container">
            <div class="chart-title">异常记录 (Top 50)</div>
            <el-table :data="anomalyData.anomalies" size="small" stripe max-height="500">
              <el-table-column prop="date" label="日期" width="120" />
              <el-table-column prop="stock_code" label="股票代码" width="140" />
              <el-table-column prop="anomaly_score" label="异常分数" width="120" align="right">
                <template #default="{ row }">
                  <el-tag :type="row.anomaly_score < -0.3 ? 'danger' : 'warning'" size="small">
                    {{ row.anomaly_score.toFixed(2) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="关键特征" min-width="200">
                <template #default="{ row }">
                  <div class="feature-tags">
                    <el-tag
                      v-for="(val, key) in row.key_features"
                      :key="key"
                      size="small"
                      :type="val !== null && val !== undefined && Math.abs(val) > 2 ? 'danger' : 'info'"
                      class="feature-tag"
                    >
                      {{ key }}={{ val }}
                    </el-tag>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </template>

        <el-empty v-else-if="!loading.anomaly" description="点击「运行分析」查看异动检测" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { runUnsupervised, getRegimeResult, getPCAResult, getAnomalyResult } from '@/api/track'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'

const activeTab = ref('regime')

const loading = ref({ regime: false, pca: false, anomaly: false })
const regimeData = ref<any>(null)
const pcaData = ref<any>(null)
const anomalyData = ref<any>(null)
const regimeUpdated = ref('')
const pcaUpdated = ref('')
const anomalyUpdated = ref('')

const regimeChartRef = ref<HTMLElement>()
const pcaChartRef = ref<HTMLElement>()

// ── 加载已有结果 ──
onMounted(async () => {
  try {
    const resp: any = await getRegimeResult()
    if (resp && resp.data) { regimeData.value = resp.data; regimeUpdated.value = resp.created_at || '' }
  } catch { /* ignore */ }
  try {
    const resp: any = await getPCAResult()
    if (resp && resp.data) { pcaData.value = resp.data; pcaUpdated.value = resp.created_at || '' }
  } catch { /* ignore */ }
  try {
    const resp: any = await getAnomalyResult()
    if (resp && resp.data) { anomalyData.value = resp.data; anomalyUpdated.value = resp.created_at || '' }
  } catch { /* ignore */ }
})

async function runRegime() {
  loading.value.regime = true
  try {
    await runUnsupervised('regime')
    ElMessage.success('市场状态分析完成')
    const resp: any = await getRegimeResult()
    if (resp && resp.data) { regimeData.value = resp.data; regimeUpdated.value = resp.created_at || '' }
    await nextTick()
    renderRegimeChart()
  } catch (e: any) {
    ElMessage.error('分析失败: ' + (e.message || ''))
  } finally {
    loading.value.regime = false
  }
}

async function runPCA() {
  loading.value.pca = true
  try {
    await runUnsupervised('pca')
    ElMessage.success('因子降维分析完成')
    const resp: any = await getPCAResult()
    if (resp && resp.data) { pcaData.value = resp.data; pcaUpdated.value = resp.created_at || '' }
    await nextTick()
    renderPCAChart()
  } catch (e: any) {
    ElMessage.error('分析失败: ' + (e.message || ''))
  } finally {
    loading.value.pca = false
  }
}

async function runAnomaly() {
  loading.value.anomaly = true
  try {
    await runUnsupervised('anomaly')
    ElMessage.success('异常检测完成')
    const resp: any = await getAnomalyResult()
    if (resp && resp.data) { anomalyData.value = resp.data; anomalyUpdated.value = resp.created_at || '' }
  } catch (e: any) {
    ElMessage.error('分析失败: ' + (e.message || ''))
  } finally {
    loading.value.anomaly = false
  }
}

// ── PCA 因子载荷 Top 20 ──
const topLoadings = computed(() => {
  if (!pcaData.value?.factor_loadings) return []
  return pcaData.value.factor_loadings
    .sort((a: any, b: any) => Math.abs(b.pc1) + Math.abs(b.pc2) - Math.abs(a.pc1) - Math.abs(a.pc2))
    .slice(0, 20)
})

function tagType(cat: string): string {
  const map: Record<string, string> = {
    '动量': 'danger', '趋势': 'primary', '波动率': 'warning',
    '量能': 'success', '统计': 'info', '赛道专属': '',
    '基本面': '',
  }
  return map[cat] || ''
}

// ── ECharts 渲染 ──
async function renderRegimeChart() {
  if (!regimeChartRef.value || !regimeData.value?.regimes) return
  const chart = echarts.init(regimeChartRef.value)
  const regimes = regimeData.value.regimes

  const dates = regimes.map((r: any) => r.date)
  const colors = regimes.map((r: any) => r.color)
  const labels = regimes.map((r: any) => r.label)

  chart.setOption({
    tooltip: { trigger: 'axis', formatter: (params: any) => {
      const i = params[0]?.dataIndex
      if (i === undefined) return ''
      return `${regimes[i].date}<br/>状态: ${regimes[i].label}`
    }},
    grid: { left: 40, right: 20, top: 20, bottom: 30 },
    xAxis: {
      type: 'category', data: dates,
      axisLabel: { rotate: 45, fontSize: 10, interval: Math.max(1, Math.floor(dates.length / 30)) },
    },
    yAxis: { type: 'category', data: ['熊市', '震荡', '牛市'], axisLabel: { fontSize: 11 } },
    series: [{
      type: 'scatter',
      symbolSize: 8,
      data: regimes.map((r: any) => ({
        value: [r.date, r.label],
        itemStyle: { color: r.color },
      })),
    }],
  })
}

async function renderPCAChart() {
  if (!pcaChartRef.value || !pcaData.value?.data_points) return
  const chart = echarts.init(pcaChartRef.value)
  const points = pcaData.value.data_points

  chart.setOption({
    tooltip: { trigger: 'item', formatter: (p: any) => `PC1: ${p.data[0].toFixed(3)}<br/>PC2: ${p.data[1].toFixed(3)}` },
    grid: { left: 50, right: 30, top: 20, bottom: 40 },
    xAxis: { type: 'value', name: 'PC1', nameLocation: 'center', nameGap: 25 },
    yAxis: { type: 'value', name: 'PC2', nameLocation: 'center', nameGap: 30 },
    series: [{
      type: 'scatter',
      symbolSize: 3,
      data: points.map((p: any) => [p.pc1, p.pc2]),
      itemStyle: { color: '#3b82f6', opacity: 0.6 },
    }],
  })
}

watch(activeTab, async (tab) => {
  await nextTick()
  if (tab === 'regime' && regimeData.value) renderRegimeChart()
  if (tab === 'pca' && pcaData.value) renderPCAChart()
})
</script>

<style scoped>
.unsupervised-page {
  padding: 20px 24px;
  max-width: 1200px;
  margin: 0 auto;
}
.page-header {
  margin-bottom: 16px;
  display: flex;
  align-items: baseline;
  gap: 12px;
}
.page-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: #1a1a2e;
  margin: 0;
}
.page-subtitle {
  font-size: 12px;
  color: #94a3b8;
}
.analysis-tabs {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.tab-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.update-hint {
  font-size: 11px;
  color: #94a3b8;
}

/* 市场状态卡片 */
.regime-card {
  border-left: 4px solid #909399;
  background: #f8fafc;
  border-radius: 8px;
  padding: 20px 24px;
  margin-bottom: 16px;
}
.regime-current {
  display: flex;
  align-items: center;
  gap: 16px;
}
.regime-badge {
  display: inline-block;
  padding: 6px 18px;
  border-radius: 20px;
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 2px;
}
.regime-desc {
  font-size: 13px;
  color: #475569;
}

/* 统计卡片 */
.stat-row {
  margin-bottom: 16px;
}
.stat-card {
  background: #f8fafc;
  border-radius: 8px;
  padding: 14px 16px;
  text-align: center;
}
.stat-label {
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 4px;
}
.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: #1a1a2e;
}
.stat-value.small {
  font-size: 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

/* 图表 */
.chart-container {
  margin-bottom: 16px;
}
.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 8px;
}
.chart-box {
  width: 100%;
  height: 300px;
  background: #fafbfc;
  border-radius: 6px;
}

/* 特征标签 */
.feature-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.feature-tag {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
