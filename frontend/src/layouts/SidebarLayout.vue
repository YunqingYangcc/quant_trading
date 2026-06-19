<template>
  <el-container class="app-container">
    <!-- 侧边栏 -->
    <el-aside width="200px" class="app-sidebar">
      <div class="sidebar-header">
        <div class="logo-text">📈 Quant Trading @杨布拉德</div>
      </div>

      <el-menu
        :default-active="activeMenu"
        router
      >
        <el-menu-item index="/">
          <el-icon><Monitor /></el-icon>
          <template #title>
            <span>🏠 总览</span>
            <span class="menu-phase">Phase H</span>
          </template>
        </el-menu-item>
        <el-menu-item index="/data">
          <el-icon><DataAnalysis /></el-icon>
          <template #title>
            <span>📖 因子手册</span>
            <span class="menu-phase">A-D</span>
          </template>
        </el-menu-item>
        <el-menu-item index="/backtest">
          <el-icon><Coin /></el-icon>
          <template #title>
            <span>📊 回测</span>
            <span class="menu-phase">Phase G</span>
          </template>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <div class="watermark">@杨布拉德</div>
      </div>
    </el-aside>

    <!-- 主内容 -->
    <el-container class="main-container">
      <el-header class="app-header" height="52px">
        <div class="header-left">
          <span class="header-title">Quant Trading Terminal @杨布拉德</span>
        </div>
        <div class="header-right">
          <span class="header-status" :style="{ color: currentPhaseColor, background: currentPhaseBg }">{{ currentPhase }}</span>
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
import { Monitor, DataAnalysis, Coin } from '@element-plus/icons-vue'

const route = useRoute()
const activeMenu = computed(() => route.path)

const currentPhase = computed(() => {
  const phases: Record<string, { label: string; color: string; bg: string }> = {
    '/': { label: '🏠 赛道总览', color: '#3b82f6', bg: '#eff6ff' },
    '/data': { label: '📖 因子手册', color: '#22c55e', bg: '#f0fdf4' },
    '/backtest': { label: '📊 回测', color: '#8b5cf6', bg: '#f5f3ff' },
  }
  return phases[route.path]?.label || '🎯 Track: ' + (route.path.split('/track/')[1] || '')
})

const currentPhaseColor = computed(() => {
  const phases: Record<string, string> = {
    '/': '#3b82f6', '/data': '#22c55e', '/backtest': '#8b5cf6',
  }
  return phases[route.path] || '#8b5cf6'
})

const currentPhaseBg = computed(() => {
  const phases: Record<string, string> = {
    '/': '#eff6ff', '/data': '#f0fdf4', '/backtest': '#f5f3ff',
  }
  return phases[route.path] || '#f5f3ff'
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
  position: relative;
  z-index: 10;
}

.sidebar-header {
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.logo-text {
  color: #f1f5f9;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.5px;
  white-space: nowrap;
  overflow: hidden;
}

/* ── 菜单覆盙 ── */
.app-sidebar :deep(.el-menu) {
  border-right: none;
  flex: none;
  background: transparent;
  padding: 8px;
}

.app-sidebar :deep(.el-menu-item) {
  height: 44px;
  line-height: 44px;
  border-radius: 8px;
  margin-bottom: 4px;
  color: rgba(255, 255, 255, 0.55);
  font-size: 14px;
  transition: all 0.25s ease;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.app-sidebar :deep(.el-menu-item .menu-phase) {
  font-size: 9px;
  color: rgba(255, 255, 255, 0.25);
  background: rgba(255, 255, 255, 0.06);
  padding: 1px 6px;
  border-radius: 6px;
  margin-left: 6px;
  letter-spacing: 0.3px;
  flex-shrink: 0;
}

.app-sidebar :deep(.el-menu-item.is-active .menu-phase) {
  color: rgba(255, 255, 255, 0.7);
  background: rgba(255, 255, 255, 0.12);
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

.app-sidebar :deep(.el-menu-item.is-disabled) {
  color: rgba(255, 255, 255, 0.2);
  cursor: not-allowed;
}

.app-sidebar :deep(.el-menu-item .el-icon) {
  font-size: 18px;
  margin-right: 8px;
}

/* ── 底部水印 ── */
.sidebar-footer {
  margin-top: auto;
  padding: 12px 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.watermark {
  text-align: center;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.2);
  font-weight: 500;
  letter-spacing: 0.5px;
}

/* ── 主内容区 ── */
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
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}

.header-status {
  font-size: 12px;
  color: #22c55e;
  background: #f0fdf4;
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
