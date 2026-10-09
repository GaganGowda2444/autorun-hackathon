# Autorun — Sandboxed Repository Execution Engine

Give Autorun a GitHub URL (or a local path) and it will **clone it, detect the
language/framework, run it in a sandbox, and show you the result** — either as
full output in your terminal or as a live web app on `http://localhost:<port>`.

```bash
python src/main.py <repo-url-or-path> [options]
```

## What you get

- **Web apps run *live*.** Flask / FastAPI / Django / Streamlit / Express /
  Next.js / Vite / NestJS and friends are kept running, their port is published
  to your host, their logs stream to your terminal, and you get a clickable
  `http://localhost:<port>` URL to open in a browser. Press `Ctrl-C` to stop.
- **CLI / one-shot programs show their complete output** (stdout + stderr) in
  the terminal, plus an inferred summary of what the program does.
- **Every run is also written as an HTML report** you can open, and optionally
  served on localhost with `--serve-report`.
- **Environment caching:** a successfully built Docker image is reused on the
  next run of the same repo+commit (instant replay).

## Install

```bash
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Docker is recommended (runs untrusted repos in an isolated container). If the
Docker daemon isn't available, Autorun falls back to running the repo as a
local **subprocess** (less isolated — only do this with code you trust, or set
`AUTORUN_NO_DOCKER=1` to force it deliberately).

## Usage

```bash
# Auto mode: web apps are served live, CLI programs run once.
python src/main.py https://github.com/user/some-flask-app

# Force live serving on a specific host port
python src/main.py https://github.com/user/app --live --port 8080

# Force a one-shot run even for a web app (just capture startup output)
python src/main.py https://github.com/user/app --no-live

# Run a CLI tool and then view its HTML report in the browser
python src/main.py ./my-local-repo --serve-report
```

### Options

| Flag | Meaning |
|---|---|
| `--live` / `--no-live` | Force live-serve mode / force one-shot. Default: auto (web apps → live). |
| `--port N` | Host port to expose the live app on, **Docker only** (host→container mapping). Without Docker the app keeps its own port. |
| `--serve-report` | After a one-shot run, serve the HTML report on a localhost URL. |
| `--timeout N` | Max seconds for a one-shot run (default 120). |
| `--output-dir DIR` | Where logs/reports/cache are written (default `./autorun-output`). |
| `--no-output` | Hide the captured stdout/stderr (summary only). |
| `--no-cache` | Ignore and don't write the environment cache. |
| `--cache-list` / `--clear-cache` | List or remove cached environments, then exit. |
| `--verbose` | Print full tracebacks on error. |

### How live vs. one-shot is decided

Autorun decides automatically — **you normally don't need any flag**. It looks at:
1. the detected framework (Flask/FastAPI/Django/Streamlit/Express/Next/…),
2. the startup command it derives (`flask run`, `uvicorn`, `npm run dev`, `manage.py runserver`, …), and
3. the **source code itself** — e.g. `app.run(...)`, `Flask(...)`, `FastAPI(...)`, `uvicorn`, `app.listen(...)` — so an app started as plain `python app.py` is still recognised as a server even when it declares no framework.

Any of these → **live** (served on localhost); everything else → **one-shot**
(runs and prints full output). You can always override with `--live` / `--no-live`.

## Output

Each run produces a `run_<timestamp>/` directory (and a `latest/` copy) under
the output dir containing:

- `execution.log` — full build + execution logs
- `result.json` — structured result (success, language, framework, metrics, cache, live URL)
- `summary.txt` — human-readable summary
- `report.html` — standalone visual report

## Supported today

Python (Flask, FastAPI, Django, Streamlit, and plain scripts) and Node.js
(Express, Next.js, Nuxt, NestJS, Vite/React/Vue, and plain scripts). See
[`docs/master_implementation_plan.md`](docs/master_implementation_plan.md) for
the longer-term research roadmap.

## Tests

```bash
pip install pytest
python -m pytest tests/ -q
```
