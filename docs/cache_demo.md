# Cache + Instant Replay Demo

**Goal of the novel feature:** the first run of a repository builds and runs the Docker
environment; the second run of the same repository/commit reuses the cached image and
skips the build entirely.

## Commands

```powershell
cd "C:\Users\gagan\OneDrive\Desktop\maj project\autorun-hackathon"
export DOCKER_HOST=tcp://localhost:2375

# 1) First run  -- builds the environment, saves the cache
python src/main.py ../test-repo/flask-app --timeout 120

# 2) Second run  -- cache HIT, skips the Docker build
python src/main.py ../test-repo/flask-app --timeout 60

# 3) Inspect the cache
python src/main.py x --cache-list

# 4) Force a fresh build, or wipe the cache
python src/main.py ../test-repo/flask-app --no-cache
python src/main.py x --clear-cache
```

## Measured on this machine (python/flask, docker)

| Run | Cache | Execution time |
|---|---|---|
| `run_20261005_200929` | MISS | 60.41 s |
| `run_20261005_200947` | **HIT** | **10.47 s** |

So a cache hit is roughly **6x faster** on this repository because it skips

```
docker build ...   (pull python:3.9-slim, pip install requirements, COPY)
```

## What the cache stores

- `<output_dir>/cache/<cache_key>.json` with: `repo_url`, `commit_sha`, `language`,
  `framework`, `base_image`, `image_tag`, `image_id`, `startup_command`,
  `created_at`, `last_used_at`, `hit_count`.
- Docker image tagged `autorun-cache:<cache_key>`.
- Key is `sha256(repo_url|commit_sha|language|framework|base_image)[:16]`, so the same
  repo/commit/stack always maps to the same cache entry.

Only **successful Docker builds** are cached; failed builds, Node `no-Docker` runs, and
`--no-cache` invocations never touch the cache.
