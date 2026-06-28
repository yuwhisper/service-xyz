import { ref, computed, inject, onMounted } from 'vue';

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
      <div class="card-header"><span class="card-title">执行日志</span><span style="font-size:12px;color:#86909c">最近 {{logs.length}} 条</span></div>
      <div v-if="!logs.length" class="empty-state"><div class="empty-state-icon">📋</div><p>暂无调用记录，前往「调度任务」执行 API</p></div>
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
    const stats = ref(null); const logs = ref([]); const detailLog = ref(null);
    const http = inject('http');
    onMounted(async () => {
      try { const r = await http.get('/service/zyx/dashboard/stats'); stats.value = r.data.data; logs.value = r.data.data.recent_logs||[]; } catch(e){}
    });
    const statsList = computed(() => [
      { icon:'🔗',value:stats.value?.total_apis||0,label:'接口总数',color:'#165dff',bg:'#e8f0fe'},
      { icon:'⚡',value:stats.value?.today_calls||0,label:'今日调用',color:'#00b42a',bg:'#e8ffea'},
      { icon:'📋',value:stats.value?.total_logs||0,label:'累计日志',color:'#722ed1',bg:'#f5edff'},
      { icon:'⏰',value:stats.value?.active_schedules||0,label:'活跃定时',color:'#ff7d00',bg:'#fff7e8'},
    ]);
    function fmt(d) { if(!d) return '-'; return new Date(d).toLocaleString(); }
    return { stats, logs, detailLog, statsList, fmt };
  }
};
