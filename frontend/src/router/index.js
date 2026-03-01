import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import AuthView from '../views/AuthView.vue'
import RunView from '../views/RunView.vue'
import ResultView from '../views/ResultView.vue'
import HistoryView from '../views/HistoryView.vue'
import CatalogView from '../views/CatalogView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView },
    { path: '/auth', component: AuthView },
    { path: '/run', component: RunView },
    { path: '/result/:id', component: ResultView },
    { path: '/history', component: HistoryView },
    { path: '/catalog/:type(methods|datasets|metrics)', component: CatalogView },
    { path: '/catalog', redirect: '/catalog/methods' }
  ]
})

export default router
