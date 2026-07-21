import { ref, computed, inject, onMounted, watch } from 'vue';

export default {
  template: `
  <div class="main-content">
    <div class="page-header"><h1>数据中心</h1><p>API 调用统计与执行日志</p></div>
    <div class="stat-grid">
      <div class="stat-card" v-for="s in statsList" :key="s.label">
        <div class="stat-card-icon" :style="{background:s.bg,color:s.color}">{{s.icon}}</div>
        <div><div class="stat-card-value">{{s.value}}</div><div class="stat-card-label">{{s.label}}</div></div>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <span class="card-title">执行日志</span>
        <span style="font-size:12px;color:#86909c">共 {{total}} 条</span>
      </div>
      <div class="toolbar">
        <input class="search-input" v-model="keyword" placeholder="搜索路径或接口名..." @keyup.enter="search" />
        <button class="btn btn-primary btn-sm" @click="search">搜索</button>
        <select class="form-select" v-model.number="pageSize" style="width:110px;margin-left:auto">
          <option :value="20">20 / 页</option>
          <option :value="50">50 / 页</option>
          <option :value="100">100 / 页</option>
          <option :value="200">200 / 页</option>
        </select>
      </div>
      <div v-if="loading" class="empty-state"><p>加载中...</p></div>
      <div v-else-if="!logs.length" class="empty-state"><div class="empty-state-icon">📋</div><p>暂无调用记录，前往「调度任务」执行 API</p></div>
      <div v-else class="table-wrap">
        <table>
          <thead><tr><th>接口</th><th>方法</th><th>路径</th><th>状态</th><th>耗时</th><th>触发</th><th>时间</th><th></th></tr></thead>
          <tbody>
            <tr v-for="l in logs" :key="l.id">
              <td style="font-weight:500">{{l.api_name||'#'+l.api_id}}</td>
              <td><span :class="['badge-method','m-'+l.method]">{{l.method}}</span></td>
              <td style="font-family:monospace;font-size:12px;color:#86909c;max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{l.path}}</td>
              <td><span :style="{color:l.status_code>=200&&l.status_code<300?'#00b42a':'#f53f3f',fontWeight:600}">{{l.status_code||0}}</span></td>
              <td>{{l.duration_ms||0}}ms</td>
              <td><span :class="['badge-status',l.triggered_by==='schedule'?'st-draft':'st-published']"><span :class="['status-dot',l.triggered_by==='schedule'?'orange':'green']"></span>{{l.triggered_by==='schedule'?'定时':'手动'}}</span></td>
              <td style="font-size:12px;color:#86909c">{{fmt(l.created_at)}}</td>
              <td><button class="btn btn-ghost btn-sm" @click="detailLog=l">详情</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="totalPages>1 || total>0" class="pagination">
        <button class="btn btn-ghost btn-sm" :disabled="page<=1" @click="page--">上一页</button>
        <span class="pagination-info">第 {{page}} / {{totalPages||1}} 页</span>
        <button class="btn btn-ghost btn-sm" :disabled="page>=totalPages" @click="page++">下一页</button>
      </div>
    </div>
    <modal-box title="执行详情" :visible="!!detailLog" @close="detailLog=null">
      <div v-if="detailLog" style="display:grid;grid-template-columns:1fr 1fr;gap:12px 24px;margin-bottom:16px">
        <div><span style="color:#86909c;font-size:12px">接口</span><div style="font-weight:500">{{detailLog.api_name}}</div></div>
        <div><span style="color:#86909c;font-size:12px">状态码</span><div :style="{color:detailLog.status_code>=200&&detailLog.status_code<300?'#00b42a':'#f53f3f',fontWeight:600}">{{detailLog.status_code}}</div></div>
        <div><span style="color:#86909c;font-size:12px">耗时</span><div>{{detailLog.duration_ms}}ms</div></div>
        <div><span style="color:#86909c;font-size:12px">触发方式</span><div>{{detailLog.triggered_by==='schedule'?'定时':'手动'}}</div></div>
        <div><span style="color:#86909c;font-size:12px">时间</span><div>{{fmt(detailLog.created_at)}}</div></div>
      </div>
      <div class="form-label" style="margin-bottom:6px">响应内容</div>
      <pre class="log-response">{{detailLog?.response_body||'(无)'}}</pre>
    </modal-box>
  </div>`,
  setup() {
    const stats = ref(null);
    const logs = ref([]);
    const detailLog = ref(null);
    const loading = ref(false);
    const keyword = ref('');
    const page = ref(1);
    const pageSize = ref(20);
    const total = ref(0);
    const http = inject('http');

    const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value) || 1));

    const statsList = computed(() => [
      { icon:'🔗',value:stats.value?.total_apis||0,label:'接口总数',color:'#165dff',bg:'#e8f0fe'},
      { icon:'⚡',value:stats.value?.today_calls||0,label:'今日调用',color:'#00b42a',bg:'#e8ffea'},
      { icon:'📋',value:stats.value?.total_logs||0,label:'累计日志',color:'#722ed1',bg:'#f5edff'},
      { icon:'⏰',value:stats.value?.active_schedules||0,label:'活跃定时',color:'#ff7d00',bg:'#fff7e8'},
    ]);

    async function loadStats() {
      try {
        const r = await http.get('/service/zyx/dashboard/stats');
        stats.value = r.data.data;
      } catch (e) {}
    }

    async function loadLogs() {
      loading.value = true;
      try {
        const q = new URLSearchParams({
          keyword: keyword.value,
          page: String(page.value),
          page_size: String(pageSize.value),
        });
        const r = await http.get(`/service/zyx/dashboard/logs?${q}`);
        const data = r.data.data || {};
        logs.value = data.items || [];
        total.value = data.total || 0;
        if (page.value > 1 && !logs.value.length && total.value > 0) {
          page.value = 1;
          return;
        }
      } catch (e) {
        logs.value = [];
        total.value = 0;
      } finally {
        loading.value = false;
      }
    }

    function search() {
      if (page.value === 1) loadLogs();
      else page.value = 1;
    }

    watch(page, loadLogs);
    watch(pageSize, () => {
      if (page.value === 1) loadLogs();
      else page.value = 1;
    });

    onMounted(async () => {
      await loadStats();
      await loadLogs();
    });

    function fmt(d) { if(!d) return '-'; return new Date(d).toLocaleString(); }
    return {
      stats, logs, detailLog, loading, keyword, page, pageSize, total, totalPages,
      statsList, search, fmt,
    };
  }
};
