<template>
  <div id="top">
    <!-- Hero -->
    <section class="hero">
      <h1>{{ about.name }}</h1>
      <p class="slogan">{{ about.slogan }}</p>
      <p class="bio">{{ about.bio }}</p>
    </section>

    <!-- 产品列表 -->
    <section id="products" class="block">
      <h2 class="block-title">产品</h2>
      <div class="grid">
        <a
          v-for="p in products"
          :key="p.name"
          class="card"
          :href="p.url"
          target="_blank"
          rel="noopener"
        >
          <div class="card-head">
            <span class="card-name">{{ p.name }}</span>
            <span class="badge" :class="p.status === '已上线' ? 'on' : 'wip'">{{ p.status }}</span>
          </div>
          <p class="card-tagline">{{ p.tagline }}</p>
          <p class="card-desc">{{ p.description }}</p>
          <div class="tags">
            <span v-for="t in p.tags" :key="t" class="tag">{{ t }}</span>
          </div>
          <div class="card-links">
            <span class="card-date">发布于 {{ p.published }}</span>
            <span class="lk">访问 ↗</span>
            <a v-if="p.github" :href="p.github" target="_blank" rel="noopener" @click.stop>GitHub ↗</a>
          </div>
        </a>
      </div>
    </section>

    <!-- 开发原则 -->
    <section id="principles" class="block">
      <h2 class="block-title">产品 / 开发原则</h2>
      <div class="principles">
        <div v-for="pr in principles" :key="pr.no" class="principle">
          <span class="pr-no">{{ String(pr.no).padStart(2, '0') }}</span>
          <div>
            <h3>{{ pr.title }}</h3>
            <p>{{ pr.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 博客 / 动态 -->
    <section id="blog" class="block">
      <h2 class="block-title">动态</h2>
      <ul class="posts">
        <li v-for="post in posts" :key="post.title" class="post">
          <span class="post-date">{{ post.date }}</span>
          <div>
            <h3>{{ post.title }}</h3>
            <p>{{ post.excerpt }}</p>
          </div>
        </li>
      </ul>
    </section>

    <!-- 关于 / 联系 -->
    <section id="about" class="block">
      <h2 class="block-title">关于 / 联系</h2>
      <div class="about">
        <p>{{ about.bio }}</p>
        <div class="about-links">
          <a v-for="l in about.links" :key="l.url" :href="l.url" target="_blank" rel="noopener" class="about-link">
            {{ l.label }} ↗
          </a>
          <a :href="`mailto:${about.email}`" class="about-link">邮件：{{ about.email }}</a>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { products, principles, posts, about } from '@/data/products.js'
</script>

<style scoped>
.hero { padding: 72px 0 32px; }
.hero h1 {
  font-size: 52px;
  margin: 0 0 10px;
  letter-spacing: -1px;
  background: linear-gradient(100deg, #14202e 18%, var(--accent2) 55%, var(--accent) 92%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.slogan { color: var(--accent2); font-weight: 600; margin: 0 0 14px; font-size: 18px; }
.bio { color: var(--fg-dim); max-width: 720px; margin: 0; font-size: 16px; }

.block { padding: 52px 0; border-top: 1px solid var(--border); }
.block-title {
  font-size: 26px;
  margin: 0 0 32px;
  position: relative;
  padding-left: 16px;
}
.block-title::before {
  content: '';
  position: absolute;
  left: 0; top: 4px; bottom: 4px;
  width: 5px; border-radius: 3px;
  background: linear-gradient(var(--accent2), var(--accent));
}

/* 产品卡片（白卡 + 科技点缀） */
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 24px; }
.card {
  display: block;
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 28px;
  box-shadow: var(--shadow);
  transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
}
.card:hover { transform: translateY(-4px); border-color: rgba(14, 165, 196, 0.5); box-shadow: 0 14px 36px rgba(14, 165, 196, 0.18); }
.card-head { display: flex; align-items: center; justify-content: space-between; }
.card-name { font-weight: 700; font-size: 20px; }
.badge { font-size: 12px; padding: 3px 10px; border-radius: 999px; }
.badge.on { background: rgba(7, 160, 80, 0.12); color: #067a3c; }
.badge.wip { background: rgba(20, 32, 46, 0.06); color: var(--fg-dim); }
.card-tagline { color: var(--accent2); margin: 12px 0 8px; font-size: 15px; font-weight: 500; }
.card-desc {
  color: var(--fg-dim);
  font-size: 15px;
  margin: 0 0 18px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: calc(15px * 1.8 * 2);
}
.tags { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; }
.tag { font-size: 12px; color: var(--fg-dim); background: rgba(14, 165, 196, 0.08); padding: 3px 10px; border-radius: 6px; }
.card-links { display: flex; align-items: center; gap: 18px; font-size: 14px; color: var(--accent2); }
.card-links .lk { color: var(--fg); }
.card-links a:hover { text-decoration: underline; }
.card-date { margin-right: auto; font-size: 13px; color: var(--fg-dim); }

/* 原则 */
.principles { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 28px 40px; }
.principle { display: flex; gap: 18px; align-items: flex-start; }
.pr-no {
  font-size: 32px; font-weight: 800; line-height: 1; min-width: 48px;
  background: linear-gradient(var(--accent2), var(--accent));
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
}
.principle h3 { margin: 0 0 6px; font-size: 18px; }
.principle p { margin: 0; color: var(--fg-dim); font-size: 15px; }

/* 动态 */
.posts { list-style: none; padding: 0; margin: 0; display: grid; gap: 22px; }
.post { display: flex; gap: 24px; align-items: flex-start; padding-bottom: 22px; border-bottom: 1px solid var(--border); }
.post:last-child { border-bottom: none; padding-bottom: 0; }
.post-date { color: var(--accent2); font-size: 14px; min-width: 100px; padding-top: 4px; }
.post h3 { margin: 0 0 6px; font-size: 18px; }
.post p { margin: 0; color: var(--fg-dim); font-size: 15px; }

/* 关于 */
.about p { color: var(--fg-dim); max-width: 720px; font-size: 16px; }
.about-links { display: flex; flex-wrap: wrap; gap: 16px; margin-top: 20px; }
.about-link {
  font-size: 15px; color: var(--accent2);
  border: 1px solid var(--border); border-radius: 10px; padding: 10px 18px;
  background: var(--bg-soft);
  transition: border-color 0.2s, box-shadow 0.2s;
}
.about-link:hover { border-color: rgba(14, 165, 196, 0.5); box-shadow: 0 8px 24px rgba(14, 165, 196, 0.14); }
</style>
