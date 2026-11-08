import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/Home.vue'

const router = createRouter({
  // 与 vite base 保持一致，使用根路径 history
  history: createWebHistory('/'),
  routes: [{ path: '/', name: 'home', component: Home }],
  scrollBehavior() {
    return { top: 0 }
  },
})

export default router
