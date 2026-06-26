import { createRouter, createWebHistory } from 'vue-router'
import UploadView from '../views/UploadView.vue'
import ProgressView from '../views/ProgressView.vue'
import ResultView from '../views/ResultView.vue'
import ExperimentsView from '../views/ExperimentsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: UploadView },
    { path: '/progress/:jobId', component: ProgressView },
    { path: '/result/:jobId', component: ResultView },
    { path: '/experiments', component: ExperimentsView },
  ],
})

export default router
