# goldtable

[![CI](https://github.com/afzal-xyz/goldtable/actions/workflows/ci.yml/badge.svg)](https://github.com/afzal-xyz/goldtable/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Snapshot testing for data pipeline outputs: capture a known-good output once, then get a row-level diff every time a code change alters it.

> **Status: early development, not yet usable.** The package scaffold and CI are in place; the diff engine is being built now. Everything under [Planned interface](#planned-interface) describes the design, not working commands. See [Project status](#project-status) for what exists today.

## The problem

A code change to a data pipeline can alter its output without anything failing.

Unit tests cover the cases someone thought to write down. Code review shows the diff of the code, not the diff of the data it produces. So a refactor that turns an inner join into a left join, rounds a balance one step earlier, or reorders a deduplication can change a few hundred rows out of a million, pass every test, and reach production unnoticed.

This has always been a risk, and AI coding agents make it a daily one. An agent asked to "clean up the transform" edits pipeline code quickly and confidently, and reports success when the tests pass. Neither the agent nor the reviewer has looked at the output.

What is missing is the data equivalent of a snapshot test: a check that says "this change altered 412 rows in `customers_out`; here are ten of them", and that fails until a human says the change was intended.

## What goldtable does

goldtable treats a pipeline's output file as a snapshot, in the same way UI and API snapshot tests treat rendered output.

| Step | Command | What happens |
|---|---|---|
| Capture | `goldtable init` | Runs the pipeline on fixed input and stores the output as the baseline, committed to git. |
| Compare | `goldtable check` | Reruns the pipeline and diffs the new output against the baseline. Exits non-zero if anything changed. |
| Promote | `goldtable accept -m "why"` | Records an intended change as the new baseline, with the reason. |

The diff reports what a reviewer needs in order to decide:

- **Schema changes:** columns added, removed, or changed in type.
- **Row changes:** rows added, removed, and changed, matched by key.
- **Per-column counts:** which columns account for the changed rows.
- **Samples:** a small, deterministic set of example rows for each category.

Because `check` is a command with an exit code, it can act as a gate in two places:

- **In the agent loop:** a Claude Code hook runs `check` when the agent finishes. If the output changed, the agent is blocked and must either fix the pipeline or explain the change and ask a human to accept it. The hook never accepts on its own.
- **In CI:** a GitHub Action runs `check` on every pull request, posts the diff as a comment, and fails the job on unexplained changes.

## Planned interface

None of this is implemented yet. It is the design the [roadmap](ROADMAP.md) builds towards.

One-off comparison of two files:

```
goldtable diff old.parquet new.csv --key customer_id --tol balance=0.005 --ignore loaded_at
```

Snapshot workflow, declared once in `goldtable.toml`:

```toml
[[snapshot]]
name = "customers_out"
command = "python pipeline.py --input fixtures/customers.csv --out out/customers.parquet"
output = "out/customers.parquet"
key = ["customer_id"]
ignore = ["loaded_at"]

[snapshot.tolerance]
balance = 0.005
```

```
goldtable init                      # capture the baseline
goldtable check                     # exit 0 if identical, 1 if different, 2 on error
goldtable accept -m "new rounding"  # promote an intended change
```

## Design choices

- **DuckDB does the work.** Joins, comparisons and counts run as SQL inside DuckDB, so files larger than memory are in scope. Python only renders bounded samples.
- **Files and local tables only.** Inputs are CSV, Parquet, JSONL, and DuckDB or SQLite tables.
- **Comparison rules are explicit.** Numeric tolerance (absolute and relative), whitespace trimming, case-insensitive strings, ignored columns, NULL handling and date precision are opt-in flags or config keys, and the report lists the rules that were applied.
- **Keys are validated.** A declared key must be unique on both sides. Without one, goldtable infers a key and says which it chose, or falls back to an unkeyed multiset comparison.
- **Baselines live in git.** They are stored under `.goldtable/` as Parquet with a readable manifest, so a baseline change shows up in the same pull request as the code that caused it.
- **Output is machine-readable.** The JSON result is a documented, stable contract, because hooks and CI consume it.
- **Exit codes are fixed.** `0` identical, `1` differences found, `2` error.

## What it is not

goldtable is not a warehouse diff tool, a dbt plugin, or a web UI, and there are no plans to add warehouse connectors.

| Tool | Focus | How goldtable differs |
|---|---|---|
| datacompy | Comparing two DataFrames from Python code | A CLI and snapshot workflow on files, with no DataFrame library in the core path |
| data-diff / reladiff | Diffing tables across databases | Local files and pipeline outputs, with a stored baseline |
| Recce, Datafold | Reviewing data changes in dbt and warehouse projects | No warehouse or dbt project needed; runs anywhere a test runs |

## Project status

| Area | State |
|---|---|
| Package scaffold, lint and type-check config | Done |
| CI on Ubuntu and Windows, Python 3.11 and 3.12 | Done |
| `goldtable diff` engine (v0.1.0) | In progress |
| Snapshot workflow: `init`, `check`, `accept` (v0.2.0) | Planned |
| Claude Code hook and GitHub Action (v0.3.0) | Planned |
| pytest plugin, schema-only mode (v0.4.0) | Planned |
| MCP server, Python API, HTML report (v0.5.0) | Planned |

The full task list, with an acceptance test for each task, is in [ROADMAP.md](ROADMAP.md).

## Development

Requires Python 3.11 or later and [uv](https://docs.astral.sh/uv/).

```
git clone https://github.com/afzal-xyz/goldtable.git
cd goldtable
uv sync
uv run goldtable --help
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy src
```

Test data is generated, never copied from real systems: fixtures use obviously synthetic values such as `cust_000123` and `Widget-A`.

## License

[MIT](LICENSE)
