<template>
  <section class="hero">
    <div class="eyebrow">DOCUMENTATION · 2026</div>
    <h1>物联网技术 <span class="grad">文档中心</span></h1>
    <p class="lead">
      围绕开源物联网平台、工业总线协议与工控工具链，沉淀可检索、可落地的一手技术资料。
    </p>
    <div class="stats">
      <div class="stat"><b>{{ articles.length }}</b><span>篇核心文档</span></div>
      <div class="stat"><b>{{ categories.length }}</b><span>大主题</span></div>
      <div class="stat"><b>进行中</b><span>IoT 产品孵化</span></div>
    </div>
  </section>

  <section class="cats">
    <router-link
      v-for="c in categories"
      :key="c.key"
      :to="`/c/${c.key}`"
      class="cat card"
    >
      <div class="cat-top">
        <h3>{{ c.name }}</h3>
        <span class="arrow">→</span>
      </div>
      <p>{{ c.desc }}</p>
      <span class="tag">{{ articlesByCat(c.key).length }} 篇</span>
    </router-link>
  </section>
</template>

<script setup>
import { categories, articles, articlesByCat } from '../data/articles.js'
</script>

<style scoped>
.hero { padding: 40px 0 24px; }
.eyebrow {
  font-size: 13px; letter-spacing: 3px; color: var(--accent);
  font-weight: 600; margin-bottom: 14px;
}
.hero h1 { font-size: clamp(38px, 6vw, 64px); margin: 0 0 18px; letter-spacing: -1px; line-height: 1.05; }
.lead { color: var(--fg-dim); max-width: 640px; font-size: 17px; margin: 0 0 28px; }
.stats { display: flex; gap: 36px; }
.stat { display: flex; flex-direction: column; }
.stat b { font-size: 26px; font-weight: 800; }
.stat span { font-size: 13px; color: var(--fg-dim); }

.cats {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 20px;
  margin: 40px 0 20px;
}
.cat { display: block; padding: 26px; }
.cat-top { display: flex; align-items: center; justify-content: space-between; }
.cat h3 { margin: 0; font-size: 20px; }
.cat .arrow { color: var(--accent); font-size: 20px; transition: transform 0.2s; }
.cat:hover .arrow { transform: translateX(5px); }
.cat p { color: var(--fg-dim); font-size: 14px; margin: 14px 0 18px; min-height: 42px; }
</style>
