#!/usr/bin/env python3
"""
Autorun Hackathon - Sandboxed Intelligent Repository Execution Engine
A CLI tool to automatically clone, build, and run GitHub repositories for quick evaluation.
"""

import argparse
import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from cloner import GitHubCloner
from detector import LanguageDetector
from sandbox import SandboxExecutor
from reporter import ResultReporter
from cache import EnvCache


def _get_commit_sha(repo_path) -> str:
    """Best-effort retrieval of the HEAD commit of a cloned repo."""
    try:
        import git
        return git.Repo(str(repo_path)).head.commit.hexsha
    except Exception:
        return None


def print_application_output(result: dict, show_full: bool = False):
    """Print the actual application output (stdout/stderr) to console.

    By default, shows COMPLETE output (no truncation).
    Use --no-output to hide output entirely.
    """
    process_output = result.get('process_output', {})
    stdout = process_output.get('stdout', '')
    stderr = process_output.get('stderr', '')
    logs = result.get('logs', '')

    # If we have process_output with stdout/stderr, use those
    # Otherwise fall back to logs
    has_output = bool(stdout.strip() or stderr.strip())

    if has_output:
        print("\n" + "=" * 70)
        print("📋 APPLICATION OUTPUT (What the repository's program actually printed)")
        print("=" * 70)

        if stdout.strip():
            print("\n📤 STDOUT (Standard Output):")
            print("-" * 70)
            print(stdout.rstrip())

        if stderr.strip():
            print("\n📥 STDERR (Standard Error):")
            print("-" * 70)
            print(stderr.rstrip())

        print("=" * 70)

        # Show what the app actually does based on its output
        print("\n🎯 REPOSITORY PURPOSE (Inferred from output):")
        print("-" * 70)
        purpose = infer_repository_purpose(stdout, stderr, result)
        print(purpose)
        print("=" * 70)


def infer_repository_purpose(stdout: str, stderr: str, result: dict) -> str:
    """Infer what the repository's application does based on its output."""
    combined = (stdout + stderr).lower()
    language = result.get('language', 'unknown')
    framework = result.get('framework', 'unknown')

    purposes = []

    # Web server indicators
    if any(kw in combined for kw in ['running on', 'listening on', 'serving on', 'started on', 'running at', 'server running']):
        port = None
        import re
        port_match = re.search(r'[: ](\d{3,5})', combined)
        if port_match:
            port = port_match.group(1)
        purposes.append("[Web Server] - Starts a web server" + (f" on port {port}" if port else ""))

    # Framework-specific
    if framework == 'flask' or 'flask' in combined:
        purposes.append("[Flask Web Application] - Python micro-framework")
    elif framework == 'django':
        purposes.append("[Django Web Application] - Python full-stack framework")
    elif framework == 'fastapi':
        purposes.append("[FastAPI Application] - Modern Python API framework")
    elif framework == 'express':
        purposes.append("[Express.js Application] - Node.js web framework")
    elif framework == 'react' or 'react' in combined:
        purposes.append("[React Application] - Frontend UI library")
    elif framework == 'next.js' or 'next' in combined:
        purposes.append("[Next.js Application] - React full-stack framework")
    elif framework == 'streamlit':
        purposes.append("[Streamlit App] - Data science web app")

    # API indicators
    if any(kw in combined for kw in ['api', 'rest', 'endpoint', 'route', 'json']):
        purposes.append("[API Service] - Provides REST/JSON endpoints")

    # Static file serving
    if 'static' in combined or 'express.static' in combined:
        purposes.append("[Static File Server] - Serves HTML/CSS/JS files")

    # Database
    if any(kw in combined for kw in ['database', 'sqlite', 'postgres', 'mysql', 'mongodb', 'redis']):
        purposes.append("[Database Connected] - Uses database storage")

    # Auth
    if any(kw in combined for kw in ['auth', 'login', 'jwt', 'token', 'session', 'cookie']):
        purposes.append("[Authentication] - Has user authentication")

    # WebSocket
    if 'websocket' in combined or 'socket.io' in combined:
        purposes.append("[Real-time/WebSocket] - Real-time communication")

    # Background jobs
    if any(kw in combined for kw in ['celery', 'worker', 'queue', 'cron', 'scheduler']):
        purposes.append("[Background Workers] - Async task processing")

    # Testing
    if any(kw in combined for kw in ['test', 'pytest', 'jest', 'mocha', 'coverage']):
        purposes.append("[Test Suite] - Runs automated tests")

    # Build/Compile
    if any(kw in combined for kw in ['build', 'compile', 'webpack', 'vite', 'bundl']):
        purposes.append("[Build Process] - Compiles/bundles assets")

    if not purposes:
        if result.get('success'):
            purposes.append("[SUCCESS] Application Runs Successfully - No specific purpose inferred")
        else:
            purposes.append("[FAILED] Application Failed to Start - Check logs for errors")

    return '\n'.join(f"  * {p}" for p in purposes)


def _serve_report(output_dir: str, port: int = 0):
    """Serve the latest HTML report on a localhost URL until Ctrl-C."""
    import functools
    import http.server
    import socketserver

    report_root = Path(output_dir) / "latest"
    if not (report_root / "report.html").exists():
        # Fall back to the output dir itself if 'latest' isn't there.
        report_root = Path(output_dir)
    if not report_root.exists():
        print("   (No report directory to serve.)")
        return

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(report_root))
    try:
        with socketserver.TCPServer(("", port), handler) as httpd:
            actual_port = httpd.server_address[1]
            url = f"http://localhost:{actual_port}/report.html"
            print("\n" + "=" * 70)
            print("📊 REPORT SERVER — view the full result in your browser at:")
            print(f"\n      👉  {url}\n")
            print("   Press Ctrl-C to stop the report server.")
            print("=" * 70 + "\n")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\n🛑 Report server stopped.")
    except OSError as e:
        print(f"   Could not start report server: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Automatically clone, build, and run GitHub repositories in a sandbox"
    )
    parser.add_argument(
        "repo_url",
        help="GitHub repository URL to clone and run"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Maximum execution time in seconds (default: 120)"
    )
    parser.add_argument(
        "--output-dir",
        default="./autorun-output",
        help="Directory to store output logs and artifacts (default: ./autorun-output)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--no-output",
        action="store_true",
        help="Hide application stdout/stderr (only show summary)"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Force a fresh build, ignoring and not writing the environment cache"
    )
    live_group = parser.add_mutually_exclusive_group()
    live_group.add_argument(
        "--live",
        dest="live",
        action="store_true",
        default=None,
        help="Keep the app running and serve it on http://localhost:<port> "
             "(auto-enabled for detected web apps)"
    )
    live_group.add_argument(
        "--no-live",
        dest="live",
        action="store_false",
        help="Run once to completion and print output, even for web apps"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Host port to expose the live app on (default: the app's own port)"
    )
    parser.add_argument(
        "--serve-report",
        action="store_true",
        help="After a one-shot run, serve the HTML report on a localhost URL"
    )
    parser.add_argument(
        "--cache-list",
        action="store_true",
        help="List cached environments and exit"
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Remove all cached environments and exit"
    )

    args = parser.parse_args()

    # The sandbox executor may print emojis; make the console UTF-8 tolerant so
    # the Windows default charmap console doesn't crash on them.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    # Determine if we should show output
    show_output = not args.no_output

    # --- Cache management flags (short-circuit) ---
    if args.cache_list or args.clear_cache:
        cache = EnvCache(args.output_dir)
        if args.clear_cache:
            removed = cache.clear()
            print(f"Removed {removed} cached environment(s).")
        else:
            for rec in cache.list():
                print(f"- {rec.get('cache_key')} | {rec.get('image_tag')} | "
                      f"{rec.get('language')}/{rec.get('framework')} | "
                      f"hits={rec.get('hit_count', 0)} | {rec.get('created_at')}")
        sys.exit(0)

    print("Autorun Hackathon - Sandboxed Repository Executor")
    print("=" * 50)

    try:
        # Step 1: Clone repository
        print(f"Cloning repository: {args.repo_url}")
        cloner = GitHubCloner()
        repo_path = cloner.clone(args.repo_url, args.output_dir)

        # Step 2: Detect language/framework
        print("Detecting language and framework...")
        detector = LanguageDetector()
        project_info = detector.detect(repo_path)
        print(f"   Detected: {project_info['language']} ({project_info.get('framework', 'unknown')})")

        # Step 3: Execute in sandbox (with environment cache)
        print("Setting up sandbox environment...")
        executor = SandboxExecutor()
        cache = EnvCache(args.output_dir)

        language = project_info.get('language')
        framework = project_info.get('framework', 'unknown')
        base_image = 'python:3.12-slim' if language == 'python' else (
            'node:20-slim' if language == 'nodejs' else 'unknown')
        commit_sha = _get_commit_sha(repo_path)

        # Decide whether to run the app *live* (keep it running on a localhost
        # URL) or as a one-shot program. Web apps default to live; the user can
        # force either mode with --live / --no-live.
        startup_cmd = executor.get_startup_command(repo_path, project_info)
        # Key the cache on the startup command too, so a cached image built
        # with a stale entrypoint is rebuilt when detection changes.
        cache_key = EnvCache.make_key(args.repo_url, commit_sha, language,
                                      framework, base_image, startup_cmd)
        detected_server = executor.is_server_workload(repo_path, project_info, startup_cmd)
        live_mode = detected_server if args.live is None else args.live
        if live_mode:
            print(f"   Detected a long-running server -> LIVE mode "
                  f"({'auto' if args.live is None else 'forced'})")
        else:
            print(f"   Running as a one-shot program "
                  f"({'auto' if args.live is None else 'forced'})")

        cached = None
        if not args.no_cache and executor.docker_client is not None:
            cached = cache.get(cache_key)

        # Build the keyword args shared by execute() and serve().
        if cached:
            print(f"   [CACHE HIT] key={cache_key} - reusing cached environment")
            run_kwargs = dict(
                cache_key=cache_key,
                cached_image_tag=cached['image_tag'],
                cached_startup_cmd=cached.get('startup_command'),
            )
        else:
            if executor.docker_client is not None:
                print(f"   [CACHE MISS] key={cache_key} - building fresh environment")
            run_kwargs = dict(cache_key=cache_key)

        if live_mode:
            result = executor.serve(
                repo_path, project_info,
                host_port=args.port, timeout=args.timeout, **run_kwargs)
        else:
            result = executor.execute(
                repo_path, project_info, args.timeout, **run_kwargs)

        result['cache_hit'] = bool(cached)
        result['cache_key'] = cache_key
        if cached:
            cache.touch(cache_key)
        elif (result.get('success') and executor.docker_client is not None
                and result.get('image_tag')):
            # Only successful Docker builds are worth caching
            cache.put(cache_key, {
                'repo_url': args.repo_url,
                'commit_sha': commit_sha,
                'language': language,
                'framework': framework,
                'base_image': base_image,
                'image_tag': result['image_tag'],
                'image_id': result.get('image_id'),
                'startup_command': result.get('startup_command'),
            })
            print(f"   [CACHE] Saved environment as '{result['image_tag']}'")

        # Step 4: Show application output (one-shot runs stream live already)
        if not args.no_output and not result.get('served'):
            print_application_output(result)

        # Step 5: Report results
        print("Generating report...")
        reporter = ResultReporter()
        reporter.report(result, args.output_dir)

        print("\nExecution completed!")
        print(f"Results saved to: {args.output_dir}")

        # Optionally serve the HTML report on a localhost URL so the full
        # result can be viewed in a browser (handy for one-shot runs).
        if args.serve_report and not result.get('served'):
            _serve_report(args.output_dir)

    except KeyboardInterrupt:
        print("\nExecution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()