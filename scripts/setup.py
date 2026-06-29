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

    # Seed demo APIs if none
    count = await execute_one("SELECT COUNT(*) AS c FROM interfaces WHERE project_id=%s", (pid,))
    if count["c"] == 0:
        demos = [
            ("获取用户列表", "GET", "https://jsonplaceholder.typicode.com/users"),
            ("获取单用户", "GET", "https://jsonplaceholder.typicode.com/users/1"),
            ("创建文章", "POST", "https://jsonplaceholder.typicode.com/posts"),
            ("更新文章", "PUT", "https://jsonplaceholder.typicode.com/posts/1"),
            ("删除文章", "DELETE", "https://jsonplaceholder.typicode.com/posts/1"),
        ]
        for name, method, path in demos:
            await execute_insert(
                "INSERT INTO interfaces (project_id,name,description,method,path,body_type,status) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (pid, name, "", method, path, "none", "published"),
            )
        print("[setup] Demo APIs seeded")

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
            "聚水潭获取Token",
            "获取或刷新聚水潭 OpenAPI access_token",
            "GET",
            "/service/zyx/jst/gettoken",
            "none",
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

    print("[setup] Done!")


if __name__ == "__main__":
    asyncio.run(setup())
