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
      path: '/portfolio',
      name: 'portfolio',
      meta: { title: 'Portfolio Monitor' },
      component: () => import('@/views/tracks/PortfolioPage.vue'),
    },
  ],
})

export default router
