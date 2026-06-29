import { createApp, ref } from 'vue';
import http from './api.js';
import { useToast, mountToast } from './toast.js';
import Dashboard from './pages/dashboard.js';

const user = ref({ username: 'Guest', role: 'guest' });
const loading = ref(false);

// ---- Pages cache (others loaded dynamically) ----
const pages = { dashboard: Dashboard };
async function loadPage(name) {
  if (pages[name]) return pages[name];
  const m = await import(`./pages/${name}.js`);
  pages[name] = m.default;
  return m.default;
}

// ---- Sidebar ----
const sidebar = {
  props: ['active', 'user'],
  emits: ['nav'],
  template: `
  <aside class="sidebar">
    <div class="sidebar-logo"><span class="sidebar-logo-icon">⚙</span>Service XYZ</div>
    <nav class="sidebar-nav">
      <div v-for="item in items" :key="item.key"
        :class="['sidebar-item',{active:active===item.key}]"
        @click="$emit('nav',item.key)">
        <span class="sidebar-item-icon">{{item.icon}}</span>
        <span>{{item.label}}</span>
        <span class="nav-dot"></span>
      </div>
    </nav>
    <div class="sidebar-footer">
      <div class="sidebar-avatar">{{(user.username||'G')[0].toUpperCase()}}</div>
      <span>{{user.username||'Guest'}}</span>
    </div>
  </aside>`,
  data() {
    return { items: [
      { key: 'dashboard', label: '数据中心', icon: '📊' },
      { key: 'dispatch', label: '调度任务', icon: '⚡' },
      { key: 'schedule', label: '定时任务', icon: '⏰' },
    ]};
  }
};

// ---- Modal ----
const modalBox = {
  props: ['title', 'visible'],
  emits: ['close'],
  template: `
  <div v-if="visible" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-box">
      <div class="modal-header">
        <h2>{{title}}</h2>
        <button class="modal-close" @click="$emit('close')">✕</button>
      </div>
      <slot></slot>
    </div>
  </div>`
};

// ---- App ----
const App = {
  template: `
  <div class="app-layout">
    <sidebar :active="currentPage" :user="user" @nav="switchPage" />
    <component :is="pageComp" :key="currentPage" />
  </div>`,
  setup() {
    const currentPage = ref('dashboard');
    const pageComp = ref(Dashboard);

    async function switchPage(key) {
      currentPage.value = key;
      pageComp.value = await loadPage(key);
    }

    return { loading, user, currentPage, pageComp, switchPage };
  }
};

// ---- Mount ----
const app = createApp(App);
app.component('sidebar', sidebar);
app.component('modal-box', modalBox);
app.provide('http', http);
app.provide('user', user);
app.provide('useToast', useToast);
mountToast();
app.mount('#app');
