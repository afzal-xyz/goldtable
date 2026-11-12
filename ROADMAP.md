# goldtable — Roadmap

**One line:** snapshot testing for data pipeline outputs, built so AI coding agents can't ship silent data changes.

**How it works:** capture a golden output once (`init`), rerun and diff on every change (`check`), promote intended changes (`accept`). A Claude Code hook and a GitHub Action turn `check` into a gate the agent can't talk its way past.

**What it is not:** a warehouse diff tool (Datafold, Recce), a dbt plugin, or a web UI. Files, local tables and in-memory frames only.

---

## How to work this roadmap with Claude Code

- One task per prompt. Each task below is sized for one agent turn plus one review.
- For any task marked **[plan first]**, ask for a plan and file list before code; approve or redirect, then let it implement.
- Every task ends with: tests pass locally (`uv run pytest`), `ruff` and `mypy` clean, one commit with a conventional-commit message. Don't let the agent batch several tasks into one commit; a readable history is part of the project.
- "Done when" is the acceptance test. If you can't verify it by running a command, the task isn't done.
- Synthetic fixtures only. Nothing that looks like a real person, account or transaction. Fixture generators use fake names like `cust_000123`, `Widget-A`, and seeded random numbers.
- Keep `CLAUDE.md` current: when a design decision is made (storage format, exit codes, config keys), record it there so later sessions don't re-decide it.

Target cadence: 4–6 tasks per week.

---

## Phase 0 — Repo bootstrap (day 1, ~5 tasks)

| # | Task | Done when |
|---|------|-----------|
| 0.1 | Create repo `afzal-xyz/goldtable` (public, MIT, personal account). Confirm `git config user.email` matches an email on your GitHub profile. | `git log` shows your name/email; GitHub shows MIT badge |
| 0.2 | Scaffold with `uv init --lib`, src layout (`src/goldtable/`), `pyproject.toml` (hatchling, Python ≥3.11), deps `duckdb`, `typer`, `rich`; dev deps `pytest`, `ruff`, `mypy`, `pytest-cov`. | `uv sync && uv run goldtable --help` prints usage |
| 0.3 | Add `CLAUDE.md` (from this repo's template), `.gitignore`, `ruff.toml`/`[tool.ruff]`, `[tool.mypy]` strict-ish. | `uv run ruff check . && uv run mypy src` clean |
| 0.4 | GitHub Actions CI: `uv sync`, ruff, mypy, pytest on `ubuntu-latest` and `windows-latest`, Python 3.11 and 3.12. | Green check on first push |
| 0.5 | README stub: one-line pitch, status badge, "not yet usable" notice. Open the v0.3–v0.5 issues from the appendix so the roadmap is visible on GitHub. | README renders; issues visible |

---

## Phase 1 — v0.1.0: the diff engine (weeks 1–3, ~12 tasks)

Goal: `goldtable diff a.parquet b.csv --key id` works on files larger than RAM and prints something a reviewer can act on.

### 1.1 Sources **[plan first]**
Load any supported input into a DuckDB relation behind a single `Source` abstraction.
- Spec syntax: `path.csv`, `path.parquet`, `path.jsonl`, `path.duckdb::table`, `path.sqlite::table`.
- CSV: delegate inference to DuckDB `read_csv_auto`; expose `--csv-opts` passthrough later, not now.
- Done when: `Source.open(spec).relation()` returns a relation for each format; tests cover all five with tiny fixtures; unknown extension raises a clear `SourceError`.

### 1.2 Schema diff
- Columns added / removed / type changed (DuckDB logical types, normalised: `BIGINT` vs `INTEGER` is a *widening*, not a change, unless `--strict-types`).
- Done when: `SchemaDiff` dataclass with `added`, `removed`, `changed`, `widened`; tests for each; `diff` prints schema section first.

### 1.3 Key handling **[plan first]**
- `--key col[,col]` validates uniqueness on both sides; duplicate keys → error listing up to 10 offending key values.
- No `--key`: infer. Scan single columns, then pairs (cap at 20 candidate columns), pick the first unique combination with no NULLs. Report what was chosen. `--no-infer` forces unkeyed mode.
- Done when: inference picks the obvious key on fixtures with and without an `id` column; duplicates produce the documented error; inference is skipped above a row cap (`--infer-limit`, default 5M).

### 1.4 Keyed row diff
- `FULL OUTER JOIN` on key, in DuckDB, never in Python. Classify rows: `added`, `removed`, `changed`, `unchanged`.
- Per-column change counts for `changed` rows.
- Bounded samples (`--samples N`, default 10) per category, deterministic order (by key).
- Done when: on a 1M-row synthetic pair with 1% mutations, counts are exact and runtime is under 10s on a laptop; memory stays flat (test marked `slow`).

### 1.5 Unkeyed row diff
- Multiset comparison with `EXCEPT ALL` both ways; duplicate-aware.
- Done when: reordering rows yields "identical"; one extra duplicate row is reported as added.

### 1.6 Comparison rules
- Numeric: `--tol col=0.01` (absolute) and `--rtol col=1e-6` (relative); `--tol *=...` applies to all numeric columns.
- Strings: `--trim`, `--ignore-case`.
- `--ignore col[,col]` excludes columns from comparison (typical: `run_id`, `loaded_at`).
- NULL == NULL by default; `--null-ne` to disable.
- Dates/timestamps: compare at `--date-precision {day,second,ms}`.
- Done when: each rule has a test proving it changes the verdict; rules are also loadable from TOML (needed by Phase 2).

### 1.7 Result model
- `DiffResult` dataclass: schema diff, row counts by category, per-column stats, samples, rules applied, timing. `to_dict()` is stable and documented (it becomes the JSON contract for hooks/Actions).
- Done when: `json.dumps(result.to_dict())` round-trips; a schema file `docs/result-schema.json` is committed and validated in tests.

### 1.8 Renderers
- Terminal (rich): summary panel, schema table, per-column table, samples table; colour only when TTY.
- `--format json` and `--format markdown` (markdown is what the GitHub Action will post).
- Done when: markdown output renders correctly when pasted into a GitHub comment; `--quiet` prints only the verdict line.

### 1.9 Exit codes and CLI polish
- `0` identical (or only ignored differences), `1` differences found, `2` error. Document in README.
- `goldtable diff --help` lists every rule flag with one-line descriptions.
- Done when: a shell test asserts each code.

### 1.10 Fixture generator
- `tests/fixtures/gen.py`: seeded, produces obviously synthetic tables (`cust_000001`, `Widget-A`, amounts from a fixed RNG) in CSV and Parquet, with optional mutations (drop rows, add rows, perturb numeric, change strings, alter types).
- Done when: every Phase 1 test uses it; no hand-written data files over 50 rows.

### 1.11 Docs
- README: install, 30-second example, the three verdict categories, rule flags, exit codes, "How goldtable differs" table (datacompy, data-diff/reladiff, duckdiff, Recce, Datafold).
- Done when: a stranger can install and run the example in under two minutes.

### 1.12 Release v0.1.0
- Trusted publishing to PyPI via GitHub Action on tag `v*`. `CHANGELOG.md` started.
- Done when: `pip install goldtable` works from a clean venv; GitHub Release exists.

---

## Phase 2 — v0.2.0: snapshot workflow (weeks 4–5, ~8 tasks)

Goal: a pipeline repo can declare its outputs once and get a `check` command that answers "did anything change?"

### 2.1 Config file **[plan first]**
`goldtable.toml` at repo root:
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
- Multiple snapshots; `command` optional (if absent, `check` assumes the output already exists).
- Done when: config is parsed with `tomllib`, validated with clear errors, and every Phase 1 rule can be expressed in it.

### 2.2 Baseline store
- `.goldtable/<name>/baseline.parquet` + `manifest.json` (schema, key, rules, row count, content hash, created_at, git commit if available, optional message).
- Done when: baselines are reproducible byte-for-byte for the same input; manifest is human-readable in a PR.

### 2.3 `goldtable init [name]`
- Runs `command` (if any), captures `output` into the baseline store. Refuses to overwrite without `--force`.
- Done when: running twice without `--force` errors; `.goldtable/` is intended to be committed and `.gitignore` guidance says so.

### 2.4 `goldtable check [name] [--format ...]`
- Runs `command`, diffs `output` against baseline with the snapshot's rules, aggregates one report across snapshots, exit code `1` if any snapshot differs.
- Done when: a deliberate one-row change in the fixture fails `check` with the row shown; reverting passes.

### 2.5 `goldtable accept [name] [-m "why"]`
- Promotes current output to baseline, records message and commit in manifest.
- Done when: `check` passes immediately after `accept`; manifest history shows the message.

### 2.6 Large outputs
- `sample = { rows = 100000, by = "key" }` in config: deterministic hash-based sampling by key so baselines stay small and the same rows are compared every run.
- Done when: a 5M-row output produces a baseline under 10 MB and `check` still catches a mutated sampled row.

### 2.7 Docs
- README "Snapshot workflow" section with the init/check/accept loop and a diagram.
- Done when: the example repo in `examples/basic/` runs the loop end to end in CI.

### 2.8 Release v0.2.0
- Tag, release notes, PyPI.

---

## Phase 3 — v0.3.0: gates for agents and CI (weeks 6–7, ~7 tasks)

Goal: this is the launch. The hook is the demo.

### 3.1 Claude Code hook **[plan first]**
- `goldtable hook install claude` writes to `.claude/settings.json`:
  - `Stop` hook → runs `goldtable check --format json`; on exit `1`, emits `{"decision":"block","reason":"<markdown summary with changed rows>"}` so the agent must either fix the pipeline or explain and ask the human to `accept`.
  - Optional `PostToolUse` (`Edit|Write`) hook → runs `check` only when the edited path matches `watch = ["pipeline/**"]` in config.
- Never auto-accept. The hook's job is to stop, not to decide.
- Done when: a recorded session shows the agent editing the pipeline, being blocked, and fixing it. Loop-guard: hook sets an env var so a blocked Stop can't re-trigger itself more than N times.

### 3.2 GitHub Action
- `action.yml` (composite) in the repo: installs goldtable, runs `check --format markdown`, posts/updates a single PR comment, fails the job on diffs. Inputs: `config`, `python-version`, `comment` (bool).
- Done when: the `examples/basic` repo's PR shows the comment; listed on the Marketplace.

### 3.3 Demo GIF
- Record with `vhs` (tape file committed): agent edit → `check` fails → fix → passes. Under 25 seconds, top of README.
- Done when: GIF under 3 MB, readable on mobile.

### 3.4 README rewrite
- Lead with the GIF and the one-liner. Sections: Why, Install, 60-second quickstart, Agent gate, CI gate, Rules, How it differs, Roadmap link.
- Done when: a reader understands the product from the first screen.

### 3.5 Launch
- Show HN, r/dataengineering, r/ClaudeAI; submit to awesome-claude-code and awesome-duckdb lists. Post in your own words; the story is "an agent changed 412 rows nobody noticed."
- Done when: posts are live and issues from feedback are triaged within 48h.

### 3.6 Release v0.3.0.

---

## Phase 4 — v0.4.0: developer ergonomics (weeks 8–10)

- **pytest plugin**: `pip install goldtable[pytest]`; `table_snapshot` fixture: `table_snapshot.assert_match(df_or_path, "customers_out")`; `--goldtable-accept` flag updates baselines (mirrors syrupy's UX).
- **Table sources polish**: `--where` filter on both sides; `duckdb://` and `sqlite://` URL forms; read-only guarantees in tests.
- **Schema-only mode**: `goldtable check --schema-only` for fast pre-commit use.
- **Column-level rules in config**: `[snapshot.columns.balance] tol = 0.005, kind = "money"`.
- **Windows path and encoding hardening**: CI already runs Windows; add BOM/CRLF CSV tests.
- Release v0.4.0.

## Phase 5 — v0.5.0: reach (weeks 11+)

- **MCP server**: `goldtable mcp` exposes `diff`, `check`, `accept` (accept requires an explicit `confirm=true`) so Codex, Cursor and others can use the gate.
- **Python API**: `goldtable.diff(a, b, key=...)` accepting pandas/Polars frames (optional extras), returning `DiffResult`.
- **HTML report**: single-file, no JS framework, for sharing a diff with non-engineers.
- **`goldtable watch`**: re-run `check` when `watch` paths change.
- Release v0.5.0.

---

## Appendix A — Issues to open on day 1

Open each as a GitHub issue with the body being the matching section above.

1. `v0.3: Claude Code Stop/PostToolUse hook that blocks on unexplained output changes`
2. `v0.3: GitHub Action that posts a diff report comment and fails the job`
3. `v0.3: README demo GIF recorded with vhs`
4. `v0.4: pytest plugin with table_snapshot fixture and --goldtable-accept`
5. `v0.4: --where filters and sqlite:// / duckdb:// source URLs`
6. `v0.4: schema-only fast mode for pre-commit`
7. `v0.4: column-level rule blocks in goldtable.toml`
8. `v0.5: MCP server exposing diff/check/accept`
9. `v0.5: Python API accepting pandas and Polars frames`
10. `v0.5: single-file HTML report`
11. `v0.5: watch mode`

## Appendix B — Decisions already made (copy into CLAUDE.md as they're confirmed)

- Engine: DuckDB for everything; no pandas in the core path.
- Package layout: `src/goldtable/{sources,schema,keys,diff,rules,result,render,config,store,cli}.py`.
- Exit codes: 0 identical, 1 differences, 2 error.
- Baselines live in `.goldtable/` and are committed.
- JSON output (`DiffResult.to_dict()`) is a public contract from v0.1; changes require a changelog entry.
- Nothing in the repo may resemble real customer, account or personal data. Fixtures are generated.

## Appendix C — Before each release

- No secrets anywhere in history (`gitleaks detect`).
- README examples run as written.
- CHANGELOG updated.
