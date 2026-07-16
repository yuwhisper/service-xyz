# Service XYZ

接口管理后台（FastAPI + Vue 3 CDN，零构建）。

## 本地开发

```bash
pip install -r requirements.txt
cp config.json.example config.json   # 填入数据库连接信息
cp .env.example .env                 # 可选，覆盖环境变量
python scripts/setup.py
python server/main.py
```

浏览器打开 http://localhost:3000 — 默认账号：`admin` / `admin123`

## 生产部署

服务器路径：`/opt/service-zyx`，端口 **8800**。

```bash
bash /opt/service-zyx/deploy/deploy.sh
```

**说明：** 服务器可能无法直接访问 GitHub。若 `git pull` 失败，请在本地 push 后通过 SFTP 上传，或在服务器配置 Git 代理/镜像。

可选 GitHub Actions 自动部署：在仓库 Secrets 中配置 `SSH_HOST`、`SSH_USER`、`SSH_KEY`（私钥），并确保服务器 `/root/.ssh/authorized_keys` 已写入对应公钥。推送到 `main`（或手动 Run workflow）后会触发 [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml)，在服务器执行 `deploy/deploy.sh`（`git fetch` + `reset --hard origin/main` 后重启服务）。

## 访问入口

| 地址 | 说明 |
|------|------|
| `https://www.ywzhaoran.xyz/service/zyx/` | 管理后台（SPA）+ API |
| `https://121.43.75.44:8443/` | 管理后台（IP 入口，旧） |

## API 前缀

所有接口均在 `/service/zyx/` 下，完整列表见 [`CLAUDE.md`](CLAUDE.md)。
