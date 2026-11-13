"""Tests for goldtable.sources (ROADMAP 1.1)."""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pytest

from goldtable.sources import Source, SourceError
from tests.fixtures import gen

N_ROWS = 20
EXPECTED_ID_SUM = N_ROWS * (N_ROWS + 1) // 2

# Formats DuckDB reads without any extension download.
BUILTIN_FORMATS = [fmt for fmt in gen.FORMATS if fmt != "sqlite"]


def _sqlite_extension_installed() -> bool:
    rows = duckdb.sql(
        "SELECT installed FROM duckdb_extensions() WHERE extension_name = 'sqlite_scanner'"
    ).fetchall()
    return bool(rows and rows[0][0])


def _require_sqlite_extension() -> None:
    """Skip when the extension is missing, unless CI has said it must be present."""
    if _sqlite_extension_installed():
        return
    if os.environ.get("GOLDTABLE_REQUIRE_SQLITE") == "1":
        pytest.fail("GOLDTABLE_REQUIRE_SQLITE=1 but DuckDB's sqlite extension is not installed")
    pytest.skip("DuckDB's sqlite extension is not installed (installing it needs network)")


def _summary(source: Source) -> tuple[int, int]:
    rows = source.relation().aggregate("count(*), sum(id)").fetchall()
    return int(rows[0][0]), int(rows[0][1])


@pytest.mark.parametrize("fmt", BUILTIN_FORMATS)
def test_relation_for_each_builtin_format(tmp_path: Path, fmt: gen.Format) -> None:
    spec = gen.write_table(tmp_path, fmt, n=N_ROWS)
    source = Source.open(spec)

    assert source.kind == fmt
    assert tuple(source.relation().columns) == gen.COLUMNS
    assert _summary(source) == (N_ROWS, EXPECTED_ID_SUM)


def test_relation_for_sqlite(tmp_path: Path) -> None:
    _require_sqlite_extension()
    spec = gen.write_table(tmp_path, "sqlite", n=N_ROWS)
    source = Source.open(spec)

    assert source.kind == "sqlite"
    assert source.table == "orders"
    assert tuple(source.relation().columns) == gen.COLUMNS
    assert _summary(source) == (N_ROWS, EXPECTED_ID_SUM)


def test_same_values_across_formats(tmp_path: Path) -> None:
    """Every built-in format yields the same ids and amounts for the same seed."""
    con = duckdb.connect()
    results = []
    for fmt in BUILTIN_FORMATS:
        source = Source.open(gen.write_table(tmp_path, fmt, n=N_ROWS, seed=7), con)
        results.append(source.relation().project("id, amount").order("id").fetchall())
    assert all(result == results[0] for result in results)
    assert len(results[0]) == N_ROWS


def test_parse_fields_for_file_and_table_specs(tmp_path: Path) -> None:
    csv = Source.open(gen.write_table(tmp_path, "csv"))
    assert (csv.kind, csv.table, csv.path) == ("csv", None, tmp_path / "orders.csv")

    db = Source.open(gen.write_table(tmp_path, "duckdb"))
    assert (db.kind, db.table, db.path) == ("duckdb", "orders", tmp_path / "orders.duckdb")


def test_extension_is_case_insensitive(tmp_path: Path) -> None:
    spec = gen.write_table(tmp_path, "csv", n=N_ROWS)
    upper = tmp_path / "ORDERS_COPY.CSV"
    upper.write_bytes(Path(spec).read_bytes())

    assert _summary(Source.open(str(upper))) == (N_ROWS, EXPECTED_ID_SUM)


def test_two_sources_share_a_connection(tmp_path: Path) -> None:
    con = duckdb.connect()
    left = Source.open(gen.write_table(tmp_path, "parquet", n=N_ROWS), con)
    right = Source.open(gen.write_table(tmp_path, "csv", n=N_ROWS), con)

    assert left.connection is con
    assert right.connection is con
    joined = left.relation().set_alias("a").join(right.relation().set_alias("b"), "id")
    assert joined.aggregate("count(*)").fetchall() == [(N_ROWS,)]


def test_two_tables_from_one_duckdb_file(tmp_path: Path) -> None:
    first = gen.write_table(tmp_path, "duckdb", name="orders", n=N_ROWS)
    db_path = first.rpartition("::")[0]
    with duckdb.connect(db_path) as writer:
        writer.execute("CREATE TABLE orders_small AS SELECT * FROM orders WHERE id <= 5")

    con = duckdb.connect()
    big = Source.open(first, con)
    small = Source.open(f"{db_path}::orders_small", con)

    assert _summary(big) == (N_ROWS, EXPECTED_ID_SUM)
    assert _summary(small) == (5, 15)


def test_duckdb_source_is_read_only(tmp_path: Path) -> None:
    source = Source.open(gen.write_table(tmp_path, "duckdb", n=N_ROWS))
    source.relation()  # attaches the file
    aliases = source.connection.sql(
        "SELECT database_name FROM duckdb_databases() WHERE database_name LIKE 'gt_duckdb_%'"
    ).fetchall()
    assert len(aliases) == 1

    with pytest.raises(duckdb.Error):
        source.connection.execute(f'DELETE FROM "{aliases[0][0]}"."orders"')
    assert _summary(source) == (N_ROWS, EXPECTED_ID_SUM)


def test_unknown_extension_raises(tmp_path: Path) -> None:
    path = tmp_path / "orders.xlsx"
    path.write_bytes(b"")

    with pytest.raises(SourceError, match=r"unsupported file extension \.xlsx"):
        Source.open(str(path))


def test_no_extension_raises(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="unsupported file extension"):
        Source.open(str(tmp_path / "orders"))


def test_empty_spec_raises() -> None:
    with pytest.raises(SourceError, match="empty source spec"):
        Source.open("  ")


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="file not found"):
        Source.open(str(tmp_path / "nope.parquet"))


def test_table_on_file_format_raises(tmp_path: Path) -> None:
    spec = gen.write_table(tmp_path, "csv")

    with pytest.raises(SourceError, match=r"only valid for \.duckdb and \.sqlite"):
        Source.open(f"{spec}::orders")


@pytest.mark.parametrize("fmt", ["duckdb", "sqlite"])
def test_database_spec_without_table_raises(tmp_path: Path, fmt: gen.Format) -> None:
    db_path = gen.write_table(tmp_path, fmt).rpartition("::")[0]

    with pytest.raises(SourceError, match="needs a table name"):
        Source.open(db_path)


def test_empty_table_name_raises(tmp_path: Path) -> None:
    db_path = gen.write_table(tmp_path, "duckdb").rpartition("::")[0]

    with pytest.raises(SourceError, match="expected a table name"):
        Source.open(f"{db_path}::")


def test_unknown_table_raises(tmp_path: Path) -> None:
    db_path = gen.write_table(tmp_path, "duckdb").rpartition("::")[0]
    source = Source.open(f"{db_path}::no_such_table")

    with pytest.raises(SourceError, match="no_such_table"):
        source.relation()


def test_unreadable_file_raises_source_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.parquet"
    path.write_bytes(b"this is not a parquet file")

    with pytest.raises(SourceError, match=r"broken\.parquet"):
        Source.open(str(path)).relation()


def test_generator_is_deterministic() -> None:
    assert gen.make_rows(10, seed=3) == gen.make_rows(10, seed=3)
    assert gen.make_rows(10, seed=3) != gen.make_rows(10, seed=4)
