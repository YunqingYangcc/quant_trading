import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      meta: { title: 'Quant Terminal' },
      component: () => import('@/views/tracks/HomePage.vue'),
    },
    {
      path: '/track/:name',
      name: 'track-detail',
      meta: { title: 'Track Detail' },
      component: () => import('@/views/tracks/TrackDashboard.vue'),
    },
    {
      path: '/data',
      name: 'data',
      meta: { title: '因子手册' },
      component: () => import('@/views/tracks/DataView.vue'),
    },
    {
      path: '/backtest',
      name: 'backtest',
      meta: { title: '回测绩效' },
      component: () => import('@/views/tracks/BacktestPage.vue'),
    },
  ],
})

export default router
