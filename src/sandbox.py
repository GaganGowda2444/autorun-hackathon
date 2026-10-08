import os
import subprocess
import tempfile
import time
import signal
import sys
import psutil
from pathlib import Path
from typing import Dict, Any, List
import docker
import socket

from config import get_config


class SandboxExecutor:
    """Executes the project in a sandboxed environment."""

    def __init__(self):
        """Initialize the sandbox executor."""
        self.config = get_config()
        sandbox_config = self.config.get_sandbox_config()

        # Time to run server processes before considering them "started successfully"
        self.SERVER_STARTUP_TIMEOUT = sandbox_config.get('server_startup_timeout', 10)

        # Check for environment variable to disable Docker
        if os.environ.get('AUTORUN_NO_DOCKER') == '1':
            self.docker_client = None
            print("[WARN] Docker disabled via AUTORUN_NO_DOCKER, using subprocess execution (less secure)")
            return

        # Check if Docker is enabled in config
        docker_config = self.config.get_docker_config()
        if not docker_config.get('enabled', True):
            self.docker_client = None
            print("[WARN] Docker disabled in config, using subprocess execution (less secure)")
            return

        try:
            self.docker_client = docker.from_env()
        except Exception:
            # Fallback to subprocess-based execution if Docker is not available
            self.docker_client = None
            print("[WARN] Docker not available, using subprocess execution (less secure)")

    def _check_tcp_port(self, host: str, port: int, timeout: float = 0.5) -> bool:
        """
        Check if a TCP port is open and accepting connections.

        Args:
            host: Host to connect to (e.g., '127.0.0.1')
            port: Port number to check
            timeout: Connection timeout in seconds

        Returns:
            bool: True if port is open and accepting connections
        """
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            return False

    def _wait_for_port(self, host: str, port: int, max_wait: int = 10) -> bool:
        """
        Wait for a TCP port to become available.

        Args:
            host: Host to connect to
            port: Port number to check
            max_wait: Maximum seconds to wait

        Returns:
            bool: True if port becomes available within max_wait seconds
        """
        start_time = time.time()
        while time.time() - start_time < max_wait:
            if self._check_tcp_port(host, port):
                return True
            time.sleep(0.5)
        return False

    def _extract_port_from_command(self, command: str, language: str) -> int:
        """
        Extract the port number from a startup command.

        Args:
            command: The startup command string
            language: The programming language ('python' or 'nodejs')

        Returns:
            int: The port number, or default port if not found
        """
        import re

        # Common port patterns in commands
        patterns = [
            r'--port[=\s]+(\d+)',           # --port=5000 or --port 5000
            r'-p[=\s]+(\d+)',               # -p=5000 or -p 5000
            r'port[=\s]+(\d+)',             # port=5000 or port 5000
            r':(\d{4,5})',                  # :5000, :8000, :3000, etc.
            r'port\s+(\d+)',                # port 5000
        ]

        for pattern in patterns:
            match = re.search(pattern, command, re.IGNORECASE)
            if match:
                try:
                    port = int(match.group(1))
                    if 1 <= port <= 65535:
                        return port
                except (ValueError, IndexError):
                    continue

        # Default ports based on language/framework patterns
        if language == 'python':
            if 'flask' in command.lower():
                return 5000
            elif 'django' in command.lower():
                return 8000
            elif 'fastapi' in command.lower() or 'uvicorn' in command.lower():
                return 8000
            elif 'streamlit' in command.lower():
                return 8501
            return 5000
        elif language == 'nodejs':
            if 'express' in command.lower():
                return 5000
            elif 'next' in command.lower():
                return 3000
            elif 'vite' in command.lower():
                return 5173
            return 3000

        return 8080

    def execute(self, repo_path: Path, project_info: Dict[str, Any], timeout: int = 120,
                cache_key: str = None, cached_image_tag: str = None,
                cached_startup_cmd: str = None) -> Dict[str, Any]:
        """
        Execute the project in a sandbox.

        Args:
            repo_path (Path): Path to the cloned repository.
            project_info (dict): Information about the project from detection.
            timeout (int): Maximum execution time in seconds.
            cache_key (str): Deterministic cache key for tagging the built image.
            cached_image_tag (str): If set and present locally, skip the build and reuse it.
            cached_startup_cmd (str): Startup command stored with the cached image.

        Returns:
            dict: Execution result including success status, logs, and metrics.
        """
        result = {
            'success': False,
            'language': project_info.get('language'),
            'framework': project_info.get('framework'),
            'logs': '',
            'error': None,
            'execution_time': 0,
            'process_output': {},
            'metrics': {}
        }

        start_time = time.time()

        try:
            if self.docker_client:
                # Use Docker for sandboxed execution
                execution_result = self._execute_in_docker(
                    repo_path, project_info, timeout,
                    cache_key=cache_key,
                    cached_image_tag=cached_image_tag,
                    cached_startup_cmd=cached_startup_cmd,
                )
            else:
                # Fallback to subprocess execution (for development/testing)
                execution_result = self._execute_in_subprocess(repo_path, project_info, timeout)

            result.update(execution_result)
            result['execution_time'] = time.time() - start_time

        except subprocess.TimeoutExpired:
            result['error'] = f"Execution timed out after {timeout} seconds"
            result['logs'] += f"\n[ERROR] Execution timed out after {timeout} seconds"
        except Exception as e:
            result['error'] = str(e)
            result['logs'] += f"\n[ERROR] {str(e)}"

        return result

    # ------------------------------------------------------------------
    # Workload classification
    # ------------------------------------------------------------------
    # Frameworks whose normal entrypoint is a long-running web/server process.
    SERVER_FRAMEWORKS = {
        'flask', 'django', 'fastapi', 'streamlit',
        'express', 'next', 'nuxt', 'nest', 'react', 'vue', 'angular',
        'svelte', 'vite',
    }
    # Substrings in a startup command that indicate a long-running server.
    SERVER_COMMAND_MARKERS = (
        'flask run', 'uvicorn', 'gunicorn', 'runserver', 'streamlit run',
        'manage.py runserver', 'npm run dev', 'npm start', 'npm run start',
        'npm run serve', 'npm run preview', 'next dev', 'next start', 'nuxt',
        'vite', 'react-scripts', 'nodemon', 'http.server', 'serve',
        'daphne', 'hypercorn', 'waitress',
    )

    def get_startup_command(self, repo_path: Path, project_info: Dict[str, Any]) -> str:
        """Return the startup command this executor would use for a repo."""
        language = project_info.get('language')
        if language == 'python':
            return self._get_python_startup_command(repo_path)
        if language == 'nodejs':
            return self._get_node_startup_command(repo_path)
        return ''

    # Signatures found in source files that reveal a long-running server even
    # when the framework isn't declared in a manifest (e.g. `python app.py`).
    SERVER_SOURCE_MARKERS = (
        'flask(', 'fastapi(', 'app.run(', 'uvicorn', 'gunicorn',
        'import streamlit', 'aiohttp', 'import sanic', 'tornado.',
        'from bottle', 'import bottle', 'app.listen(', 'http.createserver',
        "require('express')", 'require("express")', 'socket.io',
    )

    def is_server_workload(self, repo_path: Path, project_info: Dict[str, Any],
                           startup_cmd: str = None) -> bool:
        """Heuristically decide whether a repo runs a long-lived server.

        A *server* keeps running and listens on a port (it should be served on
        localhost); a *one-shot* program runs to completion and prints output.

        Detection order: declared framework -> startup-command markers ->
        source-code signatures (so an app started as `python app.py` whose
        framework isn't in a manifest is still recognised as a server).
        """
        framework = (project_info.get('framework') or '').lower()
        if framework in self.SERVER_FRAMEWORKS:
            return True
        if startup_cmd is None:
            startup_cmd = self.get_startup_command(repo_path, project_info)
        cmd = (startup_cmd or '').lower()
        if any(marker in cmd for marker in self.SERVER_COMMAND_MARKERS):
            return True
        return self._source_indicates_server(repo_path)

    def _source_indicates_server(self, repo_path: Path) -> bool:
        """Scan a few source files for web-server signatures."""
        patterns = ('*.py', '*.js', '*.ts', '*.mjs')
        scanned = 0
        for pattern in patterns:
            # Root files first, then one level down (typical app layouts).
            for candidate in list(repo_path.glob(pattern)) + list(repo_path.glob(f'*/{pattern}')):
                if scanned >= 60:  # keep it bounded on large repos
                    return False
                scanned += 1
                try:
                    text = candidate.read_text(encoding='utf-8', errors='ignore').lower()
                except Exception:
                    continue
                if any(marker in text for marker in self.SERVER_SOURCE_MARKERS):
                    return True
        return False

    def _build_or_get_image(self, repo_path: Path, project_info: Dict[str, Any],
                            cache_key: str = None, cached_image_tag: str = None,
                            cached_startup_cmd: str = None) -> Dict[str, Any]:
        """Build a Docker image for the repo, or reuse a cached one.

        Returns a dict with the built image object, its tag, build log, the
        resolved startup command and base image, and whether the cache was hit.
        """
        language = project_info.get('language')

        if language == 'python':
            image = 'python:3.9-slim'
            install_cmd = 'pip install -r requirements.txt'
            startup_cmd = self._get_python_startup_command(repo_path)
        elif language == 'nodejs':
            image = 'node:16-slim'
            install_cmd = 'npm install'
            startup_cmd = self._get_node_startup_command(repo_path)
        else:
            raise ValueError(f"Unsupported language for Docker execution: {language}")

        # Prefer the startup command recorded in the cache record
        if cached_startup_cmd:
            startup_cmd = cached_startup_cmd

        # If we couldn't determine a startup command, use a default
        if not startup_cmd:
            if language == 'python':
                startup_cmd = "python -c 'print(\"No startup command detected\"); import sys; sys.exit(0)'"
            elif language == 'nodejs':
                startup_cmd = 'echo "No startup command detected" && exit 0'

        cached_used = False
        image_obj = None
        build_log = ''
        image_tag = cached_image_tag if cached_image_tag else None

        # --- Cache hit: reuse the previously built image -----------------
        if cached_image_tag:
            try:
                image_obj = self.docker_client.images.get(cached_image_tag)
                cached_used = True
                print(f"   [CACHE HIT] Reusing cached image: {cached_image_tag}")
                build_log = f"[cache hit] Reused image {cached_image_tag} (build skipped)"
            except Exception:
                print(f"   [CACHE MISS] Cached image not found: {cached_image_tag}, rebuilding...")

        # --- Cache miss / no cache: build the image ----------------------
        if not cached_used:
            # Create a Dockerfile
            dockerfile_content = f"""
FROM {image}
WORKDIR /app
COPY . /app
RUN {install_cmd}
CMD ["sh", "-c", "{startup_cmd}"]
""".strip()

            # Write Dockerfile to a temporary directory
            import tempfile
            import shutil
            with tempfile.TemporaryDirectory() as temp_dir:
                dockerfile_path = Path(temp_dir) / "Dockerfile"
                with open(dockerfile_path, 'w') as f:
                    f.write(dockerfile_content)

                # Copy the repository content to the temporary directory
                for item in repo_path.iterdir():
                    if item.name != '.git':  # Skip .git directory to save space
                        dest = Path(temp_dir) / item.name
                        if item.is_dir():
                            shutil.copytree(item, dest)
                        else:
                            shutil.copy2(item, dest)

                # Build the Docker image
                print("   Building Docker image...")
                if cache_key:
                    image_tag = f"autorun-cache:{cache_key}"
                else:
                    image_tag = f"autorun-{int(time.time())}"
                image_obj, build_logs = self.docker_client.images.build(
                    path=str(temp_dir),
                    tag=image_tag,
                    rm=True
                )

                # Collect build logs
                build_log = '\n'.join([str(log.get('stream', '')) for log in build_logs if 'stream' in log])
                print(f"   Built image tagged: {image_tag}")

        return {
            'image_obj': image_obj,
            'image_tag': image_tag,
            'build_log': build_log,
            'cached_used': cached_used,
            'startup_cmd': startup_cmd,
            'base_image': image,
            'install_cmd': install_cmd,
        }

    # ------------------------------------------------------------------
    # Live serve mode: keep a web app running and reachable on localhost
    # ------------------------------------------------------------------
    def serve(self, repo_path: Path, project_info: Dict[str, Any],
              host_port: int = None, timeout: int = None,
              cache_key: str = None, cached_image_tag: str = None,
              cached_startup_cmd: str = None) -> Dict[str, Any]:
        """Run a web application and keep it live on http://localhost:<port>.

        Streams the application's logs to the console and blocks until the
        process stops or the user presses Ctrl-C. Returns a result dict shaped
        like :meth:`execute`'s so the reporter can consume it unchanged.
        """
        result = {
            'success': False,
            'language': project_info.get('language'),
            'framework': project_info.get('framework'),
            'logs': '',
            'error': None,
            'execution_time': 0,
            'process_output': {},
            'metrics': {},
            'served': True,
        }
        start_time = time.time()
        try:
            if self.docker_client:
                exec_result = self._serve_in_docker(
                    repo_path, project_info, host_port, timeout,
                    cache_key=cache_key, cached_image_tag=cached_image_tag,
                    cached_startup_cmd=cached_startup_cmd,
                )
            else:
                exec_result = self._serve_in_subprocess(
                    repo_path, project_info, host_port, timeout)
            result.update(exec_result)
        except Exception as e:
            result['error'] = str(e)
            result['logs'] += f"\n[ERROR] {str(e)}"
        result['execution_time'] = time.time() - start_time
        return result

    def _print_serve_banner(self, url: str, healthy: bool):
        """Print a prominent banner pointing the user at the live app."""
        print("\n" + "=" * 70)
        if healthy:
            print(f"🚀 LIVE — the application is running and reachable at:")
            print(f"\n      👉  {url}\n")
            print("   Open that URL in your browser to use the app.")
        else:
            print(f"⏳ The application was started and is being served at:")
            print(f"\n      👉  {url}\n")
            print("   (The port did not answer a health check yet — it may still")
            print("    be starting, bind a different port, or not be a web app.)")
        print("   Press Ctrl-C to stop the server and return.")
        print("=" * 70 + "\n")

    def _serve_in_docker(self, repo_path: Path, project_info: Dict[str, Any],
                         host_port: int, timeout: int,
                         cache_key: str = None, cached_image_tag: str = None,
                         cached_startup_cmd: str = None) -> Dict[str, Any]:
        """Serve a web app from inside a Docker container with a published port."""
        language = project_info.get('language')
        build_info = self._build_or_get_image(
            repo_path, project_info,
            cache_key=cache_key, cached_image_tag=cached_image_tag,
            cached_startup_cmd=cached_startup_cmd,
        )
        image_obj = build_info['image_obj']
        startup_cmd = build_info['startup_cmd']

        container_port = self._extract_port_from_command(startup_cmd, language)
        if not host_port:
            host_port = self._find_free_port(container_port)

        docker_config = self.config.get_docker_config()
        print("   Starting container (live mode)...")
        # Networking must stay enabled and the filesystem writable so the web
        # server can bind its port and write runtime files (e.g. .pyc, sessions).
        container = self.docker_client.containers.run(
            image_obj.id,
            detach=True,
            mem_limit=docker_config.get('memory_limit', '500m'),
            cpu_period=docker_config.get('cpu_period', 100000),
            cpu_quota=docker_config.get('cpu_quota', 50000),
            ports={f'{container_port}/tcp': host_port},
        )

        url = f"http://localhost:{host_port}"
        healthy = self._wait_for_port('127.0.0.1', host_port, max_wait=30)
        self._print_serve_banner(url, healthy)

        collected = []
        try:
            for chunk in container.logs(stream=True, follow=True):
                text = chunk.decode('utf-8', errors='replace')
                sys.stdout.write(text)
                sys.stdout.flush()
                collected.append(text)
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping server (Ctrl-C received)...")
        finally:
            try:
                container.reload()
                status = container.attrs.get('State', {}).get('Status')
                exit_code = container.attrs.get('State', {}).get('ExitCode', 0)
            except Exception:
                status, exit_code = None, 0
            try:
                remaining = container.logs().decode('utf-8', errors='replace')
                if remaining and not collected:
                    collected.append(remaining)
            except Exception:
                pass
            try:
                container.stop(timeout=5)
            except Exception:
                pass
            try:
                container.remove(force=True)
            except Exception:
                pass

        logs = ''.join(collected)
        # If the container exited by itself with a non-zero code, that's a failure;
        # a server we interrupted (status 'running' / stopped by us) counts as a
        # successful live run if it ever answered on its port.
        crashed = status == 'exited' and exit_code not in (0, None)
        success = bool(healthy) and not crashed
        return {
            'success': success,
            'logs': f"Build logs:\n{build_info['build_log']}\n\nExecution logs:\n{logs}",
            'error': None if success else (
                f"Container exited with code {exit_code}" if crashed
                else "Server never became reachable on its port"),
            'process_output': {'exit_code': exit_code or 0, 'logs': logs,
                               'stdout': logs, 'stderr': ''},
            'metrics': {},
            'image_tag': build_info['image_tag'],
            'image_id': image_obj.id if image_obj is not None else None,
            'base_image': build_info['base_image'],
            'startup_command': startup_cmd,
            'cache_hit': build_info['cached_used'],
            'served': True,
            'url': url,
            'healthy': healthy,
        }

    def _serve_in_subprocess(self, repo_path: Path, project_info: Dict[str, Any],
                             host_port: int, timeout: int) -> Dict[str, Any]:
        """Serve a web app as a host subprocess (used when Docker is absent).

        Installs dependencies, launches the server, streams its combined
        stdout/stderr live, prints the localhost URL, and blocks until the
        process exits or the user presses Ctrl-C.
        """
        import threading

        language = project_info.get('language')
        repo_path = repo_path.resolve()
        original_cwd = os.getcwd()
        os.chdir(repo_path)

        collected = []
        process = None
        try:
            # --- Install dependencies -----------------------------------
            if language == 'python':
                install_cmd = ['pip', 'install', '-r', 'requirements.txt']
                startup_cmd_str = self._get_python_startup_command(repo_path)
            elif language == 'nodejs':
                install_cmd = ['npm', 'install']
                startup_cmd_str = self._get_node_startup_command(repo_path)
            else:
                raise ValueError(f"Unsupported language for subprocess execution: {language}")

            print("   Installing dependencies...")
            use_shell = (language == 'nodejs' and sys.platform == 'win32')
            install_result = subprocess.run(
                install_cmd, capture_output=True, text=True,
                timeout=180, shell=use_shell)
            install_logs = f"STDOUT:\n{install_result.stdout}\nSTDERR:\n{install_result.stderr}"
            if install_result.returncode != 0:
                return {
                    'success': False,
                    'logs': install_logs,
                    'error': f"Dependency installation failed with exit code {install_result.returncode}",
                    'process_output': {'returncode': install_result.returncode,
                                       'stdout': install_result.stdout,
                                       'stderr': install_result.stderr},
                    'metrics': {},
                    'startup_command': startup_cmd_str,
                    'served': True,
                }

            # --- Launch the server --------------------------------------
            # In subprocess mode there is no port remapping: the app binds
            # whatever port its startup command specifies, so --port (a Docker
            # host:container mapping) cannot be honored here.
            container_port = self._extract_port_from_command(startup_cmd_str, language)
            if host_port and host_port != container_port:
                print(f"   (Note: --port is only applied with Docker; this app "
                      f"binds port {container_port}, so serving on {container_port}.)")
            port = container_port
            print(f"   Starting application (live mode) on port {port}...")

            popen_kwargs = dict(
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, shell=True)
            if sys.platform != 'win32':
                popen_kwargs['start_new_session'] = True  # own process group for clean kill
            process = subprocess.Popen(startup_cmd_str, **popen_kwargs)

            def _reader():
                try:
                    for line in iter(process.stdout.readline, ''):
                        sys.stdout.write(line)
                        sys.stdout.flush()
                        collected.append(line)
                except Exception:
                    pass

            reader = threading.Thread(target=_reader, daemon=True)
            reader.start()

            url = f"http://localhost:{port}"
            healthy = self._wait_for_port('127.0.0.1', port, max_wait=30)
            self._print_serve_banner(url, healthy)

            # --- Block until the process exits or the user interrupts ----
            try:
                while process.poll() is None:
                    time.sleep(0.4)
            except KeyboardInterrupt:
                print("\n\n🛑 Stopping server (Ctrl-C received)...")
            finally:
                if process.poll() is None:
                    self._kill_process_tree(process.pid)
                try:
                    process.wait(timeout=5)
                except Exception:
                    pass
                reader.join(timeout=2)

            logs = ''.join(collected)
            returncode = process.returncode
            # Process exited on its own with an error => failure. Otherwise a
            # server that answered its port (or that we stopped) is a success.
            crashed = returncode not in (0, None) and not healthy
            success = bool(healthy) or returncode in (0, None)
            if crashed:
                success = False
            return {
                'success': success,
                'logs': f"Installation logs:\n{install_logs}\n\nExecution logs:\n{logs}",
                'error': None if success else f"Process exited with code {returncode}",
                'process_output': {'returncode': returncode or 0,
                                   'stdout': logs, 'stderr': ''},
                'metrics': {},
                'startup_command': startup_cmd_str,
                'served': True,
                'url': url,
                'healthy': healthy,
            }
        finally:
            os.chdir(original_cwd)

    def _find_free_port(self, preferred: int) -> int:
        """Return `preferred` if free, otherwise an OS-assigned free port."""
        if not self._check_tcp_port('127.0.0.1', preferred):
            # Nothing is listening there; try to bind to confirm it's bindable.
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.bind(('', preferred))
                    return preferred
            except OSError:
                pass
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]

    def _execute_in_docker(self, repo_path: Path, project_info: Dict[str, Any], timeout: int,
                           cache_key: str = None, cached_image_tag: str = None,
                           cached_startup_cmd: str = None) -> Dict[str, Any]:
        """
        Execute the project in a Docker container.

        Args:
            repo_path (Path): Path to the cloned repository.
            project_info (dict): Information about the project.
            timeout (int): Maximum execution time in seconds.
            cache_key (str): If set, tag the built image as autorun-cache:<key>.
            cached_image_tag (str): If set and present locally, skip the build.
            cached_startup_cmd (str): Startup command from the cache record.

        Returns:
            dict: Execution result.
        """
        # Build (or reuse a cached) Docker image for this repository.
        language = project_info.get('language')
        build_info = self._build_or_get_image(
            repo_path, project_info,
            cache_key=cache_key,
            cached_image_tag=cached_image_tag,
            cached_startup_cmd=cached_startup_cmd,
        )
        image_obj = build_info['image_obj']
        image_tag = build_info['image_tag']
        build_log = build_info['build_log']
        cached_used = build_info['cached_used']
        startup_cmd = build_info['startup_cmd']
        image = build_info['base_image']

        # Run the container with resource limits
        print("   Running container...")
        docker_config = self.config.get_docker_config()
        container = self.docker_client.containers.run(
            image_obj.id,
            detach=True,
            mem_limit=docker_config.get('memory_limit', '500m'),
            cpu_period=docker_config.get('cpu_period', 100000),
            cpu_quota=docker_config.get('cpu_quota', 50000),
            network_disabled=docker_config.get('network_disabled', True),
            read_only=docker_config.get('read_only', True),
            tmpfs={path: '' for path in docker_config.get('tmpfs', ['/tmp', '/var/tmp'])},
            user=docker_config.get('user', '1000:1000')
        )

        # Wait for the container to finish or timeout
        # For server processes, we wait a short time to capture startup logs
        server_timeout = min(self.SERVER_STARTUP_TIMEOUT, timeout)
        try:
            # Wait for the container to finish, with timeout
            exit_code = container.wait(timeout=server_timeout)
            logs = container.logs().decode('utf-8', errors='replace')

            # Get container stats
            stats = container.stats(stream=False)

            success = exit_code['StatusCode'] == 0
            error = None if success else f"Process exited with code {exit_code['StatusCode']}"

            return {
                'success': success,
                'logs': f"Build logs:\n{build_log}\n\nExecution logs:\n{logs}",
                'error': error,
                'process_output': {
                    'exit_code': exit_code['StatusCode'],
                    'logs': logs
                },
                'metrics': {
                    'memory_usage': stats.get('memory_stats', {}).get('usage', 0),
                    'cpu_usage': stats.get('cpu_stats', {}).get('cpu_usage', {}).get('total_usage', 0)
                },
                'image_tag': image_tag,
                'image_id': image_obj.id if image_obj is not None else None,
                'base_image': image,
                'startup_command': startup_cmd,
                'cache_hit': cached_used,
            }
        except Exception as e:
            # If wait times out, the server is likely still running - check logs for success indicators
            try:
                logs = container.logs().decode('utf-8', errors='replace')
                # Check if server started successfully (look for common startup messages)
                success_indicators = [
                    'running on', 'serving on', 'listening on', 'started on',
                    'server running', 'application started', 'ready on',
                    'flask app', 'express server', 'fastapi', 'uvicorn'
                ]
                server_started = any(indicator in logs.lower() for indicator in success_indicators)

                if server_started:
                    # Server started successfully - kill it and return success
                    container.kill()
                    return {
                        'success': True,
                        'logs': f"Build logs:\n{build_log}\n\nExecution logs (server started successfully, terminated after {server_timeout}s):\n{logs}",
                        'error': None,
                        'process_output': {
                            'exit_code': 0,
                            'logs': logs
                        },
                        'metrics': {},
                        'image_tag': image_tag,
                        'image_id': image_obj.id if image_obj is not None else None,
                        'base_image': image,
                        'startup_command': startup_cmd,
                        'cache_hit': cached_used,
                    }
                else:
                    # Server didn't start properly - timeout
                    container.kill()
                    raise subprocess.TimeoutExpired(f"Container execution timed out after {timeout} seconds", timeout)
            except subprocess.TimeoutExpired:
                raise
            except Exception:
                container.kill()
                raise subprocess.TimeoutExpired(f"Container execution timed out after {timeout} seconds", timeout)
        finally:
            # Clean up the container
            try:
                container.remove(force=True)
            except:
                pass

    def _execute_in_subprocess(self, repo_path: Path, project_info: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        """
        Execute the project using subprocess (less secure, for development).

        Args:
            repo_path (Path): Path to the cloned repository.
            project_info (dict): Information about the project.
            timeout (int): Maximum execution time in seconds.

        Returns:
            dict: Execution result.
        """
        language = project_info.get('language')

        # Resolve to absolute path before changing directory
        repo_path = repo_path.resolve()

        # Change to the repository directory
        original_cwd = os.getcwd()
        os.chdir(repo_path)

        try:
            # Install dependencies
            if language == 'python':
                install_cmd = ['pip', 'install', '-r', 'requirements.txt']
                # Use shell=True for the startup command to handle shell operators
                startup_cmd_str = self._get_python_startup_command(repo_path)
            elif language == 'nodejs':
                install_cmd = ['npm', 'install']
                startup_cmd_str = self._get_node_startup_command(repo_path)
            else:
                raise ValueError(f"Unsupported language for subprocess execution: {language}")

            # Install dependencies
            print("   Installing dependencies...")
            if language == 'nodejs':
                # On Windows, npm is a .cmd file - need shell=True to find it
                use_shell = (sys.platform == 'win32')
                install_result = subprocess.run(
                    install_cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,  # Give dependency installation its own timeout
                    shell=use_shell
                )
            else:
                install_result = subprocess.run(
                    install_cmd,
                    capture_output=True,
                    text=True,
                    timeout=60  # Give dependency installation its own timeout
                )

            install_logs = f"STDOUT:\n{install_result.stdout}\nSTDERR:\n{install_result.stderr}"

            if install_result.returncode != 0:
                return {
                    'success': False,
                    'logs': install_logs,
                    'error': f"Dependency installation failed with exit code {install_result.returncode}",
                    'process_output': {'install_result': install_result},
                    'metrics': {}
                }

            # Execute the startup command
            print("   Starting application...")
            try:
                # Use shell=True to handle commands with shell operators
                process = subprocess.Popen(
                    startup_cmd_str,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=True
                )

                # Extract port from startup command for health check
                port = self._extract_port_from_command(startup_cmd_str, language)
                # Only a long-running server is worth waiting on a port for;
                # a one-shot program just runs to completion.
                is_server = self.is_server_workload(repo_path, project_info, startup_cmd_str)
                if is_server:
                    print(f"   Waiting for server on port {port}...")

                # Start metrics collection in a separate thread
                import threading
                import time

                metrics_data = {'cpu_percent': 0, 'memory_mb': 0, 'peak_memory_mb': 0}
                metrics_lock = threading.Lock()
                stop_metrics = threading.Event()

                def collect_metrics():
                    """Collect CPU and memory metrics for the process and its children."""
                    try:
                        parent = psutil.Process(process.pid)
                        while not stop_metrics.is_set():
                            try:
                                # Get CPU and memory for the process tree
                                total_cpu = 0
                                total_memory = 0
                                for proc in [parent] + parent.children(recursive=True):
                                    try:
                                        total_cpu += proc.cpu_percent(interval=0.1)
                                        mem_info = proc.memory_info()
                                        total_memory += mem_info.rss  # RSS in bytes
                                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                                        pass

                                with metrics_lock:
                                    metrics_data['cpu_percent'] = max(metrics_data['cpu_percent'], total_cpu)
                                    metrics_data['memory_mb'] = max(metrics_data['memory_mb'], total_memory / (1024 * 1024))
                                    metrics_data['peak_memory_mb'] = max(metrics_data['peak_memory_mb'], total_memory / (1024 * 1024))
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                break
                            time.sleep(0.5)
                    except Exception:
                        pass

                metrics_thread = threading.Thread(target=collect_metrics, daemon=True)
                metrics_thread.start()

                # TCP Health Check - wait for server port to become available
                # (only for server workloads; skip for one-shot CLI programs).
                if is_server:
                    print(f"   Checking server health on port {port}...")
                    if self._wait_for_port('127.0.0.1', port, max_wait=self.SERVER_STARTUP_TIMEOUT):
                        print(f"   Server is healthy on port {port}")

                # Wait for the process to finish or timeout
                # For servers, we only wait a short time to capture startup
                server_timeout = min(self.SERVER_STARTUP_TIMEOUT, timeout)
                try:
                    stdout, stderr = process.communicate(timeout=server_timeout)
                    # Process finished on its own (not a server)
                    stop_metrics.set()
                    metrics_thread.join(timeout=1)

                    with metrics_lock:
                        metrics = {
                            'cpu_percent': metrics_data['cpu_percent'],
                            'memory_mb': metrics_data['memory_mb'],
                            'peak_memory_mb': metrics_data['peak_memory_mb']
                        }

                    logs = f"Installation logs:\n{install_logs}\n\nExecution logs:\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"

                    return {
                        'success': process.returncode == 0,
                        'logs': logs,
                        'error': None if process.returncode == 0 else f"Process exited with code {process.returncode}",
                        'process_output': {
                            'returncode': process.returncode,
                            'stdout': stdout,
                            'stderr': stderr
                        },
                        'metrics': metrics
                    }
                except subprocess.TimeoutExpired:
                    # Process is still running - likely a server
                    # Check if it started successfully by reading output so far
                    try:
                        stdout, stderr = process.communicate(timeout=1)
                    except subprocess.TimeoutExpired:
                        # Still running, kill it and get what output we can
                        self._kill_process_tree(process.pid)
                        stdout, stderr = process.communicate()

                    # Stop metrics collection
                    stop_metrics.set()
                    metrics_thread.join(timeout=1)

                    with metrics_lock:
                        metrics = {
                            'cpu_percent': metrics_data['cpu_percent'],
                            'memory_mb': metrics_data['memory_mb'],
                            'peak_memory_mb': metrics_data['peak_memory_mb']
                        }

                    logs = f"Installation logs:\n{install_logs}\n\nExecution logs (server started, terminated after {server_timeout}s):\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"

                    # Check for server startup success indicators
                    success_indicators = [
                        'running on', 'serving on', 'listening on', 'started on',
                        'server running', 'application started', 'ready on',
                        'flask app', 'express server', 'fastapi', 'uvicorn',
                        'running at', 'localhost', 'listening at', 'bound to',
                        'server started', 'app running', 'http server'
                    ]
                    server_started = any(indicator in (stdout + stderr).lower() for indicator in success_indicators)

                    if server_started:
                        return {
                            'success': True,
                            'logs': logs,
                            'error': None,
                            'process_output': {
                                'returncode': 0,
                                'stdout': stdout,
                                'stderr': stderr
                            },
                            'metrics': metrics
                        }
                    else:
                        raise subprocess.TimeoutExpired(f"Execution timed out after {timeout} seconds", timeout)

            except subprocess.TimeoutExpired:
                # Re-raise to be caught by the outer handler
                raise

        finally:
            # Restore original working directory
            os.chdir(original_cwd)

    def _get_python_startup_command(self, repo_path: Path) -> str:
        """
        Determine the startup command for a Python project.

        Args:
            repo_path (Path): Path to the repository.

        Returns:
            str: The startup command to use.
        """
        # Check for requirements.txt to understand dependencies
        requirements_path = repo_path / 'requirements.txt'
        requirements = []
        if requirements_path.exists():
            try:
                requirements = requirements_path.read_text().lower()
            except:
                pass

        # Check for Flask app - prefer flask run if available
        for py_file in repo_path.glob('*.py'):
            try:
                content = py_file.read_text()
                if 'app = Flask' in content or 'Flask(__name__)' in content:
                    # Check if flask is in requirements
                    if 'flask' in requirements:
                        # Use python -m flask to ensure it works regardless of PATH
                        return 'python -m flask run --host=0.0.0.0 --port=5000'
                    return f'python {py_file.name}'
            except:
                pass

        # Check for FastAPI (uvicorn) - check before generic patterns
        for py_file in repo_path.glob('*.py'):
            try:
                content = py_file.read_text()
                if 'FastAPI' in content or 'from fastapi import' in content:
                    # Check if uvicorn is available
                    if 'uvicorn' in requirements or 'fastapi' in requirements:
                        module_name = py_file.stem
                        return f'python -m uvicorn {module_name}:app --host 0.0.0.0 --port 8000'
                    return f'python {py_file.name}'
            except:
                pass

        # Check for Streamlit
        for py_file in repo_path.glob('*.py'):
            try:
                content = py_file.read_text()
                if 'import streamlit' in content or 'streamlit.' in content:
                    if 'streamlit' in requirements:
                        return f'streamlit run {py_file.name} --server.port=8501 --server.address=0.0.0.0'
                    return f'python {py_file.name}'
            except:
                pass

        # Common patterns for Python applications
        patterns = [
            ('app.py', 'python app.py'),
            ('main.py', 'python main.py'),
            ('server.py', 'python server.py'),
            ('wsgi.py', 'python wsgi.py'),
            ('manage.py', 'python manage.py runserver'),  # Django
        ]

        for filename, command in patterns:
            if (repo_path / filename).exists():
                return command

        # Check for Flask in requirements without explicit app.py
        if 'flask' in requirements:
            return 'flask run --host=0.0.0.0 --port=5000'

        # Check for Streamlit in requirements
        if 'streamlit' in requirements:
            # Try to find the main streamlit file
            for py_file in repo_path.glob('*.py'):
                try:
                    content = py_file.read_text()
                    if 'import streamlit' in content or 'streamlit.' in content:
                        return f'streamlit run {py_file.name} --server.port=8501 --server.address=0.0.0.0'
                except:
                    pass
            return 'streamlit run app.py --server.port=8501 --server.address=0.0.0.0'

        # Check for FastAPI/uvicorn in requirements
        if 'fastapi' in requirements or 'uvicorn' in requirements:
            for py_file in repo_path.glob('*.py'):
                try:
                    content = py_file.read_text()
                    if 'FastAPI' in content or 'from fastapi import' in content:
                        module_name = py_file.stem
                        return f'uvicorn {module_name}:app --host 0.0.0.0 --port 8000'
                except:
                    pass

        # Check for Django
        if 'django' in requirements and (repo_path / 'manage.py').exists():
            return 'python manage.py runserver 0.0.0.0:8000'

        # Default fallback - use single quotes to avoid Docker CMD escaping issues
        return "python -c 'print(\"No specific startup command found, checking for common patterns\"); import sys; sys.exit(0)'"

    def _get_node_startup_command(self, repo_path: Path) -> str:
        """
        Determine the startup command for a Node.js project.

        Args:
            repo_path (Path): Path to the repository.

        Returns:
            str: The startup command to use.
        """
        # Check package.json for scripts and dependencies
        package_json_path = repo_path / 'package.json'
        package_data = {}
        scripts = {}
        dependencies = {}
        dev_dependencies = {}

        if package_json_path.exists():
            try:
                import json
                with open(package_json_path, 'r') as f:
                    package_data = json.load(f)
                    scripts = package_data.get('scripts', {})
                    dependencies = package_data.get('dependencies', {})
                    dev_dependencies = package_data.get('devDependencies', {})
            except:
                pass

        all_deps = {**dependencies, **dev_dependencies}

        # Check for framework-specific commands based on dependencies first
        # Next.js
        if 'next' in all_deps:
            if 'dev' in scripts:
                return 'npm run dev'
            return 'npx next dev'

        # Vite (React, Vue, Svelte, etc.)
        if 'vite' in all_deps or 'vite' in str(scripts):
            if 'dev' in scripts:
                return 'npm run dev'
            return 'npx vite'

        # Nuxt.js
        if 'nuxt' in all_deps:
            if 'dev' in scripts:
                return 'npm run dev'
            return 'npx nuxt dev'

        # React Scripts (Create React App)
        if 'react-scripts' in all_deps:
            if 'start' in scripts:
                return 'npm start'
            return 'react-scripts start'

        # NestJS
        if '@nestjs/core' in all_deps:
            if 'start:dev' in scripts:
                return 'npm run start:dev'
            if 'start' in scripts:
                return 'npm run start'

        # Check for common startup scripts in package.json (order matters - prefer 'dev' over 'start' for dev frameworks)
        for script_name in ['dev', 'start', 'serve', 'preview']:
            if script_name in scripts:
                return f'npm run {script_name}'

        # Express with nodemon for development
        if 'express' in all_deps and 'nodemon' in all_deps:
            if 'dev' in scripts:
                return 'npm run dev'
            # Try to find entry point
            main_file = package_data.get('main', 'index.js')
            return f'npx nodemon {main_file}'

        # Plain Express
        if 'express' in all_deps:
            main_file = package_data.get('main', 'index.js')
            return f'node {main_file}'

        # Common patterns for Node.js applications
        patterns = [
            ('server.js', 'node server.js'),
            ('index.js', 'node index.js'),
            ('app.js', 'node app.js'),
            ('main.js', 'node main.js'),
        ]

        for filename, command in patterns:
            if (repo_path / filename).exists():
                return command

        # Default fallback
        return 'echo "No specific startup command found" && exit 0'

    def _kill_process_tree(self, pid: int):
        """Kill a process and its children, cross-platform."""
        try:
            if sys.platform == 'win32':
                # Use taskkill on Windows to forcefully terminate process tree
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)],
                              capture_output=True, timeout=5)
            else:
                # On Unix, kill the process group
                import signal
                os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            pass  # Best effort