import { createApp, ref } from 'vue';

const toasts = ref([]);
let _id = 0;

export function useToast() {
  const show = (msg, type = 'success') => {
    const id = ++_id;
    toasts.value = [...toasts.value, { id, msg, type }];
    setTimeout(() => { toasts.value = toasts.value.filter(t => t.id !== id); }, 3000);
  };
  return { toasts, show };
}

// Mount toast container
export function mountToast() {
  const div = document.createElement('div');
  div.className = 'toast-container';
  document.body.appendChild(div);
  createApp({
    setup() {
      const { toasts } = useToast();
      return { toasts };
    },
    template: `<transition-group name="fade" tag="div"><div v-for="t in toasts" :key="t.id" :class="['toast','toast-'+t.type]"><span class="toast-icon">{{ t.type==='success'?'✅':t.type==='error'?'❌':'ℹ️' }}</span>{{ t.msg }}</div></transition-group>`
  }).mount(div);
}
