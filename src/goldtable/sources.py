"""Input sources: load a spec as a DuckDB relation.

Supported spec forms (ROADMAP 1.1):

    path.csv
    path.parquet
    path.jsonl
    path.duckdb::table
    path.sqlite::table

The format is taken from the file extension. Database files need a table name after
``::`` and are attached read-only. All reading is delegated to DuckDB; nothing here
iterates rows.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import duckdb

Kind = Literal["csv", "parquet", "jsonl", "duckdb", "sqlite"]

_FILE_KINDS: dict[str, Kind] = {".csv": "csv", ".parquet": "parquet", ".jsonl": "jsonl"}
_DB_KINDS: dict[str, Kind] = {".duckdb": "duckdb", ".sqlite": "sqlite"}
_TABLE_SEP = "::"

_SUPPORTED = "path.csv, path.parquet, path.jsonl, path.duckdb::table, path.sqlite::table"


class SourceError(Exception):
    """A source spec is invalid or the data behind it cannot be read."""


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _parse(spec: str) -> tuple[Path, Kind, str | None]:
    """Split a spec into (path, kind, table) and check that the pieces fit together."""
    if not spec.strip():
        raise SourceError("empty source spec")

    # Split on the last "::" so Windows drive letters (C:\...) are left alone.
    path_part, sep, table_part = spec.rpartition(_TABLE_SEP)
    if not sep:
        path_part, table = spec, None
    else:
        table = table_part.strip()
        if not table:
            raise SourceError(f"{spec!r}: expected a table name after '{_TABLE_SEP}'")
    if not path_part:
        raise SourceError(f"{spec!r}: expected a file path before '{_TABLE_SEP}'")

    path = Path(path_part)
    suffix = path.suffix.lower()

    if suffix in _FILE_KINDS:
        if table is not None:
            raise SourceError(
                f"{spec!r}: '{_TABLE_SEP}{table}' is only valid for .duckdb and .sqlite files"
            )
        return path, _FILE_KINDS[suffix], None

    if suffix in _DB_KINDS:
        if table is None:
            raise SourceError(
                f"{spec!r}: a {suffix} source needs a table name, "
                f"e.g. {path_part}{_TABLE_SEP}my_table"
            )
        return path, _DB_KINDS[suffix], table

    shown = suffix or "(none)"
    raise SourceError(f"{spec!r}: unsupported file extension {shown}. Supported: {_SUPPORTED}")


@dataclass(frozen=True)
class Source:
    """One side of a comparison: a parsed spec bound to a DuckDB connection."""

    spec: str
    path: Path
    kind: Kind
    table: str | None = None
    _con: duckdb.DuckDBPyConnection = field(
        default_factory=duckdb.connect, repr=False, compare=False
    )

    @classmethod
    def open(cls, spec: str, con: duckdb.DuckDBPyConnection | None = None) -> Source:
        """Parse ``spec`` and check that its file exists.

        Pass ``con`` to open several sources on one connection, which is required to
        compare them in a single query. Without it, a private in-memory connection is used.
        """
        path, kind, table = _parse(spec)
        if not path.is_file():
            raise SourceError(f"{spec!r}: file not found: {path}")
        return cls(
            spec=spec,
            path=path,
            kind=kind,
            table=table,
            _con=con if con is not None else duckdb.connect(),
        )

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        """The DuckDB connection this source reads through."""
        return self._con

    def relation(self) -> duckdb.DuckDBPyRelation:
        """Return a lazy DuckDB relation over the source's rows."""
        try:
            if self.kind == "csv":
                return self._con.read_csv(str(self.path))
            if self.kind == "parquet":
                return self._con.read_parquet(str(self.path))
            if self.kind == "jsonl":
                return self._con.read_json(str(self.path), format="newline_delimited")
            return self._table_relation()
        except duckdb.Error as exc:
            raise SourceError(f"{self.spec!r}: {exc}") from exc

    def _table_relation(self) -> duckdb.DuckDBPyRelation:
        assert self.table is not None  # guaranteed by _parse for database kinds
        alias = self._attach()
        # Allow "schema.table"; every part is quoted, so odd names are safe.
        parts = [alias, *self.table.split(".")]
        qualified = ".".join(_quote_ident(part) for part in parts)
        return self._con.sql(f"SELECT * FROM {qualified}")

    def _attach(self) -> str:
        """Attach the database file read-only and return its alias.

        The alias is derived from the resolved path, so opening two tables from the
        same file on one connection reuses a single attachment.
        """
        resolved = str(self.path.resolve())
        digest = hashlib.sha1(resolved.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]
        alias = f"gt_{self.kind}_{digest}"
        options = "TYPE sqlite, READ_ONLY" if self.kind == "sqlite" else "READ_ONLY"
        statement = (
            f"ATTACH IF NOT EXISTS {_quote_literal(resolved)} AS {_quote_ident(alias)} ({options})"
        )
        try:
            self._con.execute(statement)
        except duckdb.Error as exc:
            if self.kind == "sqlite":
                raise SourceError(
                    f"{self.spec!r}: could not open the SQLite file. Reading SQLite uses "
                    "DuckDB's sqlite extension, which DuckDB downloads on first use; if this "
                    "machine is offline, run `INSTALL sqlite` in DuckDB once while online. "
                    f"DuckDB said: {exc}"
                ) from exc
            raise
        return alias
