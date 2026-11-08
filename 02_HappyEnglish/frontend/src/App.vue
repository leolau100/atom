<template>
  <div class="app-layout">
    <!-- 顶部导航 -->
    <header class="app-header">
      <div class="header-inner">
        <!-- Logo -->
        <RouterLink to="/" class="logo">
          <div class="logo-badge">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L2 7l10 5 10-5-10-5z" fill="#fff" opacity=".9"/>
              <path d="M2 17l10 5 10-5M2 12l10 5 10-5" stroke="#fff" stroke-width="2" stroke-linecap="round"/>
            </svg>
          </div>
          <span class="logo-text">Happy English</span>
        </RouterLink>

        <!-- 导航 -->
        <nav class="nav">
          <RouterLink to="/" class="nav-link" :class="{ active: route.path === '/' }">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2a7 7 0 00-7 7c0 2.5 1.3 4.7 3.3 6L9 21h6l.7-6C17.7 13.7 19 11.5 19 9a7 7 0 00-7-7z" opacity=".3"/>
              <circle cx="12" cy="9" r="3" fill="currentColor"/>
              <rect x="8" y="21" width="8" height="2" rx="1" fill="currentColor"/>
            </svg>
            识别
          </RouterLink>
          <RouterLink to="/history" class="nav-link" :class="{ active: route.path === '/history' }">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <rect x="3" y="3" width="18" height="3" rx="1.5"/>
              <rect x="3" y="8" width="14" height="3" rx="1.5" opacity=".6"/>
              <rect x="3" y="13" width="10" height="3" rx="1.5" opacity=".4"/>
              <rect x="3" y="18" width="6" height="3" rx="1.5" opacity=".2"/>
            </svg>
            历史
          </RouterLink>
        </nav>
      </div>
    </header>

    <!-- 页面内容 -->
    <main class="app-main">
      <RouterView v-slot="{ Component }">
        <Transition name="fade" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </main>
  </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
const route = useRoute()
</script>

<style scoped>
.app-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* ── Header ── */
.app-header {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(255,255,255,0.6);
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 2px 20px rgba(0,0,0,0.06);
}

.header-inner {
  max-width: 720px;
  margin: 0 auto;
  padding: 0 20px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* Logo */
.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
}
.logo-badge {
  width: 38px;
  height: 38px;
  background: linear-gradient(135deg, #34C759 0%, #30A84E 100%);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 3px 10px rgba(52,199,89,0.4);
}
.logo-text {
  font-size: 18px;
  font-weight: 800;
  background: linear-gradient(135deg, #248A3D, #0A84FF);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -0.3px;
}

/* Nav */
.nav {
  display: flex;
  gap: 4px;
  background: var(--gray-100);
  padding: 3px;
  border-radius: 12px;
}
.nav-link {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  border-radius: 9px;
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-500);
  text-decoration: none;
  transition: all 0.18s;
}
.nav-link:hover { color: var(--gray-900); }
.nav-link.active {
  background: var(--white);
  color: var(--primary-dark);
  box-shadow: 0 1px 6px rgba(0,0,0,0.1);
}

/* Main */
.app-main {
  flex: 1;
  max-width: 720px;
  width: 100%;
  margin: 0 auto;
  padding: 20px 16px 40px;
}
</style>
