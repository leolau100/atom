<template>
  <div class="read-view">

    <!-- 加载中 -->
    <div v-if="loading" class="loading">
      <div class="spinner-lg"></div>
    </div>

    <template v-else-if="store.sentences.length > 0">

      <!-- 控制栏 -->
      <div class="control-bar">
        <div class="speed-group">
          <span class="speed-label">语速</span>
          <div class="speed-tabs">
            <!-- 慢速：乌龟慢慢爬 -->
            <button
              class="speed-tab"
              :class="{ active: store.speed === 0 }"
              @click="store.speed = 0; store.stopAll()"
              title="慢速"
            >
              <span class="speed-icon speed-turtle">🐢</span>
              <span class="speed-tab-label">慢速</span>
            </button>
            <!-- 正常：人走路 -->
            <button
              class="speed-tab"
              :class="{ active: store.speed === 1 }"
              @click="store.speed = 1; store.stopAll()"
              title="正常"
            >
              <span class="speed-icon speed-walk">🚶</span>
              <span class="speed-tab-label">正常</span>
            </button>
            <!-- 快速：火箭飞 -->
            <button
              class="speed-tab"
              :class="{ active: store.speed === 2 }"
              @click="store.speed = 2; store.stopAll()"
              title="快速"
            >
              <span class="speed-icon speed-rocket">🚀</span>
              <span class="speed-tab-label">快速</span>
            </button>
          </div>
        </div>
        <button
          v-if="store.playingSentenceId !== null"
          class="btn-stop"
          @click="store.stopAll()"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <rect x="4" y="4" width="16" height="16" rx="2"/>
          </svg>
          停止
        </button>
      </div>

      <!-- 句子卡片 -->
      <div class="sentence-cards">
        <div
          v-for="sentence in store.sentences"
          :key="sentence.id"
          class="sentence-card"
          :class="{
            'is-playing': store.isPlayingSentence(sentence.id) && !store.isLooping,
            'is-looping': store.isPlayingSentence(sentence.id) && store.isLooping,
            'is-loading': store.isLoadingSentence(sentence.id),
            'was-played': store.lastSentenceId === sentence.id && !store.isPlayingSentence(sentence.id)
          }"
        >
          <div class="card-header">
            <div class="card-no">{{ sentence.id + 1 }}</div>

            <!-- 循环中的标记 -->
            <div
              v-if="store.isPlayingSentence(sentence.id) && store.isLooping"
              class="loop-badge"
            >
              <span class="loop-wave"><span></span><span></span><span></span></span>
              循环中
              <Transition name="count-pop" mode="out-in">
                <span
                  v-if="store.loopCount > 0"
                  :key="store.loopCount"
                  class="loop-count"
                >×{{ store.loopCount + 1 }}</span>
              </Transition>
            </div>
            <div class="card-actions">
              <button
                class="btn-action btn-play"
                :class="{
                  loading: store.isLoadingSentence(sentence.id) && !store.isLooping,
                  active: store.isPlayingSentence(sentence.id) && !store.isLooping && !store.isLoadingSentence(sentence.id)
                }"
                @click="togglePlay(sentence.id)"
              >
                <!-- 加载中转圈 -->
                <svg v-if="store.isLoadingSentence(sentence.id) && !store.isLooping"
                  class="spin-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                  <path d="M12 2a10 10 0 0 1 0 20" opacity=".3"/>
                  <path d="M12 2a10 10 0 0 1 10 10"/>
                </svg>
                <!-- 播放中暂停图标 -->
                <svg v-else-if="store.isPlayingSentence(sentence.id) && !store.isLooping" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                  <rect x="6" y="4" width="4" height="16" rx="1.5"/>
                  <rect x="14" y="4" width="4" height="16" rx="1.5"/>
                </svg>
                <!-- 默认播放图标 -->
                <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M8 5v14l11-7L8 5z"/>
                </svg>
                <span v-if="store.isLoadingSentence(sentence.id) && !store.isLooping"></span>
                <span v-else-if="store.isPlayingSentence(sentence.id) && !store.isLooping">暂停</span>
                <span v-else>朗读</span>
              </button>

              <button
                class="btn-action btn-loop"
                :class="{
                  loading: store.isLoadingSentence(sentence.id) && store.isLooping,
                  active: store.isPlayingSentence(sentence.id) && store.isLooping && !store.isLoadingSentence(sentence.id)
                }"
                @click="toggleLoop(sentence.id)"
              >
                <!-- 循环加载中转圈 -->
                <svg v-if="store.isLoadingSentence(sentence.id) && store.isLooping"
                  class="spin-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                  <path d="M12 2a10 10 0 0 1 0 20" opacity=".3"/>
                  <path d="M12 2a10 10 0 0 1 10 10"/>
                </svg>
                <!-- 默认循环图标 -->
                <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
                  <path d="M17 2l4 4-4 4"/><path d="M3 11V9a4 4 0 014-4h14"/>
                  <path d="M7 22l-4-4 4-4"/><path d="M21 13v2a4 4 0 01-4 4H3"/>
                </svg>
                <span v-if="store.isLoadingSentence(sentence.id) && store.isLooping"></span>
                <span v-else>循环</span>
              </button>
            </div>
          </div>

          <!-- 单词：点击弹出卡片 -->
          <div class="card-words">
            <span
              v-for="(word, wIdx) in sentence.words"
              :key="wIdx"
              class="word"
              :class="{
                'word-sentence-hl': store.isPlayingSentence(sentence.id) && store.playingWordIndex === -1,
                'word-active': store.isPlayingWord(sentence.id, wIdx),
                'word-last': store.lastSentenceId === sentence.id
                          && store.lastWordIndex === wIdx
                          && !store.isPlayingWord(sentence.id, wIdx)
              }"
              @click="openWordCard(word, sentence.id, wIdx)"
            >{{ word }}</span>
          </div>
        </div>
      </div>

    </template>

    <!-- 空状态 -->
    <div v-else class="empty">
      <div class="empty-icon">
        <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
          <circle cx="32" cy="32" r="32" fill="#E8F8FF"/>
          <path d="M20 44V22a2 2 0 012-2h20a2 2 0 012 2v22l-12-6-12 6z" fill="#0A84FF" opacity=".2"/>
          <path d="M20 44V22a2 2 0 012-2h20a2 2 0 012 2v22l-12-6-12 6z" stroke="#0A84FF" stroke-width="2" stroke-linejoin="round"/>
          <line x1="27" y1="28" x2="37" y2="28" stroke="#0A84FF" stroke-width="2" stroke-linecap="round"/>
          <line x1="27" y1="33" x2="34" y2="33" stroke="#0A84FF" stroke-width="2" stroke-linecap="round" opacity=".6"/>
        </svg>
      </div>
      <p class="empty-title">还没有内容</p>
      <p class="empty-sub">先去识别一张图片吧</p>
      <RouterLink to="/" class="btn-go">去识别 →</RouterLink>
    </div>

    <!-- 单词卡片 -->
    <WordCard
      :visible="wordCardVisible"
      :word="selectedWord"
      :sentence-id="selectedSentenceId"
      :word-idx="selectedWordIdx"
      :speed="store.speed"
      @close="wordCardVisible = false"
    />

  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useReadingStore } from '@/stores/reading'
import { getRecord } from '@/api'
import WordCard from '@/components/WordCard.vue'

const route = useRoute()
const store = useReadingStore()
const loading = ref(false)

// 单词卡片状态
const wordCardVisible = ref(false)
const selectedWord = ref('')
const selectedSentenceId = ref<number | null>(null)
const selectedWordIdx = ref<number | null>(null)

onMounted(async () => {
  const id = Number(route.params.id)
  if (id && store.recordId !== id) {
    loading.value = true
    try {
      const record = await getRecord(id)
      store.loadData({ sentences: record.sentences, rawText: record.raw_text, recordId: record.id })
    } catch (e) {
      console.error(e)
    } finally {
      loading.value = false
    }
  }
})

function togglePlay(sentenceId: number) {
  if (store.isPlayingSentence(sentenceId) && !store.isLooping) {
    store.stopAll()
  } else {
    store.playSentence(sentenceId, false)
  }
}
function toggleLoop(sentenceId: number) {
  if (store.isPlayingSentence(sentenceId) && store.isLooping) {
    store.stopAll()
  } else {
    store.playSentence(sentenceId, true)
  }
}

function openWordCard(word: string, sentenceId: number, wIdx: number) {
  selectedWord.value = word
  selectedSentenceId.value = sentenceId
  selectedWordIdx.value = wIdx
  wordCardVisible.value = true
}
</script>

<style scoped>
.read-view { display: flex; flex-direction: column; gap: 14px; }

/* 加载 */
.loading {
  display: flex; flex-direction: column; align-items: center;
  gap: 16px; padding: 80px 0; color: var(--gray-500);
}
.spinner-lg {
  width: 44px; height: 44px;
  border: 3px solid var(--gray-200);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── 控制栏 ── */
.control-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--white);
  border-radius: var(--radius);
  padding: 14px 16px;
  box-shadow: var(--shadow);
  gap: 12px;
  flex-wrap: wrap;
}

.speed-group {
  display: flex;
  align-items: center;
  gap: 10px;
}
.speed-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--gray-500);
  letter-spacing: 0.5px;
}
.speed-tabs {
  display: flex;
  background: var(--gray-100);
  border-radius: 10px;
  padding: 3px;
  gap: 2px;
}
.speed-tab {
  padding: 5px 18px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--gray-500);
  background: none;
  border: none;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  min-width: 64px;
}
.speed-tab:hover { color: var(--gray-900); }
.speed-tab.active {
  background: var(--white);
  color: var(--primary-dark);
  box-shadow: 0 1px 5px rgba(0,0,0,0.1);
}

.speed-tab-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.3px;
}

/* ── 速度图标动画 ── */
.speed-icon {
  font-size: 20px;
  display: block;
  line-height: 1;
}

/* 乌龟：缓慢左右摇摆 */
.speed-turtle {
  transform-origin: center bottom;
}
.speed-tab.active .speed-turtle {
  animation: turtle-sway 2.4s ease-in-out infinite;
}
@keyframes turtle-sway {
  0%, 100% { transform: rotate(-6deg) translateX(-2px); }
  50%       { transform: rotate(6deg)  translateX(2px); }
}

/* 人走路：上下弹跳 + 轻微旋转，节奏中等 */
.speed-tab.active .speed-walk {
  animation: walk-bounce 0.9s ease-in-out infinite;
}
@keyframes walk-bounce {
  0%, 100% { transform: translateY(0)    rotate(-4deg); }
  25%       { transform: translateY(-4px) rotate(0deg); }
  50%       { transform: translateY(0)    rotate(4deg); }
  75%       { transform: translateY(-2px) rotate(0deg); }
}

/* 火箭：斜向飞出再回来，快速循环 */
.speed-tab.active .speed-rocket {
  animation: rocket-fly 0.7s ease-in-out infinite;
}
@keyframes rocket-fly {
  0%   { transform: translate(0, 0)       rotate(-45deg) scale(1); }
  40%  { transform: translate(5px, -6px)  rotate(-45deg) scale(1.18); }
  60%  { transform: translate(6px, -7px)  rotate(-45deg) scale(1.2); }
  100% { transform: translate(0, 0)       rotate(-45deg) scale(1); }
}

/* 未激活：图标灰暗 */
.speed-tab:not(.active) .speed-icon { filter: grayscale(60%) opacity(0.55); }
.speed-tab.active .speed-icon       { filter: none; }

.btn-stop {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 7px 14px;
  border-radius: 20px;
  background: var(--red-light);
  color: var(--red);
  border: none;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-stop:hover { background: var(--red); color: #fff; }

/* ── 句子卡片 ── */
.sentence-cards { display: flex; flex-direction: column; gap: 12px; }

.sentence-card {
  background: var(--white);
  border-radius: var(--radius);
  padding: 16px;
  box-shadow: var(--shadow);
  border: 2px solid transparent;
  transition: all 0.2s;
}
.sentence-card.is-playing {
  border-color: var(--primary);
  box-shadow: 0 0 0 4px var(--primary-light), var(--shadow);
  transform: translateY(-1px);
}
.sentence-card.is-looping {
  border-color: var(--primary);
  box-shadow: 0 0 0 4px var(--primary-light), var(--shadow);
  transform: translateY(-1px);
}
/* 上次播放过的句子：淡绿色细边框 */
.sentence-card.was-played {
  border-color: var(--primary-mid);
  border-width: 1.5px;
}


.sentence-card.is-loading {
  border-color: var(--gray-300);
  box-shadow: 0 0 0 4px var(--gray-100), var(--shadow);
  transform: translateY(-1px);
}

/* 循环标记 */
.loop-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px 3px 8px;
  background: var(--primary-light);
  color: var(--primary-dark);
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
}
.loop-count {
  font-size: 12px;
  font-weight: 800;
  color: var(--red);
  background: rgba(255,255,255,0.85);
  padding: 1px 7px;
  border-radius: 10px;
  display: inline-block;
}

/* 次数弹出动画 */
.count-pop-enter-active {
  animation: count-bounce 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.count-pop-leave-active {
  animation: count-shrink 0.15s ease-in forwards;
}
@keyframes count-bounce {
  0%   { transform: scale(0.4); opacity: 0; }
  60%  { transform: scale(1.25); opacity: 1; }
  100% { transform: scale(1); opacity: 1; }
}
@keyframes count-shrink {
  to { transform: scale(0.4); opacity: 0; }
}
.loop-wave {
  display: inline-flex;
  align-items: center;
  gap: 1.5px;
  height: 14px;
}
.loop-wave span {
  display: block;
  width: 2.5px;
  background: var(--primary-dark);
  border-radius: 2px;
  animation: wave 0.8s ease-in-out infinite;
}
.loop-wave span:nth-child(1) { height: 5px; animation-delay: 0s; }
.loop-wave span:nth-child(2) { height: 10px; animation-delay: 0.13s; }
.loop-wave span:nth-child(3) { height: 6px; animation-delay: 0.26s; }
@keyframes wave {
  0%, 100% { transform: scaleY(0.6); }
  50%       { transform: scaleY(1.4); }
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.card-no {
  width: 28px; height: 28px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--primary) 0%, #27AE60 100%);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 2px 8px rgba(52,199,89,0.35);
  flex-shrink: 0;
}

.card-actions { display: flex; gap: 8px; }

.btn-action {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  border-radius: 20px;
  border: 1.5px solid var(--gray-200);
  background: var(--white);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  color: var(--gray-700);
  transition: all 0.15s;
  min-width: 72px;
  justify-content: center;
}
.btn-play:hover { border-color: var(--primary); color: var(--primary); }
.btn-loop:hover { border-color: var(--blue); color: var(--blue); }

.btn-play.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
  box-shadow: 0 3px 10px rgba(52,199,89,0.4);
}
.btn-loop.active {
  background: var(--blue);
  border-color: var(--blue);
  color: #fff;
  box-shadow: 0 3px 10px rgba(10,132,255,0.35);
}

/* loading 状态 */
.btn-play.loading {
  background: var(--gray-100);
  border-color: var(--gray-200);
  color: var(--gray-500);
  cursor: default;
}
.btn-loop.loading {
  background: var(--gray-100);
  border-color: var(--gray-200);
  color: var(--gray-500);
  cursor: default;
}
.spin-icon {
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}

/* ── 单词区域 ── */
.card-words {
  display: flex;
  flex-wrap: wrap;
  gap: 5px 3px;
  line-height: 1;
}

.word {
  font-size: 21px;
  font-weight: 500;
  padding: 5px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  color: var(--gray-900);
  user-select: none;
  letter-spacing: 0.2px;
}
.word:hover {
  background: var(--accent-light);
  color: #C05200;
  transform: translateY(-1px);
}
.word.word-sentence-hl {
  background: var(--primary-light);
  color: var(--primary-dark);
}
/* 上次点击的单词：淡橙色底 */
.word.word-last {
  background: var(--accent-light);
  color: #C05200;
}
.word.word-active {
  background: var(--accent);
  color: #fff;
  transform: scale(1.1) translateY(-2px);
  box-shadow: 0 4px 12px rgba(255,159,10,0.5);
  font-weight: 700;
}

/* ── 空状态 ── */
.empty {
  display: flex; flex-direction: column; align-items: center;
  gap: 12px; padding: 80px 0; text-align: center;
}
.empty-icon { margin-bottom: 4px; }
.empty-title { font-size: 18px; font-weight: 700; color: var(--gray-900); }
.empty-sub { font-size: 14px; color: var(--gray-500); }
.btn-go {
  margin-top: 8px;
  padding: 10px 28px;
  background: linear-gradient(135deg, var(--primary) 0%, #27AE60 100%);
  color: #fff;
  border-radius: 20px;
  font-size: 15px;
  font-weight: 700;
  text-decoration: none;
  box-shadow: 0 4px 14px rgba(52,199,89,0.4);
  transition: all 0.15s;
}
.btn-go:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(52,199,89,0.5); }
</style>
