import { ref, reactive, computed, inject, onMounted } from 'vue';

function errHint(e) {
  const detail = e?.response?.data?.detail;
  if (detail && typeof detail === 'object') return detail.hint || JSON.stringify(detail);
  if (detail != null) return String(detail);
  return e?.message || '请求失败';
}

function statusClass(status) {
  const s = String(status || '').toLowerCase();
  if (s.includes('run') || s === 'waiting' || s === 'queued') return 'st-running';
  if (s.includes('finish') || s === 'success' || s === 'done') return 'st-done';
  if (s.includes('error') || s.includes('fail') || s.includes('cancel')) return 'st-fail';
  return 'st-running';
}

function statusLabel(row) {
  if (row.statusName) return row.statusName;
  const s = String(row.status || '').toLowerCase();
  if (s === 'waiting') return '等待调度';
  if (s === 'running') return '运行中';
  if (s === 'finish' || s === 'finished') return '完成';
  if (s === 'error' || s === 'failed') return '失败';
  return row.status || '—';
}

function durationText(sec) {
  if (sec == null || sec === '') return '—';
  const n = Number(sec);
  if (Number.isNaN(n)) return '—';
  return `${n}秒`;
}

export default {
  template: `
  <div class="main-content">
    <div class="page-header">
      <h1>每日数据补全</h1>
      <p>Key 在服务端 .env，本页不展示密钥；选应用后按定时调度绑定回填机器人</p>
    </div>

    <div class="card backfill-form-card">
      <div class="backfill-params">
        <div class="backfill-field backfill-field-app">
          <label>应用名称<span class="form-req">*</span></label>
          <div class="backfill-app-search">
            <input class="form-input" v-model="appKeyword" placeholder="输入应用名称搜索"
              @keyup.enter="searchApps"/>
            <button class="btn btn-ghost btn-sm" :disabled="searchingApps || busy" @click="searchApps">搜索</button>
          </div>
          <select class="form-select" v-model="form.robotUuid" :disabled="!appOptions.length"
            @change="onAppSelected">
            <option value="">{{ appSelectPlaceholder }}</option>
            <option v-for="a in appOptions" :key="a.robotUuid" :value="a.robotUuid">
              {{a.robotName}}
            </option>
          </select>
          <div v-if="selectedAppName" class="backfill-app-picked">
            已选：{{selectedAppName}}
            <span class="backfill-app-uuid">{{form.robotUuid}}</span>
          </div>
        </div>
        <div class="backfill-field">
          <label>机器人名称<span class="form-req">*</span></label>
          <select class="form-select" v-model="form.accountName" :disabled="loadingClients || !form.robotUuid">
            <option value="">{{ robotPlaceholder }}</option>
            <option v-for="c in robotOptions" :key="c.accountName" :value="c.accountName">
              {{c.accountName}}（{{c.statusName || c.status || '—'}}）
            </option>
          </select>
          <div v-if="robotHint" class="backfill-bind-hint">{{robotHint}}</div>
        </div>
        <div class="backfill-field backfill-field-sm">
          <label>开始日期</label>
          <input class="form-input" type="date" v-model="form.startDate"/>
        </div>
        <div class="backfill-field backfill-field-sm">
          <label>结束日期</label>
          <input class="form-input" type="date" v-model="form.endDate"/>
        </div>
        <div class="backfill-field backfill-field-sm">
          <label>排队超时(秒)</label>
          <input class="form-input" type="number" v-model="form.waitTimeoutSeconds"/>
        </div>
        <div class="backfill-field backfill-field-sm">
          <label>运行超时(秒)</label>
          <input class="form-input" type="number" v-model="form.runTimeout" placeholder="空=不限"/>
        </div>
        <div class="backfill-field backfill-field-sm">
          <label>优先级</label>
          <select class="form-select" v-model="form.priority">
            <option value="high">高</option>
            <option value="middle">中</option>
            <option value="low">低</option>
          </select>
        </div>
        <div class="backfill-field backfill-field-actions">
          <button class="btn btn-primary" :disabled="busy" @click="startJob">启动</button>
          <button class="btn btn-ghost" :disabled="busy" @click="loadJobs">刷新列表</button>
        </div>
      </div>
      <div v-if="hint" class="backfill-hint">{{hint}}</div>
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title">执行记录</div>
        <span style="font-size:12px;color:var(--c-sub)">共 {{jobs.length}} 条</span>
      </div>
      <div v-if="loadingList" class="empty-state"><p>加载中...</p></div>
      <div v-else-if="!jobs.length" class="empty-state"><p>暂无执行记录，填写参数后点击「启动」</p></div>
      <div v-else class="table-wrap">
        <table class="backfill-jobs-table">
          <thead>
            <tr>
              <th>任务名称</th>
              <th>状态</th>
              <th>触发时间</th>
              <th>运行时长</th>
              <th>触发账号</th>
              <th>备注</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in jobs" :key="row.jobUuid || row.id">
              <td>
                <div class="backfill-task-name">{{row.taskName || '—'}}</div>
                <div class="backfill-job-id">{{row.jobUuid}}</div>
              </td>
              <td>
                <span :class="['backfill-status', statusClass(row.status)]">{{statusLabel(row)}}</span>
              </td>
              <td class="nowrap">{{row.createdAt || '—'}}</td>
              <td>{{durationText(row.durationSec)}}</td>
              <td>{{row.accountName || '—'}}</td>
              <td class="backfill-remark">{{row.remark || '—'}}</td>
              <td class="nowrap">
                <button class="btn btn-ghost btn-sm" :disabled="busy" @click="refreshRow(row)">刷新</button>
                <button class="btn btn-ghost btn-sm" @click="showDetail(row)">详情</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <modal-box title="执行详情" :visible="!!detail" @close="detail=null" :wide="true">
      <div v-if="detail" style="display:grid;grid-template-columns:1fr 1fr;gap:12px 24px;margin-bottom:16px">
        <div><span style="color:#86909c;font-size:12px">任务</span><div style="font-weight:500">{{detail.taskName}}</div></div>
        <div><span style="color:#86909c;font-size:12px">状态</span><div>{{statusLabel(detail)}}</div></div>
        <div><span style="color:#86909c;font-size:12px">jobUuid</span><div style="font-family:monospace;font-size:12px;word-break:break-all">{{detail.jobUuid}}</div></div>
        <div><span style="color:#86909c;font-size:12px">触发时间</span><div>{{detail.createdAt || '—'}}</div></div>
        <div><span style="color:#86909c;font-size:12px">触发账号</span><div>{{detail.accountName || '—'}}</div></div>
        <div><span style="color:#86909c;font-size:12px">运行时长</span><div>{{durationText(detail.durationSec)}}</div></div>
      </div>
      <div class="form-label" style="margin-bottom:6px">备注</div>
      <div style="margin-bottom:12px;font-size:13px">{{detail?.remark || '—'}}</div>
    </modal-box>
  </div>`,
  setup() {
    const http = inject('http');
    const { show } = inject('useToast')();

    const form = reactive({
      robotUuid: '',
      accountName: '',
      startDate: '',
      endDate: '',
      waitTimeoutSeconds: 600,
      runTimeout: '',
      priority: 'middle',
    });

    const busy = ref(false);
    const loadingList = ref(false);
    const loadingClients = ref(false);
    const searchingApps = ref(false);
    const hint = ref('');
    const robotHint = ref('');
    const jobs = ref([]);
    const allClients = ref([]);
    const boundClients = ref([]);
    const useBoundOnly = ref(false);
    const appKeyword = ref('');
    const appOptions = ref([]);
    const selectedAppName = ref('');
    const detail = ref(null);

    const robotOptions = computed(() => {
      if (useBoundOnly.value && boundClients.value.length) return boundClients.value;
      return allClients.value;
    });

    const appSelectPlaceholder = computed(() => {
      if (searchingApps.value) return '搜索中...';
      if (!appOptions.value.length) return '请先搜索并选择应用';
      return '请选择应用';
    });

    const robotPlaceholder = computed(() => {
      if (!form.robotUuid) return '请先选择应用';
      if (loadingClients.value) return '加载中...';
      if (useBoundOnly.value && boundClients.value.length > 1) return '多个调度机器人，请选择';
      if (useBoundOnly.value && boundClients.value.length === 1) return '已自动选中调度机器人';
      if (!robotOptions.value.length) return '暂无机器人';
      return '请选择机器人';
    });

    async function loadClients() {
      loadingClients.value = true;
      try {
        const { data } = await http.get('/service/zyx/yingdao/clients');
        allClients.value = data?.data?.items || [];
      } catch (e) {
        allClients.value = [];
        show(errHint(e), 'error');
      } finally {
        loadingClients.value = false;
      }
    }

    async function loadJobs() {
      loadingList.value = true;
      try {
        const { data } = await http.get('/service/zyx/yingdao/jobs?limit=50');
        jobs.value = data?.data?.items || [];
      } catch (e) {
        jobs.value = [];
        show(errHint(e), 'error');
      } finally {
        loadingList.value = false;
      }
    }

    async function searchApps() {
      const key = (appKeyword.value || '').trim();
      if (!key) {
        show('请输入应用名称关键词', 'error');
        return;
      }
      searchingApps.value = true;
      try {
        const { data } = await http.get('/service/zyx/yingdao/apps/search', {
          params: { key, limit: 30 },
          timeout: 180000,
        });
        appOptions.value = data?.data?.items || [];
        if (!appOptions.value.length) {
          form.robotUuid = '';
          selectedAppName.value = '';
          boundClients.value = [];
          useBoundOnly.value = false;
          form.accountName = '';
          robotHint.value = '';
          show('未找到匹配应用', 'error');
        } else if (appOptions.value.length === 1) {
          form.robotUuid = appOptions.value[0].robotUuid;
          onAppSelected();
        } else {
          form.robotUuid = '';
          selectedAppName.value = '';
          boundClients.value = [];
          useBoundOnly.value = false;
          form.accountName = '';
          robotHint.value = `找到 ${appOptions.value.length} 个应用，请选择`;
        }
      } catch (e) {
        appOptions.value = [];
        show(errHint(e), 'error');
      } finally {
        searchingApps.value = false;
      }
    }

    function onAppSelected() {
      const uuid = (form.robotUuid || '').trim();
      const app = appOptions.value.find(a => a.robotUuid === uuid);
      selectedAppName.value = app?.robotName || '';
      form.accountName = '';
      const clients = Array.isArray(app?.runClients) ? app.runClients : [];
      boundClients.value = clients;
      if (clients.length === 1) {
        useBoundOnly.value = true;
        form.accountName = clients[0].accountName;
        robotHint.value = '已按定时调度自动选中机器人，可手动更换';
      } else if (clients.length > 1) {
        useBoundOnly.value = true;
        robotHint.value = `该应用有 ${clients.length} 个调度机器人，请手动选择`;
      } else {
        useBoundOnly.value = false;
        robotHint.value = '未配置定时调度，请从全部机器人中选择';
      }
    }

    async function startJob() {
      const robotUuid = (form.robotUuid || '').trim();
      if (!robotUuid) {
        show('请搜索并选择应用', 'error');
        return;
      }
      const accountName = (form.accountName || '').trim();
      if (!accountName) {
        show(useBoundOnly.value && boundClients.value.length > 1
          ? '请选择调度机器人'
          : '请选择机器人名称', 'error');
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
        accountName,
        params: params.length ? params : undefined,
        waitTimeoutSeconds: Number(form.waitTimeoutSeconds) || 600,
        priority: form.priority,
        useIdempotent: true,
        taskName: selectedAppName.value || undefined,
      };
      const rt = form.runTimeout === '' || form.runTimeout == null ? null : Number(form.runTimeout);
      if (rt != null && !Number.isNaN(rt)) body.runTimeout = rt;

      busy.value = true;
      hint.value = '';
      try {
        await http.post('/service/zyx/yingdao/job/start', body);
        show('启动成功');
        await loadJobs();
      } catch (e) {
        hint.value = errHint(e);
        show(hint.value, 'error');
      } finally {
        busy.value = false;
      }
    }

    async function refreshRow(row) {
      if (!row?.jobUuid) return;
      busy.value = true;
      hint.value = '';
      try {
        await http.post('/service/zyx/yingdao/job/query', { jobUuid: row.jobUuid });
        await loadJobs();
        show('状态已刷新');
      } catch (e) {
        hint.value = errHint(e);
        show(hint.value, 'error');
      } finally {
        busy.value = false;
      }
    }

    function showDetail(row) {
      detail.value = row;
    }

    onMounted(() => {
      loadClients();
      loadJobs();
    });

    return {
      form, busy, loadingList, loadingClients, searchingApps,
      hint, robotHint, jobs, detail,
      appKeyword, appOptions, selectedAppName,
      robotOptions, appSelectPlaceholder, robotPlaceholder,
      searchApps, onAppSelected, startJob, loadJobs, refreshRow, showDetail,
      statusClass, statusLabel, durationText,
    };
  }
};
