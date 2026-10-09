import { createRouter, createWebHistory } from 'vue-router'
import IncidentsPage from './pages/IncidentsPage.vue'
import IncidentDetailPage from './pages/IncidentDetailPage.vue'
import HandoverPage from './pages/HandoverPage.vue'
export const routes = [
  { path: '/', redirect: '/incidents' },
  { path: '/incidents', component: IncidentsPage },
  { path: '/incidents/:id', component: IncidentDetailPage, props: true },
  { path: '/handovers/:id?', component: HandoverPage, props: true },
]
export const router = createRouter({ history: createWebHistory(), routes })
