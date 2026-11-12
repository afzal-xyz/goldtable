# goldtable — instructions for Claude Code

## What this project is
Snapshot testing for data pipeline outputs. Capture a golden output (`init`), diff every later run against it (`check`), promote intended changes (`accept`). A Claude Code hook and a GitHub Action make `check` a gate. See `ROADMAP.md` for phases and acceptance criteria.

## Non-goals (do not build these)
Warehouse connectors, dbt integration, a web UI, anything that evaluates or benchmarks AI models.

## Stack
- Python ≥ 3.11, `uv` for everything (`uv sync`, `uv run ...`). Never use bare `pip`.
- Core deps: `duckdb`, `typer`, `rich`. Do not add pandas, polars or pyarrow to the core path; DuckDB reads CSV/Parquet/JSONL natively.
- Config parsing: stdlib `tomllib`. No pydantic.
- Dev: `pytest`, `pytest-cov`, `ruff`, `mypy`.
- Build: hatchling, src layout (`src/goldtable/`).

## Commands
```
uv sync
uv run pytest                 # fast tests
uv run pytest -m slow         # large-file tests
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run goldtable --help
```

## Layout
```
src/goldtable/
  sources.py   # Source.open(spec) -> DuckDB relation; spec forms in ROADMAP 1.1
  schema.py    # SchemaDiff
  keys.py      # key validation + inference
  rules.py     # comparison rules (tolerance, trim, ignore, null handling, date precision)
  diff.py      # keyed/unkeyed row diff, all in SQL
  result.py    # DiffResult + to_dict() (public JSON contract, see docs/result-schema.json)
  render/      # terminal.py, json.py, markdown.py
  config.py    # goldtable.toml
  store.py     # .goldtable/<name>/baseline.parquet + manifest.json
  cli.py       # typer app: diff, init, check, accept, hook
tests/
  fixtures/gen.py   # seeded synthetic table generator; the ONLY source of test data
```

## Decisions (don't re-decide; update this list when a new one is made)
- All heavy work happens inside DuckDB SQL. Python never iterates rows except to render bounded samples.
- Exit codes: 0 identical, 1 differences, 2 error.
- NULL == NULL by default.
- Baselines in `.goldtable/`, committed to git.
- `DiffResult.to_dict()` is stable; changing it needs a CHANGELOG entry.
- Type widening (INTEGER→BIGINT, FLOAT→DOUBLE) is reported but not a failure unless `--strict-types`.

## Working rules
- One roadmap task per session turn. Finish with tests green, ruff/mypy clean, one commit using conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
- For tasks marked [plan first] in ROADMAP.md: present the plan and file list, wait for approval, then implement.
- Write tests alongside the code, using `tests/fixtures/gen.py`. No hand-written data files over 50 rows. No real-looking names, accounts, addresses or transactions anywhere, including docs and examples.
- Never read or write outside the repo. No network in tests.
- Don't claim something works on Windows unless the Windows CI job passed. Say when you haven't verified something.
- Keep README examples runnable; if you change a flag, update README and `--help` in the same commit.
