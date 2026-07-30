# 每日数据补全（影刀启动应用）设计规格

> 日期：2026-07-30  
> 状态：待实现  
> 依据：`影刀/调用应用/调用应用.py` + 控制台侧栏需求

## 1. 目标

在 Service XYZ 控制台侧栏「定时任务」下方增加 **每日数据补全**，用影刀开放 API 启动指定应用，并在本页手动刷新任务状态。

成功标准：

- 页面列出全部业务/调度参数（必填、非必填标注清楚）
- `accessKeyId` / `accessKeySecret` 仅存服务器 `.env`，不出前端
- 点「启动」可拿到 `jobUuid`；点「刷新状态」才查询，**无自动轮询**
- 影刀 HTTP 状态码（200/401/400/429/500）有中文说明

## 2. 架构

```
侧栏「每日数据补全」
  → client/js/pages/backfill.js（表单 + 启动 + 手动刷新）
  → POST /service/zyx/yingdao/job/start
  → POST /service/zyx/yingdao/job/query   （仅按钮触发）
  → server/yingdao/*  （token + 代理影刀公有云 API）
```

| 组件 | 职责 |
|------|------|
| `client/js/pages/backfill.js` | 参数表单、启动、手动刷新状态、错误码文案 |
| `client/js/app.js` | 侧栏项 + 动态加载页面 |
| `server/routers/yingdao.py` | FastAPI 路由，免 JWT |
| `server/yingdao/config.py` | 读环境变量 |
| `server/yingdao/client.py` | `get_access_token` / `start_job` / `query_job`（对齐现有脚本） |

不采用：前端直调影刀、自动 5s 轮询、把本功能仅塞进「调度任务」而无独立页。

## 3. API

前缀：`/service/zyx/`。响应约定与全站一致：成功 `{ "code": 0, "data": ... }`；失败 HTTP + `detail`。

### 3.1 `POST /yingdao/job/start`

Body（字段名与影刀 / 脚本对齐）：

| 字段 | 必填 | 说明 |
|------|------|------|
| `robotUuid` | 是 | 应用 UUID |
| `accountName` | 条件 | 与 `robotClientGroupUuid` 二选一；都填时以分组为准 |
| `robotClientGroupUuid` | 条件 | 同上 |
| `params` | 否 | `[{ "name","value","type" }]`；空项不传。页面映射「开始日期」「结束日期」 |
| `waitTimeoutSeconds` | 否 | 默认 600；范围 60～950400 |
| `runTimeout` | 否 | 不传则不下发 |
| `priority` | 否 | 默认 `middle` |
| `executeScope` | 否 | 仅分组有效；默认 `any` |
| `useIdempotent` | 否 | 默认 `true`；为 true 时服务端生成 ≤36 位 uuid |

服务端用 `.env` Key/Secret 换 token，再调：

`POST https://api.yingdao.com/oapi/dispatch/v2/job/start`

成功 `data` 至少包含影刀返回的 `jobUuid`、`idempotentFlag` 及原始有用字段。

### 3.2 `POST /yingdao/job/query`

Body：`{ "jobUuid": "..." }`（必填）。

代理：`POST https://api.yingdao.com/oapi/dispatch/v2/job/query`。

成功时 `data` 含影刀 `status` / `statusName` 等原始字段（如 `waiting` / `running` / `finish` / `error`）。

### 3.3 Token

- 环境变量：`YINGDAO_ACCESS_KEY_ID`、`YINGDAO_ACCESS_KEY_SECRET`
- 可选：`YINGDAO_TOKEN_URL`、`YINGDAO_JOB_START_URL`、`YINGDAO_JOB_QUERY_URL`（默认公有云地址）
- Token 可短时内存缓存；上游 401 时清缓存重换一次再试

## 4. 前端页面

### 4.1 侧栏

- 文案：每日数据补全  
- 位置：定时任务下方  
- 图标：影刀 Logo 静态资源（如 `client/img/yingdao.png`），非 emoji  
- `app.js` 增加 menu key（建议 `backfill`），bump `?v=`

### 4.2 表单分区

1. **调度目标（必填）**  
   - `robotUuid`  
   - `accountName`、`robotClientGroupUuid`（说明二选一，都填以分组为准）

2. **应用参数（非必填）**  
   - 开始日期、结束日期（空则不加入 `params`）

3. **可选调度**  
   - waitTimeoutSeconds、runTimeout、priority、executeScope、useIdempotent  
   - 默认值与脚本一致

### 4.3 操作与状态区

- **启动**：校验必填 → start → 展示 `jobUuid` 与原始 JSON  
- **刷新状态**：无 `jobUuid` 时禁用；有则 query 一次并更新展示  
- **禁止**定时自动请求  

### 4.4 影刀 HTTP 状态码展示

与 Job 业务状态分开展示。HTTP 层提示：

| 状态码 | 说明 | 排查建议 |
|--------|------|----------|
| 200 | 正常 | 调用正常 |
| 401 | 接口未授权 | 1. 排查 accessKeyId / accessSecret 是否正确 2. 排查请求地址（公有云 / 专有云） |
| 400 | 接口参数校验错误 | Key 未配置或错误；用企业管理员在影刀后台核对 |
| 429 | 触发接口限流 | 稍后重试；参考影刀限流文档 |
| 500 | 服务内部错误 | 联系影刀技术支持 |

后端在失败响应中带上上游 HTTP 状态（及 body 摘要），前端按上表渲染中文说明；200 时再展示 Job 的 `status` / `statusName`。

## 5. 登记与部署

按现有约定：

1. `main.py` `include_router`  
2. `scripts/setup.py` builtins 幂等登记 start / query  
3. `dispatch.js` 可选补充 `API_PARAMS` / `API_DOCS`（主入口仍是独立页）  
4. `.env.example` 增加影刀变量说明；生产 `.env` 由运维填写（**不把真实密钥写入仓库**）  
5. 推送 `main` 走 Actions；确认服务器文件与服务 active  

本地脚本里的默认 Key/Uuid **可作联调参考**，但仓库内示例只用占位符。

## 6. 非目标

- 不实现自动轮询 / WebSocket  
- 不在页面配置或展示 accessKey  
- 不修改影刀应用流程本身  
- 不把 `docs/` 当作运行时依赖（Actions 仍排除 docs）

## 7. 决策摘要

| 项 | 选择 |
|----|------|
| 入口形态 | 独立侧栏页 + 后端代理 |
| 凭证 | 仅 `.env` Key/Secret |
| 账号 / robotUuid | 页面必填 |
| 状态刷新 | 仅手动「刷新状态」 |
| 轮询 | 不做 |
