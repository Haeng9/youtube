<template>
  <div class="page">
    <h1>🧪 실험(A/B) 결과 비교</h1>
    <p class="hint">같은 입력을 서로 다른 provider로 돌린 결과입니다. (예: music 단계 Suno vs ACE-Step)</p>

    <p v-if="loading">불러오는 중...</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <p v-else-if="groups.length === 0" class="empty">
      아직 실험 결과가 없습니다. 업로드한 작업에 대해 <code>POST /api/experiments/run</code> 으로 A/B를 실행하세요.
    </p>

    <div v-for="grp in groups" :key="grp.job_id" class="group">
      <div class="group-head">
        <span class="file">{{ grp.filename || grp.job_id }}</span>
        <span v-if="grp.style" class="style">스타일: {{ grp.style }}</span>
      </div>

      <div class="cards">
        <div v-for="exp in grp.experiments" :key="exp.id" class="card">
          <div class="card-head">
            <span class="provider">{{ exp.provider_name }}</span>
            <span class="step">{{ exp.step }}</span>
          </div>

          <div class="preview">
            <template v-if="exp.result_path">
              <audio v-if="kind(exp.result_path) === 'audio'" :src="resultUrl(exp.id)" controls />
              <img v-else-if="kind(exp.result_path) === 'image'" :src="resultUrl(exp.id)" />
              <video v-else-if="kind(exp.result_path) === 'video'" :src="resultUrl(exp.id)" controls />
              <a v-else :href="resultUrl(exp.id)" download>다운로드</a>
            </template>
            <span v-else class="no-output">출력 없음 (실패)</span>
          </div>

          <div class="score">
            점수:
            <input
              type="number"
              :value="exp.score ?? ''"
              @change="(e) => saveScore(exp, e.target.value)"
              placeholder="-"
            />
          </div>
        </div>
      </div>
    </div>

    <p class="link"><RouterLink to="/">← 업로드로 돌아가기</RouterLink></p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const API = 'http://localhost:8000/api'
const groups = ref([])
const loading = ref(true)
const error = ref('')

function resultUrl(id) {
  return `${API}/experiments/${id}/result`
}

function kind(path) {
  const ext = path.split('.').pop().toLowerCase()
  if (['wav', 'mp3'].includes(ext)) return 'audio'
  if (['png', 'jpg', 'jpeg'].includes(ext)) return 'image'
  if (ext === 'mp4') return 'video'
  return 'file'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`${API}/experiments`)
    if (!res.ok) throw new Error(`서버 오류 (${res.status})`)
    const data = await res.json()
    groups.value = data.groups || []
  } catch (e) {
    error.value = e.message || '백엔드 서버가 실행 중인지 확인하세요.'
  } finally {
    loading.value = false
  }
}

async function saveScore(exp, value) {
  const score = parseInt(value, 10)
  if (Number.isNaN(score)) return
  try {
    const res = await fetch(`${API}/experiments/${exp.id}/score`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ score }),
    })
    if (!res.ok) throw new Error()
    exp.score = score
  } catch {
    alert('점수 저장 실패')
  }
}

onMounted(load)
</script>

<style scoped>
.page { max-width: 900px; margin: 60px auto; padding: 0 20px; font-family: sans-serif; }
h1 { text-align: center; margin-bottom: 8px; }
.hint { text-align: center; color: #666; margin-bottom: 28px; font-size: 14px; }
.error { color: #e74c3c; text-align: center; }
.empty { text-align: center; color: #888; }
.group { border: 1px solid #eee; border-radius: 12px; padding: 16px; margin-bottom: 24px; }
.group-head { display: flex; gap: 16px; align-items: baseline; margin-bottom: 12px; }
.group-head .file { font-weight: 700; }
.group-head .style { color: #888; font-size: 13px; }
.cards { display: flex; gap: 16px; flex-wrap: wrap; }
.card { flex: 1 1 240px; border: 1px solid #e6e6e6; border-radius: 10px; padding: 12px; background: #fafafa; }
.card-head { display: flex; justify-content: space-between; margin-bottom: 10px; }
.card-head .provider { font-weight: 600; color: #42b883; }
.card-head .step { color: #aaa; font-size: 12px; }
.preview audio, .preview video, .preview img { width: 100%; border-radius: 6px; }
.preview img { background: #000; }
.no-output { color: #e74c3c; font-size: 13px; }
.score { margin-top: 10px; font-size: 14px; }
.score input { width: 70px; padding: 4px 8px; border: 1px solid #ddd; border-radius: 6px; margin-left: 6px; }
.link { text-align: center; margin-top: 24px; }
.link a { color: #3498db; text-decoration: none; }
</style>
