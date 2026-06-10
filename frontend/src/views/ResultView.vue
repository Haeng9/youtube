<template>
  <div class="page">
    <h1>✅ 변환 완료!</h1>
    <div class="video-wrap">
      <video :src="videoUrl" controls width="100%" />
    </div>
    <div class="actions">
      <a :href="`http://localhost:8000/api/download/${jobId}`" download>
        <button class="primary">영상 다운로드</button>
      </a>
      <RouterLink to="/"><button class="secondary">새로 만들기</button></RouterLink>
    </div>
  </div>
</template>

<script setup>
import { useRoute } from 'vue-router'

const route = useRoute()
const jobId = route.params.jobId
const videoUrl = `http://localhost:8000/api/download/${jobId}`
</script>

<style scoped>
.page { max-width: 680px; margin: 60px auto; padding: 0 20px; font-family: sans-serif; }
h1 { text-align: center; margin-bottom: 24px; }
.video-wrap { border-radius: 12px; overflow: hidden; margin-bottom: 24px; background: #000; }
.actions { display: flex; gap: 12px; justify-content: center; }
button { padding: 12px 28px; border: none; border-radius: 8px; font-size: 15px; cursor: pointer; color: #fff; }
.primary { background: #42b883; }
.secondary { background: #3498db; }
</style>
