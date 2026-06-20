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
          <div class="card-actions">
            <el-button size="small" type="primary" plain @click="retrain(m.track_name)" :loading="trainingTrack === m.track_name">
              {{ trainingTrack === m.track_name ? 'Training...' : '🔄 Retrain' }}
            </el-button>
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
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { getAllModels, trainTrackModel } from '@/api/track'
import * as echarts from 'echarts'

const loading = ref(true)
const models = ref<any[]>([])
const trainingTrack = ref('')
const selectedModelForFeat = ref('')
const featChartRef = ref<HTMLElement>()

const trackColors: Record<string, string> = {
  semiconductor: '#3b82f6',
  ai: '#f59e0b',
  robot: '#10b981',
  storage: '#8b5cf6',
}
function trackColor(name: string) { return trackColors[name] || '#909399' }

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
    }
  } catch (e) {
    console.error('Model data load failed', e)
  }
  loading.value = false
  nextTick(renderFeatChart)
}

async function retrain(trackName: string) {
  trainingTrack.value = trackName
  try {
    await trainTrackModel(trackName)
    await loadData()
  } catch (e: any) {
    console.error('Retrain failed', e)
  }
  trainingTrack.value = ''
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
</style>
