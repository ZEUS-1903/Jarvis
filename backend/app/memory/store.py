"""Long-term memory storage (Postgres + in-memory twin for tests)."""
from datetime import datetime, timezone
from typing import Literal, Protocol

from psycopg.rows import class_row
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel

Category = Literal["preference", "person", "project", "fact", "other"]
Status = Literal["active", "pending"]
Source = Literal["user", "assistant"]


class Memory(BaseModel):
    id: int
    content: str
    category: Category
    status: Status
    source: Source
    created_at: datetime


class MemoryNotFound(Exception):
    pass


class MemoryStore(Protocol):
    async def list(self, status: Status | None = None, limit: int = 200) -> list[Memory]: ...
    async def add(self, content: str, category: Category, status: Status, source: Source) -> Memory: ...
    async def approve(self, memory_id: int) -> Memory: ...
    async def delete(self, memory_id: int) -> None: ...


_COLUMNS = "id, content, category, status, source, created_at"


class PostgresMemoryStore:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def list(self, status: Status | None = None, limit: int = 200) -> list[Memory]:
        async with self._pool.connection() as conn:
            # class_row: psycopg builds a Memory object from each row by column name.
            cur = conn.cursor(row_factory=class_row(Memory))
            if status:
                await cur.execute(f"SELECT {_COLUMNS} FROM memories WHERE status = %s "
                                  "ORDER BY id LIMIT %s", (status, limit))
            else:
                await cur.execute(f"SELECT {_COLUMNS} FROM memories ORDER BY id LIMIT %s", (limit,))
            return await cur.fetchall()

    async def add(self, content: str, category: Category, status: Status, source: Source) -> Memory:
        async with self._pool.connection() as conn:
            cur = conn.cursor(row_factory=class_row(Memory))
            # RETURNING hands back the inserted row (with its new id) in one round-trip.
            await cur.execute(
                f"INSERT INTO memories (content, category, status, source) "
                f"VALUES (%s, %s, %s, %s) RETURNING {_COLUMNS}",
                (content, category, status, source))
            return await cur.fetchone()

    async def approve(self, memory_id: int) -> Memory:
        async with self._pool.connection() as conn:
            cur = conn.cursor(row_factory=class_row(Memory))
            await cur.execute(
                f"UPDATE memories SET status = 'active', updated_at = now() "
                f"WHERE id = %s RETURNING {_COLUMNS}", (memory_id,))
            row = await cur.fetchone()
        if row is None:
            raise MemoryNotFound(memory_id)
        return row

    async def delete(self, memory_id: int) -> None:
        async with self._pool.connection() as conn:
            cur = await conn.execute("DELETE FROM memories WHERE id = %s", (memory_id,))
            if cur.rowcount == 0:
                raise MemoryNotFound(memory_id)


class InMemoryMemoryStore:
    def __init__(self) -> None:
        self._rows: dict[int, Memory] = {}
        self._next_id = 1

    async def list(self, status: Status | None = None, limit: int = 200) -> list[Memory]:
        rows = [m for m in self._rows.values() if status is None or m.status == status]
        return rows[:limit]

    async def add(self, content: str, category: Category, status: Status, source: Source) -> Memory:
        m = Memory(id=self._next_id, content=content, category=category, status=status,
                   source=source, created_at=datetime.now(timezone.utc))
        self._rows[m.id] = m
        self._next_id += 1
        return m

    async def approve(self, memory_id: int) -> Memory:
        if memory_id not in self._rows:
            raise MemoryNotFound(memory_id)
        self._rows[memory_id] = self._rows[memory_id].model_copy(update={"status": "active"})
        return self._rows[memory_id]

    async def delete(self, memory_id: int) -> None:
        if self._rows.pop(memory_id, None) is None:
            raise MemoryNotFound(memory_id)
