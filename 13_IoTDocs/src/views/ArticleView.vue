<template>
  <div v-if="meta" class="layout">
    <aside class="side">
      <router-link to="/" class="back">← 首页</router-link>
      <div class="side-cat">{{ catName }}</div>
      <nav class="side-nav">
        <router-link
          v-for="a in siblings"
          :key="a.slug"
          :to="`/a/${a.slug}`"
          class="side-link"
          :class="{ active: a.slug === meta.slug }"
        >{{ a.title }}</router-link>
      </nav>
    </aside>

    <article class="content">
      <div v-if="loading" class="loading">加载中…</div>
      <div v-else class="md-body" v-html="html"></div>
    </article>
  </div>
  <div v-else class="empty">未找到该文章</div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import MarkdownIt from 'markdown-it'
import {
  articleBySlug, articlesByCat, categoryByKey,
} from '../data/articles.js'

const md = new MarkdownIt({ html: true, linkify: true, typographer: true, breaks: false })
const route = useRoute()
const BASE = import.meta.env.BASE_URL

const html = ref('')
const meta = ref(null)
const loading = ref(true)

const catName = computed(() => (meta.value ? categoryByKey(meta.value.cat)?.name : ''))
const siblings = computed(() => (meta.value ? articlesByCat(meta.value.cat) : []))

function rewriteImages(src, slug) {
  const base = BASE + 'iot-content/' + slug + '/'
  return src.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (m, alt, url) => {
    const u = url.trim()
    if (/^(https?:|data:|\/\/|#)/.test(u)) return m
    const fixed = u.startsWith('./') ? u.slice(2) : u
    return `![${alt}](${base}${fixed})`
  })
}

async function load(slug) {
  const a = articleBySlug(slug)
  if (!a) { meta.value = null; loading.value = false; return }
  meta.value = a
  loading.value = true
  try {
    const res = await fetch(BASE + a.file)
    const text = await res.text()
    html.value = md.render(rewriteImages(text, slug))
  } catch (e) {
    html.value = '<p>加载失败：' + e.message + '</p>'
  }
  loading.value = false
}

watch(() => route.params.slug, (s) => load(s), { immediate: true })
</script>

<style scoped>
.layout { display: grid; grid-template-columns: 240px 1fr; gap: 40px; align-items: start; }
.side {
  position: sticky; top: 84px;
  border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--panel); padding: 20px;
}
.back { color: var(--fg-dim); font-size: 13px; }
.side-cat { margin: 16px 0 10px; font-size: 13px; color: var(--accent); letter-spacing: 1px; }
.side-nav { display: flex; flex-direction: column; gap: 4px; }
.side-link {
  font-size: 14px; color: var(--fg-dim);
  padding: 7px 10px; border-radius: 8px; transition: background 0.15s, color 0.15s;
}
.side-link:hover { background: rgba(8, 145, 178, 0.09); color: var(--fg); }
.side-link.active { background: rgba(8, 145, 178, 0.14); color: var(--fg); font-weight: 600; }
.content { min-width: 0; }
.loading { color: var(--fg-dim); padding: 40px 0; }
.empty { padding: 80px 0; text-align: center; color: var(--fg-dim); }
@media (max-width: 820px) {
  .layout { grid-template-columns: 1fr; }
  .side { position: static; }
}
</style>
