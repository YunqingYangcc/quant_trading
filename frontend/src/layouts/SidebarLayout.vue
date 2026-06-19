<template>
  <el-container class="app-container">
    <!-- 侧边栏 -->
    <el-aside :width="isCollapse ? '56px' : '200px'" class="app-sidebar">
      <div class="sidebar-header" @click="isCollapse = !isCollapse">
        <div v-if="!isCollapse" class="logo-text">📈 Quant Trading</div>
        <div v-else class="logo-text logo-collapsed">Q</div>
      </div>

      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        :collapse-transition="false"
        router
      >
        <el-menu-item index="/">
          <el-icon><Monitor /></el-icon>
          <template #title>Dashboard</template>
        </el-menu-item>
        <el-menu-item index="/data" disabled>
          <el-icon><DataAnalysis /></el-icon>
          <template #title>Data</template>
        </el-menu-item>
        <el-menu-item index="/train" disabled>
          <el-icon><TrendCharts /></el-icon>
          <template #title>Training</template>
        </el-menu-item>
        <el-menu-item index="/backtest" disabled>
          <el-icon><Coin /></el-icon>
          <template #title>Backtest</template>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <div class="watermark">@杨布拉德</div>
        <el-button
          :icon="isCollapse ? 'Expand' : 'Fold'"
          text
          bg
          size="small"
          @click="isCollapse = !isCollapse"
        >
          <template #default v-if="!isCollapse">收起侧栏</template>
        </el-button>
      </div>
    </el-aside>

    <!-- 主内容 -->
    <el-container class="main-container">
      <el-header class="app-header" height="52px">
        <div class="header-left">
          <el-icon @click="isCollapse = !isCollapse" class="collapse-btn"><Fold /></el-icon>
          <span class="header-title">Quant Trading Terminal</span>
        </div>
        <div class="header-right">
          <span class="header-status">Phase A ✅</span>
        </div>
      </el-header>
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { Monitor, DataAnalysis, TrendCharts, Coin, Fold } from '@element-plus/icons-vue'

const route = useRoute()
const isCollapse = ref(false)
const activeMenu = computed(() => route.path)
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
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
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
  cursor: pointer;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  transition: all 0.3s;
}

.sidebar-header:hover {
  background: rgba(255, 255, 255, 0.03);
}

.logo-text {
  color: #f1f5f9;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.5px;
  white-space: nowrap;
  overflow: hidden;
  transition: opacity 0.3s;
}

.logo-collapsed {
  font-size: 22px;
  letter-spacing: 0;
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

/* 折叠状态菜单居中 */
.app-sidebar :deep(.el-menu--collapse .el-menu-item) {
  padding: 0 !important;
  text-align: center;
}

.app-sidebar :deep(.el-menu--collapse .el-menu-item .el-icon) {
  margin-right: 0;
}

/* ── 底部按钮 + 水印 ── */
.sidebar-footer {
  margin-top: auto;
  padding: 12px 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.watermark {
  text-align: center;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.2);
  margin-bottom: 8px;
  font-weight: 500;
  letter-spacing: 0.5px;
  transition: opacity 0.3s;
}

.sidebar-footer :deep(.el-button) {
  width: 100%;
  color: rgba(255, 255, 255, 0.45);
  border-radius: 6px;
  transition: all 0.25s;
}

.sidebar-footer :deep(.el-button:hover) {
  color: rgba(255, 255, 255, 0.8);
  background: rgba(255, 255, 255, 0.06);
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

.collapse-btn {
  font-size: 18px;
  cursor: pointer;
  color: #94a3b8;
  transition: all 0.2s;
  border-radius: 4px;
  padding: 4px;
}

.collapse-btn:hover {
  color: #3b82f6;
  background: #f1f5f9;
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
