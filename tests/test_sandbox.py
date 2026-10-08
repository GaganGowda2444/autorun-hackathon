"""
Tests for the sandbox module.
"""

import os
import sys
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from sandbox import SandboxExecutor


class TestSandboxExecutor:
    """Tests for SandboxExecutor class."""

    def test_init_without_docker(self):
        """Test initialization when Docker is not available."""
        with patch('sandbox.docker') as mock_docker:
            mock_docker.from_env.side_effect = Exception("Docker not available")

            executor = SandboxExecutor()

            assert executor.docker_client is None

    def test_init_with_autorun_no_docker_env(self):
        """Test initialization with AUTORUN_NO_DOCKER env var."""
        with patch.dict(os.environ, {'AUTORUN_NO_DOCKER': '1'}):
            with patch('sandbox.docker') as mock_docker:
                executor = SandboxExecutor()

                assert executor.docker_client is None
                # docker.from_env should not be called
                mock_docker.from_env.assert_not_called()

    def test_execute_subprocess_success(self, sample_python_project):
        """Test subprocess execution success."""
        executor = SandboxExecutor()
        executor.docker_client = None  # Force subprocess mode

        project_info = {
            'language': 'python',
            'framework': 'flask'
        }

        # Mock the subprocess to return success
        with patch('sandbox.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='Successfully installed flask',
                stderr=''
            )

            with patch('sandbox.subprocess.Popen') as mock_popen:
                mock_process = MagicMock()
                mock_process.communicate.return_value = (
                    ' * Serving Flask app\n * Running on http://0.0.0.0:5000',
                    ''
                )
                mock_process.returncode = 0
                mock_popen.return_value = mock_process

                result = executor.execute(sample_python_project, project_info, timeout=30)

                assert result['success'] is True
                assert result['language'] == 'python'
                assert 'Serving Flask app' in result['logs']

    def test_execute_dependency_install_failure(self, sample_python_project):
        """Test execution when dependency installation fails."""
        executor = SandboxExecutor()
        executor.docker_client = None

        project_info = {'language': 'python', 'framework': 'flask'}

        with patch('sandbox.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout='',
                stderr='ERROR: Could not find a version that satisfies the requirement'
            )

            result = executor.execute(sample_python_project, project_info, timeout=30)

            assert result['success'] is False
            assert 'Dependency installation failed' in result['error']

    def test_execute_timeout_handling(self, sample_python_project):
        """Test handling of execution timeout."""
        executor = SandboxExecutor()
        executor.docker_client = None

        project_info = {'language': 'python', 'framework': 'flask'}

        with patch('sandbox.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')

            with patch('sandbox.subprocess.Popen') as mock_popen:
                mock_process = MagicMock()
                import subprocess
                # First communicate(timeout=server_timeout) raises, then communicate(timeout=1) also raises
                mock_process.communicate.side_effect = [
                    subprocess.TimeoutExpired("cmd", 10),
                    subprocess.TimeoutExpired("cmd", 1),
                    ('partial output', '')
                ]
                mock_process.pid = 12345
                mock_popen.return_value = mock_process

                with patch.object(executor, '_kill_process_tree') as mock_kill:
                    result = executor.execute(sample_python_project, project_info, timeout=5)

                    # Should handle timeout
                    mock_kill.assert_called_once_with(12345)

    def test_get_python_startup_command_flask(self, sample_python_project):
        """Test getting Flask startup command."""
        executor = SandboxExecutor()
        cmd = executor._get_python_startup_command(sample_python_project)

        # Should prefer flask run when flask is in requirements
        assert 'flask run' in cmd or 'python app.py' in cmd

    def test_get_python_startup_command_fastapi(self, sample_fastapi_project):
        """Test getting FastAPI startup command."""
        executor = SandboxExecutor()
        cmd = executor._get_python_startup_command(sample_fastapi_project)

        assert 'uvicorn' in cmd
        assert 'main:app' in cmd

    def test_get_python_startup_command_streamlit(self, sample_streamlit_project):
        """Test getting Streamlit startup command."""
        executor = SandboxExecutor()
        cmd = executor._get_python_startup_command(sample_streamlit_project)

        assert 'streamlit run' in cmd

    def test_get_node_startup_command_express(self, sample_nodejs_project):
        """Test getting Express startup command."""
        executor = SandboxExecutor()
        cmd = executor._get_node_startup_command(sample_nodejs_project)

        assert 'npm run start' in cmd or 'node server.js' in cmd

    def test_get_node_startup_command_nextjs(self, sample_nextjs_project):
        """Test getting Next.js startup command."""
        executor = SandboxExecutor()
        cmd = executor._get_node_startup_command(sample_nextjs_project)

        assert 'next dev' in cmd or 'npm run dev' in cmd

    def test_get_node_startup_command_nestjs(self, sample_nestjs_project):
        """Test getting NestJS startup command."""
        executor = SandboxExecutor()
        cmd = executor._get_node_startup_command(sample_nestjs_project)

        assert 'start:dev' in cmd or 'nest start' in cmd

    def test_kill_process_tree_windows(self):
        """Test process tree killing on Windows."""
        executor = SandboxExecutor()

        with patch('sys.platform', 'win32'):
            with patch('sandbox.subprocess.run') as mock_run:
                executor._kill_process_tree(12345)

                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                assert args[0] == 'taskkill'
                assert '/F' in args
                assert '/T' in args
                assert '/PID' in args
                assert '12345' in args

    def test_kill_process_tree_unix(self):
        """Test process tree killing on Unix."""
        import sys
        if sys.platform == 'win32':
            pytest.skip("Unix-specific test")

        executor = SandboxExecutor()

        with patch('os.killpg') as mock_killpg:
            with patch('os.getpgid', return_value=12345):
                executor._kill_process_tree(12345)

                mock_killpg.assert_called_once_with(12345, 9)  # SIGKILL = 9

    def test_execute_with_docker(self, sample_python_project, mock_docker_client):
        """Test Docker execution path."""
        pytest.skip("Docker tests require complex mocking - skipped for now")

    def test_execute_docker_container_kill_on_timeout(self, sample_python_project, mock_docker_client):
        """Test Docker container is killed on timeout."""
        pytest.skip("Docker tests require complex mocking - skipped for now")

    def test_execute_docker_checks_success_indicators(self, sample_python_project, mock_docker_client):
        """Test Docker execution checks for success indicators in logs."""
        pytest.skip("Docker tests require complex mocking - skipped for now")

    # --- Live serve mode: workload classification & dispatch ---------------

    def test_is_server_workload_flask(self, sample_python_project):
        """A Flask project is classified as a long-running server."""
        executor = SandboxExecutor()
        assert executor.is_server_workload(
            sample_python_project, {'language': 'python', 'framework': 'flask'}) is True

    def test_is_server_workload_fastapi(self, sample_fastapi_project):
        """A FastAPI project is classified as a server (via command markers)."""
        executor = SandboxExecutor()
        assert executor.is_server_workload(
            sample_fastapi_project, {'language': 'python', 'framework': 'fastapi'}) is True

    def test_is_server_workload_nextjs(self, sample_nextjs_project):
        """A Next.js project is classified as a server."""
        executor = SandboxExecutor()
        assert executor.is_server_workload(
            sample_nextjs_project, {'language': 'nodejs', 'framework': 'next'}) is True

    def test_is_server_workload_cli_is_false(self, sample_cli_project):
        """A plain one-shot CLI program is NOT classified as a server."""
        executor = SandboxExecutor()
        assert executor.is_server_workload(
            sample_cli_project, {'language': 'python', 'framework': 'unknown'}) is False

    def test_get_startup_command_returns_string(self, sample_python_project):
        """get_startup_command returns a non-empty command string."""
        executor = SandboxExecutor()
        cmd = executor.get_startup_command(
            sample_python_project, {'language': 'python', 'framework': 'flask'})
        assert isinstance(cmd, str) and cmd

    def test_find_free_port_returns_int(self):
        """_find_free_port returns a usable port number."""
        executor = SandboxExecutor()
        port = executor._find_free_port(5000)
        assert isinstance(port, int) and 1 <= port <= 65535

    def test_serve_dispatches_to_subprocess_without_docker(self, sample_python_project):
        """serve() uses the subprocess path when Docker is unavailable."""
        executor = SandboxExecutor()
        executor.docker_client = None
        project_info = {'language': 'python', 'framework': 'flask'}

        with patch.object(executor, '_serve_in_subprocess') as mock_serve:
            mock_serve.return_value = {
                'success': True, 'logs': '', 'url': 'http://localhost:5000',
                'healthy': True, 'served': True,
            }
            result = executor.serve(sample_python_project, project_info, host_port=5000)

            mock_serve.assert_called_once()
            assert result['served'] is True
            assert result['url'] == 'http://localhost:5000'
            assert result['success'] is True

    def test_serve_dispatches_to_docker_when_available(self, sample_python_project):
        """serve() uses the Docker path when a Docker client is present."""
        executor = SandboxExecutor()
        executor.docker_client = MagicMock()
        project_info = {'language': 'python', 'framework': 'flask'}

        with patch.object(executor, '_serve_in_docker') as mock_serve:
            mock_serve.return_value = {
                'success': True, 'logs': '', 'url': 'http://localhost:5000',
                'healthy': True, 'served': True,
            }
            result = executor.serve(sample_python_project, project_info)

            mock_serve.assert_called_once()
            assert result['served'] is True

    def test_metrics_collection_subprocess(self, sample_python_project):
        """Test that metrics are collected during subprocess execution."""
        executor = SandboxExecutor()
        executor.docker_client = None

        project_info = {'language': 'python', 'framework': 'flask'}

        with patch('sandbox.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')

            with patch('sandbox.subprocess.Popen') as mock_popen:
                mock_process = MagicMock()
                mock_process.pid = 12345
                mock_process.communicate.return_value = ('output', '')
                mock_process.returncode = 0
                mock_popen.return_value = mock_process

                with patch('sandbox.psutil.Process') as mock_process_class:
                    mock_proc_instance = MagicMock()
                    mock_proc_instance.cpu_percent.return_value = 15.5
                    mock_proc_instance.memory_info.return_value = MagicMock(rss=50000000)
                    mock_proc_instance.children.return_value = []
                    mock_process_class.return_value = mock_proc_instance

                    result = executor.execute(sample_python_project, project_info, timeout=30)

                    assert 'metrics' in result
                    assert 'cpu_percent' in result['metrics']
                    assert 'memory_mb' in result['metrics']
                    assert 'peak_memory_mb' in result['metrics']