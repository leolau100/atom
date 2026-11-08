const BASE = '/api'

export interface SentenceItem {
  id: number
  text: string
  words: string[]
}

export interface OCRResponse {
  raw_text: string
  sentences: SentenceItem[]
}

export interface RecordResponse {
  id: number
  title: string
  raw_text: string
  sentences: SentenceItem[]
  created_at: string
}

// OCR：上传图片识别
export async function ocrImage(file: File): Promise<OCRResponse> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/ocr`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || '识别失败，请重试')
  }
  return res.json()
}

// TTS：获取朗读音频 URL（直接返回 URL 给 Audio 使用）
// speed: 0=超慢速, 1=慢速, 2=正常
export function getTtsUrl(text: string, speed = 1): string {
  return `${BASE}/tts?text=${encodeURIComponent(text)}&speed=${speed}`
}

// 保存记录
export async function saveRecord(data: {
  raw_text: string
  sentences: string[]
  title?: string
}): Promise<RecordResponse> {
  const res = await fetch(`${BASE}/records`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error('保存失败')
  return res.json()
}

// 获取历史记录列表
export async function getRecords(skip = 0, limit = 20): Promise<RecordResponse[]> {
  const res = await fetch(`${BASE}/records?skip=${skip}&limit=${limit}`)
  if (!res.ok) throw new Error('获取失败')
  return res.json()
}

// 获取单条记录
export async function getRecord(id: number): Promise<RecordResponse> {
  const res = await fetch(`${BASE}/records/${id}`)
  if (!res.ok) throw new Error('记录不存在')
  return res.json()
}

// 更新句子
export async function updateSentences(id: number, sentences: string[]): Promise<RecordResponse> {
  const res = await fetch(`${BASE}/records/${id}/sentences`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sentences }),
  })
  if (!res.ok) throw new Error('更新失败')
  return res.json()
}

// 删除记录
export async function deleteRecord(id: number): Promise<void> {
  await fetch(`${BASE}/records/${id}`, { method: 'DELETE' })
}

// 查词：音标 + 释义
export interface WordMeaning {
  cn: string
  example: string
}
export interface DictResult {
  word: string
  phonetic: string
  pos: string
  meanings: WordMeaning[]
}
export async function lookupWord(word: string): Promise<DictResult> {
  const res = await fetch(`${BASE}/dict/${encodeURIComponent(word)}`)
  if (!res.ok) throw new Error('查词失败')
  return res.json()
}
