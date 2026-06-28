import { ref, inject, onMounted } from 'vue';

export default {
  template: `
  <div class="main-content">
    <div class="page-header"><h1>调度任务</h1><p>按需调用 API，查看历史执行日志</p></div>
    <div class="toolbar">
      <input class="search-input" v-model="keyword" placeholder="搜索接口..." @keyup.enter="fetch" />
      <select class="form-select" v-model="methodFilter" style="width:110px"><option value="">全部方法</option><option v-for="m in methods" :value="m">{{m}}</option></select>
      <button class="btn btn-primary btn-sm" @click="fetch">搜索</button>
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
      <div class="form-group"><label class="form-label">Query Params (JSON)</label><textarea class="form-textarea" v-model="execParams" rows="4" placeholder='{"key":"value"}'></textarea></div>
      <div class="form-group"><label class="form-label">Headers (JSON)</label><textarea class="form-textarea" v-model="execHeaders" rows="2" placeholder='{"Authorization":"Bearer xxx"}'></textarea></div>
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
    const execApi = ref(null); const execParams = ref('{}'); const execHeaders = ref('{}'); const executing = ref(false);
    const logApi = ref(null); const logs = ref([]);
    const detailLog = ref(null);

    async function fetch() {
      loading.value = true;
      try { const r = await http.get(`/service/zyx/apis?project_id=1&keyword=${encodeURIComponent(keyword.value)}&method=${methodFilter.value}`); apis.value = r.data.data; } catch(e){} finally { loading.value = false; }
    }
    onMounted(fetch);

    function openExec(a) { execApi.value = a; execParams.value = '{}'; execHeaders.value = '{}'; }
    async function doExec() {
      executing.value = true;
      try {
        let p={},h={}; try{p=JSON.parse(execParams.value)}catch{} try{h=JSON.parse(execHeaders.value)}catch{}
        await http.post(`/service/zyx/apis/${execApi.value.id}/execute`,{params:p,headers:h});
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
    return { apis, loading, keyword, methodFilter, methods, fetch, execApi, execParams, execHeaders, executing, openExec, doExec, logApi, logs, openLogs, detailLog, fmt };
  }
};
