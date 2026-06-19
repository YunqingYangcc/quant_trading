import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'tracks',
      meta: { title: 'Track Dashboard' },
      component: () => import('@/views/tracks/TrackDashboard.vue'),
    },
  ],
})

export default router
