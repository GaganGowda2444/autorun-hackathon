# Implementation Plan — Autorun Hackathon (EnvRun)

**Status:** Active plan, 2026-10-05
**Main idea (unchanged):** Given a repository, automatically clone it, detect its
language/framework, build/run it inside an isolated sandbox, and produce a report.
**One novel feature (explicitly added):** Automatic environment caching with instant replay.

---

## 0. Current state of the codebase (verified)

| File | Role | Key facts |
|---|---|---|
| `src/main.py` | CLI entry | `repo_url` positional arg; `--timeout`, `--output-dir`, `--verbose`, `--no-output`; pipeline: clone → detect → execute → print output → report |
| `src/cloner.py` | Clone | `GitHubCloner().clone(repo_url, output_dir)`; clone dir = `output_dir/md5(repo_url)`; local paths are copied; **fresh clone every run (deletes existing dir)** |
| `src/detector.py` | Detect | `LanguageDetector().detect(repo_path)` → `{'language', 'framework', ...}` |
| `src/sandbox.py` | Execute | `SandboxExecutor().execute(repo_path, project_info, timeout)`; Docker path builds a temp `python:3.9-slim` / `node:16-slim` image tagged `autorun-<timestamp>`, **never reused, never tagged deterministically**; falls back to host subprocess when Docker unavailable |
| `src/reporter.py` | Report | Writes `result.json`, `execution.log`, `summary.txt`, `report.html` per run |
| `src/config.py` | Config | Singleton `Config`, YAML/JSON + env overrides, defaults for docker/sandbox |
| `tests/` | pytest | conftest + 5 test modules; `.pytest_cache` present so suite was run before |
| `autorun-output/` | Artifacts | `latest/`, `run_*/` dirs, `repo_*/` clones, old dockerized flask run |

**Verified weaknesses relative to the goal:**
1. Every run re-clones and rebuilds the Docker image from scratch (slow).
2. Docker images are tagged with `time.time()` → duplicates accumulate, nothing is reusable.
3. No cache key, no reuse of build results, no persisted run recipe.

---

## 1. Scope of the novel feature

**Environment Cache + Instant Replay**

- After a **successful** Docker run, tag the built image as `autorun-cache:<cache_key>`
  and persist `autorun-output/cache/<cache_key>.json` containing:
  `cache_key`, `repo_url`, `commit_sha` (when available; else URL hash), `language`,
  `framework`, base image, `image_tag`, `image_id`, `startup_command`,
  `timeout_used`, `created_at`, `last_used_at`, `hit_count`.
- On the next run with the same `cache_key` and a valid Docker daemon: **skip clone rebuild**,
  re-use the cached image, only re-run the container. Report `cache_hit: true`
  and `cached_execution_time`.
- Cache miss → normal path, then save.
- CLI additions (non-breaking):
  - `--no-cache` — bypass cache (force fresh build)
  - `--clear-cache` — remove cached images + metadata and exit
  - `--cache-list` — print cache table and exit
- Never cache: failed builds, host-subprocess (non-Docker) runs, or `AUTORUN_NO_DOCKER=1`.

### Cache key construction (must be deterministic, safe)
```
cache_key = sha256( f"{repo_url}|{commit_sha or 'HEAD'}|{language}|{framework}|{base_image}" )[:16]
```
- `commit_sha`: after cloning, `git -C <repo_path> rev-parse HEAD` (use `git.Repo(repo_path).head.commit.hexsha`); if unavailable, fall back to md5(repo_url) like the cloner.
- Key stays stable for the same repo/commit/language → replay is correct.

---

## 2. Implementation phases (each phase = testable milestone)

### Phase 1 — Sandbox hooks for caching
- In `src/sandbox.py::_execute_in_docker`:
  - change image tag from `autorun-{int(time.time())}` to `autorun-cache:<cache_key>` when a cache key is provided (pass it in via `execute(..., cache_key=None)`).
  - expose the built `image_obj.id` and resolved `startup_cmd`, `image`, `install_cmd` in the returned result dict so the cache layer can persist them.
- Add optional param `cached_image_tag=None` to `execute()`:
  - if provided and the image exists locally (`docker.from_env().images.get(tag)` succeeds), **skip cloning-rebuild path**: go straight to `containers.run(cached_image_tag, ...)`.

### Phase 2 — New module `src/cache.py`
- `EnvCache` class:
  - `make_key(repo_url, commit_sha, language, framework, base_image) -> str`
  - `get(cache_key) -> dict | None` (validates image still exists in Docker)
  - `put(cache_key, record) -> None`
  - `list() -> list[dict]`, `clear() -> None` (remove records + `docker rmi` tagged images), `touch(cache_key)` (update `last_used_at`, `hit_count`)
- Storage: `<output_dir>/cache/*.json` + image tags `autorun-cache:<key>`.

### Phase 3 — Wire into `src/main.py`
- After detection, compute `cache_key` (needs commit sha from cloned repo).
- If `--no-cache` not set: `hit = cache.get(key)`; print `Cache HIT/MISS`.
- On hit: call `executor.execute(repo_path, project_info, timeout, cached_image_tag=hit['image_tag'])`.
- On miss/success: save cache record, re-tag image to `autorun-cache:<key>`.
- Add `--cache-list` and `--clear-cache` to print/remove cache and exit.
- Keep `--output` printing and reporter unchanged; add `cache_hit` and `cache_key` fields to `result`.

### Phase 4 — Reporter surface
- Add two lines to `summary.txt` and the HTML report: `Cache: HIT|MISS`, `Cache key: ...`, plus total wall time saved estimate.

### Phase 5 — Tests (`tests/test_cache.py`)
- Unit: key determinism, `put/get/list/clear/touch` with tmp dir.
- Unit: skip-build on hit (monkeypatch Docker client; assert `images.build` not called).
- Unit: failed run is never cached; non-Docker path never cached.
- Keep all existing tests passing (`pytest -q`).

### Phase 6 — Bench + demo evidence
- Run the same repo twice (fresh vs cached) and record both times.
- Add `docs/cache_demo.md` with commands + measured before/after numbers.

---

## 3. Non-goals / safety rules (do not implement)
- No LLM agent, no automatic host-network changes, no Node/Java support in the cache layer.
- Do not cache when Docker is unavailable or `AUTORUN_NO_DOCKER=1`.
- Do not bypass the existing success contract: a cached replay still must prove the app/tests start.
- Do not mutate `test-repo/` or old `autorun-output/` artifacts.

## 4. Acceptance criteria
1. First run on a public Python repo succeeds end-to-end and writes a cache record + tagged image.
2. Second run on the same repo/commit prints `Cache HIT`, does **not** call `images.build`, and finishes noticeably faster.
3. `--no-cache` forces a rebuild; `--clear-cache` removes records and images.
4. `pytest -q` passes (old + new tests).
5. `summary.txt`/`report.html` show `Cache: HIT|MISS`.

## 5. File-by-file change list (summary)
- `src/cache.py` — **new**
- `src/sandbox.py` — accept `cache_key`/`cached_image_tag`, deterministic tag, expose image id
- `src/main.py` — cache lookup/save, 3 new flags, `cache_hit` in result
- `src/reporter.py` — two lines in summary + HTML
- `tests/test_cache.py` — **new**
- `docs/cache_demo.md` — **new** (after measuring)
