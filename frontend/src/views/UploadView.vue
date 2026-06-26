<template>
  <div class="page">
    <h1>🎵 AI 음악 스타일 변환</h1>

    <div
      class="drop-zone"
      :class="{ active: dragging }"
      @dragover.prevent="dragging = true"
      @dragleave="dragging = false"
      @drop.prevent="onDrop"
      @click="fileInput.click()"
    >
      <input ref="fileInput" type="file" accept=".mp3" hidden @change="onFileSelect" />
      <p v-if="!selectedFile">MP3 파일을 드래그하거나 클릭해서 선택</p>
      <p v-else>✅ {{ selectedFile.name }}</p>
    </div>

    <div class="field">
      <label>변환 스타일</label>
      <select v-model="style">
        <option value="jpop">J-POP</option>
        <option value="kpop">K-POP</option>
        <option value="lofi">Lo-Fi</option>
        <option value="jazz">Jazz</option>
      </select>
    </div>

    <button :disabled="!selectedFile || loading" @click="submit">
      {{ loading ? '업로드 중...' : '변환 시작' }}
    </button>

    <p class="link"><RouterLink to="/experiments">🧪 실험(A/B) 결과 비교</RouterLink></p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const fileInput = ref(null)
const selectedFile = ref(null)
const style = ref('jpop')
const loading = ref(false)
const dragging = ref(false)

function onFileSelect(e) {
  selectedFile.value = e.target.files[0] || null
}

function onDrop(e) {
  dragging.value = false
  const file = e.dataTransfer.files[0]
  if (file?.name.endsWith('.mp3')) selectedFile.value = file
}

async function submit() {
  if (!selectedFile.value) return
  loading.value = true
  const form = new FormData()
  form.append('file', selectedFile.value)
  form.append('style', style.value)
  try {
    const res = await fetch('http://localhost:8000/api/upload', { method: 'POST', body: form })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `서버 오류 (${res.status})`)
    }
    const { job_id } = await res.json()
    router.push(`/progress/${job_id}`)
  } catch (e) {
    alert(`업로드 실패 — ${e.message || '백엔드 서버가 실행 중인지 확인하세요.'}`)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page { max-width: 560px; margin: 60px auto; padding: 0 20px; font-family: sans-serif; }
h1 { text-align: center; margin-bottom: 32px; }
.drop-zone {
  border: 2px dashed #aaa; border-radius: 12px;
  padding: 60px 20px; text-align: center; cursor: pointer; transition: border-color .2s;
}
.drop-zone.active, .drop-zone:hover { border-color: #42b883; }
.field { margin: 24px 0; }
.field label { display: block; margin-bottom: 8px; font-weight: 600; }
.field select { width: 100%; padding: 10px; border-radius: 8px; border: 1px solid #ddd; font-size: 15px; }
button {
  width: 100%; padding: 14px; background: #42b883; color: #fff;
  border: none; border-radius: 8px; font-size: 16px; cursor: pointer;
}
button:disabled { background: #aaa; cursor: not-allowed; }
.link { text-align: center; margin-top: 20px; }
.link a { color: #3498db; text-decoration: none; }
</style>
