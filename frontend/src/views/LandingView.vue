<template>
  <div class="landing-page">
    <section class="hero">
      <p class="eyebrow">AI Agent Lab</p>
      <h1>一級入口首頁</h1>
      <p class="subtitle">從這裡分流到發票、PDF、管理與設定四個二級工作區。</p>
    </section>

    <section class="launcher-grid">
      <button class="launcher-card invoice" @click="go('/projects')">
        <span class="icon">🧾</span>
        <strong>發票憑證處理系統</strong>
        <small>進入既有專案、切圖、憑證貼章與 PDF 產出流程</small>
      </button>

      <button class="launcher-card pdf" @click="go('/pdf-tasks')">
        <span class="icon">📄</span>
        <strong>獨立 PDF 任務處理</strong>
        <small>上傳 PDF、查看狀態、進入編輯工作區</small>
      </button>

      <button class="launcher-card management" @click="go('/management')">
        <span class="icon">👥</span>
        <strong>人員 / 組別 / 印章管理</strong>
        <small>集中管理人員、組別、模板與蓋章配置</small>
      </button>

      <button class="launcher-card settings" @click="go('/settings')">
        <span class="icon">⚙️</span>
        <strong>系統設定</strong>
        <small>維護模型、參數與其他全域設定</small>
      </button>
    </section>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

const go = (path) => {
  router.push(path)
}
</script>

<style scoped>
.landing-page {
  min-height: calc(100vh - 72px);
  padding: 3rem 1.5rem 4rem;
  background:
    radial-gradient(circle at top left, rgba(66, 184, 131, 0.18), transparent 34%),
    radial-gradient(circle at top right, rgba(15, 118, 110, 0.18), transparent 28%),
    linear-gradient(180deg, #111827 0%, #0b1220 100%);
  color: #f3f4f6;
}

.hero {
  max-width: 960px;
  margin: 0 auto 2.5rem;
}

.eyebrow {
  margin: 0 0 0.75rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #7dd3fc;
  font-size: 0.78rem;
}

h1 {
  margin: 0;
  font-size: clamp(2.2rem, 5vw, 4.4rem);
  line-height: 1;
}

.subtitle {
  margin: 1rem 0 0;
  max-width: 42rem;
  color: #cbd5e1;
  font-size: 1.05rem;
}

.launcher-grid {
  max-width: 1100px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.launcher-card {
  text-align: left;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 1.5rem;
  padding: 1.5rem;
  min-height: 180px;
  background: rgba(15, 23, 42, 0.72);
  color: inherit;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.28);
  transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.launcher-card:hover {
  transform: translateY(-3px);
  border-color: rgba(125, 211, 252, 0.55);
  background: rgba(15, 23, 42, 0.88);
}

.launcher-card .icon {
  font-size: 1.8rem;
}

.launcher-card strong {
  font-size: 1.2rem;
}

.launcher-card small {
  color: #cbd5e1;
  line-height: 1.6;
}

.invoice { background: linear-gradient(160deg, rgba(30, 41, 59, 0.95), rgba(17, 24, 39, 0.88)); }
.pdf { background: linear-gradient(160deg, rgba(7, 89, 133, 0.88), rgba(15, 23, 42, 0.9)); }
.management { background: linear-gradient(160deg, rgba(22, 101, 52, 0.86), rgba(15, 23, 42, 0.9)); }
.settings { background: linear-gradient(160deg, rgba(88, 80, 236, 0.78), rgba(15, 23, 42, 0.9)); }

@media (max-width: 760px) {
  .landing-page {
    padding-top: 2rem;
  }

  .launcher-grid {
    grid-template-columns: 1fr;
  }
}
</style>