<template>
  <div class="features-page">
    <!-- Header -->
    <div class="fp-header">
      <div class="fp-header-left">
        <div class="fp-title-row">
          <span class="fp-title-icon">📋</span>
          <div>
            <div class="fp-title">Feature Config</div>
            <div class="fp-subtitle">特征配置管理 · {{ configs.length }} 个特征</div>
          </div>
        </div>
      </div>
      <div class="fp-header-actions">
        <el-button size="small" @click="handleIncremental" :loading="loadingInc" :icon="RefreshRight">
          增量更新
        </el-button>
        <el-button size="small" @click="handleSync" :loading="loadingSync" :icon="Connection">
          从已计算同步
        </el-button>
        <el-button type="primary" size="small" @click="openCreate" :icon="Plus">
          新建特征
        </el-button>
      </div>
    </div>

    <!-- Focus Panel -->
    <div class="fp-focus">
      <!-- Stats Bar -->
      <div class="fp-stats-row">
        <div class="fp-stat-item">
          <span class="fp-stat-num">{{ configs.length }}</span>
          <span class="fp-stat-label">全部特征</span>
        </div>
        <div class="fp-stat-divider" />
        <div class="fp-stat-item">
          <span class="fp-stat-num fp-stat-green">{{ enabledCount }}</span>
          <span class="fp-stat-label">已启用</span>
        </div>
        <div class="fp-stat-divider" />
        <div class="fp-stat-item">
          <span class="fp-stat-num fp-stat-muted">{{ disabledCount }}</span>
          <span class="fp-stat-label">已禁用</span>
        </div>
        <div class="fp-stat-divider" />
        <div class="fp-stat-item">
          <span class="fp-stat-num fp-stat-blue">{{ whitelistFactors.length }}</span>
          <span class="fp-stat-label">已验证因子</span>
        </div>
        <div class="fp-stat-divider" />
        <div class="fp-stat-item">
          <span class="fp-stat-num fp-stat-purple">{{ categoryCount }}</span>
          <span class="fp-stat-label">分类数</span>
        </div>
        <div class="fp-stat-divider" />
        <div class="fp-stat-item">
          <span class="fp-stat-num" style="font-size:15px">{{ metadata.version }}</span>
          <span class="fp-stat-label">版本 · {{ metadata.latest_date || '未知' }}</span>
        </div>
      </div>

      <!-- Top Factors -->
      <div class="fp-top-factors" v-if="topFactors.length > 0">
        <div class="fp-top-header">
          <span class="fp-top-title">🔥 最强因子（按 |IC| 排序）</span>
          <span class="fp-top-hint">IC 绝对值越大，预测能力越强</span>
        </div>
        <div class="fp-top-grid">
          <div v-for="(f, i) in topFactors" :key="f.factor_name" class="fp-top-item" :class="'fp-top-rank-' + (i + 1)">
            <div class="fp-top-rank">{{ i + 1 }}</div>
            <div class="fp-top-body">
              <div class="fp-top-name">{{ f.factor_name }}</div>
              <div class="fp-top-bar-wrap">
                <div
                  class="fp-top-bar-fill"
                  :style="{
                    width: Math.min(Math.abs(f.ic_mean) * 5000, 100) + '%',
                    background: f.ic_mean >= 0 ? '#ef4444' : '#3b82f6'
                  }"
                />
              </div>
            </div>
            <div class="fp-top-val" :class="f.ic_mean >= 0 ? 'fp-top-red' : 'fp-top-blue'">
              {{ (f.ic_mean * 100).toFixed(2) }}
              <span class="fp-top-dir">{{ f.ic_mean >= 0 ? '正向' : '负向' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Toolbar -->
    <div class="fp-toolbar">
      <el-input
        v-model="searchQuery"
        placeholder="搜索特征名称或标识..."
        size="small"
        clearable
        :prefix-icon="Search"
        class="fp-search"
      />
      <el-select v-model="filterCategory" size="small" placeholder="全部分类" clearable class="fp-cat-select">
        <el-option v-for="cat in categories" :key="cat.value" :label="cat.label" :value="cat.value" />
      </el-select>
      <el-select v-model="filterStatus" size="small" placeholder="全部状态" clearable class="fp-status-select">
        <el-option label="已启用" value="enabled" />
        <el-option label="已禁用" value="disabled" />
      </el-select>
      <span class="fp-count">{{ filteredConfigs.length }} / {{ configs.length }}</span>
    </div>

    <!-- Table -->
    <div class="fp-table-wrap">
      <div v-if="loading" class="fp-loading">
        <el-skeleton :rows="8" animated />
      </div>
      <template v-else>
        <div
          v-for="item in filteredConfigs"
          :key="item.id"
          class="fp-row"
          :class="{ 'fp-row-expanded': expanded.has(item.id), 'fp-row-disabled': !item.is_enabled }"
        >
          <!-- Row Header (always visible) -->
          <div class="fpr-header" @click="toggleExpand(item.id)">
            <div class="fpr-toggle">
              <el-switch
                :model-value="!!item.is_enabled"
                size="small"
                @click.stop
                @change="(val: boolean) => handleToggle(item, val)"
              />
            </div>
            <div class="fpr-name-group">
              <div class="fpr-cn-name">{{ item.display_name || item.feature_name }}</div>
              <div class="fpr-en-name">{{ item.feature_name }}</div>
            </div>
            <div class="fpr-category">
              <el-tag
                size="small"
                :type="catTagType(item.category)"
                effect="plain"
                class="fp-cat-tag"
              >{{ catLabel(item.category) }}</el-tag>
            </div>
            <div class="fpr-desc" :title="item.description || ''">
              <span class="fpr-desc-text">{{ item.description ? truncate(item.description, 60) : '—' }}</span>
            </div>
            <div class="fpr-actions">
              <el-button text size="small" @click.stop="openEdit(item)" :icon="Edit">编辑</el-button>
              <el-button text size="small" type="danger" @click.stop="handleDelete(item)" :icon="Delete">删除</el-button>
            </div>
          </div>

          <!-- Expanded Detail -->
          <div v-if="expanded.has(item.id)" class="fpr-detail">
            <div class="fpr-detail-grid">
              <div class="fpr-detail-section">
                <div class="fpr-ds-label">📝 大白话释义</div>
                <div class="fpr-ds-value">{{ item.description || '暂无释义' }}</div>
              </div>
              <div class="fpr-detail-section">
                <div class="fpr-ds-label">📐 计算公式</div>
                <div class="fpr-ds-value formula">{{ item.formula || '—' }}</div>
              </div>
              <div class="fpr-detail-section">
                <div class="fpr-ds-label">💡 解读方法</div>
                <div class="fpr-ds-value">{{ item.interpretation || '—' }}</div>
              </div>
              <div class="fpr-detail-section" v-if="item.default_params">
                <div class="fpr-ds-label">⚙️ 默认参数</div>
                <div class="fpr-ds-value">
                  <code>{{ JSON.stringify(item.default_params) }}</code>
                </div>
              </div>
            </div>
            <div class="fpr-detail-meta">
              <span>创建: {{ formatTime(item.created_at) }}</span>
              <span v-if="item.updated_at"> · 更新: {{ formatTime(item.updated_at) }}</span>
              <span v-if="item.is_user_defined"> · 用户自定义</span>
            </div>
          </div>
        </div>

        <el-empty v-if="!filteredConfigs.length" :description="searchQuery ? '无匹配特征' : '暂无特征配置，点击「从已计算同步」导入'" />
      </template>
    </div>

    <!-- Edit Drawer -->
    <el-drawer
      v-model="drawerVisible"
      :title="editingId ? '编辑特征配置' : '新建特征配置'"
      size="500px"
    >
      <template #default>
        <el-form :model="form" label-position="top" size="small">
          <el-form-item label="特征标识 (feature_name)" v-if="!editingId">
            <el-input v-model="form.feature_name" placeholder="如: rsi_6" />
          </el-form-item>
          <el-form-item label="中文名">
            <el-input v-model="form.display_name" placeholder="如: 6日RSI" />
          </el-form-item>
          <el-form-item label="分类">
            <el-select v-model="form.category" placeholder="选择分类" clearable>
              <el-option v-for="cat in categories" :key="cat.value" :label="cat.label" :value="cat.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="大白话释义">
            <el-input
              v-model="form.description"
              type="textarea"
              :rows="3"
              placeholder="用通俗语言描述这个特征的含义..."
            />
          </el-form-item>
          <el-form-item label="计算公式">
            <el-input
              v-model="form.formula"
              type="textarea"
              :rows="2"
              placeholder="可选：技术指标的数学公式"
            />
          </el-form-item>
          <el-form-item label="解读方法">
            <el-input
              v-model="form.interpretation"
              type="textarea"
              :rows="2"
              placeholder="可选：如何根据这个特征做交易决策"
            />
          </el-form-item>
          <el-form-item label="启用状态">
            <el-switch v-model="form.is_enabled" :active-value="1" :inactive-value="0" />
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="drawerVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Search, Plus, Edit, Delete, RefreshRight, Connection } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listFeatureConfigs,
  createFeatureConfig,
  updateFeatureConfig,
  deleteFeatureConfig,
  toggleFeatureConfig,
  syncFeatureConfigs,
  incrementalCompute,
  getWhitelist,
  type FeatureConfig,
  type FeatureConfigCreate,
  type FeatureConfigUpdate,
} from '@/api/track'
import request from '@/api/index'

const configs = ref<FeatureConfig[]>([])
const whitelistFactors = ref<any[]>([])
const metadata = ref({ version: 'v1', latest_date: '', total_records: 0, stock_count: 0 })
const loading = ref(true)
const loadingSync = ref(false)
const loadingInc = ref(false)
const saving = ref(false)
const searchQuery = ref('')
const filterCategory = ref('')
const filterStatus = ref('')
const expanded = ref<Set<number>>(new Set())

// Drawer
const drawerVisible = ref(false)
const editingId = ref<number | null>(null)
const form = ref<{
  feature_name: string
  display_name: string
  category: string
  description: string
  formula: string
  interpretation: string
  is_enabled: number
}>({
  feature_name: '',
  display_name: '',
  category: '',
  description: '',
  formula: '',
  interpretation: '',
  is_enabled: 1,
})

const categories = [
  { value: 'momentum', label: '⚡ 动量类' },
  { value: 'trend', label: '📈 趋势类' },
  { value: 'volatility', label: '🌊 波动率类' },
  { value: 'volume', label: '📊 量能类' },
  { value: 'statistical', label: '📐 统计类' },
  { value: 'track_specific', label: '🏷️ 赛道专属' },
  { value: 'generic', label: '🔧 通用类' },
  { value: 'fundamental', label: '🏢 基本面类' },
]

function catLabel(val: string | null): string {
  const found = categories.find(c => c.value === val)
  if (found) return found.label
  if (val === 'generic') return '🔧 通用类'
  if (val?.startsWith('track_')) return '🏷️ 赛道专属'
  return val || '未分类'
}

function catTagType(val: string | null): string {
  if (!val) return 'info'
  if (val === 'momentum') return 'danger'
  if (val === 'trend') return 'primary'
  if (val === 'volatility') return 'warning'
  if (val === 'volume') return 'success'
  if (val === 'statistical') return ''
  if (val === 'fundamental') return 'success'
  return 'info'
}

const filteredConfigs = computed(() => {
  let list = configs.value
  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    list = list.filter(c =>
      c.feature_name.toLowerCase().includes(q) ||
      (c.display_name || '').toLowerCase().includes(q) ||
      (c.description || '').toLowerCase().includes(q)
    )
  }
  if (filterCategory.value) {
    list = list.filter(c => c.category === filterCategory.value)
  }
  if (filterStatus.value === 'enabled') {
    list = list.filter(c => c.is_enabled === 1)
  } else if (filterStatus.value === 'disabled') {
    list = list.filter(c => c.is_enabled === 0)
  }
  return list
})

// ── Focus Panel ──
const enabledCount = computed(() => configs.value.filter(c => c.is_enabled === 1).length)
const disabledCount = computed(() => configs.value.filter(c => c.is_enabled === 0).length)

const categoryCount = computed(() => {
  const cats = new Set(configs.value.map(c => c.category).filter(Boolean))
  return cats.size
})

const topFactors = computed(() => {
  return [...whitelistFactors.value]
    .sort((a, b) => Math.abs(b.ic_mean || 0) - Math.abs(a.ic_mean || 0))
    .slice(0, 8)
})

function toggleExpand(id: number) {
  if (expanded.value.has(id)) expanded.value.delete(id)
  else expanded.value.add(id)
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n) + '…' : s
}

function formatTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function loadConfigs() {
  loading.value = true
  try {
    const res: any = await listFeatureConfigs()
    configs.value = Array.isArray(res) ? res : []
  } catch {
    configs.value = []
  } finally {
    loading.value = false
  }
}

async function handleSync() {
  loadingSync.value = true
  try {
    const res: any = await syncFeatureConfigs()
    ElMessage.success(`同步完成: 新增 ${res.synced} 个特征，共 ${res.total} 个`)
    await loadConfigs()
  } catch (e: any) {
    ElMessage.error('同步失败: ' + (e.message || ''))
  } finally {
    loadingSync.value = false
  }
}

async function handleIncremental() {
  loadingInc.value = true
  try {
    const res: any = await incrementalCompute()
    ElMessage.success(`增量计算完成: ${res.stocks_with_new_data} 只股票有更新，新增 ${res.total_added_records} 条记录`)
  } catch (e: any) {
    ElMessage.error('增量计算失败: ' + (e.message || ''))
  } finally {
    loadingInc.value = false
  }
}

async function handleToggle(item: FeatureConfig, val: boolean) {
  try {
    await toggleFeatureConfig(item.id)
    item.is_enabled = val ? 1 : 0
    ElMessage.success(val ? '已启用' : '已禁用')
  } catch (e: any) {
    ElMessage.error('操作失败: ' + (e.message || ''))
  }
}

function openCreate() {
  editingId.value = null
  form.value = { feature_name: '', display_name: '', category: '', description: '', formula: '', interpretation: '', is_enabled: 1 }
  drawerVisible.value = true
}

function openEdit(item: FeatureConfig) {
  editingId.value = item.id
  form.value = {
    feature_name: item.feature_name,
    display_name: item.display_name || '',
    category: item.category || '',
    description: item.description || '',
    formula: item.formula || '',
    interpretation: item.interpretation || '',
    is_enabled: item.is_enabled,
  }
  drawerVisible.value = true
}

async function handleSave() {
  if (!editingId.value && !form.value.feature_name.trim()) {
    ElMessage.warning('请输入特征标识')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      const data: FeatureConfigUpdate = {
        display_name: form.value.display_name || undefined,
        category: form.value.category || undefined,
        description: form.value.description || undefined,
        formula: form.value.formula || undefined,
        interpretation: form.value.interpretation || undefined,
        is_enabled: form.value.is_enabled,
      }
      await updateFeatureConfig(editingId.value, data)
      ElMessage.success('更新成功')
    } else {
      const data: FeatureConfigCreate = {
        feature_name: form.value.feature_name,
        display_name: form.value.display_name || undefined,
        category: form.value.category || undefined,
        description: form.value.description || undefined,
        formula: form.value.formula || undefined,
        interpretation: form.value.interpretation || undefined,
        is_enabled: form.value.is_enabled,
      }
      await createFeatureConfig(data)
      ElMessage.success('创建成功')
    }
    drawerVisible.value = false
    await loadConfigs()
  } catch (e: any) {
    ElMessage.error('保存失败: ' + (e.message || ''))
  } finally {
    saving.value = false
  }
}

async function handleDelete(item: FeatureConfig) {
  try {
    await ElMessageBox.confirm(`确定删除特征「${item.display_name || item.feature_name}」？`, '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteFeatureConfig(item.id)
    ElMessage.success('已删除')
    await loadConfigs()
  } catch {
    // cancelled
  }
}

onMounted(() => {
  loadConfigs()
  loadWhitelist()
  loadMetadata()
})

async function loadWhitelist() {
  try {
    const res: any = await getWhitelist()
    whitelistFactors.value = Array.isArray(res) ? res : []
  } catch {
    whitelistFactors.value = []
  }
}

async function loadMetadata() {
  try {
    const res: any = await request.get('/features/metadata')
    if (res) {
      metadata.value = {
        version: res.version || 'v1',
        latest_date: res.latest_trade_date || '',
        total_records: res.total_records || 0,
        stock_count: res.stock_count || 0,
      }
    }
  } catch {
    // ignore
  }
}
</script>

<style scoped>
.features-page {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  overflow-y: auto;
}

/* ═══ Header ═══ */
.fp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}

.fp-header-left {
  display: flex;
  align-items: center;
}

.fp-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.fp-title-icon {
  font-size: 20px;
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #8b5cf6, #7c3aed);
  border-radius: 8px;
  color: white;
}

.fp-title {
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
}

.fp-subtitle {
  font-size: 11px;
  color: #94a3b8;
}

.fp-header-actions {
  display: flex;
  gap: 8px;
}

/* ═══ Focus Panel ═══ */
.fp-focus {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.fp-stats-row {
  display: flex;
  align-items: center;
  gap: 0;
  background: #fff;
  border-radius: 10px;
  padding: 12px 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}

.fp-stat-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
  min-width: 0;
}

.fp-stat-num {
  font-size: 20px;
  font-weight: 700;
  color: #1e293b;
  line-height: 1.2;
}

.fp-stat-green { color: #16a34a; }
.fp-stat-muted { color: #94a3b8; }
.fp-stat-blue { color: #2563eb; }
.fp-stat-purple { color: #7c3aed; }

.fp-stat-label {
  font-size: 10px;
  color: #94a3b8;
  letter-spacing: 0.3px;
}

.fp-stat-divider {
  width: 1px;
  height: 32px;
  background: #e2e8f0;
  margin: 0 8px;
  flex-shrink: 0;
}

/* ── Top Factors ── */
.fp-top-factors {
  background: #fff;
  border-radius: 10px;
  padding: 12px 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}

.fp-top-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.fp-top-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.fp-top-hint {
  font-size: 10px;
  color: #94a3b8;
}

.fp-top-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
}

.fp-top-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  background: #f8fafc;
  border: 1px solid #f1f5f9;
  transition: all 0.15s;
}

.fp-top-item:hover {
  border-color: #93c5fd;
  background: #f0f7ff;
}

.fp-top-rank-1 { background: #fef2f2; border-color: #fecaca; }
.fp-top-rank-2 { background: #fff7ed; border-color: #fed7aa; }
.fp-top-rank-3 { background: #fffbeb; border-color: #fde68a; }

.fp-top-rank {
  font-size: 11px;
  font-weight: 800;
  color: #64748b;
  width: 18px;
  text-align: center;
  flex-shrink: 0;
}

.fp-top-rank-1 .fp-top-rank { color: #dc2626; }
.fp-top-rank-2 .fp-top-rank { color: #ea580c; }
.fp-top-rank-3 .fp-top-rank { color: #d97706; }

.fp-top-body {
  flex: 1;
  min-width: 0;
}

.fp-top-name {
  font-size: 11px;
  font-weight: 600;
  color: #334155;
  font-family: 'SF Mono', 'Fira Code', monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 3px;
}

.fp-top-bar-wrap {
  height: 4px;
  background: #e2e8f0;
  border-radius: 2px;
  overflow: hidden;
}

.fp-top-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s;
}

.fp-top-val {
  font-size: 13px;
  font-weight: 700;
  text-align: right;
  flex-shrink: 0;
  line-height: 1.1;
}

.fp-top-red { color: #dc2626; }
.fp-top-blue { color: #2563eb; }

.fp-top-dir {
  display: block;
  font-size: 9px;
  font-weight: 500;
  opacity: 0.6;
}

/* ═══ Toolbar ═══ */
.fp-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.fp-search {
  flex: 1;
  max-width: 300px;
}

.fp-cat-select {
  width: 130px;
}

.fp-status-select {
  width: 110px;
}

.fp-count {
  font-size: 11px;
  color: #94a3b8;
  margin-left: auto;
}

/* ═══ Table ═══ */
.fp-table-wrap {
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
  overflow: hidden;
  flex: 1;
}

.fp-loading {
  padding: 20px;
}

/* Row */
.fp-row {
  border-bottom: 1px solid #f1f5f9;
  transition: background 0.1s;
}

.fp-row:last-child {
  border-bottom: none;
}

.fp-row:hover {
  background: #f8fafc;
}

.fp-row-expanded {
  background: #f8faff;
  border-left: 3px solid #6366f1;
}

.fp-row-disabled {
  opacity: 0.6;
}

.fpr-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  cursor: pointer;
}

.fpr-toggle {
  flex-shrink: 0;
  width: 36px;
  display: flex;
  justify-content: center;
}

.fpr-name-group {
  width: 160px;
  flex-shrink: 0;
  min-width: 0;
}

.fpr-cn-name {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  line-height: 1.3;
}

.fpr-en-name {
  font-size: 10px;
  color: #94a3b8;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.fpr-category {
  width: 90px;
  flex-shrink: 0;
}

.fp-cat-tag {
  font-size: 10px;
  white-space: nowrap;
}

.fpr-desc {
  flex: 1;
  min-width: 0;
  padding: 0 4px;
}

.fpr-desc-text {
  font-size: 12px;
  color: #64748b;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.fpr-actions {
  flex-shrink: 0;
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s;
}

.fp-row:hover .fpr-actions,
.fp-row-expanded .fpr-actions {
  opacity: 1;
}

/* ═══ Detail Panel ═══ */
.fpr-detail {
  padding: 0 16px 14px 68px;
  border-top: 1px dashed #e2e8f0;
  margin-top: 2px;
}

.fpr-detail-grid {
  display: grid;
  gap: 10px;
}

.fpr-detail-section {
  line-height: 1.5;
}

.fpr-ds-label {
  font-size: 10px;
  font-weight: 600;
  color: #94a3b8;
  margin-bottom: 2px;
  letter-spacing: 0.3px;
}

.fpr-ds-value {
  font-size: 13px;
  color: #334155;
}

.fpr-ds-value.formula {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  padding: 6px 10px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
  color: #1e293b;
}

.fpr-ds-value code {
  background: #f1f5f9;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 12px;
  font-family: 'SF Mono', monospace;
}

.fpr-detail-meta {
  margin-top: 8px;
  font-size: 10px;
  color: #94a3b8;
}
</style>
