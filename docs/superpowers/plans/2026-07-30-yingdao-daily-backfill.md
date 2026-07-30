# 每日数据补全（影刀）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在控制台侧栏增加「每日数据补全」，通过后端代理启动影刀应用，并支持手动刷新 Job 状态。

**架构：** 独立页 `backfill.js` 收集参数 → `POST /service/zyx/yingdao/job/start|query` → `server/yingdao/client.py` 用 `.env` Key/Secret 换 token 后调用影刀公有云 API。密钥不出前端；无自动轮询。

**技术栈：** FastAPI、requests、Vue 3 CDN、MySQL `interfaces` 登记（setup.py）

**规格：** `docs/superpowers/specs/2026-07-30-yingdao-daily-backfill-design.md`

---

## 文件结构

| 文件 | 职责 |
|------|------|
| 创建 `server/yingdao/__init__.py` | 包标记 |
| 创建 `server/yingdao/config.py` | 读取 `YINGDAO_*` 环境变量 |
| 创建 `server/yingdao/client.py` | token / start_job / query_job |
| 创建 `server/routers/yingdao.py` | FastAPI 路由与入参校验 |
| 创建 `client/js/pages/backfill.js` | 表单页：启动 + 手动刷新 |
| 创建 `client/img/yingdao.svg` | 侧栏影刀图标 |
| 创建 `tests/test_yingdao_client.py` | client 负载组装与错误映射（mock requests） |
| 修改 `server/main.py` | `include_router(yingdao.router)` |
| 修改 `scripts/setup.py` | builtins 登记两条接口 |
| 修改 `client/js/app.js` | 侧栏项 + 缓存版本 |
| 修改 `client/css/app.css` | 侧栏图片图标样式（如需） |
| 修改 `.env.example` | 影刀变量占位 |
| 修改 `CLAUDE.md` | API 表补充两行 |
| 修改 `client/js/pages/dispatch.js` | API_PARAMS / API_DOCS（可选但计划内完成） |

生产 `.env` 只在服务器手填 Key/Secret，**不写入仓库**。

---

### 任务 1：影刀 client 配置 + 可测核心逻辑

**文件：**
- 创建：`server/yingdao/__init__.py`
- 创建：`server/yingdao/config.py`
- 创建：`server/yingdao/client.py`
- 创建：`tests/test_yingdao_client.py`

- [ ] **步骤 1：编写失败的测试（payload 与校验）**

```python
# tests/test_yingdao_client.py
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.yingdao import client as yd


def test_build_start_payload_account_mode():
    body = yd.build_start_payload(
        robot_uuid="r1",
        account_name="admin@wxbh",
        robot_client_group_uuid="",
        params=[{"name": "开始日期", "value": "2026-07-27", "type": "str"}],
        wait_timeout_seconds=600,
        run_timeout=None,
        priority="middle",
        execute_scope="any",
        use_idempotent=False,
        idempotent_uuid=None,
    )
    assert body["robotUuid"] == "r1"
    assert body["accountName"] == "admin@wxbh"
    assert "robotClientGroupUuid" not in body
    assert body["params"][0]["name"] == "开始日期"
    assert body["waitTimeoutSeconds"] == 600


def test_build_start_payload_group_wins():
    body = yd.build_start_payload(
        robot_uuid="r1",
        account_name="admin@wxbh",
        robot_client_group_uuid="g1",
        params=None,
        wait_timeout_seconds=120,
        run_timeout=300,
        priority="high",
        execute_scope="all",
        use_idempotent=True,
        idempotent_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    )
    assert body["robotClientGroupUuid"] == "g1"
    assert body["executeScope"] == "all"
    assert "accountName" not in body
    assert body["runTimeout"] == 300
    assert body["idempotentUuid"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_build_start_payload_requires_target():
    with pytest.raises(ValueError, match="账号|分组"):
        yd.build_start_payload(
            robot_uuid="r1",
            account_name="",
            robot_client_group_uuid="",
            params=None,
            wait_timeout_seconds=600,
            run_timeout=None,
            priority="middle",
            execute_scope="any",
            use_idempotent=False,
            idempotent_uuid=None,
        )


def test_map_yingdao_http_hint():
    assert "限流" in yd.http_status_hint(429)
    assert "未授权" in yd.http_status_hint(401)
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd service-xyz
python -m pytest tests/test_yingdao_client.py -v
```

预期：FAIL（模块不存在或函数未定义）

- [ ] **步骤 3：实现 config + client**

`server/yingdao/__init__.py`：空文件或 docstring。

`server/yingdao/config.py`：

```python
import os

ACCESS_KEY_ID = os.getenv("YINGDAO_ACCESS_KEY_ID", "")
ACCESS_KEY_SECRET = os.getenv("YINGDAO_ACCESS_KEY_SECRET", "")
TOKEN_URL = os.getenv(
    "YINGDAO_TOKEN_URL",
    "https://api.yingdao.com/oapi/token/v2/token/create",
)
JOB_START_URL = os.getenv(
    "YINGDAO_JOB_START_URL",
    "https://api.yingdao.com/oapi/dispatch/v2/job/start",
)
JOB_QUERY_URL = os.getenv(
    "YINGDAO_JOB_QUERY_URL",
    "https://api.yingdao.com/oapi/dispatch/v2/job/query",
)
```

`server/yingdao/client.py` 要点（对齐 `影刀/调用应用/调用应用.py`）：

- `_token_cache: dict` 存 `{token, expires_at}`；无明确过期则缓存 50 分钟
- `get_access_token(force=False)`：缺 Key 抛 `ValueError`；POST TOKEN_URL；`success` 假则抛错
- `build_start_payload(...)`：纯函数，供测试；分组优先；过滤空 params；idempotent 截断 36
- `start_job(...)` / `query_job(job_uuid)`：Bearer 请求；非 200 抛自定义 `YingdaoHttpError(status_code, body)`
- `http_status_hint(code: int) -> str`：返回规格表中文说明（200/401/400/429/500/其它）
- 401：清缓存、`force` 重换 token 再试一次

- [ ] **步骤 4：运行测试确认通过**

```bash
python -m pytest tests/test_yingdao_client.py -v
```

预期：PASS（若环境无 pytest：`pip install pytest`）

- [ ] **步骤 5：Commit**

```bash
git add server/yingdao tests/test_yingdao_client.py
git commit -m "$(cat <<'EOF'
2026-07-30 HH:mm 新增影刀client与单元测试支撑每日数据补全
EOF
)"
```

（时间用提交时本地 `yyyy-MM-dd HH:mm`。）

---

### 任务 2：FastAPI 路由

**文件：**
- 创建：`server/routers/yingdao.py`
- 修改：`server/main.py`

- [ ] **步骤 1：实现路由**

`server/routers/yingdao.py`：

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.yingdao import client as yd
from server.yingdao.client import YingdaoHttpError

router = APIRouter(prefix="/service/zyx/yingdao", tags=["yingdao"])


class JobStartBody(BaseModel):
    robotUuid: str = Field(...)
    accountName: str | None = None
    robotClientGroupUuid: str | None = None
    params: list[dict] | None = None
    waitTimeoutSeconds: int | None = 600
    runTimeout: int | None = None
    priority: str | None = "middle"
    executeScope: str | None = "any"
    useIdempotent: bool = True


class JobQueryBody(BaseModel):
    jobUuid: str = Field(...)


def _raise_yd(e: YingdaoHttpError):
    hint = yd.http_status_hint(e.status_code)
    raise HTTPException(
        e.status_code if e.status_code in (400, 401, 429, 500) else 502,
        detail={"hint": hint, "yingdao_status": e.status_code, "body": e.body},
    ) from e


@router.post("/job/start")
async def job_start(body: JobStartBody):
    try:
        data = yd.start_job(...)  # 映射 body 字段
        return {"code": 0, "data": data}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except YingdaoHttpError as e:
        _raise_yd(e)
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@router.post("/job/query")
async def job_query(body: JobQueryBody):
    # 同上模式，调用 yd.query_job(body.jobUuid)
    ...
```

`main.py`：`from server.routers import ... yingdao` 并 `app.include_router(yingdao.router)`。

- [ ] **步骤 2：本地冒烟（无真实 Key 时）**

```bash
python -c "from server.routers.yingdao import router; print([r.path for r in router.routes])"
```

预期：含 `/service/zyx/yingdao/job/start`、`/job/query`。

- [ ] **步骤 3：Commit**

```bash
git add server/routers/yingdao.py server/main.py
git commit -m "2026-07-30 HH:mm 封装影刀job启动与查询API路由"
```

---

### 任务 3：setup 登记 + 环境变量示例 + 文档

**文件：**
- 修改：`scripts/setup.py`（builtins 列表末尾追加）
- 修改：`.env.example`
- 修改：`CLAUDE.md`（业务 API 表）
- 修改：`client/js/pages/dispatch.js`（API_PARAMS + API_DOCS）

- [ ] **步骤 1：setup builtins**

追加：

```python
(
    "影刀启动应用",
    "每日数据补全：启动影刀应用（Key在服务端）",
    "POST",
    "/service/zyx/yingdao/job/start",
    "json",
),
(
    "影刀查询Job状态",
    "按 jobUuid 查询影刀任务状态",
    "POST",
    "/service/zyx/yingdao/job/query",
    "json",
),
```

- [ ] **步骤 2：.env.example**

```bash
# Yingdao（每日数据补全）
# POST /service/zyx/yingdao/job/start
# POST /service/zyx/yingdao/job/query
YINGDAO_ACCESS_KEY_ID=
YINGDAO_ACCESS_KEY_SECRET=
# YINGDAO_TOKEN_URL=https://api.yingdao.com/oapi/token/v2/token/create
# YINGDAO_JOB_START_URL=https://api.yingdao.com/oapi/dispatch/v2/job/start
# YINGDAO_JOB_QUERY_URL=https://api.yingdao.com/oapi/dispatch/v2/job/query
```

- [ ] **步骤 3：dispatch.js**

为两条 path 增加参数框与简短 API_DOCS（字段同规格）。`query` 仅 `jobUuid`。

- [ ] **步骤 4：更新 CLAUDE.md API 表两行**

- [ ] **步骤 5：Commit**

```bash
git add scripts/setup.py .env.example CLAUDE.md client/js/pages/dispatch.js
git commit -m "2026-07-30 HH:mm 登记影刀启动查询接口并补充环境变量说明"
```

---

### 任务 4：前端页面 + 侧栏影刀图标

**文件：**
- 创建：`client/img/yingdao.svg`（或 png）
- 创建：`client/js/pages/backfill.js`
- 修改：`client/js/app.js`
- 修改：`client/css/app.css`
- 修改：`server/main.py`（若需 mount `/img`）

- [ ] **步骤 1：静态图标**

使用简洁影刀风格 SVG（蓝底白字「影」或官方色块即可），保存 `client/img/yingdao.svg`。  
确认 `main.py` 能提供该静态文件：已有 `/{filename:path}` fallback 到 `client/`，访问 `/img/yingdao.svg` 即可；若不行则 `app.mount("/img", StaticFiles(...))`。

- [ ] **步骤 2：侧栏**

`app.js` items：

```javascript
{ key: 'dashboard', label: '数据中心', icon: '📊' },
{ key: 'dispatch', label: '调度任务', icon: '⚡' },
{ key: 'schedule', label: '定时任务', icon: '⏰' },
{ key: 'backfill', label: '每日数据补全', iconImg: '/img/yingdao.svg' },
```

模板支持 `iconImg`：有则 `<img class="sidebar-item-icon-img" :src="item.iconImg">`，否则 emoji。

CSS：

```css
.sidebar-item-icon-img{width:18px;height:18px;object-fit:contain;border-radius:3px}
```

bump：`?v=20260730b`（或更新当日版本串）。

- [ ] **步骤 3：backfill.js 页面**

结构：

1. `page-header`：标题「每日数据补全」，副标题说明 Key 在服务端  
2. card「调度目标」：robotUuid*、accountName、robotClientGroupUuid + 二选一提示  
3. card「应用参数」：开始日期、结束日期（`type=date` 或 text）  
4. card「可选调度」：waitTimeoutSeconds、runTimeout、priority（select）、executeScope（select）、useIdempotent（checkbox）  
5. 按钮行：`启动`（primary）、`刷新状态`（ghost，无 jobUuid 时 disabled）  
6. 结果区：展示 HTTP hint（若有）、jobUuid、status/statusName、`<pre>` 原始 JSON  

逻辑：

- `start()`：组装 body；`params` 仅含非空日期；`http.post('/service/zyx/yingdao/job/start', body)`  
- 成功：保存 `jobUuid`，toast 成功  
- 失败：读 `error.response.data.detail`（对象则显示 `hint`），toast/页面红字  
- `refresh()`：`post('/service/zyx/yingdao/job/query', { jobUuid })`  
- **无** `setInterval`

默认值：waitTimeoutSeconds=600，priority=middle，executeScope=any，useIdempotent=true。

- [ ] **步骤 4：本地打开页面目测**

```bash
python server/main.py
# 浏览器打开 http://localhost:3000 点侧栏「每日数据补全」
```

预期：参数分区可见；无 Key 时点启动应 400 中文提示缺配置。

- [ ] **步骤 5：Commit**

```bash
git add client/js/pages/backfill.js client/js/app.js client/css/app.css client/img/yingdao.svg server/main.py
git commit -m "2026-07-30 HH:mm 新增每日数据补全页面与影刀侧栏入口"
```

---

### 任务 5：联调、推送与服务器核对

**文件：** 无新代码（配置在服务器）

- [ ] **步骤 1：服务器写入 Key（勿提交）**

SSH 到生产，编辑 `/opt/service-zyx/.env` 增加真实：

```bash
YINGDAO_ACCESS_KEY_ID=...
YINGDAO_ACCESS_KEY_SECRET=...
```

（可用本地脚本默认值作联调，但不要写进 git。）

- [ ] **步骤 2：合并推送**

按仓库约定：未推送的本地 commit 全部 `git push origin main`；若本机 GitHub 不稳可重试。

- [ ] **步骤 3：确认 Actions**

打开最新 Deploy run；若 SCP 再因 `/tmp/service-zyx-release.tgz` 权限失败，先 `rm -f` 再 `workflow_dispatch`。

- [ ] **步骤 4：服务器核验**

```bash
# 在服务器
grep -n yingdao /opt/service-zyx/server/main.py
test -f /opt/service-zyx/client/js/pages/backfill.js && echo OK_PAGE
grep -n YINGDAO /opt/service-zyx/.env | sed 's/=.*/=***/'
systemctl is-active service-zyx
python3 /opt/service-zyx/scripts/setup.py   # 若 Actions 已跑可跳过
```

- [ ] **步骤 5：端到端（真实影刀）**

页面填 `robotUuid` + `accountName`，可选开始日期 → 启动 → 复制 jobUuid → 点「刷新状态」直到 finish/error。  
确认 429/401 时页面出现规格中文 hint。

- [ ] **步骤 6：收尾 Commit（仅若有文档微调）**

无代码则跳过。有 CLAUDE/README 小修正再提交推送。

---

## 规格覆盖自检

| 规格项 | 任务 |
|--------|------|
| 独立侧栏页 + 影刀图标 | 任务 4 |
| Key 仅 .env | 任务 1–3、5 |
| 页面必填 robotUuid / 账号或分组 | 任务 2、4 |
| 开始/结束日期可选 | 任务 4 |
| 可选调度参数 | 任务 1、2、4 |
| 手动刷新、无自动轮询 | 任务 4 |
| HTTP 状态码中文 hint | 任务 1、2、4 |
| setup + dispatch 登记 | 任务 3 |
| 推送并核服务器 | 任务 5 |

无 TODO/待定占位；类型字段与规格 camelCase（`robotUuid` 等）前后一致。
