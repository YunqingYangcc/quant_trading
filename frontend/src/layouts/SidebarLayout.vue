<template>
  <el-container class="app-container">
    <el-aside width="220px" class="app-sidebar">
      <div class="sidebar-header">
        <div class="logo-brand">
          <div class="logo-icon">◈</div>
          <div class="logo-texts">
            <div class="logo-title">Quant Trading</div>
            <div class="logo-meta">@杨布拉德 · v1.0</div>
          </div>
        </div>
      </div>

      <div class="sidebar-nav">
        <div class="nav-section">
          <div class="section-label">DATA</div>
          <div class="section-divider" />
          <el-menu :default-active="activeMenu" router>
            <el-menu-item index="/">
              <el-icon><Monitor /></el-icon>
              <span>Dashboard</span>
            </el-menu-item>
            <el-menu-item index="/features">
              <el-icon><List /></el-icon>
              <span>Feature Config</span>
            </el-menu-item>
            <el-menu-item index="/factors">
              <el-icon><Coin /></el-icon>
              <span>Factor Config</span>
            </el-menu-item>
            <el-menu-item index="/model-factory">
              <el-icon><Cpu /></el-icon>
              <span>Model Factory</span>
            </el-menu-item>
          </el-menu>
        </div>

        <div class="nav-section">
          <div class="section-label">TRACKS</div>
          <div class="section-divider" />
          <el-menu :default-active="activeMenu" router>
            <el-menu-item index="/track/semiconductor">
              <el-icon><TrendCharts /></el-icon>
              <span>半导体</span>
            </el-menu-item>
            <el-menu-item index="/track/ai">
              <el-icon><TrendCharts /></el-icon>
              <span>AI算力</span>
            </el-menu-item>
            <el-menu-item index="/track/robot">
              <el-icon><TrendCharts /></el-icon>
              <span>机器人</span>
            </el-menu-item>
            <el-menu-item index="/track/storage">
              <el-icon><TrendCharts /></el-icon>
              <span>存储</span>
            </el-menu-item>
            <el-menu-item index="/track/material">
              <el-icon><TrendCharts /></el-icon>
              <span>上游材料</span>
            </el-menu-item>
            <el-menu-item index="/track/ai-power">
              <el-icon><TrendCharts /></el-icon>
              <span>算力能源</span>
            </el-menu-item>
          </el-menu>
        </div>

        <div class="nav-section">
          <div class="section-label">TOOLS</div>
          <div class="section-divider" />
          <el-menu :default-active="activeMenu" router>
            <el-menu-item index="/runner">
              <el-icon><Operation /></el-icon>
              <span>量化流水线</span>
            </el-menu-item>
            <el-menu-item index="/backtest">
              <el-icon><Coin /></el-icon>
              <span>策略实验室</span>
            </el-menu-item>
            <el-menu-item index="/unsupervised">
              <el-icon><DataAnalysis /></el-icon>
              <span>智能分析</span>
            </el-menu-item>
            <el-menu-item index="/daily-report">
              <el-icon><Document /></el-icon>
              <span>每日日报</span>
            </el-menu-item>
            <el-menu-item index="/sector-leaders">
              <el-icon><Star /></el-icon>
              <span>业务逻辑分析</span>
            </el-menu-item>
          </el-menu>
        </div>
      </div>

      <div class="sidebar-footer">
        <div class="status-row">
          <span class="status-dot" />
          <span class="status-text">System Online</span>
        </div>
      </div>
    </el-aside>

    <el-container class="main-container">
      <el-header class="app-header" height="48px">
        <div class="header-title">{{ pageTitle }}</div>
        <div class="header-actions">
          <span class="header-ver">v1.0.0</span>
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
import { Monitor, List, Coin, Cpu, TrendCharts, Operation, DataAnalysis, Document, Star } from '@element-plus/icons-vue'

const route = useRoute()
const activeMenu = computed(() => {
  if (route.path.startsWith('/track/')) return route.path
  return route.path
})

const pageTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/features': 'Feature Config',
  '/factors': 'Factor Config',
  '/alpha': 'Alpha Research',
  '/model-factory': 'Model Factory',
  '/backtest': '策略实验室',
  '/runner': '量化流水线',
  '/unsupervised': '智能分析',
  '/daily-report': '每日日报',
  '/sector-leaders': '业务逻辑分析',
}
const pageTitle = computed(() => {
  if (route.path.startsWith('/track/')) return 'Alpha Workstation · ' + (route.params.name as string || '')
  return pageTitles[route.path] || 'Quant Trading'
})
</script>

<style scoped>
.app-container {
  height: 100vh;
  overflow: hidden;
  display: flex;
}

/* ═══════════════════════ SIDEBAR ═══════════════════════ */
.app-sidebar {
  width: 220px;
  min-width: 220px;
  background: linear-gradient(180deg, #141a29 0%, #1a2235 100%);
  display: flex;
  flex-direction: column;
  user-select: none;
  position: relative;
  box-shadow:
    inset -1px 0 0 rgba(255, 255, 255, 0.03),
    1px 0 0 rgba(0, 0, 0, 0.35);
  z-index: 10;
}

/* ── Header / Brand ── */
.sidebar-header {
  padding: 20px 18px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.logo-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  border-radius: 8px;
  color: #fff;
  font-size: 16px;
  font-weight: 300;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.25);
  flex-shrink: 0;
}

.logo-texts {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.logo-title {
  color: #e8edf5;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.2px;
  line-height: 1.3;
}

.logo-meta {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.35);
  letter-spacing: 0.3px;
  line-height: 1.3;
  margin-top: 1px;
}

/* ── Navigation Sections ── */
.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.sidebar-nav::-webkit-scrollbar {
  width: 2px;
}

.sidebar-nav::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.06);
  border-radius: 1px;
}

.nav-section {
  margin-top: 2px;
}

.section-label {
  font-size: 9px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.3);
  padding: 14px 20px 6px;
  letter-spacing: 1.5px;
}

.section-divider {
  height: 1px;
  margin: 0 20px 4px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.06), transparent);
}

/* ── El-menu Override ── */
.app-sidebar :deep(.el-menu) {
  border-right: none;
  background: transparent;
}

.app-sidebar :deep(.el-menu-item) {
  height: 36px;
  line-height: 36px;
  margin: 1px 8px;
  padding: 0 12px;
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.55);
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
}

/* Hover */
.app-sidebar :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.85);
}

/* Active state */
.app-sidebar :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, rgba(59, 130, 246, 0.12), rgba(59, 130, 246, 0.03));
  color: #60a5fa;
}

/* Active left accent bar */
.app-sidebar :deep(.el-menu-item.is-active)::before {
  content: '';
  position: absolute;
  left: -8px;
  top: 6px;
  bottom: 6px;
  width: 2px;
  background: #3b82f6;
  border-radius: 0 2px 2px 0;
  box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
  transition: all 0.2s ease;
}

/* Active glow effect */
.app-sidebar :deep(.el-menu-item.is-active)::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 6px;
  box-shadow: inset 0 0 12px rgba(59, 130, 246, 0.06);
  pointer-events: none;
}

/* Icon styling */
.app-sidebar :deep(.el-menu-item .el-icon) {
  font-size: 15px;
  margin: 0;
  width: 18px;
  text-align: center;
  transition: color 0.2s ease;
}

.app-sidebar :deep(.el-menu-item:hover .el-icon) {
  color: rgba(255, 255, 255, 0.7);
}

.app-sidebar :deep(.el-menu-item.is-active .el-icon) {
  color: #60a5fa;
}

/* ── Footer ── */
.sidebar-footer {
  margin-top: auto;
  padding: 12px 18px 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
}

.status-row {
  display: flex;
  align-items: center;
  gap: 7px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.3);
  animation: pulse 2.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.status-text {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.3);
  letter-spacing: 0.5px;
}

/* ═══════════════════════ MAIN ═══════════════════════ */
.main-container {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.app-header {
  background: #fff;
  border-bottom: 1px solid #e8ecf0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 48px !important;
  flex-shrink: 0;
}

.header-title {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-ver {
  font-size: 10px;
  color: #c0c4cc;
  font-family: 'SF Mono', monospace;
}

.app-main {
  background: #f5f6f8;
  padding: 0;
  overflow: auto;
  flex: 1;
  height: calc(100vh - 48px);
}
</style>
