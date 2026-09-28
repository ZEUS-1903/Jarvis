"""PostgreSQL access: a connection pool plus a tiny migration runner.

Why a pool: opening a Postgres connection costs a network round-trip plus
authentication (~ms). A pool keeps a few connections open and lends them out
per query, so requests don't pay that cost every time.
"""
import logging
from pathlib import Path

from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger("jarvis.db")

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class DatabaseUnavailable(RuntimeError):
    pass


def make_pool(url: str) -> AsyncConnectionPool:
    """Created closed; opened at app startup (see main.py lifespan)."""
    return AsyncConnectionPool(url, min_size=1, max_size=5, open=False)


async def open_pool(pool: AsyncConnectionPool, url: str) -> None:
    try:
        await pool.open(wait=True, timeout=5)
    except Exception as exc:
        await pool.close()
        raise DatabaseUnavailable(
            f"Can't connect to PostgreSQL ({_redact(url)}): {exc}\n"
            "Is it running? On macOS: `brew services start postgresql@17`. "
            "Check JARVIS_DATABASE_URL in backend/.env."
        ) from exc


async def migrate(pool: AsyncConnectionPool) -> list[str]:
    """Apply migrations/NNN_*.sql files that haven't run yet, in order.

    Each file runs in its own transaction together with the bookkeeping insert:
    either the whole migration applies and is recorded, or nothing changes.
    """
    applied_now = []
    async with pool.connection() as conn:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        await conn.commit()
        done = {row[0] for row in await (await conn.execute(
            "SELECT name FROM schema_migrations")).fetchall()}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in done:
                continue
            async with conn.transaction():
                await conn.execute(path.read_text())
                await conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
            applied_now.append(path.name)
            logger.info("db.migrated", extra={"migration": path.name})
    return applied_now


def _redact(url: str) -> str:
    """Never log passwords: postgresql://user:secret@host -> postgresql://user:***@host"""
    if "@" in url and ":" in url.split("@")[0].split("//")[-1]:
        head, tail = url.split("@", 1)
        return head.rsplit(":", 1)[0] + ":***@" + tail
    return url
