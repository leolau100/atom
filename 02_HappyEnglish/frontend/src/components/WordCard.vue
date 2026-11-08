<template>
  <!-- 遮罩点击关闭 -->
  <Teleport to="body">
    <Transition name="card-fade">
      <div v-if="visible" class="wc-overlay" @click.self="$emit('close')">
        <Transition name="card-slide">
          <div v-if="visible" class="wc-card">

            <!-- 关闭按钮 -->
            <button class="wc-close" @click="$emit('close')" aria-label="关闭">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>

            <!-- 查词加载中 -->
            <div v-if="dictLoading" class="wc-dict-loading">
              <div class="wc-spinner"></div>
              <span>查询中...</span>
            </div>

            <!-- 查词结果 -->
            <template v-else>
              <!-- 单词 + 音标 -->
              <div class="wc-word-row">
                <span class="wc-word">{{ cleanWord }}</span>
                <span v-if="dictData?.phonetic" class="wc-phonetic">{{ dictData.phonetic }}</span>
                <span v-if="dictData?.pos" class="wc-pos">{{ dictData.pos }}</span>
              </div>

              <!-- 发音按钮 -->
              <button
                class="wc-play-btn"
                :class="{ loading: audioLoading, playing: audioPlaying }"
                @click="playWord"
                :disabled="audioLoading"
              >
                <!-- loading 转圈 -->
                <svg v-if="audioLoading" class="wc-spin-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                  <path d="M12 2a10 10 0 0 1 0 20" opacity=".3"/>
                  <path d="M12 2a10 10 0 0 1 10 10"/>
                </svg>
                <!-- 播放图标 -->
                <svg v-else-if="!audioPlaying" width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M11 5L6 9H2v6h4l5 4V5z"/>
                  <path d="M15.54 8.46a5 5 0 0 1 0 7.07M19.07 4.93a10 10 0 0 1 0 14.14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>
                </svg>
                <!-- 播放中波形 -->
                <span v-else class="wc-wave">
                  <span></span><span></span><span></span><span></span>
                </span>
                <span>{{ audioLoading ? '加载中' : audioPlaying ? '播放中' : '发音' }}</span>
              </button>

              <!-- 释义列表 -->
              <div v-if="dictData?.meanings?.length" class="wc-meanings">
                <div
                  v-for="(m, i) in dictData.meanings"
                  :key="i"
                  class="wc-meaning-item"
                >
                  <div class="wc-cn">{{ m.cn }}</div>
                  <div v-if="m.example" class="wc-example">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity=".5">
                      <path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V20c0 1 0 1 1 1z"/>
                      <path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3c0 1 0 1 1 1z"/>
                    </svg>
                    {{ m.example }}
                  </div>
                </div>
              </div>

              <!-- 查词失败 -->
              <div v-else-if="!dictLoading" class="wc-no-data">
                暂无释义
              </div>
            </template>

          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { lookupWord, getTtsUrl } from '@/api'
import type { DictResult } from '@/api'
import { useReadingStore } from '@/stores/reading'

const props = defineProps<{
  visible: boolean
  word: string
  sentenceId: number | null    // 对应的句子 id
  wordIdx: number | null       // 对应句子里的单词下标
  speed: number
}>()

const store = useReadingStore()

// 清理标点，用于 TTS 和查词
const cleanWord = computed(() =>
  props.word.replace(/[.,!?;:'"()\-]/g, '').trim().toLowerCase()
)

const dictLoading = ref(false)
const dictData = ref<DictResult | null>(null)
const audioLoading = ref(false)
const audioPlaying = ref(false)

let currentAudio: HTMLAudioElement | null = null

// 每次卡片出现时自动查词
watch(() => props.visible, async (v) => {
  if (!v) {
    // 关闭时停止音频
    currentAudio?.pause()
    currentAudio = null
    audioLoading.value = false
    audioPlaying.value = false
    return
  }
  if (!cleanWord.value) return
  dictLoading.value = true
  dictData.value = null
  try {
    dictData.value = await lookupWord(cleanWord.value)
  } catch {
    dictData.value = null
  } finally {
    dictLoading.value = false
  }
})

// 点击发音按钮
async function playWord() {
  if (audioLoading.value || audioPlaying.value) return
  if (!cleanWord.value) return

  // 停止正在播放的句子或循环，并记录本次单词的 last 状态
  store.stopAll()
  if (props.sentenceId !== null && props.wordIdx !== null) {
    store.lastSentenceId = props.sentenceId
    store.lastWordIndex = props.wordIdx
  }

  // 停掉上一次单词音频
  if (currentAudio) {
    currentAudio.pause()
    currentAudio = null
    audioPlaying.value = false
  }

  audioLoading.value = true

  const url = getTtsUrl(cleanWord.value, props.speed)

  try {
    const resp = await fetch(url)
    if (!resp.ok) throw new Error('TTS 请求失败')
    const blob = await resp.blob()
    const blobUrl = URL.createObjectURL(blob)

    const audio = new Audio(blobUrl)
    currentAudio = audio

    audioLoading.value = false
    audioPlaying.value = true

    audio.onended = () => {
      audioPlaying.value = false
      URL.revokeObjectURL(blobUrl)
    }
    audio.onerror = () => {
      audioPlaying.value = false
      audioLoading.value = false
    }

    await audio.play()
  } catch {
    audioLoading.value = false
    audioPlaying.value = false
  }
}
</script>

<style scoped>
/* ── 遮罩 ── */
.wc-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  z-index: 200;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: 0 0 env(safe-area-inset-bottom, 0);
}

/* ── 卡片 ── */
.wc-card {
  background: #fff;
  border-radius: 24px 24px 0 0;
  width: 100%;
  max-width: 600px;
  padding: 28px 24px 40px;
  position: relative;
  box-shadow: 0 -8px 40px rgba(0,0,0,0.15);
}

/* 关闭按钮 */
.wc-close {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 32px; height: 32px;
  border-radius: 50%;
  background: var(--gray-100);
  border: none;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  color: var(--gray-500);
  transition: all 0.15s;
}
.wc-close:hover { background: var(--gray-200); color: var(--gray-900); }

/* 查词加载 */
.wc-dict-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 0;
  color: var(--gray-500);
  font-size: 14px;
}
.wc-spinner {
  width: 20px; height: 20px;
  border: 2.5px solid var(--gray-200);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* 单词行 */
.wc-word-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}
.wc-word {
  font-size: 32px;
  font-weight: 800;
  color: var(--gray-900);
  letter-spacing: -0.5px;
  line-height: 1;
}
.wc-phonetic {
  font-size: 17px;
  color: var(--gray-500);
  font-family: 'Lucida Sans Unicode', 'Segoe UI', sans-serif;
  letter-spacing: 0.5px;
}
.wc-pos {
  font-size: 12px;
  font-weight: 600;
  color: var(--blue);
  background: var(--blue-light);
  padding: 2px 10px;
  border-radius: 20px;
  white-space: nowrap;
}

/* 发音按钮 */
.wc-play-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  border-radius: 14px;
  border: none;
  background: linear-gradient(135deg, var(--primary) 0%, #27AE60 100%);
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  margin-bottom: 20px;
  transition: all 0.15s;
  box-shadow: 0 4px 14px rgba(52,199,89,0.4);
  min-width: 120px;
  justify-content: center;
}
.wc-play-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(52,199,89,0.5);
}
.wc-play-btn:disabled { opacity: 0.7; cursor: default; }
.wc-play-btn.loading {
  background: var(--gray-200);
  color: var(--gray-700);
  box-shadow: none;
}

/* 转圈图标动画 */
.wc-spin-icon {
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}

/* 播放中波形 */
.wc-wave {
  display: flex;
  align-items: center;
  gap: 2px;
  height: 20px;
}
.wc-wave span {
  display: block;
  width: 3px;
  background: #fff;
  border-radius: 2px;
  animation: wave 0.8s ease-in-out infinite;
}
.wc-wave span:nth-child(1) { height: 8px; animation-delay: 0s; }
.wc-wave span:nth-child(2) { height: 14px; animation-delay: 0.1s; }
.wc-wave span:nth-child(3) { height: 10px; animation-delay: 0.2s; }
.wc-wave span:nth-child(4) { height: 6px; animation-delay: 0.3s; }
@keyframes wave {
  0%, 100% { transform: scaleY(0.6); }
  50%       { transform: scaleY(1.4); }
}

/* 释义 */
.wc-meanings { display: flex; flex-direction: column; gap: 12px; }
.wc-meaning-item {
  padding: 12px 14px;
  background: var(--gray-50);
  border-radius: 12px;
  border-left: 3px solid var(--primary-light);
}
.wc-cn {
  font-size: 17px;
  font-weight: 600;
  color: var(--gray-900);
  margin-bottom: 5px;
}
.wc-example {
  display: flex;
  align-items: flex-start;
  gap: 5px;
  font-size: 13px;
  color: var(--gray-500);
  line-height: 1.5;
  font-style: italic;
}
.wc-no-data {
  font-size: 14px;
  color: var(--gray-500);
  padding: 8px 0;
}

/* ── 动画 ── */
.card-fade-enter-active, .card-fade-leave-active { transition: opacity 0.2s ease; }
.card-fade-enter-from, .card-fade-leave-to { opacity: 0; }

.card-slide-enter-active { transition: transform 0.28s cubic-bezier(.22,1,.36,1); }
.card-slide-leave-active { transition: transform 0.2s ease-in; }
.card-slide-enter-from, .card-slide-leave-to { transform: translateY(100%); }
</style>
