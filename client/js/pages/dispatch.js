import { ref, computed, inject, onMounted } from 'vue';

/** 各接口执行参数定义；未列出的接口视为无参 */
const API_PARAMS = {
  '/service/zyx/jst/order/query': [
    { key: 'o_id', label: 'o_id（内部订单号）', type: 'text' },
    { key: 'so_id', label: 'so_id（线上订单号）', type: 'text' },
  ],
  '/service/zyx/jst/sku/query': [
    { key: 'sku', label: 'sku（货号）', type: 'text' },
  ],
  '/service/zyx/jst/inventory/query': [
    { key: 'sku', label: 'sku（商品编码）', type: 'text' },
    { key: 'wms_co_ids', label: 'wms_co_ids（分仓编号，JSON数组如[15774928]）', type: 'text' },
  ],
  '/service/zyx/dingtalk/dingpan/upload': [
    { key: 'local_path', label: 'local_path（服务器本地路径）', type: 'text' },
    { key: 'as_zip', label: 'as_zip（目录先压缩）', type: 'bool' },
    { key: 'save_name', label: 'save_name（钉盘保存名）', type: 'text' },
    { key: 'folder_url', label: 'folder_url（钉盘文件夹链接）', type: 'text' },
  ],
};

export default {
  template: `
  <div class="main-content">
    <div class="page-header"><h1>调度任务</h1><p>按需调用 API，查看历史执行日志</p></div>
    <div class="toolbar">
      <input class="search-input" v-model="keyword" placeholder="搜索接口..." @keyup.enter="loadData" />
      <select class="form-select" v-model="methodFilter" style="width:110px"><option value="">全部方法</option><option v-for="m in methods" :value="m">{{m}}</option></select>
      <button class="btn btn-primary btn-sm" @click="loadData">搜索</button>
    </div>
    <div class="card">
      <div v-if="loading" class="empty-state"><p>加载中...</p></div>
      <div v-else-if="!apis.length" class="empty-state"><div class="empty-state-icon">📭</div><p>暂无接口</p></div>
      <div v-else class="table-wrap">
        <table>
          <thead><tr><th>方法</th><th>路径</th><th>名称</th><th>描述</th><th style="width:160px">操作</th></tr></thead>
          <tbody>
            <tr v-for="a in apis" :key="a.id">
              <td><span :class="['badge-method','m-'+a.method]">{{a.method}}</span></td>
              <td style="font-family:monospace;font-size:12px">{{a.path}}</td>
              <td style="font-weight:500">{{a.name}}</td>
              <td style="color:#86909c;font-size:12px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{a.description||'-'}}</td>
              <td>
                <button class="btn btn-primary btn-sm" @click="openExec(a)">执行</button>
                <button class="btn btn-ghost btn-sm" style="margin-left:6px" @click="openLogs(a)">日志</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Execute Modal -->
    <modal-box title="执行 API" :visible="!!execApi" @close="execApi=null">
      <div class="form-group"><label class="form-label">{{execApi?.method}} {{execApi?.path}}</label></div>
      <template v-if="execFields.length">
        <div class="form-group" v-for="f in execFields" :key="f.key">
          <label class="form-label">{{f.label}}</label>
          <label v-if="f.type==='bool'" style="display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer">
            <input type="checkbox" v-model="execForm[f.key]" />
            <span>是</span>
          </label>
          <input v-else class="form-input" v-model="execForm[f.key]" :placeholder="f.label" />
        </div>
      </template>
      <div v-else class="form-group" style="color:#86909c;font-size:13px">此接口无需填写参数</div>
      <div class="modal-footer">
        <button class="btn btn-ghost" @click="execApi=null">取消</button>
        <button class="btn btn-primary" @click="doExec" :disabled="executing">{{executing?'提交中...':'提交执行'}}</button>
      </div>
    </modal-box>

    <!-- Logs Modal -->
    <modal-box title="执行日志" :visible="!!logApi" @close="logApi=null">
      <div v-if="!logs.length" class="empty-state"><p>暂无记录</p></div>
      <div v-else class="table-wrap">
        <table>
          <thead><tr><th>时间</th><th>状态</th><th>耗时</th><th>参数</th><th></th></tr></thead>
          <tbody>
            <tr v-for="l in logs" :key="l.id">
              <td style="font-size:12px;color:#86909c">{{fmt(l.created_at)}}</td>
              <td><span :style="{color:l.status_code>=200&&l.status_code<300?'#00b42a':'#f53f3f',fontWeight:600}">{{l.status_code||0}}</span></td>
              <td>{{l.duration_ms}}ms</td>
              <td style="font-size:12px;color:#86909c;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{l.request_params||'-'}}</td>
              <td><button class="btn btn-ghost btn-sm" @click="detailLog=l">详情</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </modal-box>

    <!-- Detail Modal -->
    <modal-box title="响应详情" :visible="!!detailLog" @close="detailLog=null">
      <div v-if="detailLog" style="margin-bottom:12px"><span style="color:#86909c;font-size:12px">状态码 {{detailLog.status_code}} · 耗时 {{detailLog.duration_ms}}ms · {{fmt(detailLog.created_at)}}</span></div>
      <pre class="log-response">{{detailLog?.response_body||'(无)'}}</pre>
    </modal-box>
  </div>`,
  setup() {
    const http = inject('http');
    const { show } = inject('useToast')();
    const apis = ref([]); const loading = ref(true);
    const keyword = ref(''); const methodFilter = ref('');
    const methods = ['GET','POST','PUT','DELETE','PATCH'];
    const execApi = ref(null); const execForm = ref({}); const executing = ref(false);
    const logApi = ref(null); const logs = ref([]);
    const detailLog = ref(null);

    const execFields = computed(() => {
      const path = execApi.value?.path || '';
      return API_PARAMS[path] || [];
    });

    async function loadData() {
      loading.value = true;
      try { const r = await http.get(`/service/zyx/apis?project_id=1&keyword=${encodeURIComponent(keyword.value)}&method=${methodFilter.value}`); apis.value = r.data.data || []; } catch(e){ apis.value = []; } finally { loading.value = false; }
    }
    onMounted(loadData);

    function openExec(a) {
      execApi.value = a;
      const form = {};
      for (const f of (API_PARAMS[a.path] || [])) {
        form[f.key] = f.type === 'bool' ? false : '';
      }
      execForm.value = form;
    }

    function buildParams() {
      const out = {};
      for (const f of execFields.value) {
        const v = execForm.value[f.key];
        if (f.type === 'bool') {
          if (v) out[f.key] = true;
          continue;
        }
        const text = (v == null ? '' : String(v)).trim();
        if (text) out[f.key] = text;
      }
      return out;
    }

    async function doExec() {
      executing.value = true;
      try {
        await http.post(`/service/zyx/apis/${execApi.value.id}/execute`, {
          params: buildParams(),
          headers: {},
        });
        execApi.value = null;
        show('已提交执行，请在数据中心查看结果');
      } catch(e) { show('执行失败: '+(e.response?.data?.detail||e.message),'error'); }
      finally { executing.value = false; }
    }

    async function openLogs(a) {
      logApi.value = a; logs.value = [];
      try { const r = await http.get(`/service/zyx/apis/${a.id}/logs`); logs.value = r.data.data; } catch(e){}
    }

    function fmt(d) { if(!d) return '-'; return new Date(d).toLocaleString(); }
    return { apis, loading, keyword, methodFilter, methods, loadData, execApi, execForm, execFields, executing, openExec, doExec, logApi, logs, openLogs, detailLog, fmt };
  }
};
