import { ref, inject } from 'vue';

export default {
  template: `
  <div class="login-page">
    <form class="login-card" @submit.prevent="onSubmit">
      <h1>Service XYZ</h1>
      <div class="subtitle">API Management Console</div>
      <div v-if="error" class="login-error">{{error}}</div>
      <div class="form-group">
        <label class="form-label">账号</label>
        <input class="form-input" v-model="username" placeholder="admin" required />
      </div>
      <div class="form-group">
        <label class="form-label">密码</label>
        <input class="form-input" type="password" v-model="password" placeholder="输入密码" required />
      </div>
      <button class="btn btn-primary btn-lg" type="submit" :disabled="submitting" style="width:100%;margin-top:4px">
        {{submitting?'登录中...':'登 录'}}
      </button>
    </form>
  </div>`,
  setup(props, { emit }) {
    const username = ref('admin');
    const password = ref('');
    const error = ref('');
    const submitting = ref(false);
    const http = inject('http');
    const userRef = inject('user');

    async function onSubmit() {
      error.value = ''; submitting.value = true;
      try {
        const r = await http.post('/service/zyx/auth/login', {
          username: username.value,
          password: password.value
        });
        localStorage.setItem('token', r.data.data.token);
        userRef.value = r.data.data.user;
        emit('login');
      } catch (e) {
        error.value = e.response?.data?.detail || '登录失败';
      } finally {
        submitting.value = false;
      }
    }
    return { username, password, error, submitting, onSubmit };
  }
};
