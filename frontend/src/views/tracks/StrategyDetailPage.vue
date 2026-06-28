<template>
  <div class="strategy-detail-page">
    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="5" animated />
    </div>

    <template v-else-if="strategy">
      <div class="page-header">
        <el-button text @click="$router.back()"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
        <h2>{{ strategy.name }}</h2>
        <el-tag :type="tagType(strategy.type)" size="small">{{ strategy.type }}</el-tag>
      </div>

      <div class="detail-grid">
        <!-- 左列: 策略信息 -->
        <div class="detail-left">
          <div class="info-card">
            <div class="card-title">策略概述</div>
            <div class="info-item">
              <span class="info-label">一句话说明</span>
              <span class="info-value">{{ strategy.description || '无' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">选股机制</span>
              <span class="info-value">{{ strategy.mechanism || '无' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">适用行情</span>
              <span class="info-value">{{ strategy.market_condition || '通用' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">预期效果</span>
              <span class="info-value">{{ strategy.expected_effect || '无' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">风险提示</span>
              <span class="info-value">{{ strategy.limitations || '无' }}</span>
            </div>
          </div>

          <!-- 参数说明 -->
          <div class="info-card" v-if="strategy.params_detail && Object.keys(strategy.params_detail).length">
            <div class="card-title">参数说明</div>
            <div class="param-item" v-for="(desc, param) in strategy.params_detail" :key="param">
              <span class="param-name">{{ param }}</span>
              <span class="param-desc">{{ desc }}</span>
            </div>
          </div>
        </div>

        <!-- 右列: 绩效 -->
        <div class="detail-right">
          <div class="info-card">
            <div class="card-title">
              各赛道绩效
              <el-tag v-if="strategy.performance?.length" type="info" size="small" style="margin-left: 8px;">
                {{ strategy.performance.length }} 赛道
              </el-tag>
            </div>
            <el-table v-if="strategy.performance?.length" :data="strategy.performance" size="small" stripe>
              <el-table-column prop="track_name" label="赛道" width="120" />
              <el-table-column prop="sharpe" label="Sharpe" width="100" align="right">
                <template #default="{ row }">
                  <span :style="{ color: row.sharpe > 0.5 ? '#67c23a' : row.sharpe > 0 ? '#e6a23c' : '#f56c6c', fontWeight: 600 }">
                    {{ row.sharpe.toFixed(2) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="max_drawdown" label="最大回撤" width="110" align="right">
                <template #default="{ row }">
                  <span :style="{ color: Math.abs(row.max_drawdown) < 0.15 ? '#67c23a' : '#f56c6c' }">
                    {{ (row.max_drawdown * 100).toFixed(1) }}%
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="win_rate" label="胜率" width="90" align="right">
                <template #default="{ row }">{{ (row.win_rate * 100).toFixed(0) }}%</template>
              </el-table-column>
              <el-table-column prop="backtest_date" label="回测日期" width="110">
                <template #default="{ row }">{{ row.backtest_date || '-' }}</template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="暂无绩效数据，请先运行回测" :image-size="60" />
          </div>

          <div class="info-card">
            <div class="card-title">快速操作</div>
            <div class="quick-actions">
              <el-button type="primary" size="small" @click="goToBacktest">在策略实验室中回测</el-button>
              <el-button size="small" @click="goToDailyReport">查看每日报告排名</el-button>
            </div>
          </div>
        </div>
      </div>
    </template>

    <el-empty v-else description="策略不存在" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getStrategyDetail } from '@/api/track'
import { ArrowLeft } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const strategy = ref<any>(null)
const loading = ref(true)

onMounted(async () => {
  const key = route.params.key as string
  try {
    const resp: any = await getStrategyDetail(key)
    strategy.value = resp
  } catch {
    strategy.value = null
  } finally {
    loading.value = false
  }
})

function tagType(type: string): string {
  const map: Record<string, string> = {
    'technical': '', 'momentum': 'success', 'trend': 'primary',
    'mean_reversion': 'warning', 'volume': 'info', 'composite': 'danger',
    'ai': '',
  }
  return map[type] || 'info'
}

function goToBacktest() {
  router.push('/backtest')
}
function goToDailyReport() {
  router.push('/daily-report')
}
</script>

<style scoped>
.strategy-detail-page {
  padding: 20px 24px;
  max-width: 1100px;
  margin: 0 auto;
}
.loading-state { padding: 40px; }
.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}
.page-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: #1a1a2e;
  margin: 0;
}
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
.detail-left, .detail-right { display: flex; flex-direction: column; gap: 16px; }
.info-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.card-title {
  font-size: 14px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0f2f5;
}
.info-item {
  display: flex;
  padding: 6px 0;
  gap: 12px;
}
.info-label {
  font-size: 12px;
  color: #94a3b8;
  min-width: 80px;
  flex-shrink: 0;
}
.info-value {
  font-size: 13px;
  color: #334155;
  line-height: 1.6;
}
.param-item {
  display: flex;
  padding: 5px 0;
  gap: 12px;
}
.param-name {
  font-family: 'SF Mono', monospace;
  font-size: 12px;
  color: #3b82f6;
  min-width: 140px;
  flex-shrink: 0;
}
.param-desc {
  font-size: 12px;
  color: #64748b;
}
.quick-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
