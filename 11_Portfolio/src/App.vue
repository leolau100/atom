<template>
  <div class="site">
    <header class="nav">
      <a class="brand" href="#top">
        <svg class="brand-logo" viewBox="0 0 64 64" width="30" height="30" aria-hidden="true">
          <defs>
            <linearGradient id="brandG" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#2bd4ff"/>
              <stop offset="100%" stop-color="#07c160"/>
            </linearGradient>
          </defs>
          <rect width="64" height="64" rx="14" fill="#0b1220"/>
          <g fill="url(#brandG)">
            <circle cx="23" cy="26" r="8"/>
            <circle cx="42" cy="40" r="8" opacity="0.85"/>
          </g>
          <path d="M23 26 L42 40" stroke="url(#brandG)" stroke-width="2.4" stroke-linecap="round" opacity="0.6"/>
        </svg>
        <span>DoublePoint</span>
      </a>
    </header>

    <main>
      <Home />
    </main>

    <footer class="foot">
      <span>© {{ year }} DoublePoint</span>
      <span class="dot">·</span>
      <span>Build something we like and want.</span>
    </footer>
  </div>
</template>

<script setup>
import Home from '@/views/Home.vue'
const year = new Date().getFullYear()
</script>

<style>
:root {
  --bg: #eef2f7;
  --bg-soft: #ffffff;
  --fg: #14202e;
  --fg-dim: #5b6675;
  --accent: #07a050;
  --accent2: #0ea5c4;
  --border: rgba(14, 165, 196, 0.18);
  --radius: 16px;
  --shadow: 0 10px 30px rgba(30, 60, 90, 0.10);
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  color: var(--fg);
  font-family: 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', system-ui, sans-serif;
  line-height: 1.8;
  -webkit-font-smoothing: antialiased;
  background-color: var(--bg);
  background-image:
    linear-gradient(rgba(14, 165, 196, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(14, 165, 196, 0.06) 1px, transparent 1px),
    radial-gradient(1000px 620px at 12% -12%, rgba(7, 193, 96, 0.20), transparent 60%),
    radial-gradient(900px 560px at 92% -4%, rgba(14, 165, 196, 0.20), transparent 58%),
    radial-gradient(1200px 720px at 50% 116%, rgba(99, 102, 241, 0.16), transparent 60%);
  background-size: 46px 46px, 46px 46px, 100% 100%, 100% 100%, 100% 100%;
  background-repeat: repeat, repeat, no-repeat, no-repeat, no-repeat;
  background-attachment: fixed;
  position: relative;
}
/* 顶部流动扫描光带（亮色版，低透明度不抢内容） */
body::before {
  content: '';
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  background: linear-gradient(115deg, transparent 32%, rgba(14, 165, 196, 0.06) 48%, rgba(7, 193, 96, 0.06) 52%, transparent 70%);
  background-size: 220% 220%;
  animation: scan 9s ease-in-out infinite;
}
@keyframes scan {
  0% { background-position: 0% 0%; }
  50% { background-position: 100% 100%; }
  100% { background-position: 0% 0%; }
}
a { color: inherit; text-decoration: none; }

.site { max-width: 1280px; margin: 0 auto; padding: 0 40px; position: relative; z-index: 1; }

.nav {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 0;
  background: transparent;
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--border);
}
.brand { display: inline-flex; align-items: center; gap: 10px; font-weight: 800; font-size: 19px; letter-spacing: 0.5px; }
.brand-logo { border-radius: 8px; box-shadow: 0 2px 10px rgba(14, 165, 196, 0.25); flex-shrink: 0; }

.foot {
  margin-top: 80px;
  padding: 32px 0 48px;
  border-top: 1px solid var(--border);
  color: var(--fg-dim);
  font-size: 14px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.foot .dot { opacity: 0.5; }
</style>
