import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      meta: { title: 'Dashboard' },
      component: () => import('@/views/tracks/HomePage.vue'),
    },
    {
      path: '/pipeline',
      name: 'pipeline',
      meta: { title: 'Data Pipeline' },
      component: () => import('@/views/tracks/DataView.vue'),
    },
    {
      path: '/features',
      name: 'features',
      meta: { title: 'Feature Config' },
      component: () => import('@/views/tracks/FeatureConfigPage.vue'),
    },
    {
      path: '/factors',
      name: 'factors',
      meta: { title: 'Factor Config' },
      component: () => import('@/views/tracks/FactorConfigPage.vue'),
    },
    {
      path: '/alpha',
      name: 'alpha',
      meta: { title: 'Alpha Research' },
      component: () => import('@/views/tracks/AlphaResearchPage.vue'),
    },
    {
      path: '/model-factory',
      name: 'model-factory',
      meta: { title: 'Model Factory' },
      component: () => import('@/views/tracks/ModelFactoryPage.vue'),
    },
    {
      path: '/track/:name',
      name: 'track-detail',
      meta: { title: 'Alpha Workstation' },
      component: () => import('@/views/tracks/TrackDashboard.vue'),
    },
    {
      path: '/backtest',
      name: 'backtest',
      meta: { title: 'Backtest Lab' },
      component: () => import('@/views/tracks/BacktestPage.vue'),
    },
    {
      path: '/runner',
      name: 'runner',
      meta: { title: '量化流水线' },
      component: () => import('@/views/tracks/PipelineRunnerPage.vue'),
    },
    {
      path: '/unsupervised',
      name: 'unsupervised',
      meta: { title: '智能分析' },
      component: () => import('@/views/tracks/UnsupervisedPage.vue'),
    },
    {
      path: '/strategy/:key',
      name: 'strategy-detail',
      meta: { title: '策略详情' },
      component: () => import('@/views/tracks/StrategyDetailPage.vue'),
    },
    {
      path: '/daily-report',
      name: 'daily-report',
      meta: { title: '每日日报' },
      component: () => import('@/views/tracks/DailyReportPage.vue'),
    },
    {
      path: '/sector-leaders',
      name: 'sector-leaders',
      meta: { title: '业务逻辑分析' },
      component: () => import('@/views/tracks/SectorLeadersPage.vue'),
    },
  ],
})

export default router
