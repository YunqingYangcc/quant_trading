<template>
  <el-container class="app-container">
    <el-aside width="200px" class="app-sidebar">
      <div class="sidebar-header">
        <div class="logo">📈 Quant Trading</div>
        <div class="logo-sub">@杨布拉德</div>
      </div>

      <div class="nav-group">
        <div class="group-label">DATA</div>
        <el-menu :default-active="activeMenu" router>
          <el-menu-item index="/">
            <el-icon><Monitor /></el-icon>
            <span>Dashboard</span>
          </el-menu-item>
          <el-menu-item index="/pipeline">
            <el-icon><Connection /></el-icon>
            <span>Data Pipeline</span>
          </el-menu-item>
          <el-menu-item index="/alpha">
            <el-icon><DataAnalysis /></el-icon>
            <span>Alpha Research</span>
          </el-menu-item>
        </el-menu>
      </div>

      <div class="nav-group">
        <div class="group-label">STRATEGY</div>
        <el-menu :default-active="activeMenu" router>
          <el-menu-item index="/model-factory">
            <el-icon><Cpu /></el-icon>
            <span>Model Factory</span>
          </el-menu-item>
          <el-menu-item :index="'/track/' + (currentTrack || 'semiconductor')">
            <el-icon><TrendCharts /></el-icon>
            <span>Alpha Workstation</span>
          </el-menu-item>
          <el-menu-item index="/backtest">
            <el-icon><Coin /></el-icon>
            <span>Backtest Lab</span>
          </el-menu-item>
          <el-menu-item index="/portfolio">
            <el-icon><PieChart /></el-icon>
            <span>Portfolio</span>
          </el-menu-item>
        </el-menu>
      </div>

      <div class="sidebar-footer">
        <div class="dot-row">
          <span class="d d-on" />
          <span class="d d-on" />
          <span class="d d-on" />
          <span class="d" />
        </div>
      </div>
    </el-aside>

    <el-container class="main-container">
      <el-header class="app-header" height="48px">
        <div class="header-title">{{ pageTitle }}</div>
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
import { Monitor, Connection, DataAnalysis, Cpu, TrendCharts, Coin, PieChart } from '@element-plus/icons-vue'

const route = useRoute()
const activeMenu = computed(() => {
  if (route.path.startsWith('/track/')) return route.path
  return route.path
})
const currentTrack = computed(() => (route.params.name as string) || 'semiconductor')

const pageTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/pipeline': 'Data Pipeline',
  '/alpha': 'Alpha Research',
  '/model-factory': 'Model Factory',
  '/backtest': 'Backtest Lab',
  '/portfolio': 'Portfolio',
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
}

/* ── SIDEBAR ── */
.app-sidebar {
  width: 200px;
  background: #0c0f15;
  display: flex;
  flex-direction: column;
  user-select: none;
}

.sidebar-header {
  padding: 18px 16px 12px;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}

.logo {
  color: #e8edf5;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.3px;
}

.logo-sub {
  font-size: 10px;
  color: rgba(255,255,255,0.15);
  margin-top: 1px;
}

/* ── NAV GROUPS ── */
.nav-group {
  padding: 0;
}

.group-label {
  font-size: 9px;
  font-weight: 700;
  color: rgba(255,255,255,0.2);
  padding: 16px 16px 6px;
  letter-spacing: 1.2px;
}

.app-sidebar :deep(.el-menu) {
  border-right: none;
  background: transparent;
  padding: 0;
}

.app-sidebar :deep(.el-menu-item) {
  height: 36px;
  line-height: 36px;
  margin: 0;
  padding: 0 16px;
  border-radius: 0;
  color: rgba(255,255,255,0.45);
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.12s;
}

.app-sidebar :deep(.el-menu-item:hover) {
  background: rgba(255,255,255,0.04);
  color: rgba(255,255,255,0.75);
}

.app-sidebar :deep(.el-menu-item.is-active) {
  background: rgba(59,130,246,0.15);
  color: #60a5fa;
}

.app-sidebar :deep(.el-menu-item .el-icon) {
  font-size: 15px;
  margin: 0;
  width: 18px;
  text-align: center;
}

/* ── FOOTER DOTS ── */
.sidebar-footer {
  margin-top: auto;
  padding: 14px 16px;
  border-top: 1px solid rgba(255,255,255,0.04);
}

.dot-row {
  display: flex;
  gap: 6px;
}

.d {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(255,255,255,0.08);
}

.d-on {
  background: #3b82f6;
}

/* ── MAIN ── */
.main-container {
  display: flex;
  flex-direction: column;
}

.app-header {
  background: #fff;
  border-bottom: 1px solid #e8ecf0;
  display: flex;
  align-items: center;
  padding: 0 20px;
  height: 48px !important;
}

.header-title {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}

.app-main {
  background: #f5f6f8;
  padding: 0;
  overflow: auto;
  height: calc(100vh - 48px);
}
</style>
