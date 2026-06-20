<template>
  <SidebarLayout />
</template>

<script setup lang="ts">
import SidebarLayout from '@/layouts/SidebarLayout.vue'
</script>

<style>
/* 全局字号调大 */
:root {
  --el-font-size-base: 15px;
  --el-font-size-small: 13px;
  --el-font-size-extra-small: 12px;
  --el-font-size-medium: 16px;
  --el-font-size-large: 18px;
}

html {
  font-size: 15px;
}

body {
  font-size: 15px;
  -webkit-font-smoothing: antialiased;
}

/* Element Plus 表格/标签/输入框内文字 */
.el-table .cell,
.el-tag,
.el-button,
.el-input__inner,
.el-select,
.el-radio__label,
.el-checkbox__label {
  font-size: inherit;
}

/* 主内容区统一继承全局字号 */
.app-main,
.home-page,
.portfolio-page,
.backtest-page,
.alpha-page,
.model-factory-page,
.data-view,
.track-dashboard {
  font-size: 15px;
}
</style>
