"""Seeded synthetic table generator: the only source of test data.

Minimal version for ROADMAP 1.1: one small table, written in any supported source
format. Mutations (dropped rows, perturbed values, altered types) arrive with ROADMAP 1.10.

Every value is obviously synthetic: ``cust_000001``, ``Widget-A``, amounts from a seeded RNG.
"""

from __future__ import annotations

import datetime as dt
import random
import sqlite3
from pathlib import Path
from typing import Literal

import duckdb

Format = Literal["csv", "parquet", "jsonl", "duckdb", "sqlite"]

FORMATS: tuple[Format, ...] = ("csv", "parquet", "jsonl", "duckdb", "sqlite")

COLUMNS: tuple[str, ...] = ("id", "customer", "product", "qty", "amount", "active", "order_date")

_DDL = (
    "id INTEGER, customer VARCHAR, product VARCHAR, qty INTEGER, "
    "amount DOUBLE, active BOOLEAN, order_date DATE"
)
_PRODUCTS = ("Widget-A", "Widget-B", "Widget-C", "Gadget-X", "Gadget-Y")
_EPOCH = dt.date(2020, 1, 1)

Row = tuple[int, str, str, int, float, bool, dt.date]


def make_rows(n: int = 20, seed: int = 0) -> list[Row]:
    """Return ``n`` deterministic rows; the same ``seed`` always gives the same rows."""
    rng = random.Random(seed)
    return [
        (
            i,
            f"cust_{rng.randrange(1, 1000):06d}",
            rng.choice(_PRODUCTS),
            rng.randrange(1, 10),
            round(rng.uniform(1.0, 500.0), 2),
            rng.random() < 0.8,
            _EPOCH + dt.timedelta(days=rng.randrange(0, 365)),
        )
        for i in range(1, n + 1)
    ]


def write_table(
    directory: Path,
    fmt: Format,
    *,
    name: str = "orders",
    n: int = 20,
    seed: int = 0,
) -> str:
    """Write a synthetic table under ``directory`` and return its source spec.

    File formats return ``<directory>/<name>.<ext>``; database formats return
    ``<directory>/<name>.<ext>::<name>``. Writing a second table to an existing
    database file adds it alongside the first.
    """
    rows = make_rows(n, seed)
    path = directory / f"{name}.{fmt}"

    if fmt == "sqlite":
        # Written with the stdlib so the fixture needs no DuckDB extension.
        with sqlite3.connect(path) as con:
            con.execute(f'CREATE TABLE "{name}" ({_DDL})')
            con.executemany(
                f'INSERT INTO "{name}" VALUES (?, ?, ?, ?, ?, ?, ?)',
                [(*row[:6], row[6].isoformat()) for row in rows],
            )
        con.close()
        return f"{path}::{name}"

    con_duck = duckdb.connect(str(path)) if fmt == "duckdb" else duckdb.connect()
    try:
        con_duck.execute(f'CREATE TABLE "{name}" ({_DDL})')
        con_duck.executemany(f'INSERT INTO "{name}" VALUES (?, ?, ?, ?, ?, ?, ?)', rows)
        if fmt == "duckdb":
            return f"{path}::{name}"
        duck_format = "json" if fmt == "jsonl" else fmt
        target = str(path).replace("'", "''")
        con_duck.execute(f"COPY \"{name}\" TO '{target}' (FORMAT {duck_format})")
        return str(path)
    finally:
        con_duck.close()
