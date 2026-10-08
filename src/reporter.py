import json
import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any


class ResultReporter:
    """Generates reports of the execution results."""

    def __init__(self):
        """Initialize the reporter."""
        pass

    def report(self, result: Dict[str, Any], output_dir: str = "./autorun-output"):
        """
        Generate and save the report.

        Args:
            result (dict): The execution result from the sandbox executor.
            output_dir (str): Directory to save the report and logs.
        """
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate timestamp for this run
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = output_path / f"run_{timestamp}"
        run_dir.mkdir(parents=True, exist_ok=True)

        # Save detailed logs
        log_file = run_dir / "execution.log"
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(result.get('logs', 'No logs available'))

        # Save structured result as JSON
        json_file = run_dir / "result.json"
        # Create a copy of result for JSON serialization (handle non-serializable items)
        json_result = {
            'success': result.get('success', False),
            'language': result.get('language'),
            'framework': result.get('framework'),
            'error': result.get('error'),
            'execution_time': result.get('execution_time', 0),
            'metrics': result.get('metrics', {}),
            'timestamp': timestamp,
            'process_output': result.get('process_output', {}),
            'cache_hit': result.get('cache_hit'),
            'cache_key': result.get('cache_key'),
        }
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_result, f, indent=2)

        # Generate human-readable summary
        summary_file = run_dir / "summary.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(self._generate_summary(result, timestamp))

        latest_dir = output_path / "latest"
        # Print summary to console
        print("\n" + "="*50)
        print("EXECUTION SUMMARY")
        print("="*50)
        print(self._generate_summary(result, timestamp))
        print("="*50)
        print(f"[DIR] Detailed results saved to: {run_dir}")
        print(f"[LINK] Latest run copy: {latest_dir}")

        # Generate HTML report
        html_file = run_dir / "report.html"
        self._generate_html_report(result, timestamp, html_file)
        print(f"[HTML] Visual report: {html_file}")

        # Also create a latest copy for easy access (after report.html exists)
        try:
            if latest_dir.exists():
                shutil.rmtree(latest_dir, ignore_errors=True)
            shutil.copytree(run_dir, latest_dir, dirs_exist_ok=True)
        except Exception as e:
            print(f"   Warning: Could not create 'latest' copy: {e}")

    def _generate_html_report(self, result: Dict[str, Any], timestamp: str, output_path: Path):
        """Generate a standalone HTML report with embedded CSS."""
        success = result.get('success', False)
        language = result.get('language', 'unknown')
        framework = result.get('framework', 'unknown')
        error = result.get('error')
        exec_time = result.get('execution_time', 0)
        metrics = result.get('metrics', {})
        process_output = result.get('process_output', {})

        # Status styling
        status_class = "success" if success else "failed"
        status_text = "SUCCESS" if success else "FAILED"
        status_icon = "✅" if success else "❌"

        # Metrics
        cpu_percent = metrics.get('cpu_percent', metrics.get('cpu_usage', 0))
        memory_mb = metrics.get('memory_mb', metrics.get('memory_usage', 0))
        if isinstance(memory_mb, (int, float)) and memory_mb > 1000:
            memory_mb = memory_mb / (1024 * 1024)
        peak_mb = metrics.get('peak_memory_mb', memory_mb)

        # Logs
        stdout = process_output.get('stdout', '')
        stderr = process_output.get('stderr', '')
        logs = process_output.get('logs', '')

        # Infer repository purpose
        purpose_html = self._infer_repository_purpose(stdout, stderr, result)

        # Escape HTML for safe embedding (only for stdout/stderr/logs)
        stdout_html = self._escape_html(stdout)
        stderr_html = self._escape_html(stderr)
        logs_html = self._escape_html(logs)

        # Metrics for HTML template
        cpu_pct = min(100, cpu_percent) if cpu_percent else 0
        mem_limit = 500  # MB
        mem_pct = min(100, (memory_mb / mem_limit) * 100) if memory_mb else 0

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Autorun Hackathon - Execution Report</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f6fa; color: #2c3e50; line-height: 1.6; padding: 20px; }}
        .container {{ max-width: 900px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #1e3a5f 0%, #007acc 100%); color: white; padding: 30px; }}
        .header h1 {{ font-size: 1.8rem; font-weight: 600; margin-bottom: 8px; }}
        .header .meta {{ opacity: 0.9; font-size: 0.9rem; }}
        .status-badge {{ display: inline-block; padding: 8px 16px; border-radius: 20px; font-weight: 600; font-size: 0.85rem; margin-top: 12px; }}
        .status-badge.success {{ background: rgba(0,184,148,0.2); color: #00b894; border: 1px solid #00b894; }}
        .status-badge.failed {{ background: rgba(231,76,60,0.2); color: #e74c3c; border: 1px solid #e74c3c; }}
        .content {{ padding: 30px; }}
        .section {{ margin-bottom: 24px; }}
        .section h2 {{ font-size: 1.1rem; font-weight: 600; color: #1e3a5f; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #e0e6ed; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; }}
        .card {{ background: #f8f9fa; border-radius: 8px; padding: 20px; border-left: 4px solid #007acc; }}
        .card h3 {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px; color: #636e72; margin-bottom: 8px; }}
        .card .value {{ font-size: 1.5rem; font-weight: 600; color: #2c3e50; }}
        .card .unit {{ font-size: 0.85rem; color: #636e72; margin-left: 4px; }}
        .progress-bar {{ height: 8px; background: #e0e6ed; border-radius: 4px; overflow: hidden; margin-top: 8px; }}
        .progress-bar .fill {{ height: 100%; border-radius: 4px; transition: width 0.3s ease; }}
        .progress-bar .fill.memory {{ background: linear-gradient(90deg, #00b894, #00cec9); }}
        .progress-bar .fill.cpu {{ background: linear-gradient(90deg, #007acc, #74b9ff); }}
        .logs {{ background: #1e1e1e; color: #d4d4d4; border-radius: 8px; padding: 20px; font-family: 'Consolas', 'Monaco', monospace; font-size: 0.85rem; max-height: 500px; overflow: auto; white-space: pre-wrap; }}
        .logs .stdout {{ color: #4ec9b0; }}
        .logs .stderr {{ color: #f14c4c; }}
        .logs .info {{ color: #9cdcfe; }}
        .purpose-list {{ background: #e8f5e9; border-radius: 8px; padding: 20px; border-left: 4px solid #00b894; }}
        .purpose-list h3 {{ color: #2e7d32; margin-bottom: 12px; }}
        .purpose-list ul {{ margin: 0; padding-left: 20px; }}
        .purpose-list li {{ margin-bottom: 8px; line-height: 1.6; }}
        .output-section {{ background: #fafafa; border-radius: 8px; padding: 20px; border: 1px solid #e0e6ed; }}
        .output-section h3 {{ color: #1e3a5f; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }}
        .output-section pre {{ background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 6px; overflow: auto; font-family: 'Consolas', 'Monaco', monospace; font-size: 0.8rem; max-height: 400px; overflow: auto; white-space: pre-wrap; }}
        .stdout-text {{ color: #4ec9b0; }}
        .stderr-text {{ color: #f14c4c; }}
        .footer {{ text-align: center; padding: 20px; color: #636e72; font-size: 0.85rem; border-top: 1px solid #e0e6ed; }}
        @media print {{ body {{ background: white; }} .container {{ box-shadow: none; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Autorun Hackathon</h1>
            <div class="meta">Execution Report • {timestamp}</div>
            <span class="status-badge {status_class}">{status_icon} {status_text}</span>
        </div>

        <div class="content">
            <div class="section">
                <h2>📋 Project Info</h2>
                <div class="grid">
                    <div class="card">
                        <h3>Language</h3>
                        <div class="value">{language.title()}</div>
                    </div>
                    <div class="card">
                        <h3>Framework</h3>
                        <div class="value">{framework.title() if framework != 'unknown' else 'N/A'}</div>
                    </div>
                    <div class="card">
                        <h3>Cache</h3>
                        <div class="value">{'HIT' if result.get('cache_hit') else ('MISS' if 'cache_hit' in result else 'N/A')}</div>
                    </div>
                    <div class="card">
                        <h3>Execution Time</h3>
                        <div class="value">{exec_time:.2f}<span class="unit">s</span></div>
                    </div>
                    <div class="card">
                        <h3>Timestamp</h3>
                        <div class="value" style="font-size: 0.9rem;">{timestamp}</div>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2>📊 Resource Metrics</h2>
                <div class="grid">
                    <div class="card">
                        <h3>CPU Usage</h3>
                        <div class="value">{cpu_pct:.1f}<span class="unit">%</span></div>
                        <div class="progress-bar"><div class="fill cpu" style="width: {cpu_pct}%"></div></div>
                    </div>
                    <div class="card">
                        <h3>Memory Used</h3>
                        <div class="value">{memory_mb:.1f}<span class="unit">MB</span></div>
                        <div class="progress-bar"><div class="fill memory" style="width: {mem_pct}%"></div></div>
                        <div style="font-size: 0.75rem; color: #636e72; margin-top: 4px;">Limit: {mem_limit} MB</div>
                    </div>
                    <div class="card">
                        <h3>Peak Memory</h3>
                        <div class="value">{peak_mb:.1f}<span class="unit">MB</span></div>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2>🎯 Repository Purpose (Inferred from Output)</h2>
                <div class="purpose-list">
                    <h3>🔍 What This Repository Does</h3>
                    {purpose_html}
                </div>
            </div>

            {f'<div class="section"><h2>❌ Error Details</h2><div class="card" style="border-left-color: #e74c3c; background: #fdf2f2;"><div class="value" style="font-size: 0.9rem; color: #e74c3c;">{self._escape_html(error)}</div></div></div>' if error else ''}

            <div class="section">
                <h2>📝 Application Output</h2>
                <div class="output-section">
                    <h3>📤 STDOUT (Standard Output)</h3>
                    <pre class="stdout-text">{stdout_html if stdout_html.strip() else ''}</pre>
                </div>
                <div class="output-section">
                    <h3>📥 STDERR (Standard Error)</h3>
                    <pre class="stderr-text">{stderr_html if stderr_html.strip() else ''}</pre>
                </div>
            </div>

            <div class="section">
                <h2>📋 Full Execution Logs</h2>
                <div class="logs">
                    {self._format_logs_for_html(stdout, stderr, logs)}
                </div>
            </div>
        </div>

        <div class="footer">
            Generated by <strong>Autorun Hackathon</strong> — Sandboxed Intelligent Repository Execution Engine<br>
            <a href="https://github.com/yourusername/autorun-hackathon" style="color: #007acc;">GitHub Repository</a>
        </div>
    </div>
</body>
</html>"""

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

    def _infer_repository_purpose(self, stdout: str, stderr: str, result: dict) -> str:
        """Infer what the repository's application does based on its output."""
        combined = (stdout + stderr).lower()
        language = result.get('language', 'unknown')
        framework = result.get('framework', 'unknown')

        purposes = []

        # Web server indicators
        if any(kw in combined for kw in ['running on', 'listening on', 'serving on', 'started on', 'running at', 'server running']):
            port = None
            port_match = re.search(r'[: ](\d{3,5})', combined)
            if port_match:
                port = port_match.group(1)
            purposes.append(f"🌐 <strong>Web Server</strong> - Starts a web server" + (f" on port {port}" if port else ""))

        # Framework-specific
        if framework == 'flask' or 'flask' in combined:
            purposes.append("🐍 <strong>Flask Web Application</strong> - Python micro-framework")
        elif framework == 'django':
            purposes.append("🐍 <strong>Django Web Application</strong> - Python full-stack framework")
        elif framework == 'fastapi':
            purposes.append("🐍 <strong>FastAPI Application</strong> - Modern Python API framework")
        elif framework == 'express':
            purposes.append("🟢 <strong>Express.js Application</strong> - Node.js web framework")
        elif framework == 'react' or 'react' in combined:
            purposes.append("⚛️ <strong>React Application</strong> - Frontend UI library")
        elif framework == 'next.js' or 'next' in combined:
            purposes.append("▲ <strong>Next.js Application</strong> - React full-stack framework")
        elif framework == 'streamlit':
            purposes.append("📊 <strong>Streamlit App</strong> - Data science web app")

        # API indicators
        if any(kw in combined for kw in ['api', 'rest', 'endpoint', 'route', 'json']):
            purposes.append("🔌 <strong>API Service</strong> - Provides REST/JSON endpoints")

        # Static file serving
        if 'static' in combined or 'express.static' in combined:
            purposes.append("📁 <strong>Static File Server</strong> - Serves HTML/CSS/JS files")

        # Database
        if any(kw in combined for kw in ['database', 'sqlite', 'postgres', 'mysql', 'mongodb', 'redis']):
            purposes.append("🗄️ <strong>Database Connected</strong> - Uses database storage")

        # Auth
        if any(kw in combined for kw in ['auth', 'login', 'jwt', 'token', 'session', 'cookie']):
            purposes.append("🔐 <strong>Authentication</strong> - Has user authentication")

        # WebSocket
        if 'websocket' in combined or 'socket.io' in combined:
            purposes.append("🔌 <strong>Real-time/WebSocket</strong> - Real-time communication")

        # Background jobs
        if any(kw in combined for kw in ['celery', 'worker', 'queue', 'cron', 'scheduler']):
            purposes.append("⚙️ <strong>Background Workers</strong> - Async task processing")

        # Testing
        if any(kw in combined for kw in ['test', 'pytest', 'jest', 'mocha', 'coverage']):
            purposes.append("🧪 <strong>Test Suite</strong> - Runs automated tests")

        # Build/Compile
        if any(kw in combined for kw in ['build', 'compile', 'webpack', 'vite', 'bundl']):
            purposes.append("🔨 <strong>Build Process</strong> - Compiles/bundles assets")

        if not purposes:
            if result.get('success'):
                purposes.append("✅ <strong>Application Runs Successfully</strong> - No specific purpose inferred")
            else:
                purposes.append("❌ <strong>Application Failed to Start</strong> - Check logs for errors")

        # Convert to HTML list
        html_items = ''.join(f'<li>{p}</li>' for p in purposes)
        return f'<ul>{html_items}</ul>'

    def _format_logs_for_html(self, stdout: str, stderr: str, logs: str) -> str:
        """Format logs for HTML display with syntax highlighting."""
        parts = []
        if logs:
            for line in logs.strip().split('\n'):
                cls = 'info'
                if 'error' in line.lower() or 'fail' in line.lower():
                    cls = 'stderr'
                elif 'warning' in line.lower() or 'warn' in line.lower():
                    cls = 'stderr'
                parts.append(f'<div class="{cls}">{self._escape_html(line)}</div>')
        if stdout:
            parts.append('<div class="stdout">--- STDOUT ---</div>')
            for line in stdout.strip().split('\n'):
                parts.append(f'<div class="stdout">{self._escape_html(line)}</div>')
        if stderr:
            parts.append('<div class="stderr">--- STDERR ---</div>')
            for line in stderr.strip().split('\n'):
                parts.append(f'<div class="stderr">{self._escape_html(line)}</div>')
        return '\n'.join(parts) if parts else '<div class="info">No output captured</div>'

    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters."""
        import html
        return html.escape(text)

    def _generate_summary(self, result: Dict[str, Any], timestamp: str) -> str:
        """
        Generate a human-readable summary of the result.

        Args:
            result (dict): The execution result.
            timestamp (str): Timestamp of the run.

        Returns:
            str: Formatted summary string.
        """
        lines = []
        lines.append(f"Timestamp: {timestamp}")
        lines.append(f"Language: {result.get('language', 'unknown')}")
        lines.append(f"Framework: {result.get('framework', 'unknown')}")
        lines.append(f"Success: {'YES' if result.get('success', False) else 'NO'}")
        lines.append(f"Execution Time: {result.get('execution_time', 0):.2f} seconds")

        if result.get('served'):
            lines.append(f"Mode: LIVE (served)")
            if result.get('url'):
                lines.append(f"URL: {result['url']}")
            lines.append(f"Health check: {'PASSED' if result.get('healthy') else 'not confirmed'}")

        if 'cache_hit' in result:
            lines.append(f"Cache: {'HIT' if result.get('cache_hit') else 'MISS'}")
        if result.get('cache_key'):
            lines.append(f"Cache Key: {result['cache_key']}")

        if result.get('error'):
            lines.append(f"Error: {result.get('error')}")

        # Show metrics if available
        metrics = result.get('metrics', {})
        if metrics:
            lines.append("\nResource Usage:")
            # Docker metrics format (memory_usage in bytes, cpu_usage in units)
            if 'memory_usage' in metrics:
                mb_used = metrics['memory_usage'] / (1024 * 1024) if metrics['memory_usage'] else 0
                lines.append(f"  Memory: {mb_used:.2f} MB")
            if 'cpu_usage' in metrics:
                lines.append(f"  CPU Usage: {metrics['cpu_usage']} units")
            # Subprocess metrics format (cpu_percent, memory_mb, peak_memory_mb)
            if 'cpu_percent' in metrics:
                lines.append(f"  CPU: {metrics['cpu_percent']:.1f}%")
            if 'memory_mb' in metrics:
                lines.append(f"  Memory: {metrics['memory_mb']:.2f} MB")
            if 'peak_memory_mb' in metrics:
                lines.append(f"  Peak Memory: {metrics['peak_memory_mb']:.2f} MB")

        # Show process output hints
        process_output = result.get('process_output', {})
        if process_output:
            lines.append("\nProcess Output Available:")
            if 'logs' in process_output:
                log_lines = process_output['logs'].strip().split('\n')
                lines.append(f"  Logs: {len(log_lines)} lines captured")
            if 'stdout' in process_output and process_output['stdout']:
                stdout_preview = process_output['stdout'].replace('\n', ' ')
                lines.append(f"  STDOUT: {stdout_preview}")
            if 'stderr' in process_output and process_output['stderr']:
                stderr_preview = process_output['stderr'].replace('\n', ' ')
                lines.append(f"  STDERR: {stderr_preview}")

        return '\n'.join(lines)