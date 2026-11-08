import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import ReadView from '@/views/ReadView.vue'
import HistoryView from '@/views/HistoryView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/read/:id?', name: 'read', component: ReadView },
    { path: '/history', name: 'history', component: HistoryView },
  ]
})

export default router
