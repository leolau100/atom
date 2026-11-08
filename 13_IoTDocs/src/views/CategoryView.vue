<template>
  <div v-if="cat">
    <router-link to="/" class="back">← 返回首页</router-link>
    <header class="head">
      <h1 class="grad">{{ cat.name }}</h1>
      <p>{{ cat.desc }}</p>
    </header>
    <div class="list">
      <router-link
        v-for="a in list"
        :key="a.slug"
        :to="`/a/${a.slug}`"
        class="item card"
      >
        <div class="item-top">
          <h3>{{ a.title }}</h3>
          <span class="arrow">→</span>
        </div>
        <span class="tag">{{ a.tag }}</span>
      </router-link>
    </div>
  </div>
  <div v-else class="empty">未找到该分类</div>
</template>

<script setup>
import { computed } from 'vue'
import { categoryByKey, articlesByCat } from '../data/articles.js'

const props = defineProps({ cat: String })
const cat = computed(() => categoryByKey(props.cat))
const list = computed(() => articlesByCat(props.cat))
</script>

<style scoped>
.back { color: var(--fg-dim); font-size: 14px; }
.back:hover { color: var(--fg); }
.head { padding: 20px 0 28px; }
.head h1 { font-size: 40px; margin: 0 0 8px; }
.head p { color: var(--fg-dim); margin: 0; }
.list { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 18px; }
.item { display: block; padding: 22px; }
.item-top { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.item h3 { margin: 0; font-size: 17px; line-height: 1.4; }
.item .arrow { color: var(--accent); }
.item:hover .arrow { transform: translateX(4px); }
.item .tag { margin-top: 14px; }
.empty { padding: 80px 0; text-align: center; color: var(--fg-dim); }
</style>
