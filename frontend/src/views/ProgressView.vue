<template>
  <div class="page">
    <h1>처리 중...</h1>
    <div class="card">
      <div class="icon">
        <span v-if="job?.status === 'done'">✅</span>
        <span v-else-if="job?.status === 'failed'">❌</span>
        <span v-else>⏳</span>
      </div>
      <p>{{ job?.message || '불러오는 중...' }}</p>
      <div v-if="job?.status === 'processing'" class="bar-wrap">
        <div class="bar" />
      </div>
    </div>
    <RouterLink v-if="job?.status === 'done'" :to="`/result/${jobId}`">
      <button class="primary">결과 보기</button>
    </RouterLink>
    <RouterLink v-if="job?.status === 'failed'" to="/">
      <button class="danger">다시 시작</button>
    </RouterLink>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const jobId = route.params.jobId
const job = ref(null)
let timer = null

async function poll() {
  try {
    const res = await fetch(`http://localhost:8000/api/jobs/${jobId}`)
    if (!res.ok) {
      clearInterval(timer)
      job.value = { status: 'failed', message: `작업을 찾을 수 없습니다. (${res.status})` }
      return
    }
    job.value = await res.json()
    if (job.value.status === 'done' || job.value.status === 'failed') clearInterval(timer)
  } catch (e) { console.error(e) }
}

onMounted(() => { poll(); timer = setInterval(poll, 2000) })
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
.page { max-width: 480px; margin: 60px auto; text-align: center; padding: 0 20px; font-family: sans-serif; }
.card { border: 1px solid #eee; border-radius: 12px; padding: 40px 20px; margin: 32px 0; }
.icon { font-size: 48px; margin-bottom: 16px; }
p { font-size: 17px; color: #555; }
.bar-wrap { height: 8px; background: #eee; border-radius: 4px; margin-top: 20px; overflow: hidden; }
.bar { height: 100%; width: 50%; background: #42b883; animation: slide 1.4s infinite; }
@keyframes slide { 0%{transform:translateX(-100%)} 100%{transform:translateX(300%)} }
button { padding: 12px 32px; border: none; border-radius: 8px; font-size: 15px; cursor: pointer; color: #fff; margin-top: 8px; }
.primary { background: #42b883; }
.danger { background: #e74c3c; }
</style>
