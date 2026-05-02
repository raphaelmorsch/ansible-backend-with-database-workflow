"""Minimal Orders CRUD API for PostgreSQL connectivity PoC (DB outside the cluster)."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime
import asyncpg
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

POOL: asyncpg.Pool | None = None


def _pool_connect_kwargs() -> dict:
    url = os.environ.get("DATABASE_URL")
    if url:
        return {"dsn": url}
    return {
        "host": os.environ.get("PGHOST", "localhost"),
        "port": int(os.environ.get("PGPORT", "5432")),
        "user": os.environ.get("PGUSER", "postgres"),
        "password": os.environ.get("PGPASSWORD", ""),
        "database": os.environ.get("PGDATABASE", "postgres"),
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    global POOL
    POOL = await asyncpg.create_pool(min_size=1, max_size=5, **_pool_connect_kwargs())
    async with POOL.acquire() as conn:
        await _ensure_schema(conn)
    yield
    await POOL.close()
    POOL = None


app = FastAPI(title="Orders PoC", lifespan=lifespan)


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
