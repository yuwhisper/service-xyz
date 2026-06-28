import aiomysql
from server.config import DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME

_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = await aiomysql.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS,
            db=DB_NAME,
            charset="utf8mb4",
            autocommit=True,
            minsize=2,
            maxsize=10,
        )
    return _pool


async def get_conn():
    pool = await get_pool()
    return await pool.acquire()


async def release_conn(conn):
    pool = await get_pool()
    await pool.release(conn)


async def execute(sql: str, params=None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, params)
            return await cur.fetchall()


async def execute_one(sql: str, params=None):
    rows = await execute(sql, params)
    return rows[0] if rows else None


async def execute_insert(sql: str, params=None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            return cur.lastrowid


async def execute_update(sql: str, params=None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            return cur.rowcount
