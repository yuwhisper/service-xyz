"""Database setup: create tables + seed demo data."""
import asyncio
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))

from server.database import execute, execute_one, execute_insert, get_pool
from server.auth import hash_password


async def setup():
    print("[setup] Connecting to MySQL...")
    await get_pool()

    # Create tables
    await execute("""
        CREATE TABLE IF NOT EXISTS api_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            api_id INT NOT NULL,
            request_params TEXT,
            response_body TEXT,
            status_code INT,
            duration_ms INT,
            triggered_by ENUM('manual','schedule') DEFAULT 'manual',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (api_id) REFERENCES interfaces(id) ON DELETE CASCADE,
            INDEX idx_api_id (api_id),
            INDEX idx_created (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("[setup] api_logs table ready")

    await execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id INT AUTO_INCREMENT PRIMARY KEY,
            api_id INT NOT NULL,
            name VARCHAR(200) NOT NULL,
            cron_expression VARCHAR(100),
            params TEXT,
            enabled TINYINT DEFAULT 1,
            last_run_at DATETIME NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (api_id) REFERENCES interfaces(id) ON DELETE CASCADE,
            INDEX idx_enabled (enabled)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("[setup] schedules table ready")

    # Ensure admin user exists
    admin = await execute_one("SELECT id FROM users WHERE email=%s", ("admin@service-xyz.com",))
    if not admin:
        admin_id = await execute_insert(
            "INSERT INTO users (email,username,password,role,status) VALUES (%s,%s,%s,%s,%s)",
            ("admin@service-xyz.com", "admin", hash_password("admin123"), "admin", 1),
        )
        print(f"[setup] Admin user created (id={admin_id})")
    else:
        print("[setup] Admin user exists")

    # Ensure default project exists
    proj = await execute_one("SELECT id FROM projects WHERE name='Default'")
    if not proj:
        admin_user = await execute_one("SELECT id FROM users WHERE email=%s", ("admin@service-xyz.com",))
        pid = await execute_insert(
            "INSERT INTO projects (name,description,owner_id) VALUES (%s,%s,%s)",
            ("Default", "Default project", admin_user["id"]),
        )
        print(f"[setup] Default project created (id={pid})")
    else:
        pid = proj["id"]
        print("[setup] Default project exists")

    # Register built-in service APIs (idempotent by path)
    builtins = [
        (
            "Ozon FBO 发货",
            "读取今日待发货登记并自动申请 Ozon 供货单",
            "POST",
            "/service/zyx/ozon/fahuo",
            "json",
        ),
        (
            "钉钉钉盘上传",
            "压缩并上传服务器本地文件/目录到钉盘",
            "POST",
            "/service/zyx/dingtalk/dingpan/upload",
            "json",
        ),
        (
            "钉钉在线表写入",
            "按起始单元格写入钉钉在线表格二维内容",
            "POST",
            "/service/zyx/dingtalk/workbook/write",
            "json",
        ),
        (
            "钉钉在线表最后一行",
            "获取工作表最后非空行及下一行可写位置",
            "POST",
            "/service/zyx/dingtalk/workbook/last-row",
            "json",
        ),
        (
            "钉钉AI多维表写入",
            "向AI多维表指定数据表新增记录",
            "POST",
            "/service/zyx/dingtalk/notable/records",
            "json",
        ),
        (
            "钉钉AI多维表上传附件(路径)",
            "用服务器本地路径上传附件，返回附件字段对象",
            "POST",
            "/service/zyx/dingtalk/notable/upload-attachment",
            "json",
        ),
        (
            "钉钉AI多维表上传附件(文件)",
            "form-data 上传附件到AI表格资源空间",
            "POST",
            "/service/zyx/dingtalk/notable/upload-attachment-file",
            "form-data",
        ),
        (
            "聚水潭获取Token",
            "获取或刷新聚水潭 OpenAPI access_token",
            "GET",
            "/service/zyx/jst/gettoken",
            "none",
        ),
        (
            "聚水潭查询商品资料",
            "按 SKU 查询聚水潭商品资料，返回 /open/sku/query 原始字段",
            "GET",
            "/service/zyx/jst/sku/query",
            "none",
        ),
        (
            "聚水潭查询订单详情",
            "按内部/线上单号、时间、start_ts 等可选条件查订单；volume/package 等自定义字段单独传布尔，返回原始 data",
            "POST",
            "/service/zyx/jst/order/query",
            "json",
        ),
        (
            "聚水潭查询商品库存",
            "按 SKU + 分仓编号列表查询库存，返回 /open/inventory/query 原始字段",
            "POST",
            "/service/zyx/jst/inventory/query",
            "json",
        ),
        (
            "聚水潭按名称查虚拟仓ID",
            "按中文虚拟仓名精确匹配，返回 lwh_id 与 bind_wms（实体仓）",
            "POST",
            "/service/zyx/jst/lwh/query",
            "json",
        ),
        (
            "聚水潭创建虚拟仓调拨单",
            "按中文仓名创建虚拟仓调拨；创建前校验调出/调入/实体仓/SKU/库存，失败返回详细中文",
            "POST",
            "/service/zyx/jst/lwh/allocation/create",
            "json",
        ),
    ]
    for name, desc, method, path, body_type in builtins:
        exists = await execute_one(
            "SELECT id FROM interfaces WHERE project_id=%s AND path=%s",
            (pid, path),
        )
        if not exists:
            await execute_insert(
                "INSERT INTO interfaces (project_id,name,description,method,path,body_type,status) "
                "VALUES (%s,%s,%s,%s,%s,%s,'published')",
                (pid, name, desc, method, path, body_type),
            )
            print(f"[setup] Registered builtin API: {name}")
        else:
            await execute_insert(
                "UPDATE interfaces SET name=%s, description=%s, method=%s, body_type=%s "
                "WHERE project_id=%s AND path=%s",
                (name, desc, method, body_type, pid, path),
            )
            print(f"[setup] Updated builtin API: {name}")

    print("[setup] Done!")


if __name__ == "__main__":
    asyncio.run(setup())
