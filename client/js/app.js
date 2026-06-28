import { createApp, ref } from 'vue';
import http from './api.js';
import { useToast, mountToast } from './toast.js';
import LoginPage from './pages/login.js';
import Dashboard from './pages/dashboard.js';

// ---- Auth ----
const user = ref(null);
const loading = ref(true);

const token = localStorage.getItem('token');
if (token) {
  http.get('/service/zyx/auth/user/me')
    .then(r => user.value = r.data.data)
    .catch(() => localStorage.removeItem('token'))
    .finally(() => loading.value = false);
} else {
  loading.value = false;
}

function logout() { localStorage.removeItem('token'); user.value = null; }

// ---- Pages cache (others loaded dynamically) ----
const pages = { dashboard: Dashboard, login: LoginPage };
async function loadPage(name) {
  if (pages[name]) return pages[name];
  const m = await import(`./pages/${name}.js`);
  pages[name] = m.default;
  return m.default;
}

// ---- Sidebar ----
const sidebar = {
  props: ['active', 'user'],
  emits: ['nav', 'logout'],
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
      <div class="sidebar-avatar">{{(user.username||'A')[0].toUpperCase()}}</div>
      <span>{{user.username||'User'}}</span>
      <button class="sidebar-logout" @click="$emit('logout')">退出</button>
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
  components: { LoginPage },
  template: `
  <div v-if="loading" style="display:flex;align-items:center;justify-content:center;height:100vh;color:#86909c;font-size:14px">Loading...</div>
  <LoginPage v-else-if="!user" @login="onLogin" />
  <div v-else class="app-layout">
    <sidebar :active="currentPage" :user="user" @nav="switchPage" @logout="logout" />
    <component :is="pageComp" :key="currentPage" />
  </div>`,
  setup() {
    const currentPage = ref('dashboard');
    const pageComp = ref(Dashboard);

    async function onLogin() {
      currentPage.value = 'dashboard';
      pageComp.value = Dashboard;
    }
    async function switchPage(key) {
      currentPage.value = key;
      pageComp.value = await loadPage(key);
    }

    return { loading, user, currentPage, pageComp, onLogin, switchPage, logout, LoginPage };
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
