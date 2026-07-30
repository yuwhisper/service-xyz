import { ref, reactive, computed, inject } from 'vue';

function errHint(e) {
  const detail = e?.response?.data?.detail;
  if (detail && typeof detail === 'object') return detail.hint || JSON.stringify(detail);
  if (detail != null) return String(detail);
  return e?.message || '请求失败';
}

export default {
  template: `
  <div class="main-content">
    <div class="page-header">
      <h1>每日数据补全</h1>
      <p>Key 在服务端 .env，本页不展示密钥</p>
    </div>

    <div class="card">
      <div class="card-header"><div class="card-title">调度目标</div></div>
      <div class="form-group">
        <label class="form-label">robotUuid<span class="form-req">*</span></label>
        <input class="form-input" v-model="form.robotUuid" placeholder="应用 UUID"/>
      </div>
      <div class="form-group">
        <label class="form-label">accountName <span style="color:var(--c-sub);font-weight:400;font-size:12px">条件必填</span></label>
        <input class="form-input" v-model="form.accountName" placeholder="执行账号名"/>
      </div>
      <div class="form-group">
        <label class="form-label">robotClientGroupUuid <span style="color:var(--c-sub);font-weight:400;font-size:12px">条件必填</span></label>
        <input class="form-input" v-model="form.robotClientGroupUuid" placeholder="机器人分组 UUID"/>
        <div class="cron-helper">账号与分组二选一，都填以分组为准</div>
      </div>
    </div>

    <div class="card">
      <div class="card-header"><div class="card-title">应用参数</div></div>
      <div class="form-group">
        <label class="form-label">开始日期</label>
        <input class="form-input" type="date" v-model="form.startDate"/>
      </div>
      <div class="form-group">
        <label class="form-label">结束日期</label>
        <input class="form-input" type="date" v-model="form.endDate"/>
      </div>
    </div>

    <div class="card">
      <div class="card-header"><div class="card-title">可选调度</div></div>
      <div class="form-group">
        <label class="form-label">waitTimeoutSeconds</label>
        <input class="form-input" type="number" v-model="form.waitTimeoutSeconds" placeholder="600"/>
      </div>
      <div class="form-group">
        <label class="form-label">runTimeout</label>
        <input class="form-input" type="number" v-model="form.runTimeout" placeholder="不传则不限制"/>
      </div>
      <div class="form-group">
        <label class="form-label">priority</label>
        <select class="form-select" v-model="form.priority">
          <option value="low">low</option>
          <option value="middle">middle</option>
          <option value="high">high</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">executeScope</label>
        <select class="form-select" v-model="form.executeScope">
          <option value="any">any</option>
          <option value="all">all</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label" style="display:flex;align-items:center;gap:8px;cursor:pointer">
          <input type="checkbox" v-model="form.useIdempotent"/>
          useIdempotent
        </label>
      </div>
    </div>

    <div style="display:flex;gap:10px;margin-bottom:16px">
      <button class="btn btn-primary" :disabled="busy" @click="startJob">启动</button>
      <button class="btn btn-ghost" :disabled="busy || !jobUuid" @click="refreshStatus">刷新状态</button>
    </div>

    <div class="card">
      <div class="card-header"><div class="card-title">结果</div></div>
      <div v-if="hint" style="color:var(--c-red);font-size:13px;margin-bottom:12px;font-weight:500">{{hint}}</div>
      <div class="form-group">
        <label class="form-label">jobUuid</label>
        <div style="font-family:monospace;font-size:13px">{{jobUuid || '—'}}</div>
      </div>
      <div class="form-group">
        <label class="form-label">status / statusName</label>
        <div style="font-size:13px">{{statusText}}</div>
      </div>
      <div class="form-group" style="margin-bottom:0">
        <label class="form-label">原始响应</label>
        <pre class="log-response">{{rawJson || '(无)'}}</pre>
      </div>
    </div>
  </div>`,
  setup() {
    const http = inject('http');
    const { show } = inject('useToast')();

    const form = reactive({
      robotUuid: '',
      accountName: '',
      robotClientGroupUuid: '',
      startDate: '',
      endDate: '',
      waitTimeoutSeconds: 600,
      runTimeout: '',
      priority: 'middle',
      executeScope: 'any',
      useIdempotent: true,
    });

    const busy = ref(false);
    const jobUuid = ref('');
    const hint = ref('');
    const status = ref('');
    const statusName = ref('');
    const rawJson = ref('');

    const statusText = computed(() => {
      if (!status.value && !statusName.value) return '—';
      return `${status.value || '—'}${statusName.value ? ' / ' + statusName.value : ''}`;
    });

    function applyResult(data) {
      const d = data || {};
      if (d.jobUuid) jobUuid.value = d.jobUuid;
      if (d.status != null) status.value = d.status;
      if (d.statusName != null) statusName.value = d.statusName;
      rawJson.value = JSON.stringify(d, null, 2);
    }

    async function startJob() {
      const robotUuid = (form.robotUuid || '').trim();
      if (!robotUuid) {
        show('请填写 robotUuid', 'error');
        return;
      }
      const accountName = (form.accountName || '').trim();
      const robotClientGroupUuid = (form.robotClientGroupUuid || '').trim();
      if (!accountName && !robotClientGroupUuid) {
        show('请填写 accountName 或 robotClientGroupUuid', 'error');
        return;
      }

      const params = [];
      if ((form.startDate || '').trim()) {
        params.push({ name: '开始日期', value: form.startDate.trim(), type: 'str' });
      }
      if ((form.endDate || '').trim()) {
        params.push({ name: '结束日期', value: form.endDate.trim(), type: 'str' });
      }

      const body = {
        robotUuid,
        accountName: accountName || undefined,
        robotClientGroupUuid: robotClientGroupUuid || undefined,
        params: params.length ? params : undefined,
        waitTimeoutSeconds: Number(form.waitTimeoutSeconds) || 600,
        priority: form.priority,
        executeScope: form.executeScope,
        useIdempotent: !!form.useIdempotent,
      };
      const rt = form.runTimeout === '' || form.runTimeout == null ? null : Number(form.runTimeout);
      if (rt != null && !Number.isNaN(rt)) body.runTimeout = rt;

      busy.value = true;
      hint.value = '';
      try {
        const { data } = await http.post('/service/zyx/yingdao/job/start', body);
        const payload = data?.data ?? data;
        applyResult(payload);
        if (payload?.jobUuid) jobUuid.value = payload.jobUuid;
        show('启动成功');
      } catch (e) {
        hint.value = errHint(e);
        show(hint.value, 'error');
      } finally {
        busy.value = false;
      }
    }

    async function refreshStatus() {
      if (!jobUuid.value) return;
      busy.value = true;
      hint.value = '';
      try {
        const { data } = await http.post('/service/zyx/yingdao/job/query', { jobUuid: jobUuid.value });
        const payload = data?.data ?? data;
        applyResult(payload);
        show('状态已刷新');
      } catch (e) {
        hint.value = errHint(e);
        show(hint.value, 'error');
      } finally {
        busy.value = false;
      }
    }

    return { form, busy, jobUuid, hint, rawJson, statusText, startJob, refreshStatus };
  }
};
