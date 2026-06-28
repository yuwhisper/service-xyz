import { ref, reactive, inject, onMounted } from 'vue';

export default {
  template: `
  <div class="main-content">
    <div class="page-header" style="display:flex;justify-content:space-between;align-items:flex-start">
      <div><h1>定时任务</h1><p>按 Cron 表达式定时自动调用 API</p></div>
      <button class="btn btn-primary" @click="openCreate">+ 创建任务</button>
    </div>
    <div class="card">
      <div v-if="loading" class="empty-state"><p>加载中...</p></div>
      <div v-else-if="!schedules.length" class="empty-state"><div class="empty-state-icon">⏰</div><p>暂无定时任务，点击上方按钮创建</p></div>
      <div v-else class="table-wrap">
        <table>
          <thead><tr><th>任务名称</th><th>关联 API</th><th>Cron 表达式</th><th>状态</th><th>上次执行</th><th style="width:140px">操作</th></tr></thead>
          <tbody>
            <tr v-for="s in schedules" :key="s.id">
              <td style="font-weight:500">{{s.name}}</td>
              <td style="font-size:12px">{{getApiName(s.api_id)}}</td>
              <td><code style="background:#f5f5f7;padding:3px 8px;border-radius:4px;font-size:12px;font-family:monospace">{{s.cron_expression}}</code></td>
              <td>
                <span :class="['badge-status',s.enabled?'st-published':'st-deprecated']" style="cursor:pointer" @click="toggle(s)">
                  <span :class="['status-dot',s.enabled?'green':'red']"></span>{{s.enabled?'启用':'停用'}}
                </span>
              </td>
              <td style="font-size:12px;color:#86909c">{{s.last_run_at?new Date(s.last_run_at).toLocaleString():'未执行'}}</td>
              <td>
                <button class="btn btn-ghost btn-sm" @click="openEdit(s)">编辑</button>
                <button class="btn btn-danger btn-sm" style="margin-left:4px" @click="remove(s.id)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Form Modal -->
    <modal-box :title="editingId?'编辑任务':'创建任务'" :visible="showForm" @close="showForm=false">
      <div class="form-group"><label class="form-label">任务名称</label><input class="form-input" v-model="form.name" placeholder="例：每日数据同步"/></div>
      <div class="form-group"><label class="form-label">关联 API</label>
        <select class="form-select" v-model="form.api_id"><option value="">-- 选择 API --</option><option v-for="a in apis" :value="a.id">{{a.method}} {{a.path}} - {{a.name}}</option></select>
      </div>
      <div class="form-group"><label class="form-label">Cron 表达式</label><input class="form-input" v-model="form.cron_expression" placeholder="0 0 * * *"/><div class="cron-helper">分 时 日 月 周 · 0 9 * * * = 每天9点 · */30 * * * * = 每30分钟</div></div>
      <div class="form-group"><label class="form-label">参数 (JSON)</label><textarea class="form-textarea" v-model="form.params" rows="3" placeholder='{"key":"value"}'></textarea></div>
      <div class="modal-footer">
        <button class="btn btn-ghost" @click="showForm=false">取消</button>
        <button class="btn btn-primary" @click="save">保存</button>
      </div>
    </modal-box>
  </div>`,
  setup() {
    const http = inject('http');
    const { show } = inject('useToast')();
    const schedules = ref([]); const apis = ref([]); const loading = ref(true);
    const showForm = ref(false); const editingId = ref(null);
    const form = reactive({ api_id:'', name:'', cron_expression:'0 0 * * *', params:'{}' });

    async function fetch() {
      loading.value = true;
      try {
        const [sr, ar] = await Promise.all([http.get('/service/zyx/schedules'), http.get('/service/zyx/apis?project_id=1')]);
        schedules.value = sr.data.data; apis.value = ar.data.data;
      } catch(e){} finally { loading.value = false; }
    }
    onMounted(fetch);

    function openCreate() { Object.assign(form, { api_id:'', name:'', cron_expression:'0 0 * * *', params:'{}' }); editingId.value = null; showForm.value = true; }
    function openEdit(s) { Object.assign(form, { api_id:s.api_id, name:s.name, cron_expression:s.cron_expression, params:s.params }); editingId.value = s.id; showForm.value = true; }
    async function save() {
      const body = { ...form, api_id: parseInt(form.api_id), enabled: 1 };
      try {
        if (editingId.value) await http.put(`/service/zyx/schedules/${editingId.value}`, body);
        else await http.post('/service/zyx/schedules', body);
        showForm.value = false; fetch(); show('保存成功');
      } catch(e) { show('保存失败: '+(e.response?.data?.detail||e.message),'error'); }
    }
    async function remove(id) { if(!confirm('确认删除？')) return; try { await http.delete(`/service/zyx/schedules/${id}`); fetch(); show('已删除'); } catch(e){ show('删除失败','error'); } }
    async function toggle(s) {
      try {
        await http.put(`/service/zyx/schedules/${s.id}`, { api_id:s.api_id, name:s.name, cron_expression:s.cron_expression, params:s.params, enabled:s.enabled?0:1 });
        fetch();
      } catch(e){ show('操作失败','error'); }
    }
    function getApiName(id) { const a = apis.value.find(x=>x.id===id); return a?`${a.method} ${a.path}`:`#${id}`; }
    return { schedules, apis, loading, showForm, editingId, form, openCreate, openEdit, save, remove, toggle, getApiName };
  }
};
