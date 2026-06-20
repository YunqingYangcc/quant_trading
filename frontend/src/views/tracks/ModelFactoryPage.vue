<template>
  <div class="model-factory-page">
    <div class="page-header">
      <h2>🤖 Model Factory</h2>
      <el-button size="small" @click="loadData" :loading="loading">重新加载</el-button>
    </div>

    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="3" animated />
    </div>

    <template v-else>
      <!-- 模型卡片网格 -->
      <div class="model-grid">
        <div v-for="m in models" :key="m.track_name" class="model-card"
          :class="{ 'overfit': m.overfitting }">
          <div class="card-top">
            <div class="card-name" :style="{ color: trackColor(m.track_name) }">
              {{ m.track_name?.toUpperCase() }}
            </div>
            <el-tag :type="m.status === 'trained' ? 'success' : 'warning'" size="small" effect="dark" round>
              {{ m.overfitting ? '⚠️ Overfit' : '✅ Ready' }}
            </el-tag>
          </div>
          <div class="card-meta">
            <span class="meta-label">Training</span>
            <span class="meta-value">{{ m.trained_at || 'N/A' }}</span>
          </div>
          <div class="card-metrics">
            <div class="metric">
              <span class="m-label">Train R²</span>
              <span class="m-value" :style="{ color: m.train_r2 > 0 ? '#67c23a' : '#f56c6c' }">{{ (m.train_r2 || 0).toFixed(4) }}</span>
            </div>
            <div class="metric">
              <span class="m-label">Val R²</span>
              <span class="m-value">{{ (m.val_r2 || 0).toFixed(4) }}</span>
            </div>
            <div class="metric">
              <span class="m-label">Test R²</span>
              <span class="m-value">{{ (m.test_r2 || 0).toFixed(4) }}</span>
            </div>
            <div class="metric">
              <span class="m-label">CV Mean</span>
              <span class="m-value">{{ (m.cv_mean_r2 || 0).toFixed(4) }}</span>
            </div>
            <div class="metric">
              <span class="m-label">Stocks</span>
              <span class="m-value">{{ m.n_stocks || 0 }}</span>
            </div>
            <div class="metric">
              <span class="m-label">Samples</span>
              <span class="m-value">{{ (m.train_rows || 0).toLocaleString() }}</span>
            </div>
          </div>
          <div class="card-actions" style="display:flex;gap:6px;">
            <el-button size="small" type="primary" plain @click="retrain(m.track_name)" :loading="trainingTrack === m.track_name">
              {{ trainingTrack === m.track_name ? 'Training...' : '🔄 Retrain' }}
            </el-button>
            <el-button size="small" @click="openParamDialog(m.track_name)">
              ⚙️ 参数训练
            </el-button>
          </div>
          <!-- 评分结果展示 -->
          <div v-if="latestScores[m.track_name]" class="card-scores">
            <div class="scores-header" @click="toggleScores(m.track_name)">
              <span>📊 评分结果</span>
              <span class="sentiment-badge" :style="{ background: sentimentColor(latestScores[m.track_name].track_sentiment) }">
                {{ latestScores[m.track_name].track_sentiment }}
              </span>
              <span class="toggle-icon">{{ expandedScores[m.track_name] ? '▲' : '▼' }}</span>
            </div>
            <div v-show="expandedScores[m.track_name]" class="scores-body">
              <div v-for="s in latestScores[m.track_name].scores.slice(0, 20)" :key="s.stock_code" class="score-row">
                <span class="score-rank">#{{ s.rank }}</span>
                <span class="score-stock">{{ s.stock_name || s.stock_code }}</span>
                <span class="score-val" :style="{ color: s.score > 0 ? '#f56c6c' : '#67c23a' }">{{ s.score.toFixed(4) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 特征重要性 Top10 -->
      <div class="section-card">
        <div class="section-title">📊 特征重要性 Top 10</div>
        <div class="track-tabs">
          <el-radio-group v-model="selectedModelForFeat" size="small">
            <el-radio-button v-for="m in models" :key="m.track_name" :value="m.track_name">
              {{ m.track_name?.toUpperCase() }}
            </el-radio-button>
          </el-radio-group>
        </div>
        <div ref="featChartRef" class="chart-box" />
      </div>

      <!-- 模型训练结果比对 -->
      <div class="section-card">
        <div class="section-title">📋 模型训练结果 比对</div>
        <el-table :data="models" size="small" stripe style="width:100%">
          <el-table-column prop="track_name" label="赛道" width="120">
            <template #default="{ row }">
              <span :style="{ fontWeight: 600, color: trackColor(row.track_name) }">{{ row.track_name?.toUpperCase() }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="trained_at" label="训练时间" width="150" />
          <el-table-column prop="n_stocks" label="股票数" width="70" align="center" />
          <el-table-column prop="train_rows" label="训练样本" width="100" align="right">
            <template #default="{ row }">{{ (row.train_rows || 0).toLocaleString() }}</template>
          </el-table-column>
          <el-table-column prop="train_r2" label="Train R²" width="100" align="right">
            <template #default="{ row }"><span :style="{ color: row.train_r2 > 0 ? '#67c23a' : '#f56c6c' }">{{ (row.train_r2 || 0).toFixed(4) }}</span></template>
          </el-table-column>
          <el-table-column prop="val_r2" label="Val R²" width="100" align="right">
            <template #default="{ row }">{{ (row.val_r2 || 0).toFixed(4) }}</template>
          </el-table-column>
          <el-table-column prop="test_r2" label="Test R²" width="100" align="right">
            <template #default="{ row }">{{ (row.test_r2 || 0).toFixed(4) }}</template>
          </el-table-column>
          <el-table-column prop="cv_mean_r2" label="CV Mean" width="100" align="right">
            <template #default="{ row }">{{ (row.cv_mean_r2 || 0).toFixed(4) }}</template>
          </el-table-column>
          <el-table-column prop="overfitting" label="过拟合" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row.overfitting ? 'danger' : 'success'" size="small" effect="plain">{{ row.overfitting ? '⚠️' : '✅' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" align="center">
            <template #default="{ row }">
              <el-button size="small" type="primary" link @click="retrain(row.track_name)" :loading="trainingTrack === row.track_name">重训</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 评分历史 -->
      <div class="section-card">
        <div class="section-title">📈 评分历史</div>
        <div style="margin-bottom:12px;">
          <el-radio-group v-model="historyTrackName" size="small">
            <el-radio-button v-for="m in models" :key="m.track_name" :value="m.track_name">
              {{ m.track_name?.toUpperCase() }}
            </el-radio-button>
          </el-radio-group>
        </div>
        <div v-if="scoreHistory.length === 0" style="color:#909399;font-size:13px;padding:12px 0;">暂无评分历史，训练后将自动生成</div>
        <div v-for="(h, hi) in scoreHistory" :key="hi" class="history-item">
          <div class="history-header">
            <span class="history-time">{{ h.scored_at }}</span>
            <span class="history-metrics">
              Train R²: <b :style="{ color: h.train_r2 > 0 ? '#67c23a' : '#f56c6c' }">{{ h.train_r2.toFixed(4) }}</b>
              Val R²: <b>{{ h.val_r2.toFixed(4) }}</b>
              Test R²: <b>{{ h.test_r2.toFixed(4) }}</b>
            </span>
          </div>
          <div class="history-scores">
            <div v-for="s in h.scores.slice(0, 10)" :key="s.rank" class="score-row">
              <span class="score-rank">#{{ s.rank }}</span>
              <span class="score-stock">{{ s.stock_name || s.stock_code }}</span>
              <span class="score-val" :style="{ color: s.score > 0 ? '#f56c6c' : '#67c23a' }">{{ s.score.toFixed(4) }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 参数配置对话框 -->
    <el-dialog v-model="paramDialogVisible" :title="`⚙️ 参数训练 - ${paramDialogTrack.toUpperCase()}`" width="500px" :close-on-click-modal="false">
      <div class="param-form">
        <div class="param-row">
          <label>num_leaves（叶子节点数）</label>
          <el-slider v-model="trainParams.num_leaves" :min="4" :max="128" :step="1" show-input size="small" />
        </div>
        <div class="param-row">
          <label>max_depth（最大深度）</label>
          <el-slider v-model="trainParams.max_depth" :min="3" :max="20" :step="1" show-input size="small" />
        </div>
        <div class="param-row">
          <label>learning_rate（学习率）</label>
          <el-slider v-model="trainParams.learning_rate" :min="0.01" :max="0.5" :step="0.01" show-input size="small" />
        </div>
        <div class="param-row">
          <label>n_estimators（迭代轮数）</label>
          <el-slider v-model="trainParams.n_estimators" :min="100" :max="3000" :step="100" show-input size="small" />
        </div>
        <div class="param-row">
          <label>reg_alpha（L1 正则）</label>
          <el-slider v-model="trainParams.reg_alpha" :min="0" :max="5" :step="0.1" show-input size="small" />
        </div>
        <div class="param-row">
          <label>reg_lambda（L2 正则）</label>
          <el-slider v-model="trainParams.reg_lambda" :min="0" :max="5" :step="0.1" show-input size="small" />
        </div>
        <div class="param-row">
          <label>feature_fraction（特征采样）</label>
          <el-slider v-model="trainParams.feature_fraction" :min="0.3" :max="1.0" :step="0.05" show-input size="small" />
        </div>
        <div class="param-row">
          <label>bagging_fraction（样本采样）</label>
          <el-slider v-model="trainParams.bagging_fraction" :min="0.3" :max="1.0" :step="0.05" show-input size="small" />
        </div>
      </div>
      <template #footer>
        <el-button @click="paramDialogVisible = false" size="small">取消</el-button>
        <el-button type="primary" @click="trainWithParams" :loading="trainingTrack === paramDialogTrack" size="small">
          {{ trainingTrack === paramDialogTrack ? '训练中...' : '开始训练' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { getAllModels, trainTrackModel, getScoreHistory } from '@/api/track'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'

const loading = ref(true)
const models = ref<any[]>([])
const trainingTrack = ref('')
const selectedModelForFeat = ref('')
const featChartRef = ref<HTMLElement>()

// 参数训练对话框
const paramDialogVisible = ref(false)
const paramDialogTrack = ref('')
const trainParams = ref({
  num_leaves: 31,
  max_depth: 8,
  learning_rate: 0.05,
  n_estimators: 1000,
  reg_alpha: 0.1,
  reg_lambda: 1.0,
  feature_fraction: 0.8,
  bagging_fraction: 0.9,
  min_child_samples: 20,
})

// 评分结果
const latestScores = ref<Record<string, any>>({})
const expandedScores = ref<Record<string, boolean>>({})

// 评分历史
const historyTrackName = ref('')
const scoreHistory = ref<any[]>([])

const trackColors: Record<string, string> = {
  semiconductor: '#3b82f6',
  ai: '#f59e0b',
  robot: '#10b981',
  storage: '#8b5cf6',
}
function trackColor(name: string) { return trackColors[name] || '#909399' }

function sentimentColor(val: number): string {
  if (val >= 60) return '#f56c6c'
  if (val >= 40) return '#e6a23c'
  return '#67c23a'
}

const currentModel = computed(() => {
  return models.value.find(m => m.track_name === selectedModelForFeat.value)
})

async function loadData() {
  loading.value = true
  try {
    const res = await getAllModels()
    models.value = (res as any) || []
    if (models.value.length > 0 && !selectedModelForFeat.value) {
      selectedModelForFeat.value = models.value[0].track_name
      historyTrackName.value = models.value[0].track_name
    }
  } catch (e) {
    console.error('Model data load failed', e)
  }
  loading.value = false
  nextTick(renderFeatChart)
  loadScoreHistory()
}

async function retrain(trackName: string) {
  trainingTrack.value = trackName
  try {
    const res = await trainTrackModel(trackName)
    if ((res as any)?.scores) {
      latestScores.value[trackName] = res as any
      expandedScores.value[trackName] = true
    }
    ElMessage.success(`${trackName} 训练完成`)
    await loadData()
  } catch (e: any) {
    ElMessage.error(`${trackName} 训练失败: ${e.message || ''}`)
    console.error('Retrain failed', e)
  }
  trainingTrack.value = ''
}

function openParamDialog(trackName: string) {
  paramDialogTrack.value = trackName
  // 如果有历史参数，用最后一次的
  paramDialogVisible.value = true
}

async function trainWithParams() {
  const trackName = paramDialogTrack.value
  if (!trackName) return
  trainingTrack.value = trackName
  paramDialogVisible.value = false
  try {
    const res = await trainTrackModel(trackName, { ...trainParams.value })
    if ((res as any)?.scores) {
      latestScores.value[trackName] = res as any
      expandedScores.value[trackName] = true
    }
    await loadData()
  } catch (e: any) {
    console.error('Train with params failed', e)
  }
  trainingTrack.value = ''
}

function toggleScores(trackName: string) {
  expandedScores.value[trackName] = !expandedScores.value[trackName]
}

async function loadScoreHistory() {
  if (!historyTrackName.value || models.value.length === 0) return
  try {
    const res = await getScoreHistory(historyTrackName.value)
    scoreHistory.value = (res as any) || []
  } catch (e) {
    console.error('Load score history failed', e)
  }
}

function renderFeatChart() {
  nextTick(() => {
    if (!featChartRef.value || !currentModel.value) return
    const features = currentModel.value.top_features || []
    if (features.length === 0) return

    const chart = echarts.init(featChartRef.value)
    const names = features.map((f: any) => f.name).reverse()
    const values = features.map((f: any) => f.importance).reverse()

    chart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 180, right: 30, top: 10, bottom: 20 },
      xAxis: { type: 'value' },
      yAxis: { type: 'category', data: names, axisLabel: { fontSize: 10 } },
      series: [{
        type: 'bar',
        data: values.map((v: number) => ({
          value: v,
          itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: trackColor(currentModel.value.track_name) },
            { offset: 1, color: trackColor(currentModel.value.track_name) + '66' },
          ]) },
        })),
        barWidth: 14,
      }],
    })
  })
}

watch(selectedModelForFeat, renderFeatChart)
watch(models, () => { nextTick(renderFeatChart) })
watch(historyTrackName, loadScoreHistory)

onMounted(loadData)
</script>

<style scoped>
.model-factory-page {
  min-height: 100%;
  padding: 24px 32px;
  background: #f5f7fa;
}
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; font-size: 22px; color: #1e293b; }
.loading-state { padding: 40px; background: #fff; border-radius: 10px; }

.model-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 16px; }
.model-card { background: #fff; border-radius: 10px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border-top: 3px solid transparent; }
.model-card.overfit { border-top-color: #f56c6c; }
.card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.card-name { font-size: 16px; font-weight: 700; }
.card-meta { font-size: 11px; color: #909399; margin-bottom: 10px; }
.card-meta .meta-label { color: #c0c4cc; }
.card-meta .meta-value { margin-left: 4px; }
.card-metrics { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 8px; margin-bottom: 12px; }
.metric { display: flex; justify-content: space-between; font-size: 11px; padding: 2px 0; border-bottom: 1px solid #f5f5f5; }
.m-label { color: #909399; }
.m-value { font-weight: 600; color: #303133; }
.card-actions { text-align: center; }

.section-card { background: #fff; border-radius: 8px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom: 16px; }
.section-title { font-size: 14px; font-weight: 600; color: #303133; margin-bottom: 12px; }
.chart-box { width: 100%; height: 380px; }
.track-tabs { margin-bottom: 12px; }

/* 评分结果 */
.card-scores { margin-top: 10px; border-top: 1px solid #f0f0f0; padding-top: 8px; }
.scores-header { display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 600; color: #606266; cursor: pointer; padding: 4px 0; }
.sentiment-badge { font-size: 10px; font-weight: 700; color: #fff; padding: 1px 8px; border-radius: 8px; }
.toggle-icon { margin-left: auto; font-size: 10px; color: #909399; }
.scores-body { max-height: 320px; overflow-y: auto; margin-top: 6px; }
.score-row { display: flex; align-items: center; gap: 8px; font-size: 11px; padding: 3px 4px; border-bottom: 1px solid #f8f8f8; }
.score-row:hover { background: #fafafa; }
.score-rank { width: 24px; color: #909399; font-weight: 500; }
.score-stock { flex: 1; color: #303133; }
.score-val { font-weight: 600; font-family: 'SF Mono', monospace; min-width: 60px; text-align: right; }

/* 评分历史 */
.history-item { margin-bottom: 12px; padding: 10px 12px; background: #fafafa; border-radius: 6px; border: 1px solid #eee; }
.history-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.history-time { font-size: 11px; color: #909399; }
.history-metrics { font-size: 11px; color: #606266; display: flex; gap: 12px; }
.history-metrics b { margin-left: 2px; }
.history-scores { display: grid; grid-template-columns: repeat(2, 1fr); gap: 2px 12px; }

/* 参数表单 */
.param-form { display: flex; flex-direction: column; gap: 14px; }
.param-row label { display: block; font-size: 12px; color: #606266; margin-bottom: 4px; font-weight: 500; }
</style>
