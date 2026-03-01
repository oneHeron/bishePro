import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import AuthView from '../views/AuthView.vue'
import RunView from '../views/RunView.vue'
import ResultView from '../views/ResultView.vue'
import HistoryView from '../views/HistoryView.vue'
import CatalogView from '../views/CatalogView.vue'
import { getToken } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView },
    { path: '/auth', component: AuthView },
    { path: '/run', component: RunView },
    { path: '/result/:id', component: ResultView, meta: { requiresAuth: true } },
    { path: '/history', component: HistoryView },
    { path: '/catalog/:type(methods|datasets|metrics)', component: CatalogView },
    { path: '/catalog', redirect: '/catalog/methods' }
  ]
})

router.beforeEach((to) => {
  if (!to.meta?.requiresAuth) return true
  const token = getToken()
  if (token) return true
  return { path: '/auth', query: { redirect: to.fullPath } }
})

export default router
