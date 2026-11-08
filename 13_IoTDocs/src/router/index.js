import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import CategoryView from '../views/CategoryView.vue'
import ArticleView from '../views/ArticleView.vue'

const routes = [
  { path: '/', name: 'home', component: Home },
  { path: '/c/:cat', name: 'category', component: CategoryView, props: true },
  { path: '/a/:slug', name: 'article', component: ArticleView, props: true },
]

export default createRouter({
  history: createWebHistory('/iot/'),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})
