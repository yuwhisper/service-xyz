# Service XYZ

接口管理后台 + 业务 API（FastAPI + Vue 3 CDN，零构建）。

- 控制台：数据中心 / 调度任务 / 定时任务
- 内置：Ozon FBO 发货、钉钉钉盘上传、聚水潭 Token / SKU / 订单 / 库存查询
- 全站业务 API **免 JWT**，可供影刀等直接调用

## 本地开发

```bash
pip install -r requirements.txt
cp config.json.example config.json   # 填入数据库连接
cp .env.example .env                 # 可选，覆盖环境变量
python scripts/setup.py
python server/main.py
```

打开 http://localhost:3000 — 默认账号：`admin` / `admin123`

## 生产部署

| 项 | 值 |
|----|-----|
| 路径 | `/opt/service-zyx` |
| 端口 | **8800**（systemd `service-zyx`） |
| 环境 | `/opt/service-zyx/.env` |

推送 `main` 后由 GitHub Actions 打包 SCP 到服务器并重启（服务器常无法直连 GitHub，勿依赖 `git pull`）。Secrets：`SSH_HOST`、`SSH_USER`、`SSH_KEY`。详见 [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml)。

手动部署：

```bash
bash /opt/service-zyx/deploy/deploy.sh
```

## 访问入口

| 地址 | 说明 |
|------|------|
| https://www.ywzhaoran.xyz/service/zyx/ | 管理后台 + API（推荐） |
| https://121.43.75.44:8443/ | IP 入口（旧） |

## 主要 API

前缀：`/service/zyx/`

| Method | Path | 说明 |
|--------|------|------|
| POST | `/ozon/fahuo` | Ozon FBO 发货（`wait: true` 同步） |
| GET | `/ozon/fahuo/status/{job_id}` | 发货任务状态 |
| POST | `/dingtalk/dingpan/upload` | 钉盘上传 |
| GET/POST | `/jst/gettoken` | 聚水潭 Token |
| GET/POST | `/jst/sku/query` | 按 SKU 查商品（原始字段） |
| GET/POST | `/jst/order/query` | 按 `o_id` / `so_id` 查订单（原始数据） |
| GET/POST | `/jst/inventory/query` | 按 SKU + 分仓编号列表查库存 |
| GET | `/dashboard/stats` | 概览统计 |
| GET | `/dashboard/logs` | 执行日志（搜索 + 分页） |
| * | `/apis`、`/schedules` | 控制台接口定义与定时任务 |

完整约定、目录结构、新增 API 登记方式见 [`CLAUDE.md`](CLAUDE.md)。

## 目录速览

```
server/          FastAPI（routers + ozon / jushuitan / dingtalk）
client/          Vue 3 SPA（CDN，无构建）
scripts/setup.py 建表 + 登记内置 API
deploy/          systemd / nginx / 部署脚本
```

## 影刀调用 Ozon 发货（示例）

```http
POST https://www.ywzhaoran.xyz/service/zyx/ozon/fahuo
Content-Type: application/json

{"wait": true, "upload_to_dingpan": true}
```

看响应 `data.run_status`、`data.success`、`data.file_ids`。长耗时需 Nginx `proxy_read_timeout` ≥ 1800s；也可 `wait: false` 后轮询 status。
