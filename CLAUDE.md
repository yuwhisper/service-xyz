## 项目概述

**Service XYZ** — 接口管理后台（API Management Console），参考影刀 RPA 控制台 UI 设计，提供 API 接口的统一管理、调试执行和定时调度能力。

## 沟通方式

- 默认中文回复；代码、命令、变量名、文件路径保持英文
- 结论先行，简洁直接，不先铺垫背景
- 给真实判断——方案有问题直接指出，发现更好做法主动说明

## Git

- 不自动 `git commit` 或 `git push`，除非我明确要求
- 提交前先展示将要提交的变更摘要
- commit message 使用简洁英文

## 红线操作

以下操作即使在 auto-accept 模式下也必须先问我：
- 删除文件、目录或 git 历史
- 修改 `.env`、密钥、token、证书、CI/CD 配置
- `git push`、`git rebase`、`git reset --hard`、强制推送
- 公开发布（`npm publish`、生产部署等）

## 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 后端框架 | FastAPI (Python) | latest |
| 数据库 | MySQL (远程 121.43.75.44) + aiomysql | — |
| 认证 | JWT (pyjwt + hashlib.pbkdf2) | — |
| 前端框架 | React (CDN esm.sh, 零构建) | ^18.3 |

> **注意**: 机器装有绿盾软件，npm 写入的 node_modules 会被透明加密。前端用 CDN import map 加载 React，无本地 node_modules 和构建步骤。

## 目录结构

```
service-xyz/
├── server/                  # Python 后端（FastAPI）
│   ├── main.py              # 入口 + CORS + 静态文件 + SPA fallback
│   ├── config.py            # 配置（config.json + 环境变量）
│   ├── database.py          # aiomysql 连接池
│   ├── auth.py              # JWT 认证 + 密码哈希
│   └── routers/
│       ├── auth.py          # POST /service/zyx/auth/login
│       ├── dashboard.py     # GET  /service/zyx/dashboard/stats
│       ├── apis.py          # CRUD /service/zyx/apis + execute + logs
│       └── schedules.py     # CRUD /service/zyx/schedules
├── client/                  # 前端（纯静态，CDN 加载）
│   ├── index.html           # 入口 + import map
│   ├── css/app.css          # 影刀风格样式
│   └── js/
│       ├── app.js           # SPA 布局 + 路由
│       ├── api.js           # axios 实例 + JWT 拦截
│       ├── auth.js          # AuthContext
│       ├── components/
│       │   ├── sidebar.js   # 侧边栏导航
│       │   ├── modal.js     # 通用弹窗
│       │   └── stat-card.js # 统计卡片
│       └── pages/
│           ├── login.js     # 登录页
│           ├── dashboard.js # 数据中心
│           ├── dispatch.js  # 调度任务
│           └── schedule.js  # 定时任务
├── scripts/
│   └── setup.py             # 数据库初始化 + 种子数据
└── config.json              # 项目配置
```

## 快速开始

```bash
# 1. 安装 Python 依赖
pip install fastapi uvicorn aiomysql pyjwt python-jose passlib aiohttp

# 2. 初始化数据库（建表 + 种子数据）
python scripts/setup.py

# 3. 启动服务
python server/main.py
# 访问 http://localhost:3000
# 管理员: admin@service-xyz.com / admin123
```

## API 路由

| Method | Path | Auth | 说明 |
|--------|------|:--:|------|
| POST | /service/zyx/auth/login | — | 登录 |
| GET | /service/zyx/auth/user/me | ✅ | 当前用户 |
| GET | /service/zyx/dashboard/stats | ✅ | 概览统计 |
| GET | /service/zyx/apis | ✅ | 接口列表 |
| GET | /service/zyx/apis/:id | ✅ | 接口详情 |
| POST | /service/zyx/apis | ✅ | 创建接口 |
| PUT | /service/zyx/apis/:id | ✅ | 更新接口 |
| DELETE | /service/zyx/apis/:id | ✅ | 删除接口 |
| POST | /service/zyx/apis/:id/execute | ✅ | 执行接口 |
| GET | /service/zyx/apis/:id/logs | ✅ | 执行日志 |
| GET | /service/zyx/schedules | ✅ | 定时任务列表 |
| POST | /service/zyx/schedules | ✅ | 创建定时任务 |
| PUT | /service/zyx/schedules/:id | ✅ | 更新定时任务 |
| DELETE | /service/zyx/schedules/:id | ✅ | 删除定时任务 |

## 数据库

MySQL 远程服务器 `121.43.75.44:3306`，库名 `zyx`。

表：
- `users` — 用户（email/username/password/role）
- `projects` — 项目
- `interfaces` — API 接口定义（method/path/name）
- `api_logs` — 执行日志（request_params/response_body/status_code/duration_ms）
- `schedules` — 定时任务（api_id/cron_expression/enabled）

## 约定

- API 统一返回 `{ "code": 0, "data": ... }` 成功，`{ "code": xxx, "detail": "..." }` 失败（FastAPI 风格）
- 密码使用 pbkdf2_hmac(sha512) 哈希
- 前端文件用 `.js` 扩展名，纯 `React.createElement` 编写
- import map 通过 esm.sh CDN 加载所有依赖
