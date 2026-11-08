<template>
  <div class="home">

    <!-- ① 上传区（未选图时显示） -->
    <section v-if="!imageLoaded" class="upload-section">
      <label
        class="drop-zone"
        :class="{ dragging }"
        @dragover.prevent="dragging = true"
        @dragleave="dragging = false"
        @drop.prevent="onDrop"
      >
        <div class="drop-icon">📷</div>
        <p class="drop-title">拍照 / 上传图片</p>
        <p class="drop-hint">支持 JPG、PNG 等格式，点击或拖入</p>
        <input
          ref="fileInput"
          type="file"
          accept="image/*"
          capture="environment"
          class="visually-hidden-input"
          @change="onFileChange"
        />
      </label>
    </section>

    <!-- ② 框选区（已选图时显示） -->
    <section v-else class="crop-section">
      <div class="crop-toolbar">
        <span class="crop-hint">
          {{ hasCrop ? '✅ 已选中区域，点击识别' : '✏️ 拖拽选择要识别的区域' }}
        </span>
        <div class="crop-toolbar-right">
          <button class="btn-sm btn-clear-crop" v-if="hasCrop" @click="clearCrop">清除选框</button>
          <button class="btn-sm btn-reupload" @click="reupload">换图片</button>
        </div>
      </div>

      <!-- Canvas 画布：显示图片 + 绘制选框 -->
      <div class="canvas-wrap" ref="canvasWrapRef">
        <canvas
          ref="canvasRef"
          class="crop-canvas"
          @mousedown="startDraw"
          @mousemove="onDraw"
          @mouseup="endDraw"
          @mouseleave="endDraw"
          @touchstart.prevent="startDrawTouch"
          @touchmove.prevent="onDrawTouch"
          @touchend.prevent="endDraw"
        />
      </div>

      <button
        class="btn-primary btn-recognize"
        :disabled="loading"
        @click="recognize"
      >
        <span v-if="loading" class="spinner"></span>
        <span>{{ loading ? '识别中...' : (hasCrop ? '🔍 识别选中区域' : '🔍 识别全图') }}</span>
      </button>
    </section>

    <!-- 错误提示 -->
    <Transition name="fade">
      <div v-if="error" class="error-banner">⚠️ {{ error }}</div>
    </Transition>

    <!-- 识别结果 & 句子编辑 -->
    <Transition name="slide-up">
      <section v-if="sentences.length > 0" class="result-section">
        <div class="result-header">
          <h2>识别结果</h2>
          <span class="sentence-count">{{ sentences.length }} 个句子</span>
        </div>

        <p class="result-hint">点击句子可以编辑，确认无误后点击「开始阅读」</p>

        <div class="sentence-list">
          <div v-for="(s, idx) in sentences" :key="idx" class="sentence-item">
            <span class="sentence-no">{{ idx + 1 }}</span>
            <div class="sentence-body">
              <template v-if="editingIdx === idx">
                <textarea
                  v-model="sentences[idx]"
                  class="sentence-input"
                  @blur="editingIdx = -1"
                  @keydown.enter.prevent="editingIdx = -1"
                  autofocus
                  rows="2"
                />
              </template>
              <template v-else>
                <span class="sentence-text" @click="editingIdx = idx">{{ s }}</span>
                <button class="btn-edit" @click="editingIdx = idx" title="编辑">✏️</button>
              </template>
            </div>
            <button class="btn-del" @click="deleteSentence(idx)" title="删除">🗑️</button>
          </div>
          <button class="btn-add-sentence" @click="addSentence">+ 添加句子</button>
        </div>

        <div class="action-row">
          <button class="btn-primary btn-read" @click="goRead">🎧 开始阅读</button>
        </div>
      </section>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ocrImage, saveRecord } from '@/api'
import { useReadingStore } from '@/stores/reading'

const router = useRouter()
const store = useReadingStore()

// ── 状态 ─────────────────────────────────────────────────────────────────
const fileInput = ref<HTMLInputElement>()
const canvasRef = ref<HTMLCanvasElement>()
const canvasWrapRef = ref<HTMLDivElement>()
const dragging = ref(false)
const loading = ref(false)
const error = ref('')
const imageLoaded = ref(false)

// 原始图片（用于裁剪，保持原始分辨率）
let originalImage: HTMLImageElement | null = null

// 框选状态
const isDrawing = ref(false)
const hasCrop = ref(false)
// 选框在 canvas 显示坐标系中的位置
const cropRect = ref({ x: 0, y: 0, w: 0, h: 0 })
let drawStart = { x: 0, y: 0 }

// 结果
const rawText = ref('')
const sentences = ref<string[]>([])
const editingIdx = ref(-1)

// ── 文件处理 ──────────────────────────────────────────────────────────────
function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) loadFile(file)
}
function onDrop(e: DragEvent) {
  dragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file?.type.startsWith('image/')) loadFile(file)
}
function reupload() {
  imageLoaded.value = false
  hasCrop.value = false
  sentences.value = []
  error.value = ''
  originalImage = null
  nextTick(() => fileInput.value?.click())
}

function loadFile(file: File) {
  const url = URL.createObjectURL(file)
  const img = new Image()
  img.onload = () => {
    originalImage = img
    imageLoaded.value = true
    hasCrop.value = false
    sentences.value = []
    error.value = ''
    nextTick(() => renderCanvas())
  }
  img.src = url
}

// ── Canvas 渲染 ───────────────────────────────────────────────────────────
function renderCanvas() {
  const canvas = canvasRef.value
  const wrap = canvasWrapRef.value
  if (!canvas || !wrap || !originalImage) return

  // canvas 显示宽度 = 容器宽度，高度等比缩放
  const displayW = wrap.clientWidth
  const scale = displayW / originalImage.naturalWidth
  const displayH = originalImage.naturalHeight * scale

  canvas.width = displayW
  canvas.height = displayH
  canvas.style.width = `${displayW}px`
  canvas.style.height = `${displayH}px`

  drawScene()
}

function drawScene() {
  const canvas = canvasRef.value
  if (!canvas || !originalImage) return
  const ctx = canvas.getContext('2d')!

  // 绘制图片
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.drawImage(originalImage, 0, 0, canvas.width, canvas.height)

  if (!hasCrop.value) return

  const { x, y, w, h } = cropRect.value
  if (Math.abs(w) < 4 || Math.abs(h) < 4) return

  // 蒙层：非选区变暗
  ctx.fillStyle = 'rgba(0,0,0,0.45)'
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  // 镂空选区（显示原图）
  const rx = w < 0 ? x + w : x
  const ry = h < 0 ? y + h : y
  const rw = Math.abs(w)
  const rh = Math.abs(h)
  ctx.drawImage(originalImage,
    rx / canvas.width * originalImage.naturalWidth,
    ry / canvas.height * originalImage.naturalHeight,
    rw / canvas.width * originalImage.naturalWidth,
    rh / canvas.height * originalImage.naturalHeight,
    rx, ry, rw, rh
  )

  // 选框边框
  ctx.strokeStyle = '#4CAF50'
  ctx.lineWidth = 2
  ctx.setLineDash([6, 3])
  ctx.strokeRect(rx, ry, rw, rh)
  ctx.setLineDash([])

  // 四角手柄
  const handles = [
    [rx, ry], [rx + rw, ry], [rx, ry + rh], [rx + rw, ry + rh]
  ]
  ctx.fillStyle = '#4CAF50'
  handles.forEach(([hx, hy]) => {
    ctx.beginPath()
    ctx.arc(hx, hy, 5, 0, Math.PI * 2)
    ctx.fill()
  })
}

// ── 拖拽画框（鼠标） ──────────────────────────────────────────────────────
function getPos(e: MouseEvent): { x: number; y: number } {
  const rect = canvasRef.value!.getBoundingClientRect()
  return { x: e.clientX - rect.left, y: e.clientY - rect.top }
}

function startDraw(e: MouseEvent) {
  const pos = getPos(e)
  drawStart = pos
  cropRect.value = { x: pos.x, y: pos.y, w: 0, h: 0 }
  isDrawing.value = true
  hasCrop.value = false
}

function onDraw(e: MouseEvent) {
  if (!isDrawing.value) return
  const pos = getPos(e)
  cropRect.value = {
    x: drawStart.x,
    y: drawStart.y,
    w: pos.x - drawStart.x,
    h: pos.y - drawStart.y,
  }
  hasCrop.value = true
  drawScene()
}

function endDraw() {
  if (!isDrawing.value) return
  isDrawing.value = false
  const { w, h } = cropRect.value
  // 太小的选框视为无效
  if (Math.abs(w) < 10 || Math.abs(h) < 10) {
    hasCrop.value = false
    drawScene()
  }
}

// ── 触摸支持 ──────────────────────────────────────────────────────────────
function getTouchPos(e: TouchEvent): { x: number; y: number } {
  const rect = canvasRef.value!.getBoundingClientRect()
  const t = e.touches[0]
  return { x: t.clientX - rect.left, y: t.clientY - rect.top }
}

function startDrawTouch(e: TouchEvent) {
  const pos = getTouchPos(e)
  drawStart = pos
  cropRect.value = { x: pos.x, y: pos.y, w: 0, h: 0 }
  isDrawing.value = true
  hasCrop.value = false
}

function onDrawTouch(e: TouchEvent) {
  if (!isDrawing.value) return
  const pos = getTouchPos(e)
  cropRect.value = {
    x: drawStart.x, y: drawStart.y,
    w: pos.x - drawStart.x, h: pos.y - drawStart.y,
  }
  hasCrop.value = true
  drawScene()
}

function clearCrop() {
  hasCrop.value = false
  cropRect.value = { x: 0, y: 0, w: 0, h: 0 }
  drawScene()
}

// ── 裁剪并生成 File ───────────────────────────────────────────────────────
function getCroppedFile(): Promise<File> {
  return new Promise((resolve, reject) => {
    const canvas = canvasRef.value!
    const img = originalImage!

    let rx: number, ry: number, rw: number, rh: number

    if (hasCrop.value) {
      const { x, y, w, h } = cropRect.value
      // 转换为正向矩形
      rx = (w < 0 ? x + w : x) / canvas.width * img.naturalWidth
      ry = (h < 0 ? y + h : y) / canvas.height * img.naturalHeight
      rw = Math.abs(w) / canvas.width * img.naturalWidth
      rh = Math.abs(h) / canvas.height * img.naturalHeight
    } else {
      // 未框选：使用全图
      rx = 0; ry = 0; rw = img.naturalWidth; rh = img.naturalHeight
    }

    // 创建离屏 canvas 裁剪
    const offscreen = document.createElement('canvas')
    offscreen.width = Math.round(rw)
    offscreen.height = Math.round(rh)
    const ctx = offscreen.getContext('2d')!
    ctx.drawImage(img, rx, ry, rw, rh, 0, 0, offscreen.width, offscreen.height)

    offscreen.toBlob(blob => {
      if (!blob) { reject(new Error('裁剪失败')); return }
      resolve(new File([blob], 'crop.jpg', { type: 'image/jpeg' }))
    }, 'image/jpeg', 0.95)
  })
}

// ── 识别 ──────────────────────────────────────────────────────────────────
async function recognize() {
  loading.value = true
  error.value = ''
  try {
    const file = await getCroppedFile()
    const result = await ocrImage(file)
    rawText.value = result.raw_text
    sentences.value = result.sentences.map(s => s.text)
  } catch (e: any) {
    error.value = e.message || '识别失败，请重试'
  } finally {
    loading.value = false
  }
}

// ── 句子操作 ──────────────────────────────────────────────────────────────
function deleteSentence(idx: number) { sentences.value.splice(idx, 1) }
function addSentence() {
  sentences.value.push('New sentence here.')
  editingIdx.value = sentences.value.length - 1
}

async function goRead() {
  if (sentences.value.length === 0) return
  try {
    const record = await saveRecord({ raw_text: rawText.value, sentences: sentences.value })
    store.loadData({ sentences: record.sentences, rawText: record.raw_text, recordId: record.id })
    router.push(`/read/${record.id}`)
  } catch {
    error.value = '保存失败，请重试'
  }
}
</script>

<style scoped>
/* 文件 input 视觉隐藏，放在 label 内部用绝对定位覆盖 */
.visually-hidden-input {
  position: absolute;
  top: 0; left: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
}

.home { display: flex; flex-direction: column; gap: 20px; }

/* ── 上传区 ── */
.upload-section { display: flex; flex-direction: column; gap: 16px; }
.drop-zone {
  position: relative;
  border: 2px dashed var(--gray-300);
  border-radius: var(--radius);
  padding: 48px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.drop-zone:hover, .drop-zone.dragging {
  border-color: var(--primary);
  background: var(--primary-light);
}
.drop-icon { font-size: 48px; }
.drop-title { font-size: 17px; font-weight: 600; color: var(--gray-700); }
.drop-hint  { font-size: 13px; color: var(--gray-500); }

/* ── 框选区 ── */
.crop-section { display: flex; flex-direction: column; gap: 12px; }

.crop-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: #fff;
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow);
  flex-wrap: wrap;
  gap: 8px;
}
.crop-hint { font-size: 13px; color: var(--gray-700); font-weight: 500; }
.crop-toolbar-right { display: flex; gap: 8px; }

.btn-sm {
  padding: 5px 14px;
  border-radius: 20px;
  border: 1.5px solid var(--gray-300);
  background: #fff;
  font-size: 12px;
  font-weight: 500;
  color: var(--gray-700);
  cursor: pointer;
  transition: all 0.15s;
}
.btn-sm:hover { border-color: var(--primary); color: var(--primary); }
.btn-clear-crop:hover { border-color: var(--red); color: var(--red); }

.canvas-wrap {
  width: 100%;
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow);
  background: #000;
  line-height: 0; /* 消除 canvas 下方间距 */
}

.crop-canvas {
  display: block;
  width: 100%;
  cursor: crosshair;
  touch-action: none; /* 禁止默认触摸滚动，让拖拽生效 */
}

/* ── 通用按钮 ── */
.btn-primary {
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 16px;
  font-weight: 600;
  padding: 14px;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-primary:hover:not(:disabled) { background: var(--primary-dark); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.spinner {
  width: 18px; height: 18px;
  border: 2px solid rgba(255,255,255,0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── 错误 ── */
.error-banner {
  background: #FFF3E0;
  border: 1px solid #FFB300;
  border-radius: var(--radius-sm);
  padding: 12px 16px;
  font-size: 14px;
  color: #E65100;
}

/* ── 识别结果 ── */
.result-section {
  background: #fff;
  border-radius: var(--radius);
  padding: 20px;
  box-shadow: var(--shadow);
}
.result-header {
  display: flex; align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.result-header h2 { font-size: 17px; font-weight: 700; }
.sentence-count {
  font-size: 13px; color: var(--gray-500);
  background: var(--gray-100);
  padding: 2px 10px; border-radius: 20px;
}
.result-hint { font-size: 13px; color: var(--gray-500); margin-bottom: 16px; }

.sentence-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 20px; }
.sentence-item {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 12px;
  background: var(--gray-50);
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-sm);
}
.sentence-no {
  font-size: 12px; font-weight: 700;
  color: var(--primary); background: var(--primary-light);
  width: 24px; height: 24px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.sentence-body { flex: 1; display: flex; align-items: flex-start; gap: 8px; }
.sentence-text {
  flex: 1; font-size: 15px; line-height: 1.6;
  color: var(--gray-900); cursor: pointer; word-break: break-word;
}
.sentence-text:hover { color: var(--primary-dark); }
.sentence-input {
  flex: 1; font-size: 15px; line-height: 1.6;
  border: 1.5px solid var(--primary); border-radius: 6px;
  padding: 6px 10px; resize: vertical; background: #fff; width: 100%;
}
.btn-edit, .btn-del {
  background: none; border: none; font-size: 16px;
  padding: 2px; cursor: pointer; opacity: 0.4;
  transition: opacity 0.15s; flex-shrink: 0;
}
.btn-edit:hover, .btn-del:hover { opacity: 1; }
.btn-add-sentence {
  background: none; border: 1.5px dashed var(--gray-300);
  border-radius: var(--radius-sm); padding: 10px;
  font-size: 14px; color: var(--gray-500); cursor: pointer; transition: all 0.15s;
}
.btn-add-sentence:hover { border-color: var(--primary); color: var(--primary); }

.action-row { display: flex; justify-content: center; }
.btn-read { max-width: 280px; font-size: 17px; padding: 16px; }
</style>
