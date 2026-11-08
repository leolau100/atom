<template>
  <div class="app">
    <header class="topbar">
      <div class="wrap row">
        <router-link to="/" class="brand">
          <span class="dot"></span>
          <span>IoT<span class="grad">·</span>Docs</span>
        </router-link>
        <nav class="nav">
          <router-link to="/">首页</router-link>
          <a href="https://github.com/leolau100" target="_blank" rel="noopener">GitHub</a>
        </nav>
      </div>
    </header>

    <main class="wrap">
      <router-view />
    </main>

    <footer>
      <div class="wrap">
        IoT Docs · 物联网与工业协议技术文档中心 · Build something we like and want.
      </div>
    </footer>
  </div>
</template>

<script setup>
// 根布局
</script>

<style scoped>
.app { min-height: 100vh; display: flex; flex-direction: column; }
.topbar .row { display: flex; align-items: center; justify-content: space-between; }
main.wrap { flex: 1; padding-top: 36px; padding-bottom: 40px; }
.nav a { margin-left: 4px; }
.nav a.router-link-active { color: var(--fg); }
</style>
