import { ref, computed, inject, onMounted } from 'vue';

/** 各接口执行参数定义；未列出的接口视为无参 */
const API_PARAMS = {
  '/service/zyx/jst/order/query': [
    { key: 'o_id', label: 'o_id（内部订单号，单个）', type: 'text' },
    { key: 'so_id', label: 'so_id（线上订单号，单个）', type: 'text' },
    { key: 'o_ids', label: 'o_ids（内部单号列表，JSON如[123]）', type: 'text' },
    { key: 'so_ids', label: 'so_ids（线上单号列表，JSON如["A"]）', type: 'text' },
    { key: 'shop_id', label: 'shop_id（店铺编号）', type: 'text' },
    { key: 'is_offline_shop', label: 'is_offline_shop（线下店铺）', type: 'bool' },
    { key: 'modified_begin', label: 'modified_begin（起始时间）', type: 'text' },
    { key: 'modified_end', label: 'modified_end（结束时间）', type: 'text' },
    { key: 'date_type', label: 'date_type（0修改/2订单/3发货）', type: 'text' },
    { key: 'status', label: 'status（订单状态）', type: 'text' },
    { key: 'page_index', label: 'page_index（页码）', type: 'text' },
    { key: 'page_size', label: 'page_size（每页条数≤100）', type: 'text' },
    { key: 'start_ts', label: 'start_ts（ts增量）', type: 'text' },
    { key: 'is_get_total', label: 'is_get_total（查总条数）', type: 'bool' },
    { key: 'order_types', label: 'order_types（订单类型JSON数组）', type: 'text' },
    { key: 'archive', label: 'archive（历史订单）', type: 'bool' },
    { key: 'volume', label: 'volume（自定义：体积）', type: 'bool' },
    { key: 'package', label: 'package（自定义：包材）', type: 'bool' },
    { key: 'outer_drp_co_id', label: 'outer_drp_co_id（货主分销）', type: 'bool' },
    { key: 'cus_id', label: 'cus_id（货通客户id）', type: 'bool' },
    { key: 'logistics_status', label: 'logistics_status（o2o配送状态）', type: 'bool' },
    { key: 'src_combine_sku_qty', label: 'src_combine_sku_qty（原组合数量）', type: 'bool' },
    { key: 'referrer_name', label: 'referrer_name（达人名称）', type: 'bool' },
    { key: 'presale_date', label: 'presale_date（预售时间）', type: 'bool' },
    { key: 'drp_price', label: 'drp_price（采购价）', type: 'bool' },
    { key: 'item_plan_delivery_date', label: 'item_plan_delivery_date（最晚发货）', type: 'bool' },
    { key: 'activity_u_id', label: 'activity_u_id（团长id）', type: 'bool' },
    { key: 'activity_u_name', label: 'activity_u_name（团长名称）', type: 'bool' },
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
  '/service/zyx/dingtalk/workbook/write': [
    { key: 'user_id', label: 'user_id（操作人 userid）', type: 'text' },
    { key: 'workbook_id', label: 'workbook_id（文档ID）', type: 'text' },
    { key: 'sheet_id', label: 'sheet_id（工作表名）', type: 'text' },
    { key: 'range_address', label: 'range_address（如 A2）', type: 'text' },
    { key: 'values', label: 'values（二维JSON，如[["a","b"]]）', type: 'json' },
  ],
  '/service/zyx/dingtalk/workbook/last-row': [
    { key: 'user_id', label: 'user_id（操作人 userid）', type: 'text' },
    { key: 'workbook_id', label: 'workbook_id（文档ID）', type: 'text' },
    { key: 'sheet_id', label: 'sheet_id（工作表名）', type: 'text' },
  ],
  '/service/zyx/dingtalk/notable/records': [
    { key: 'user_id', label: 'user_id（操作人 userid）', type: 'text' },
    { key: 'base_id', label: 'base_id（AI多维表文档ID）', type: 'text' },
    { key: 'sheet_id', label: 'sheet_id（数据表名，如数据表）', type: 'text' },
    { key: 'records', label: 'records（JSON数组，如[{"店铺名":"1688-01"}]）', type: 'json' },
  ],
  '/service/zyx/ozon/fahuo': [
    { key: 'wait', label: 'wait（true=同步等待结果）', type: 'bool' },
    { key: 'upload_to_dingpan', label: 'upload_to_dingpan（上传钉盘）', type: 'bool' },
  ],
};

/** 接口参数文档：请求体示例 + 字段含义 + 响应体示例 + 每个响应字段含义 */
const API_DOCS = {
  '/service/zyx/dingtalk/workbook/last-row': {
    requestExample: {
      user_id: '17605205775264779',
      workbook_id: 'QBnd5ExVEq9b7799cggRdNrvVyeZqMmz',
      sheet_id: '测试',
    },
    requestFields: [
      { key: 'user_id', type: 'string', required: '是', desc: '操作人 userid，服务端换 unionId' },
      { key: 'workbook_id', type: 'string', required: '是', desc: '文档 ID' },
      { key: 'sheet_id', type: 'string', required: '是', desc: '工作表名称或 ID' },
    ],
    responseExample: {
      code: 0,
      data: {
        id: 'stxxxx',
        name: '测试',
        lastNonEmptyRow: 10,
        lastNonEmptyColumn: 0,
        rowCount: 200,
        columnCount: 40,
        last_excel_row: 11,
        next_excel_row: 12,
      },
    },
    responseFields: [
      { key: 'code', desc: '业务状态码，成功固定为 0' },
      { key: 'data.id', desc: '工作表 ID' },
      { key: 'data.name', desc: '工作表名称' },
      { key: 'data.lastNonEmptyRow', desc: '钉钉原值，最后一行非空行位置，从 0 起；空表为 -1' },
      { key: 'data.lastNonEmptyColumn', desc: '钉钉原值，最后一列非空列位置，从 0 起；空表为 -1' },
      { key: 'data.rowCount', desc: '工作表总行数' },
      { key: 'data.columnCount', desc: '工作表总列数' },
      { key: 'data.last_excel_row', desc: 'Excel 行号（lastNonEmptyRow+1）；空表为 0' },
      { key: 'data.next_excel_row', desc: '下一行可写位置；空表为 1，写入时可用 A{next_excel_row}' },
    ],
  },
  '/service/zyx/dingtalk/notable/records': {
    requestExample: {
      user_id: '17605205775264779',
      base_id: 'X6GRezwJlLr9OOrrfg0NjexAJdqbropQ',
      sheet_id: '数据表',
      records: [{ '店铺名': '1688-01' }],
    },
    requestFields: [
      { key: 'user_id', type: 'string', required: '是', desc: '操作人 userid，服务端换 unionId' },
      { key: 'base_id', type: 'string', required: '是', desc: 'AI 多维表文档 ID（链接 /nodes/ 后一段）' },
      { key: 'sheet_id', type: 'string', required: '是', desc: '数据表名称或 ID（左侧「数据表」，不是视图页签 1688-01）' },
      { key: 'records', type: 'array', required: '是', desc: '记录列表；每项为 {字段名: 值}，也可 {fields:{...}}' },
    ],
    responseExample: {
      code: 0,
      data: {
        value: [{ id: 'recxxxx' }],
      },
    },
    responseFields: [
      { key: 'code', desc: '业务状态码，成功固定为 0' },
      { key: 'data.value', desc: '成功新增的记录列表' },
      { key: 'data.value[].id', desc: '新建记录的 recordId' },
    ],
  },
  '/service/zyx/dingtalk/workbook/write': {
    requestExample: {
      user_id: '17605205775264779',
      workbook_id: 'QBnd5ExVEq9b7799cggRdNrvVyeZqMmz',
      sheet_id: '测试',
      range_address: 'A2',
      values: [['示例内容']],
    },
    requestFields: [
      { key: 'user_id', type: 'string', required: '是', desc: '操作人 userid，服务端换 unionId' },
      { key: 'workbook_id', type: 'string', required: '是', desc: '文档 ID' },
      { key: 'sheet_id', type: 'string', required: '是', desc: '工作表名称或 ID' },
      { key: 'range_address', type: 'string', required: '是', desc: '起始单元格或区域，如 A2；单格会按 values 自动扩展' },
      { key: 'values', type: 'array', required: '是', desc: '要写入的二维列表' },
    ],
    responseExample: {
      code: 0,
      data: { a1Notation: 'A2' },
    },
    responseFields: [
      { key: 'code', desc: '业务状态码，成功固定为 0' },
      { key: 'data.a1Notation', desc: '实际被更新的单元格区域地址' },
    ],
  },
  '/service/zyx/dingtalk/dingpan/upload': {
    requestExample: {
      local_path: '/opt/service-zyx/ozon-fahuo-data/demo',
      as_zip: true,
      save_name: 'demo.zip',
      folder_url: 'https://qr.dingtalk.com/page/yunpan?route=previewDentry&spaceId=xxx&fileId=xxx&type=folder',
    },
    requestFields: [
      { key: 'local_path', type: 'string', required: '是', desc: '服务器本地文件或目录路径' },
      { key: 'as_zip', type: 'boolean', required: '否', desc: '目录时是否先压缩再上传，默认 false' },
      { key: 'save_name', type: 'string', required: '否', desc: '钉盘保存名；目录默认 {目录名}.zip' },
      { key: 'folder_url', type: 'string', required: '否', desc: '钉盘文件夹复制链接，可覆盖默认目标' },
      { key: 'space_id', type: 'string', required: '否', desc: '钉盘 spaceId，可与 parent_folder_id 一起指定目标' },
      { key: 'parent_folder_id', type: 'string', required: '否', desc: '目标文件夹 fileId' },
    ],
    responseExample: {
      code: 0,
      data: {
        data: [
          {
            fileId: 'xxx',
            spaceId: 'xxx',
            fileName: 'demo.zip',
            fileSize: '1024',
            fileType: 'zip',
            uuid: 'xxx',
            path: '/demo.zip',
          },
        ],
      },
    },
    responseFields: [
      { key: 'code', desc: '业务状态码，成功固定为 0' },
      { key: 'data.data', desc: '上传结果文件列表' },
      { key: 'data.data[].fileId', desc: '钉盘文件 ID' },
      { key: 'data.data[].spaceId', desc: '钉盘空间 ID' },
      { key: 'data.data[].fileName', desc: '保存后的文件名' },
      { key: 'data.data[].fileSize', desc: '文件大小（字符串）' },
      { key: 'data.data[].fileType', desc: '文件扩展名' },
      { key: 'data.data[].uuid', desc: '钉盘文件 uuid' },
      { key: 'data.data[].path', desc: '钉盘内路径' },
    ],
  },
  '/service/zyx/jst/gettoken': {
    requestExample: { force: false, code: '' },
    requestFields: [
      { key: 'force', type: 'boolean', required: '否', desc: '是否强制刷新 token' },
      { key: 'code', type: 'string', required: '否', desc: '首次授权码；刷新时可不传' },
    ],
    responseExample: {
      code: 0,
      data: {
        access_token: 'xxx',
        expires_in: 7200,
        refresh_token: 'xxx',
      },
    },
    responseFields: [
      { key: 'code', desc: '业务状态码，成功固定为 0' },
      { key: 'data.access_token', desc: '聚水潭 access_token' },
      { key: 'data.expires_in', desc: '有效期（秒）' },
      { key: 'data.refresh_token', desc: '刷新 token' },
    ],
  },
  '/service/zyx/jst/sku/query': {
    requestExample: { sku: 'ABC-001' },
    requestFields: [
      { key: 'sku', type: 'string', required: '是', desc: '商品编码 / 货号' },
    ],
    responseExample: {
      code: 0,
      data: { sku: 'ABC-001', found: true, item: {} },
    },
    responseFields: [
      { key: 'code', desc: '业务状态码，成功固定为 0' },
      { key: 'data.sku', desc: '查询的 SKU' },
      { key: 'data.found', desc: '是否查到商品' },
      { key: 'data.item', desc: '聚水潭原始商品字段；未找到时为 null' },
    ],
  },
  '/service/zyx/jst/order/query': {
    requestExample: {
      o_ids: [123456],
      so_ids: [],
      modified_begin: '2026-07-01 00:00:00',
      modified_end: '2026-07-07 23:59:59',
      page_index: 1,
      page_size: 50,
      volume: true,
      package: true,
    },
    requestFields: [
      { key: 'o_id', type: 'string', required: '否', desc: '内部订单号（单个，兼容旧参数）' },
      { key: 'so_id', type: 'string', required: '否', desc: '线上订单号（单个，兼容旧参数）' },
      { key: 'o_ids', type: 'array', required: '否', desc: '内部订单号列表，最多20；与时间/线上单号/start_ts 不能同时为空' },
      { key: 'so_ids', type: 'array', required: '否', desc: '线上单号列表，最多20' },
      { key: 'shop_id', type: 'integer', required: '否', desc: '店铺编号' },
      { key: 'is_offline_shop', type: 'boolean', required: '否', desc: 'shop_id=0 且为 true 时查线下店铺单据' },
      { key: 'modified_begin', type: 'string', required: '否', desc: '起始时间，须与 modified_end 同时存在，间隔≤7天' },
      { key: 'modified_end', type: 'string', required: '否', desc: '结束时间' },
      { key: 'date_type', type: 'number', required: '否', desc: '0修改时间 / 2订单日期 / 3发货时间，默认0' },
      { key: 'status', type: 'string', required: '否', desc: 'WaitPay/Delivering/Merged/Question/Split/WaitOuterSent/WaitConfirm/WaitFConfirm/Sent/Cancelled' },
      { key: 'page_index', type: 'integer', required: '否', desc: '页码，从1开始' },
      { key: 'page_size', type: 'integer', required: '否', desc: '每页条数，最大100' },
      { key: 'start_ts', type: 'integer', required: '否', desc: 'ts时间戳增量查询（>=），建议配合 is_get_total=false' },
      { key: 'is_get_total', type: 'boolean', required: '否', desc: '是否查总条数；start_ts 时建议 false' },
      { key: 'order_types', type: 'array', required: '否', desc: '订单类型，如 ["普通订单"]' },
      { key: 'archive', type: 'boolean', required: '否', desc: '是否查历史订单，默认 false' },
      { key: 'volume', type: 'boolean', required: '否', desc: 'order_flds：体积' },
      { key: 'package', type: 'boolean', required: '否', desc: 'order_flds：包材' },
      { key: 'outer_drp_co_id', type: 'boolean', required: '否', desc: 'order_flds：货主分销' },
      { key: 'cus_id', type: 'boolean', required: '否', desc: 'order_flds：货通客户id' },
      { key: 'logistics_status', type: 'boolean', required: '否', desc: 'order_flds：o2o配送状态' },
      { key: 'src_combine_sku_qty', type: 'boolean', required: '否', desc: 'order_item_flds：原组合商品数量' },
      { key: 'referrer_name', type: 'boolean', required: '否', desc: 'order_item_flds：达人名称' },
      { key: 'presale_date', type: 'boolean', required: '否', desc: 'order_item_flds：预售时间' },
      { key: 'drp_price', type: 'boolean', required: '否', desc: 'order_item_flds：采购价' },
      { key: 'item_plan_delivery_date', type: 'boolean', required: '否', desc: 'order_item_flds：最晚发货时间' },
      { key: 'activity_u_id', type: 'boolean', required: '否', desc: 'order_item_flds：团长id' },
      { key: 'activity_u_name', type: 'boolean', required: '否', desc: 'order_item_flds：团长名称' },
    ],
    responseExample: {
      code: 0,
      data: {},
    },
    responseFields: [
      { key: 'code', desc: '业务状态码，成功固定为 0' },
      { key: 'data', desc: '聚水潭 /open/orders/single/query 返回的原始 data' },
    ],
  },
  '/service/zyx/jst/inventory/query': {
    requestExample: { sku: 'ABC-001', wms_co_ids: [15774928] },
    requestFields: [
      { key: 'sku', type: 'string', required: '是', desc: '商品编码' },
      { key: 'wms_co_ids', type: 'array', required: '否', desc: '分仓公司编号列表；空表示所有仓总库存' },
    ],
    responseExample: {
      code: 0,
      data: {},
    },
    responseFields: [
      { key: 'code', desc: '业务状态码，成功固定为 0' },
      { key: 'data', desc: '聚水潭库存查询原始返回数据' },
    ],
  },
  '/service/zyx/ozon/fahuo': {
    requestExample: { wait: true, upload_to_dingpan: true },
    requestFields: [
      { key: 'wait', type: 'boolean', required: '否', desc: 'true 同步等待结果；false 返回 job_id 异步执行' },
      { key: 'upload_to_dingpan', type: 'boolean', required: '否', desc: '成功后是否上传钉盘' },
      { key: 'dingpan_folder_url', type: 'string', required: '否', desc: '钉盘目标文件夹链接，可覆盖默认' },
    ],
    responseExample: {
      code: 0,
      data: {
        job_id: 'uuid',
        job_status: 'done',
        run_status: 'success',
        success: [],
        file_ids: [],
      },
    },
    responseFields: [
      { key: 'code', desc: '业务状态码，成功固定为 0' },
      { key: 'data.job_id', desc: '任务 ID' },
      { key: 'data.job_status', desc: '任务状态：running / done 等' },
      { key: 'data.run_status', desc: '业务结果：success / partial / failed / skipped（异步未完成时可能暂无）' },
      { key: 'data.success', desc: '成功创建的供货单唯一 ID 列表' },
      { key: 'data.file_ids', desc: '上传钉盘后的文件 ID 列表' },
    ],
  },
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
          <thead><tr><th>方法</th><th>路径</th><th>名称</th><th>描述</th><th style="width:240px">操作</th></tr></thead>
          <tbody>
            <tr v-for="a in apis" :key="a.id">
              <td><span :class="['badge-method','m-'+a.method]">{{a.method}}</span></td>
              <td style="font-family:monospace;font-size:12px">{{a.path}}</td>
              <td style="font-weight:500">{{a.name}}</td>
              <td style="color:#86909c;font-size:12px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{a.description||'-'}}</td>
              <td>
                <button class="btn btn-ghost btn-sm" @click="openDocs(a)">参数</button>
                <button class="btn btn-primary btn-sm" style="margin-left:6px" @click="openExec(a)">执行</button>
                <button class="btn btn-ghost btn-sm" style="margin-left:6px" @click="openLogs(a)">日志</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Docs Modal -->
    <modal-box title="接口参数" :visible="!!docsApi" :wide="true" @close="docsApi=null">
      <div class="api-docs-path">{{docsApi?.method}} {{docsApi?.path}}</div>
      <template v-if="docsInfo">
        <div class="api-docs-section">
          <div class="api-docs-title">请求体示例</div>
          <pre class="log-response">{{fmtJson(docsInfo.requestExample)}}</pre>
          <table class="api-docs-table">
            <thead><tr><th>字段</th><th>类型</th><th>必填</th><th>说明</th></tr></thead>
            <tbody>
              <tr v-for="f in docsInfo.requestFields" :key="'req-'+f.key">
                <td class="code">{{f.key}}</td>
                <td>{{f.type}}</td>
                <td>{{f.required}}</td>
                <td>{{f.desc}}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="api-docs-section">
          <div class="api-docs-title">响应体示例（成功）</div>
          <pre class="log-response">{{fmtJson(docsInfo.responseExample)}}</pre>
          <table class="api-docs-table">
            <thead><tr><th>字段</th><th>说明</th></tr></thead>
            <tbody>
              <tr v-for="f in docsInfo.responseFields" :key="'resp-'+f.key">
                <td class="code">{{f.key}}</td>
                <td>{{f.desc}}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
      <div v-else class="api-docs-empty">该接口暂无参数说明文档</div>
      <div class="modal-footer">
        <button class="btn btn-ghost" @click="docsApi=null">关闭</button>
      </div>
    </modal-box>

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
    const docsApi = ref(null);

    const execFields = computed(() => {
      const path = execApi.value?.path || '';
      return API_PARAMS[path] || [];
    });

    const docsInfo = computed(() => {
      const path = docsApi.value?.path || '';
      return API_DOCS[path] || null;
    });

    async function loadData() {
      loading.value = true;
      try { const r = await http.get(`/service/zyx/apis?project_id=1&keyword=${encodeURIComponent(keyword.value)}&method=${methodFilter.value}`); apis.value = r.data.data || []; } catch(e){ apis.value = []; } finally { loading.value = false; }
    }
    onMounted(loadData);

    function openDocs(a) {
      docsApi.value = a;
    }

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
        if (!text) continue;
        if (f.type === 'json') {
          out[f.key] = JSON.parse(text);
          continue;
        }
        out[f.key] = text;
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
    function fmtJson(obj) {
      try { return JSON.stringify(obj, null, 2); } catch (e) { return String(obj); }
    }

    return {
      apis, loading, keyword, methodFilter, methods, loadData,
      execApi, execForm, execFields, executing, openExec, doExec,
      logApi, logs, openLogs, detailLog, fmt, fmtJson,
      docsApi, docsInfo, openDocs,
    };
  }
};
