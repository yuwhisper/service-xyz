import { ref, reactive, inject, onMounted } from 'vue';

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
      <p>Key 在服务端 .env，本页不展示密钥</p>
    </div>

    <div class="card backfill-form-card">
      <div class="backfill-params">
        <div class="backfill-field">
          <label>应用UUID<span class="form-req">*</span></label>
          <input class="form-input" v-model="form.robotUuid" placeholder="robotUuid"/>
        </div>
        <div class="backfill-field">
          <label>机器人名称<span class="form-req">*</span></label>
          <input class="form-input" v-model="form.accountName" placeholder="控制台机器人账号"/>
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
                <div class="backfill-task-name">{{row.taskName || '每日数据补全'}}</div>
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
    const hint = ref('');
    const jobs = ref([]);
    const detail = ref(null);

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

    async function startJob() {
      const robotUuid = (form.robotUuid || '').trim();
      if (!robotUuid) {
        show('请填写应用UUID', 'error');
        return;
      }
      const accountName = (form.accountName || '').trim();
      if (!accountName) {
        show('请填写机器人名称', 'error');
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
        taskName: '每日数据补全',
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

    onMounted(loadJobs);

    return {
      form, busy, loadingList, hint, jobs, detail,
      startJob, loadJobs, refreshRow, showDetail,
      statusClass, statusLabel, durationText,
    };
  }
};
