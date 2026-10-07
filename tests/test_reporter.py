"""
Tests for the reporter module.
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from reporter import ResultReporter


class TestResultReporter:
    """Tests for ResultReporter class."""

    def test_report_creates_output_directory(self, temp_dir):
        """Test that report creates output directory."""
        reporter = ResultReporter()
        result = {
            'success': True,
            'language': 'python',
            'framework': 'flask',
            'execution_time': 10.5,
            'metrics': {},
            'logs': 'Test logs'
        }

        output_dir = temp_dir / "test_output"
        reporter.report(result, str(output_dir))

        assert output_dir.exists()
        # Should have a run_* directory
        run_dirs = list(output_dir.glob("run_*"))
        assert len(run_dirs) == 1

    def test_report_creates_execution_log(self, temp_dir):
        """Test that execution.log is created."""
        reporter = ResultReporter()
        result = {
            'success': True,
            'language': 'python',
            'framework': 'flask',
            'execution_time': 10.5,
            'metrics': {},
            'logs': 'Test log content'
        }

        output_dir = temp_dir / "test_output"
        reporter.report(result, str(output_dir))

        run_dir = list(output_dir.glob("run_*"))[0]
        log_file = run_dir / "execution.log"
        assert log_file.exists()
        assert log_file.read_text() == 'Test log content'

    def test_report_creates_result_json(self, temp_dir):
        """Test that result.json is created with correct content."""
        reporter = ResultReporter()
        result = {
            'success': True,
            'language': 'python',
            'framework': 'flask',
            'execution_time': 10.5,
            'metrics': {'cpu_percent': 15.0, 'memory_mb': 50.0},
            'logs': 'Test logs',
            'error': None
        }

        output_dir = temp_dir / "test_output"
        reporter.report(result, str(output_dir))

        run_dir = list(output_dir.glob("run_*"))[0]
        json_file = run_dir / "result.json"
        assert json_file.exists()

        with open(json_file) as f:
            json_result = json.load(f)

        assert json_result['success'] is True
        assert json_result['language'] == 'python'
        assert json_result['framework'] == 'flask'
        assert json_result['execution_time'] == 10.5
        assert json_result['metrics']['cpu_percent'] == 15.0

    def test_report_creates_summary_txt(self, temp_dir):
        """Test that summary.txt is created."""
        reporter = ResultReporter()
        result = {
            'success': True,
            'language': 'python',
            'framework': 'flask',
            'execution_time': 10.5,
            'metrics': {'cpu_percent': 15.0, 'memory_mb': 50.0},
            'logs': 'Test logs',
            'error': None
        }

        output_dir = temp_dir / "test_output"
        reporter.report(result, str(output_dir))

        run_dir = list(output_dir.glob("run_*"))[0]
        summary_file = run_dir / "summary.txt"
        assert summary_file.exists()

        content = summary_file.read_text()
        assert 'Timestamp:' in content
        assert 'Language: python' in content
        assert 'Framework: flask' in content
        assert 'Success: YES' in content
        assert 'Execution Time: 10.50 seconds' in content

    def test_report_creates_latest_copy(self, temp_dir):
        """Test that latest directory is created."""
        reporter = ResultReporter()
        result = {
            'success': True,
            'language': 'python',
            'framework': 'flask',
            'execution_time': 10.5,
            'metrics': {},
            'logs': 'Test logs'
        }

        output_dir = temp_dir / "test_output"
        reporter.report(result, str(output_dir))

        latest_dir = output_dir / "latest"
        assert latest_dir.exists()
        assert (latest_dir / "execution.log").exists()
        assert (latest_dir / "result.json").exists()

    def test_report_handles_error_result(self, temp_dir):
        """Test reporting a failed execution."""
        reporter = ResultReporter()
        result = {
            'success': False,
            'language': 'python',
            'framework': 'flask',
            'execution_time': 5.0,
            'metrics': {},
            'logs': 'Error logs',
            'error': 'Execution timed out'
        }

        output_dir = temp_dir / "test_output"
        reporter.report(result, str(output_dir))

        run_dir = list(output_dir.glob("run_*"))[0]
        summary_file = run_dir / "summary.txt"
        content = summary_file.read_text()

        assert 'Success: NO' in content
        assert 'Error: Execution timed out' in content

    def test_report_handles_docker_metrics_format(self, temp_dir):
        """Test reporting with Docker metrics format (memory_usage in bytes)."""
        reporter = ResultReporter()
        result = {
            'success': True,
            'language': 'python',
            'framework': 'flask',
            'execution_time': 10.5,
            'metrics': {
                'memory_usage': 52428800,  # 50MB in bytes
                'cpu_usage': 1000000
            },
            'logs': 'Test logs'
        }

        output_dir = temp_dir / "test_output"
        reporter.report(result, str(output_dir))

        run_dir = list(output_dir.glob("run_*"))[0]
        summary_file = run_dir / "summary.txt"
        content = summary_file.read_text()

        assert 'Memory: 50.00 MB' in content
        assert 'CPU Usage: 1000000 units' in content

    def test_report_handles_subprocess_metrics_format(self, temp_dir):
        """Test reporting with subprocess metrics format."""
        reporter = ResultReporter()
        result = {
            'success': True,
            'language': 'python',
            'framework': 'flask',
            'execution_time': 10.5,
            'metrics': {
                'cpu_percent': 15.5,
                'memory_mb': 47.5,
                'peak_memory_mb': 48.0
            },
            'logs': 'Test logs'
        }

        output_dir = temp_dir / "test_output"
        reporter.report(result, str(output_dir))

        run_dir = list(output_dir.glob("run_*"))[0]
        summary_file = run_dir / "summary.txt"
        content = summary_file.read_text()

        assert 'CPU: 15.5%' in content
        assert 'Memory: 47.50 MB' in content
        assert 'Peak Memory: 48.00 MB' in content

    def test_generate_summary_with_process_output(self, temp_dir):
        """Test summary generation with process output."""
        reporter = ResultReporter()
        result = {
            'success': True,
            'language': 'nodejs',
            'framework': 'express',
            'execution_time': 12.3,
            'metrics': {},
            'logs': 'Test logs',
            'process_output': {
                'stdout': 'Server running on port 3000',
                'stderr': 'Warning: deprecated API'
            }
        }

        output_dir = temp_dir / "test_output"
        reporter.report(result, str(output_dir))

        run_dir = list(output_dir.glob("run_*"))[0]
        summary_file = run_dir / "summary.txt"
        content = summary_file.read_text()

        assert 'STDOUT:' in content
        assert 'STDERR:' in content