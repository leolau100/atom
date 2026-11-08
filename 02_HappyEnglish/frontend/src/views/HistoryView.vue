<template>
  <div class="history">
    <div class="history-header">
      <h2>学习记录</h2>
      <span class="count">共 {{ records.length }} 条</span>
    </div>

    <div v-if="loading" class="loading">
      <div class="spinner"></div>
    </div>

    <div v-else-if="records.length === 0" class="empty">
      <p>📭 还没有学习记录</p>
      <RouterLink to="/" class="btn-go">去识别第一张图片 →</RouterLink>
    </div>

    <div v-else class="record-list">
      <div
        v-for="record in records"
        :key="record.id"
        class="record-card"
        @click="openRecord(record.id)"
      >
        <div class="record-body">
          <p class="record-title">{{ record.title }}</p>
          <p class="record-meta">
            <span>{{ record.sentences.length }} 个句子</span>
            <span>·</span>
            <span>{{ formatDate(record.created_at) }}</span>
          </p>
          <p class="record-preview">{{ record.sentences[0]?.text || '' }}</p>
        </div>
        <div class="record-actions" @click.stop>
          <button class="btn-read" @click="openRecord(record.id)" title="阅读">▶️</button>
          <button class="btn-del" @click="confirmDelete(record.id)" title="删除">🗑️</button>
        </div>
      </div>
    </div>

    <!-- 确认删除 -->
    <Transition name="fade">
      <div v-if="deleteId !== null" class="modal-overlay" @click.self="deleteId = null">
        <div class="modal">
          <p>确认删除这条记录？</p>
          <div class="modal-actions">
            <button class="btn-cancel" @click="deleteId = null">取消</button>
            <button class="btn-confirm-del" @click="doDelete">删除</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getRecords, deleteRecord } from '@/api'
import type { RecordResponse } from '@/api'
import { useReadingStore } from '@/stores/reading'

const router = useRouter()
const store = useReadingStore()
const records = ref<RecordResponse[]>([])
const loading = ref(false)
const deleteId = ref<number | null>(null)

onMounted(fetchRecords)

async function fetchRecords() {
  loading.value = true
  try {
    records.value = await getRecords()
  } finally {
    loading.value = false
  }
}

function openRecord(id: number) {
  const record = records.value.find(r => r.id === id)
  if (record) {
    store.loadData({
      sentences: record.sentences,
      rawText: record.raw_text,
      recordId: record.id,
    })
  }
  router.push(`/read/${id}`)
}

function confirmDelete(id: number) {
  deleteId.value = id
}

async function doDelete() {
  if (deleteId.value === null) return
  await deleteRecord(deleteId.value)
  records.value = records.value.filter(r => r.id !== deleteId.value)
  deleteId.value = null
}

function formatDate(iso: string) {
  const d = new Date(iso)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return `${d.getMonth() + 1}月${d.getDate()}日`
}
</script>

<style scoped>
.history { display: flex; flex-direction: column; gap: 16px; }

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.history-header h2 { font-size: 20px; font-weight: 700; }
.count { font-size: 13px; color: var(--gray-500); }

.loading {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}
.spinner {
  width: 32px; height: 32px;
  border: 3px solid var(--gray-200);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 0;
  color: var(--gray-500);
  font-size: 15px;
}
.btn-go {
  color: var(--primary);
  font-weight: 600;
  text-decoration: none;
}

.record-list { display: flex; flex-direction: column; gap: 10px; }

.record-card {
  background: #fff;
  border-radius: var(--radius);
  padding: 16px;
  box-shadow: var(--shadow);
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  transition: box-shadow 0.15s, transform 0.15s;
}
.record-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}
.record-body { flex: 1; min-width: 0; }
.record-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--gray-900);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}
.record-meta {
  display: flex;
  gap: 6px;
  font-size: 12px;
  color: var(--gray-500);
  margin-bottom: 6px;
}
.record-preview {
  font-size: 13px;
  color: var(--gray-700);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.record-actions { display: flex; gap: 4px; flex-shrink: 0; }
.btn-read, .btn-del {
  background: none;
  border: 1.5px solid var(--gray-200);
  border-radius: 8px;
  width: 36px; height: 36px;
  font-size: 16px;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.15s;
}
.btn-read:hover { border-color: var(--primary); background: var(--primary-light); }
.btn-del:hover { border-color: var(--red); background: #FFEBEE; }

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
  padding: 20px;
}
.modal {
  background: #fff;
  border-radius: var(--radius);
  padding: 24px;
  max-width: 280px;
  width: 100%;
  text-align: center;
  box-shadow: var(--shadow-md);
}
.modal p { font-size: 16px; margin-bottom: 20px; }
.modal-actions { display: flex; gap: 12px; }
.btn-cancel, .btn-confirm-del {
  flex: 1;
  padding: 10px;
  border-radius: var(--radius-sm);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  border: none;
}
.btn-cancel { background: var(--gray-100); color: var(--gray-700); }
.btn-confirm-del { background: var(--red); color: #fff; }
</style>
