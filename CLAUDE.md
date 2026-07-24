## 项目概述

**Service XYZ** — 接口管理后台 + 业务 API 网关。

- 控制台：按影刀风格管理/调试/调度 HTTP 接口，查看执行日志
- 内置业务：Ozon FBO 发货、钉钉钉盘上传、聚水潭 Token / SKU / 订单 / 库存查询
- 全站 API **免 JWT**，影刀等外部系统可直接调用

## 沟通方式

- 默认中文回复；代码、命令、变量名、文件路径保持英文
- 结论先行，简洁直接
- 方案有问题直接指出，发现更好做法主动说明

## Git

- 不自动 `git commit` / `git push`，除非明确要求
- **「提交」= `git commit` + `git push`**
- commit message：`yyyy-MM-dd HH:mm` + 改动简述（例：`2026-07-21 15:30 更新钉钉钉盘默认上传文件夹链接`）

## 红线操作

以下操作必须先确认：

- 删除文件、目录或 git 历史
- 修改 `.env`、密钥、token、证书、CI/CD 配置
- `git rebase`、`git reset --hard`、强制推送
- 未经要求不要 `git push`（「提交」时除外）

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | FastAPI + uvicorn + aiomysql / pymysql |
| 数据库 | MySQL（库名 `zyx`） |
| 认证 | 业务 API 免 JWT；`auth.py` 仍有登录发 token 能力，路由未强制校验 |
| 前端 | Vue 3 + axios（CDN esm.sh，零构建，无 npm） |
| 业务依赖 | requests、openpyxl、Pillow、pymupdf |

> 机器装有绿盾：npm `node_modules` 会被透明加密。前端必须走 CDN import map，禁止引入本地构建链。

## 目录结构

```
service-xyz/
├── server/                      # FastAPI 后端
│   ├── main.py                  # 入口：CORS、路由、静态资源、SPA fallback
│   ├── config.py                # config.json + 环境变量
│   ├── database.py              # aiomysql 连接池
│   ├── auth.py                  # JWT / 密码哈希（可选登录）
│   ├── routers/
│   │   ├── auth.py              # /service/zyx/auth/*
│   │   ├── dashboard.py         # 统计 + 全量日志分页搜索
│   │   ├── apis.py              # interfaces CRUD / 执行 / 日志
│   │   ├── schedules.py         # 定时任务 CRUD
│   │   ├── ozon.py              # Ozon FBO 发货
│   │   ├── dingtalk.py          # 钉盘上传
│   │   └── jst.py               # 聚水潭 token / SKU / 订单 / 库存
│   ├── ozon/                    # fahuo_core + fahuo_runner
│   ├── jushuitan/               # OpenAPI client + token 缓存
│   └── dingtalk/                # 钉盘上传实现
├── client/                      # Vue 3 SPA（纯静态）
│   ├── index.html               # import map 入口
│   ├── css/app.css
│   └── js/
│       ├── app.js               # 布局 + 侧边栏 + 页面切换
│       ├── api.js               # axios 实例
│       ├── toast.js
│       └── pages/
│           ├── dashboard.js     # 数据中心
│           ├── dispatch.js      # 调度任务（按接口显示参数框）
│           ├── schedule.js      # 定时任务
│           └── login.js         # 登录页（当前未强制登录门禁）
├── deploy/
│   ├── deploy.sh                # 服务器部署脚本
│   ├── service-zyx.service      # systemd（端口 8800）
│   └── nginx-*.conf
├── scripts/
│   ├── setup.py                 # 建表 + 种子 + 登记内置 API
│   └── setup_ozon_table.sql     # Ozon 装箱发货登记表（手动执行）
├── .github/workflows/deploy.yml # Actions：打包 SCP 部署
├── docs/                        # 影刀等调用说明
├── .env.example
├── config.json.example
├── requirements.txt
├── CLAUDE.md
└── README.md
```

运行时数据（不入库）：

- `/opt/service-zyx/ozon-fahuo-data` — 发货输出归档（`OZON_ARCHIVE_ROOT`）
- `/opt/service-zyx/.jst_tokens.json` — 聚水潭 token 缓存

## 快速开始（本地）

```bash
pip install -r requirements.txt
cp config.json.example config.json   # 填数据库
cp .env.example .env                 # 可选
python scripts/setup.py
python server/main.py
# http://localhost:3000
# 默认账号 username=admin / password=admin123
```

| 环境 | 端口 | 说明 |
|------|------|------|
| 本地 | `PORT`，默认 **3000** | `python server/main.py` |
| 生产 | **8800** | systemd `service-zyx` |
| 域名 | 443 → 8800 | `https://www.ywzhaoran.xyz/service/zyx/` |
| IP 入口 | 8443 → 8800 | `https://121.43.75.44:8443/`（旧） |

## 生产部署

- 路径：`/opt/service-zyx`，环境文件：`.env`
- 推送 `main` → GitHub Actions 打包 SCP 上传 → `pip install` → `setup.py` → `systemctl restart service-zyx`
- 服务器拉 GitHub 常超时，**不要依赖服务器 `git pull`**；以 Actions SCP 为准
- 手动：`bash /opt/service-zyx/deploy/deploy.sh`

## API 路由

前缀均为 `/service/zyx/`。业务路由均免 JWT。

### 控制台

| Method | Path | 说明 |
|--------|------|------|
| POST | `/auth/login` | 登录（可选） |
| GET | `/auth/user/me` | 当前实现固定返回 guest |
| GET | `/dashboard/stats` | 概览统计 |
| GET | `/dashboard/logs` | 全量日志；`keyword` 搜路径/接口名；`page` + `page_size`(20/50/100/200) |
| GET/POST/PUT/DELETE | `/apis`、`/apis/{id}` | 接口定义 CRUD |
| POST | `/apis/{id}/execute` | 调度执行（内部路径转发本机） |
| GET | `/apis/{id}/logs` | 单接口最近日志 |
| GET/POST/PUT/DELETE | `/schedules`、`/schedules/{id}` | 定时任务 |

### 业务

| Method | Path | 说明 |
|--------|------|------|
| POST | `/ozon/fahuo` | Ozon FBO 发货；`wait=true` 同步 / 默认异步返回 `job_id` |
| GET | `/ozon/fahuo/status/{job_id}` | 发货任务状态 |
| POST | `/dingtalk/dingpan/upload` | 上传本地文件/目录到钉盘 |
| GET/POST | `/jst/gettoken` | 聚水潭 access_token（`code` / `force`） |
| GET/POST | `/jst/sku/query` | 按 `sku` 查商品资料，返回原始字段 |
| GET/POST | `/jst/order/query` | 按 `o_id` 或 `so_id` 查订单，返回原始 data |
| GET/POST | `/jst/inventory/query` | 按 `sku` + `wms_co_ids` 查分仓库存 |

## 内置业务模块

### Ozon FBO（`server/ozon/`）

- 读表 `ods_ozon_装箱发货登记表`（运营发货日期=当天且发货状态为空）
- 按 日期+店铺+发货人+发货方式+批次/订单号 分组创供货单，生成箱唛/询价表/顺序表
- 成功后可选压缩上传钉盘（`OZON_UPLOAD_DINGPAN` / 请求参数 `upload_to_dingpan`）
- 店铺凭证：`OZON_SHOP_DATA`；归档根：`OZON_ARCHIVE_ROOT`

影刀推荐同步调用：

```http
POST https://www.ywzhaoran.xyz/service/zyx/ozon/fahuo
Content-Type: application/json

{"wait": true, "upload_to_dingpan": true}
```

- HTTP 始终 200，`code` 始终 0
- `run_status`：`success` / `partial` / `failed` / `skipped`
- 成功唯一 ID：`data.success`；钉盘 fileId：`data.file_ids`
- 异步：`{"wait": false}` → 轮询 `/ozon/fahuo/status/{job_id}`
- Nginx 对 `/service/zyx/ozon` 建议 `proxy_read_timeout` ≥ 1800s

### 钉钉钉盘（`server/dingtalk/`）

- 凭证：`DINGTALK_APP_KEY` / `SECRET` / `UNION_ID`
- 默认文件夹：`DINGTALK_DEFAULT_FOLDER_URL`（请求可传 `dingpan_folder_url` 覆盖）
- 上传路径白名单：`DINGTALK_UPLOAD_ALLOW_ROOTS`

### 聚水潭（`server/jushuitan/`）

- Token 与 `/jst/gettoken` 共用 `get_access_token()` 缓存（`.jst_tokens.json`）
- SKU / 订单 / 库存接口返回聚水潭原始字段，不做翻译或二次加工
- 库存：`POST /jst/inventory/query`，body `{ "sku": "...", "wms_co_ids": [分仓编号, ...] }`；空列表表示所有仓总库存

## 数据库

库名 `zyx`。主要表：

| 表 | 说明 |
|----|------|
| `users` / `projects` | 用户与项目（setup 种子管理员与 Default 项目） |
| `interfaces` | 控制台可见的 API 目录 |
| `api_logs` | 执行日志 |
| `schedules` | 定时任务 |
| `ods_ozon_装箱发货登记表` | Ozon 待发货登记（见 `scripts/setup_ozon_table.sql`） |

### 新增 API 必须登记 `interfaces`

调度任务 / 定时任务 / 数据中心列表**只读** `interfaces` 表，**不会**自动扫描 FastAPI 路由。

1. 在 `server/routers/` 写路由，并在 `main.py` `include_router`
2. 在 [`scripts/setup.py`](scripts/setup.py) 的 `builtins` 按 path 幂等追加
3. 执行 `python scripts/setup.py`（本地或部署时会跑）
4. 确认控制台「调度任务」能看到

当前 builtins：

| 名称 | Method | Path | body_type |
|------|--------|------|-----------|
| Ozon FBO 发货 | POST | `/service/zyx/ozon/fahuo` | json |
| 钉钉钉盘上传 | POST | `/service/zyx/dingtalk/dingpan/upload` | json |
| 聚水潭获取Token | GET | `/service/zyx/jst/gettoken` | none |
| 聚水潭查询商品资料 | GET | `/service/zyx/jst/sku/query` | none |
| 聚水潭查询订单详情 | GET | `/service/zyx/jst/order/query` | none |
| 聚水潭查询商品库存 | POST | `/service/zyx/jst/inventory/query` | json |

内部路径（以 `/` 开头）：执行时转发到 `INTERNAL_API_BASE`（默认 `http://127.0.0.1:{PORT}`；生产一般为 8800）。

调度弹窗参数：在 [`client/js/pages/dispatch.js`](client/js/pages/dispatch.js) 的 `API_PARAMS` 按 path 配置输入框；无参接口不显示输入框。

## 环境变量（摘要）

详见 [`.env.example`](.env.example)。

| 类别 | 变量 |
|------|------|
| 服务 | `PORT` |
| MySQL | `DB_HOST` `DB_PORT` `DB_NAME` `DB_USER` `DB_PASS` |
| Ozon | `OZON_ARCHIVE_ROOT` `OZON_SHOP_DATA` `OZON_UPLOAD_DINGPAN` … |
| 钉盘 | `DINGTALK_APP_KEY` `DINGTALK_APP_SECRET` `DINGTALK_UNION_ID` `DINGTALK_DEFAULT_FOLDER_URL` … |
| 聚水潭 | `JUSHUITAN_APP_KEY` `JUSHUITAN_APP_SECRET` `JUSHUITAN_AUTH_CODE` `JUSHUITAN_TOKEN_FILE` |

## 约定

- 成功响应：`{ "code": 0, "data": ... }`；错误走 FastAPI `detail`
- 密码：pbkdf2_hmac(sha512)，`salt:hex`
- 前端页面用 `.js` + Vue SFC 风格 `template` 字符串；依赖走 esm.sh
- `client/js/components/`、`auth.js` 等遗留 React 文件勿再扩展；以 `app.js` + `pages/` 为准
