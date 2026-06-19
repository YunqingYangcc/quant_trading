<template>
  <el-container class="app-container">
    <!-- 侧边栏 -->
    <el-aside width="200px" class="app-sidebar">
      <div class="sidebar-header">
        <div class="logo-text">📈 Quant Trading</div>
        <div class="logo-sub">@杨布拉德</div>
      </div>

      <!-- 步骤分隔 -->
      <div class="step-section">
        <div class="step-label">数据层</div>
        <el-menu :default-active="activeMenu" router>
          <el-menu-item index="/">
            <el-icon><Monitor /></el-icon>
            <template #title>
              <span>① 总览</span>
              <span class="menu-phase">起步</span>
            </template>
          </el-menu-item>
          <el-menu-item index="/data">
            <el-icon><DataAnalysis /></el-icon>
            <template #title>
              <span>② 因子</span>
              <span class="menu-phase">研究</span>
            </template>
          </el-menu-item>
        </el-menu>
      </div>

      <div class="step-section">
        <div class="step-label">策略层</div>
        <el-menu :default-active="activeMenu" router>
          <el-menu-item :index="'/track/' + (currentTrack || 'semiconductor')">
            <el-icon><TrendCharts /></el-icon>
            <template #title>
              <span>③ 赛道</span>
              <span class="menu-phase">选股</span>
            </template>
          </el-menu-item>
          <el-menu-item index="/backtest">
            <el-icon><Coin /></el-icon>
            <template #title>
              <span>④ 回测</span>
              <span class="menu-phase">验证</span>
            </template>
          </el-menu-item>
        </el-menu>
      </div>

      <div class="sidebar-footer">
        <div class="pipeline-dots">
          <span class="dot done" title="数据完成">●</span>
          <span class="dot done" title="因子完成">●</span>
          <span class="dot active" title="赛道进行中">●</span>
          <span class="dot" title="回测就绪">●</span>
        </div>
      </div>
    </el-aside>

    <!-- 主内容 -->
    <el-container class="main-container">
      <el-header class="app-header" height="52px">
        <div class="header-left">
          <span class="header-title">{{ pageTitle }}</span>
        </div>
        <div class="header-right">
          <span class="header-status" :style="{ color: currentPhaseColor, background: currentPhaseBg }">
            {{ stepLabel }}
          </span>
        </div>
      </el-header>
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Monitor, DataAnalysis, TrendCharts, Coin } from '@element-plus/icons-vue'

const route = useRoute()
const activeMenu = computed(() => {
  const path = route.path
  // /track/xxx → /track/xxx 保持高亮
  if (path.startsWith('/track/')) return path
  return path
})

const currentTrack = computed(() => {
  return (route.params.name as string) || 'semiconductor'
})

// ── 页面标题映射 ──
const pageTitles: Record<string, string> = {
  '/': '① 总览 · 赛道量化终端',
  '/data': '② 因子 · 研究与分析',
  '/backtest': '④ 回测 · 绩效验证',
}
const pageTitle = computed(() => {
  if (route.path.startsWith('/track/')) return '③ 赛道 · ' + (route.params.name as string || '分析')
  return pageTitles[route.path] || 'Quant Trading'
})

// ── 步骤标签映射 ──
const steps: Record<string, { label: string; color: string; bg: string }> = {
  '/': { label: 'Step 1/4 · 总览', color: '#3b82f6', bg: '#eff6ff' },
  '/data': { label: 'Step 2/4 · 因子研究', color: '#22c55e', bg: '#f0fdf4' },
  '/backtest': { label: 'Step 4/4 · 回测验证', color: '#8b5cf6', bg: '#f5f3ff' },
}
const stepLabel = computed(() => {
  if (route.path.startsWith('/track/')) return 'Step 3/4 · 赛道选股'
  return steps[route.path]?.label || 'Quant Trading'
})
const currentPhaseColor = computed(() => {
  if (route.path.startsWith('/track/')) return '#f59e0b'
  return steps[route.path]?.color || '#3b82f6'
})
const currentPhaseBg = computed(() => {
  if (route.path.startsWith('/track/')) return '#fefce8'
  return steps[route.path]?.bg || '#eff6ff'
})
</script>

<style scoped>
.app-container {
  height: 100vh;
  overflow: hidden;
}

/* ── 侧边栏 ── */
.app-sidebar {
  background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 1px 0 8px rgba(0, 0, 0, 0.12);
  z-index: 10;
}

.sidebar-header {
  padding: 14px 16px 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  text-align: center;
}

.logo-text {
  color: #f1f5f9;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.logo-sub {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.25);
  margin-top: 2px;
}

/* ── 步骤分组 ── */
.step-section {
  padding: 4px 0;
}

.step-label {
  font-size: 10px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.3);
  padding: 6px 16px 2px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

/* ── 菜单 ── */
.app-sidebar :deep(.el-menu) {
  border-right: none;
  background: transparent;
  padding: 2px 8px;
}

.app-sidebar :deep(.el-menu-item) {
  height: 40px;
  line-height: 40px;
  border-radius: 6px;
  margin-bottom: 2px;
  color: rgba(255, 255, 255, 0.55);
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.app-sidebar :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.9);
}

.app-sidebar :deep(.el-menu-item.is-active) {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: #fff;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.35);
}

.app-sidebar :deep(.el-menu-item .menu-phase) {
  font-size: 9px;
  color: rgba(255, 255, 255, 0.25);
  background: rgba(255, 255, 255, 0.06);
  padding: 1px 6px;
  border-radius: 6px;
  letter-spacing: 0.3px;
  flex-shrink: 0;
}

.app-sidebar :deep(.el-menu-item.is-active .menu-phase) {
  color: rgba(255, 255, 255, 0.7);
  background: rgba(255, 255, 255, 0.12);
}

.app-sidebar :deep(.el-menu-item .el-icon) {
  font-size: 16px;
  margin-right: 6px;
}

/* ── 底部进度点 ── */
.sidebar-footer {
  margin-top: auto;
  padding: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.pipeline-dots {
  display: flex;
  justify-content: center;
  gap: 8px;
}

.dot {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.15);
  transition: all 0.3s;
}

.dot.done {
  color: #67c23a;
}

.dot.active {
  color: #60a5fa;
  font-size: 12px;
}

/* ── 主内容 ── */
.main-container {
  display: flex;
  flex-direction: column;
}

.app-header {
  background: #fff;
  border-bottom: 1px solid #e8ecf0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-title {
  font-size: 14px;
  font-weight: 600;
  color: #475569;
}

.header-status {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 12px;
  font-weight: 500;
}

.app-main {
  background: #f8fafc;
  padding: 0;
  overflow: auto;
  height: calc(100vh - 52px);
}
</style>
