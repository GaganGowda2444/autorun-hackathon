"""
Shared test fixtures and configuration.
"""

import pytest
import tempfile
import shutil
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    tmpdir = Path(tempfile.mkdtemp())
    yield tmpdir
    # Cleanup
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def sample_python_project(temp_dir):
    """Create a sample Python Flask project."""
    project_dir = temp_dir / "flask_project"
    project_dir.mkdir()

    (project_dir / "app.py").write_text("""
from flask import Flask
app = Flask(__name__)

@app.route('/')
def hello():
    return 'Hello World!'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
""")

    (project_dir / "requirements.txt").write_text("Flask>=2.0.0\n")

    return project_dir


@pytest.fixture
def sample_fastapi_project(temp_dir):
    """Create a sample FastAPI project."""
    project_dir = temp_dir / "fastapi_project"
    project_dir.mkdir()

    (project_dir / "main.py").write_text("""
from fastapi import FastAPI

app = FastAPI()

@app.get('/')
def read_root():
    return {'Hello': 'World'}

@app.get('/health')
def health():
    return {'status': 'ok'}
""")

    (project_dir / "requirements.txt").write_text("fastapi>=0.100.0\nuvicorn>=0.23.0\n")

    return project_dir


@pytest.fixture
def sample_nodejs_project(temp_dir):
    """Create a sample Node.js Express project."""
    project_dir = temp_dir / "express_project"
    project_dir.mkdir()

    (project_dir / "package.json").write_text("""{
  "name": "express-app",
  "version": "1.0.0",
  "main": "server.js",
  "scripts": {
    "start": "node server.js"
  },
  "dependencies": {
    "express": "^4.18.0"
  }
}""")

    (project_dir / "server.js").write_text("""
const express = require('express');
const app = express();
const PORT = process.env.PORT || 3000;

app.get('/', (req, res) => {
    res.send('Hello from Express!');
});

app.get('/health', (req, res) => {
    res.json({ status: 'ok' });
});

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});
""")

    return project_dir


@pytest.fixture
def sample_nextjs_project(temp_dir):
    """Create a sample Next.js project."""
    project_dir = temp_dir / "nextjs_project"
    project_dir.mkdir()

    (project_dir / "package.json").write_text("""{
  "name": "next-app",
  "version": "1.0.0",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "^13.0.0",
    "react": "^18.0.0",
    "react-dom": "^18.0.0"
  }
}""")

    return project_dir


@pytest.fixture
def sample_nestjs_project(temp_dir):
    """Create a sample NestJS project."""
    project_dir = temp_dir / "nestjs_project"
    project_dir.mkdir()

    (project_dir / "package.json").write_text("""{
  "name": "nest-app",
  "version": "1.0.0",
  "scripts": {
    "start:dev": "nest start --watch",
    "build": "nest build"
  },
  "dependencies": {
    "@nestjs/core": "^10.0.0",
    "@nestjs/common": "^10.0.0",
    "rxjs": "^7.8.0"
  }
}""")

    return project_dir


@pytest.fixture
def sample_streamlit_project(temp_dir):
    """Create a sample Streamlit project."""
    project_dir = temp_dir / "streamlit_project"
    project_dir.mkdir()

    (project_dir / "app.py").write_text("""
import streamlit as st

st.title('Hello Streamlit!')
st.write('This is a test app.')
""")

    (project_dir / "requirements.txt").write_text("streamlit>=1.25.0\n")

    return project_dir


@pytest.fixture
def mock_docker_client():
    """Create a mock Docker client."""
    from unittest.mock import MagicMock

    client = MagicMock()
    image_obj = MagicMock()
    image_obj.id = "sha256:test123"
    client.images.build.return_value = (image_obj, [{'stream': 'Step 1/3...'}])

    container = MagicMock()
    container.wait.return_value = {'StatusCode': 0}
    container.logs.return_value = b'Server running on port 5000'
    container.stats.return_value = {
        'memory_stats': {'usage': 52428800},  # 50MB
        'cpu_stats': {'cpu_usage': {'total_usage': 1000000}}
    }
    client.containers.run.return_value = container

    return client