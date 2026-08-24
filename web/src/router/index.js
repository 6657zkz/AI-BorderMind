import { createRouter, createWebHistory } from 'vue-router'
import ResearchView from '../views/ResearchView.vue'
import SignalsView from '../views/SignalsView.vue'
import EvidenceView from '../views/EvidenceView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'research', component: ResearchView },
    { path: '/signals', name: 'signals', component: SignalsView },
    { path: '/evidence/:chainId?', name: 'evidence', component: EvidenceView },
  ],
})

export default router
