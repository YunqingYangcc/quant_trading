<template>
  <div class="daily-sim-page">
    <div class="page-header">
      <h2>个股模拟日报</h2>
      <div class="header-right">
        <span class="page-date">{{ report?.date || '加载中...' }}</span>
        <el-button size="small" type="primary" :loading="loading" @click="refresh">刷新</el-button>
      </div>
    </div>

    <div v-if="loading" class="loading-state"><el-skeleton :rows="4" animated /></div>

    <el-row :gutter="12" class="stat-row" v-if="report?.stocks">
      <el-col :span="6"><div class="stat-card">总股票<span class="stat-num">{{ report.total }}</span></div></el-col>
      <el-col :span="6"><div class="stat-card">有记录<span class="stat-num">{{ hasPred }}</span></div></el-col>
      <el-col :span="6"><div class="stat-card">平均胜率<span class="stat-num">{{ avgWin }}%</span></div></el-col>
    </el-row>

    <template v-if="report?.stocks">
      <div v-for="group in trackGroups" :key="group.track" class="track-section">
        <div class="track-header">{{ group.track }} ({{ group.stocks.length }}只)</div>
        <el-table :data="group.stocks" size="small" stripe>
          <el-table-column label="定位" width="55">
            <template #default="{ row }"><el-tag :type="row.position==='龙1'?'danger':'warning'" size="small" effect="dark">{{ row.position }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="name" label="股票" width="90" />
          <el-table-column prop="code" label="代码" width="110" />
          <el-table-column prop="segment" label="细分" width="110" />
          <el-table-column label="涨跌" width="85" align="right">
            <template #default="{ row }"><span :class="row.change_pct>0?'up':row.change_pct<0?'down':'flat'" style="font-weight:700">{{ row.change_pct>0?'+':'' }}{{ row.change_pct.toFixed(2) }}%</span></template>
          </el-table-column>
          <el-table-column label="预测胜率" width="120" align="center">
            <template #default="{ row }">
              <template v-if="row.pred_total>0">
                <span :style="{color:row.pred_win_rate>50?'#67c23a':row.pred_win_rate>30?'#e6a23c':'#f56c6c',fontWeight:700}">{{ row.pred_win_rate }}%</span>
                <span class="pred-count">({{ row.pred_good }}/{{ row.pred_total }})</span>
              </template>
              <span v-else class="no-data">暂无</span>
            </template>
          </el-table-column>
          <el-table-column label="" width="100">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="goTrack(row.code)">个股分析</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>
    <el-empty v-else-if="!loading" description="暂无数据，请先在TrackDashboard保存预测" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const router = useRouter()
const report = ref<any>(null)
const loading = ref(false)

const trackGroups = computed(() => {
  if (!report.value?.stocks) return []
  const map: Record<string, any[]> = {}
  for (const s of report.value.stocks) { const t = s.track || '其他'; (map[t] = map[t] || []).push(s) }
  return Object.entries(map).map(([t, items]) => ({ track: t, stocks: items }))
})
const hasPred = computed(() => report.value?.stocks?.filter((s: any) => s.pred_total > 0).length || 0)
const avgWin = computed(() => {
  const stocks = (report.value?.stocks || []).filter((s: any) => s.pred_total > 0)
  if (!stocks.length) return 0
  return (stocks.reduce((sum: number, s: any) => sum + s.pred_win_rate, 0) / stocks.length).toFixed(0)
})

onMounted(load)
async function load() { loading.value = true; try { report.value = await (await fetch('http://localhost:8000/api/v1/daily-report/latest')).json() } catch {} finally { loading.value = false } }
async function refresh() { await load(); ElMessage.success('已刷新') }
function goTrack(code: string) { router.push(`/track/semiconductor`) }
</script>

<style scoped>
.daily-sim-page { padding: 20px 24px; max-width: 1400px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { font-size: 20px; font-weight: 600; color: #1a1a2e; margin: 0; }
.header-right { display: flex; align-items: center; gap: 12px; }
.page-date { font-size: 12px; color: #94a3b8; }
.stat-row { margin-bottom: 16px; }
.stat-card { background: #fff; border-radius: 8px; padding: 12px 16px; font-size: 12px; color: #64748b; display: flex; justify-content: space-between; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.stat-num { font-size: 20px; font-weight: 700; color: #1a1a2e; }
.track-section { margin-bottom: 16px; }
.track-header { font-size: 13px; font-weight: 600; color: #475569; margin-bottom: 6px; padding-bottom: 4px; border-bottom: 2px solid #3b82f6; }
.up { color: #f56c6c; } .down { color: #67c23a; } .flat { color: #909399; }
.pred-count { font-size: 10px; color: #94a3b8; }
.no-data { font-size: 11px; color: #c0c4cc; }
</style>
