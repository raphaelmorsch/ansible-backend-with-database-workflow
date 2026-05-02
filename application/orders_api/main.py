"""Minimal Orders CRUD API for PostgreSQL connectivity PoC (DB outside the cluster)."""

from __future__ import annotations

import asyncio
import logging
import os
import ssl
from contextlib import asynccontextmanager
from datetime import datetime
import asyncpg
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

POOL: asyncpg.Pool | None = None

log = logging.getLogger(__name__)


def _ssl_for_asyncpg():
    """asyncpg may try SSL by default; plain Postgres (no TLS) then fails in _create_ssl_connection."""
    mode = (os.environ.get("PGSSLMODE") or "disable").strip().lower()
    if mode in ("disable", "off", "false", "no", "allow"):
        return False
    if mode == "prefer":
        return False
    if mode in ("require", "verify-ca", "verify-full"):
        ctx = ssl.create_default_context()
        if mode == "require":
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return False


def _pool_connect_kwargs() -> dict:
    ssl_arg = _ssl_for_asyncpg()
    url = os.environ.get("DATABASE_URL")
    if url:
        return {"dsn": url, "ssl": ssl_arg}
    return {
        "host": os.environ.get("PGHOST", "localhost"),
        "port": int(os.environ.get("PGPORT", "5432")),
        "user": os.environ.get("PGUSER", "postgres"),
        "password": os.environ.get("PGPASSWORD", ""),
        "database": os.environ.get("PGDATABASE", "postgres"),
        "ssl": ssl_arg,
    }


async def _ensure_schema(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            customer_name TEXT NOT NULL,
            item_description TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )


def _connect_timeout_sec() -> float:
    return float(os.environ.get("PGCONNECT_TIMEOUT", "45"))


def _pool_retry_settings() -> tuple[int, float]:
    retries = int(os.environ.get("PG_POOL_CONNECT_RETRIES", "30"))
    delay = float(os.environ.get("PG_POOL_CONNECT_DELAY_SEC", "4"))
    return max(1, retries), max(0.5, delay)


async def _create_pool_with_retries() -> asyncpg.Pool:
    """New VM Postgres often accepts TCP a bit after the Deployment rolls; retry instead of one-shot fail."""
    connect_kw = _pool_connect_kwargs()
    connect_kw["timeout"] = _connect_timeout_sec()
    host = connect_kw.get("host") or os.environ.get("PGHOST", "?")
    retries, delay = _pool_retry_settings()
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            pool = await asyncpg.create_pool(min_size=1, max_size=5, **connect_kw)
            if attempt > 1:
                log.warning(
                    "PostgreSQL pool ready on attempt %s/%s (host=%s)",
                    attempt,
                    retries,
                    host,
                )
            return pool
        except Exception as e:
            last_exc = e
            log.warning(
                "PostgreSQL pool attempt %s/%s failed (host=%s): %s: %s",
                attempt,
                retries,
                host,
                type(e).__name__,
                e,
            )
            if attempt >= retries:
                break
            await asyncio.sleep(delay)
    log.error(
        "PostgreSQL pool startup exhausted (%s attempts, host=%s)",
        retries,
        host,
        exc_info=last_exc,
    )
    assert last_exc is not None
    raise RuntimeError(
        "Cannot open PostgreSQL pool after retries. Often: Postgres/service on the VM "
        "still starting, security group rule propagation, or cluster egress not allowed yet. "
        f"host={host!r} retries={retries} delay_sec={delay}. "
        "psql from your laptop does not prove the pod path is ready at the same time."
    ) from last_exc


@asynccontextmanager
async def lifespan(app: FastAPI):
    global POOL
    POOL = await _create_pool_with_retries()
    async with POOL.acquire() as conn:
        await _ensure_schema(conn)
    yield
    await POOL.close()
    POOL = None


app = FastAPI(title="Orders PoC", lifespan=lifespan)

_STATIC_DIR = Path(__file__).resolve().parent / "static"
_INDEX_FILE = _STATIC_DIR / "index.html"


def _load_index_html() -> str:
    if not _INDEX_FILE.is_file():
        raise HTTPException(
            status_code=503,
            detail=(
                "Web UI file missing in container (expected orders_api/static/index.html). "
                "Rebuild with: cd application && oc start-build orders-api --from-dir=. --follow"
            ),
        )
    return _INDEX_FILE.read_text(encoding="utf-8")


@app.get("/", include_in_schema=False)
async def orders_web_ui_root():
    return HTMLResponse(_load_index_html(), media_type="text/html; charset=utf-8")


@app.get("/ui", include_in_schema=False)
async def orders_web_ui_alias():
    """Alternate path if something in front of the app interferes with ``/``."""
    return HTMLResponse(_load_index_html(), media_type="text/html; charset=utf-8")


class OrderCreate(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=256)
    item_description: str = Field(..., min_length=1, max_length=512)
    quantity: int = Field(default=1, ge=1, le=1_000_000)


class OrderUpdate(BaseModel):
    customer_name: str | None = Field(None, min_length=1, max_length=256)
    item_description: str | None = Field(None, min_length=1, max_length=512)
    quantity: int | None = Field(None, ge=1, le=1_000_000)


class OrderOut(BaseModel):
    id: int
    customer_name: str
    item_description: str
    quantity: int
    created_at: datetime


@app.get("/live", include_in_schema=False)
async def live():
    """Process is up (used for liveness); does not touch PostgreSQL."""
    return {"status": "alive"}


@app.get("/health")
async def health():
    if POOL is None:
        raise HTTPException(status_code=503, detail="database pool not ready")
    async with POOL.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ok"}


@app.get("/orders", response_model=list[OrderOut])
async def list_orders():
    assert POOL is not None
    async with POOL.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, customer_name, item_description, quantity, created_at
            FROM orders
            ORDER BY id ASC
            """
        )
    return [OrderOut(**dict(r)) for r in rows]


@app.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(order_id: int):
    assert POOL is not None
    async with POOL.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, customer_name, item_description, quantity, created_at
            FROM orders WHERE id = $1
            """,
            order_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="order not found")
    return OrderOut(**dict(row))


@app.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(body: OrderCreate):
    assert POOL is not None
    async with POOL.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO orders (customer_name, item_description, quantity)
            VALUES ($1, $2, $3)
            RETURNING id, customer_name, item_description, quantity, created_at
            """,
            body.customer_name,
            body.item_description,
            body.quantity,
        )
    return OrderOut(**dict(row))


@app.put("/orders/{order_id}", response_model=OrderOut)
async def update_order(order_id: int, body: OrderUpdate):
    assert POOL is not None
    fields: dict[str, object] = {}
    if body.customer_name is not None:
        fields["customer_name"] = body.customer_name
    if body.item_description is not None:
        fields["item_description"] = body.item_description
    if body.quantity is not None:
        fields["quantity"] = body.quantity
    if not fields:
        raise HTTPException(status_code=400, detail="no fields to update")

    # asyncpg binds $1, $2, ... in left-to-right order in the SQL string.
    parts: list[str] = []
    values: list[object] = []
    n = 1
    for col, val in fields.items():
        parts.append(f"{col} = ${n}")
        values.append(val)
        n += 1
    values.append(order_id)
    sets = ", ".join(parts)
    query = f"""
        UPDATE orders SET {sets}
        WHERE id = ${n}
        RETURNING id, customer_name, item_description, quantity, created_at
    """
    async with POOL.acquire() as conn:
        row = await conn.fetchrow(query, *values)
    if row is None:
        raise HTTPException(status_code=404, detail="order not found")
    return OrderOut(**dict(row))


@app.delete("/orders/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(order_id: int):
    assert POOL is not None
    async with POOL.acquire() as conn:
        result = await conn.execute("DELETE FROM orders WHERE id = $1", order_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="order not found")
