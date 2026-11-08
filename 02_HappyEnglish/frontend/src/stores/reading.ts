import { defineStore } from 'pinia'
import { ref, computed, nextTick } from 'vue'
import type { SentenceItem } from '@/api'
import { getTtsUrl } from '@/api'

export type SpeedLevel = 0 | 1 | 2
export const SPEED_LABELS: Record<SpeedLevel, string> = {
  0: '慢速',
  1: '正常',
  2: '快速',
}

export const useReadingStore = defineStore('reading', () => {
  const sentences = ref<SentenceItem[]>([])
  const rawText = ref('')
  const recordId = ref<number | null>(null)

  const playingSentenceId = ref<number | null>(null)
  const playingWordIndex = ref<number | null>(null)
  const loadingSentenceId = ref<number | null>(null)
  const isLooping = ref(false)
  const loopCount = ref(0)
  const speed = ref<SpeedLevel>(1)

  // 最后一次播放/点击的记录，用于高亮保留
  const lastSentenceId = ref<number | null>(null)
  const lastWordIndex = ref<number | null>(null)

  // 用自增 sessionId 做守卫，替代 audio 对象对比
  // 每次 stopAll 时 sessionId 自增，所有挂起的异步回调检测到 sessionId 变化就自动放弃
  let currentSessionId = 0
  let currentAudio: HTMLAudioElement | null = null
  let loopTimer: ReturnType<typeof setTimeout> | null = null

  // ── 停止所有播放 ───────────────────────────────────────────────────
  function stopAll() {
    currentSessionId++          // 使所有进行中的异步链路失效
    if (currentAudio) {
      currentAudio.pause()
      currentAudio.src = ''
      currentAudio = null
    }
    if (loopTimer) {
      clearTimeout(loopTimer)
      loopTimer = null
    }
    playingSentenceId.value = null
    playingWordIndex.value = null
    loadingSentenceId.value = null
    loopCount.value = 0
    isLooping.value = false
    // lastSentenceId / lastWordIndex 不清零，保留高亮
  }

  // ── 播放整句（单次或循环入口）──────────────────────────────────────
  async function playSentence(sentenceId: number, loop = false) {
    stopAll()
    const sentence = sentences.value.find(s => s.id === sentenceId)
    if (!sentence) return

    isLooping.value = loop
    loopCount.value = 0
    playingSentenceId.value = sentenceId
    playingWordIndex.value = -1
    lastSentenceId.value = sentenceId   // 记录最后播放的句子
    lastWordIndex.value = null          // 切换句子时清空上次单词高亮

    if (loop) {
      await _loopPlay(sentenceId, currentSessionId)
    } else {
      await _playOnce(sentence.text, currentSessionId, () => {
        playingSentenceId.value = null
        playingWordIndex.value = null
        // lastSentenceId 保留，维持高亮
      })
    }
  }

  // ── 内部：循环播放逻辑（不再调 stopAll，避免清零状态）─────────────
  async function _loopPlay(sentenceId: number, sid: number) {
    const sentence = sentences.value.find(s => s.id === sentenceId)
    if (!sentence) return

    while (true) {
      if (currentSessionId !== sid) break   // 被外部停止

      await _playOnce(sentence.text, sid, () => {})
      if (currentSessionId !== sid) break   // 播放结束后再检查

      loopCount.value++

      // 循环间隔 600ms
      await new Promise<void>(resolve => {
        loopTimer = setTimeout(resolve, 600)
      })
      if (currentSessionId !== sid) break
    }
  }

  // ── 内部：播放一次文本 ────────────────────────────────────────────
  async function _playOnce(text: string, sid: number, onEnd: () => void): Promise<void> {
    const url = getTtsUrl(text, speed.value)

    // 设置 loading 状态，等 Vue 渲染
    loadingSentenceId.value = playingSentenceId.value
    await nextTick()

    if (currentSessionId !== sid) return

    // 并行 fetch + 最短 400ms loading 展示
    let blob: Blob
    try {
      const [b] = await Promise.all([
        fetch(url).then(r => {
          if (!r.ok) throw new Error(`TTS ${r.status}`)
          return r.blob()
        }),
        new Promise<void>(r => setTimeout(r, 400)),
      ])
      blob = b
    } catch (err) {
      console.warn('TTS fetch 失败:', err)
      if (currentSessionId === sid) {
        loadingSentenceId.value = null
        playingSentenceId.value = null
      }
      return
    }

    if (currentSessionId !== sid) return

    loadingSentenceId.value = null   // loading 结束

    const blobUrl = URL.createObjectURL(blob)
    const audio = new Audio(blobUrl)
    currentAudio = audio

    await new Promise<void>((resolve) => {
      audio.onended = () => {
        URL.revokeObjectURL(blobUrl)
        onEnd()
        resolve()
      }
      audio.onerror = () => {
        URL.revokeObjectURL(blobUrl)
        if (currentSessionId === sid) {
          loadingSentenceId.value = null
          playingSentenceId.value = null
        }
        resolve()
      }
      audio.play().catch(() => {
        if (currentSessionId === sid) {
          loadingSentenceId.value = null
          playingSentenceId.value = null
        }
        resolve()
      })
    })
  }

  // ── 播放单词 ──────────────────────────────────────────────────────
  async function playWord(sentenceId: number, wordIndex: number) {
    stopAll()
    const sentence = sentences.value.find(s => s.id === sentenceId)
    if (!sentence) return

    const word = sentence.words[wordIndex]
    if (!word) return
    const cleanWord = word.replace(/[.,!?;:'"()\-]/g, '').trim()
    if (!cleanWord) return

    playingSentenceId.value = sentenceId
    playingWordIndex.value = wordIndex
    lastSentenceId.value = sentenceId   // 记录最后播放的句子
    lastWordIndex.value = wordIndex     // 记录最后点击的单词

    await _playOnce(cleanWord, currentSessionId, () => {
      playingWordIndex.value = null
      playingSentenceId.value = null
      // lastWordIndex 保留，维持单词高亮
    })
  }

  // ── 数据加载 ──────────────────────────────────────────────────────
  function loadData(data: { sentences: SentenceItem[]; rawText: string; recordId?: number }) {
    stopAll()
    sentences.value = data.sentences
    rawText.value = data.rawText
    recordId.value = data.recordId ?? null
  }

  // ── 计算属性 ──────────────────────────────────────────────────────
  const isPlayingSentence = computed(() => (id: number) => playingSentenceId.value === id)
  const isPlayingWord = computed(() => (sentenceId: number, wordIdx: number) =>
    playingSentenceId.value === sentenceId && playingWordIndex.value === wordIdx
  )
  const isLoadingSentence = computed(() => (id: number) => loadingSentenceId.value === id)

  return {
    sentences, rawText, recordId,
    playingSentenceId, playingWordIndex, loadingSentenceId,
    lastSentenceId, lastWordIndex,
    isLooping, loopCount, speed,
    isPlayingSentence, isPlayingWord, isLoadingSentence,
    loadData, playSentence, playWord, stopAll,
  }
})
