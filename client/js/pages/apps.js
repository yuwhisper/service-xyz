import { ref, inject, onMounted } from 'vue';

function errHint(e) {
  const detail = e?.response?.data?.detail;
  if (detail && typeof detail === 'object') return detail.hint || JSON.stringify(detail);
  if (detail != null) return String(detail);
  return e?.message || '请求失败';
}

function runClientsText(row) {
  const list = row?.runClients;
  if (!Array.isArray(list) || !list.length) return '—';
  return list.map(x => (typeof x === 'string' ? x : (x.accountName || x.robotClientName || ''))).filter(Boolean).join('、') || '—';
}

export default {
  template: `
  <div class="main-content">
    <div class="page-header">
      <h1>影刀应用</h1>
      <p>从影刀拉取应用列表；运行机器人字段接口不返回，暂显示 —</p>
    </div>

    <div class="card">
      <div class="apps-toolbar">
        <div class="apps-search">
          <input class="form-input" v-model="keyword" placeholder="应用名称模糊搜索"
            @keyup.enter="search"/>
          <button class="btn btn-primary" :disabled="loading" @click="search">搜索</button>
          <button class="btn btn-ghost" :disabled="loading" @click="reset">重置</button>
        </div>
        <span class="apps-total">共 {{total}} 条</span>
      </div>

      <div v-if="loading" class="empty-state"><p>加载中...</p></div>
      <div v-else-if="!items.length" class="empty-state"><p>暂无应用</p></div>
      <div v-else class="table-wrap">
        <table class="apps-table">
          <thead>
            <tr>
              <th>应用名称</th>
              <th>应用UUID</th>
              <th>创建时间</th>
              <th>更新时间</th>
              <th>所有者</th>
              <th>运行机器人</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in items" :key="row.robotUuid">
              <td class="apps-name">{{row.robotName || '—'}}</td>
              <td class="apps-uuid" :title="row.robotUuid">{{row.robotUuid || '—'}}</td>
              <td class="nowrap">{{row.createTime || '—'}}</td>
              <td class="nowrap">{{row.updateTime || '—'}}</td>
              <td>{{row.ownerName || '—'}}</td>
              <td class="apps-clients">{{runClientsText(row)}}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="total > 0" class="apps-pager">
        <button class="btn btn-ghost btn-sm" :disabled="loading || page<=1" @click="go(page-1)">上一页</button>
        <span>{{page}} / {{pages}}</span>
        <button class="btn btn-ghost btn-sm" :disabled="loading || page>=pages" @click="go(page+1)">下一页</button>
        <select class="form-select apps-page-size" v-model.number="size" :disabled="loading" @change="search">
          <option :value="10">10条/页</option>
          <option :value="20">20条/页</option>
          <option :value="50">50条/页</option>
        </select>
      </div>
    </div>
  </div>`,
  setup() {
    const http = inject('http');
    const { show } = inject('useToast')();

    const keyword = ref('');
    const activeKey = ref('');
    const items = ref([]);
    const loading = ref(false);
    const page = ref(1);
    const size = ref(20);
    const total = ref(0);
    const pages = ref(1);

    async function load() {
      loading.value = true;
      try {
        const { data } = await http.get('/service/zyx/yingdao/apps', {
          params: {
            key: activeKey.value || undefined,
            page: page.value,
            size: size.value,
          },
        });
        const d = data?.data || {};
        items.value = d.items || [];
        total.value = d.total || 0;
        pages.value = d.pages || 1;
        page.value = d.page || page.value;
      } catch (e) {
        items.value = [];
        total.value = 0;
        pages.value = 1;
        show(errHint(e), 'error');
      } finally {
        loading.value = false;
      }
    }

    function search() {
      activeKey.value = (keyword.value || '').trim();
      page.value = 1;
      load();
    }

    function reset() {
      keyword.value = '';
      activeKey.value = '';
      page.value = 1;
      load();
    }

    function go(p) {
      page.value = p;
      load();
    }

    onMounted(load);

    return {
      keyword, items, loading, page, size, total, pages,
      search, reset, go, runClientsText,
    };
  }
};
