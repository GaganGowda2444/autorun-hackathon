"""
Tests for the detector module.
"""

import sys
import tempfile
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from detector import LanguageDetector


class TestLanguageDetector:
    """Tests for LanguageDetector class."""

    def test_detect_python_flask(self, sample_python_project):
        """Test detection of Python Flask project."""
        detector = LanguageDetector()
        result = detector.detect(sample_python_project)

        assert result['language'] == 'python'
        assert result['framework'] == 'flask'
        assert result['confidence'] > 0.5

    def test_detect_nodejs_express(self, sample_nodejs_project):
        """Test detection of Node.js Express project."""
        detector = LanguageDetector()
        result = detector.detect(sample_nodejs_project)

        assert result['language'] == 'nodejs'
        assert result['framework'] == 'express'
        assert result['confidence'] > 0.5

    def test_detect_fastapi(self, sample_fastapi_project):
        """Test detection of FastAPI project."""
        detector = LanguageDetector()
        result = detector.detect(sample_fastapi_project)

        assert result['language'] == 'python'
        assert result['framework'] == 'fastapi'
        assert result['confidence'] > 0.5

    def test_detect_nextjs(self, sample_nextjs_project):
        """Test detection of Next.js project."""
        detector = LanguageDetector()
        result = detector.detect(sample_nextjs_project)

        assert result['language'] == 'nodejs'
        assert result['framework'] == 'next'
        assert result['confidence'] > 0.5

    def test_detect_nestjs(self, sample_nestjs_project):
        """Test detection of NestJS project."""
        detector = LanguageDetector()
        result = detector.detect(sample_nestjs_project)

        assert result['language'] == 'nodejs'
        assert result['framework'] == 'nest'
        assert result['confidence'] > 0.5

    def test_detect_streamlit(self, sample_streamlit_project):
        """Test detection of Streamlit project."""
        detector = LanguageDetector()
        result = detector.detect(sample_streamlit_project)

        assert result['language'] == 'python'
        assert result['framework'] == 'streamlit'
        assert result['confidence'] > 0.5

    def test_detect_python_without_framework(self, temp_dir):
        """Test detection of Python project without specific framework."""
        project_dir = temp_dir / "generic_python"
        project_dir.mkdir()
        (project_dir / "requirements.txt").write_text("requests>=2.28.0\n")
        (project_dir / "script.py").write_text("print('hello')\n")

        detector = LanguageDetector()
        result = detector.detect(project_dir)

        assert result['language'] == 'python'
        # Framework might be 'unknown' or None
        assert result['confidence'] > 0

    def test_detect_nodejs_without_framework(self, temp_dir):
        """Test detection of Node.js project without specific framework."""
        project_dir = temp_dir / "generic_nodejs"
        project_dir.mkdir()
        (project_dir / "package.json").write_text("""{
  "name": "test",
  "version": "1.0.0",
  "dependencies": {
    "lodash": "^4.17.21"
  }
}""")
        (project_dir / "index.js").write_text("console.log('hello');\n")

        detector = LanguageDetector()
        result = detector.detect(project_dir)

        assert result['language'] == 'nodejs'
        assert result['confidence'] > 0

    def test_detect_unknown_language(self, temp_dir):
        """Test detection of unknown language."""
        project_dir = temp_dir / "unknown"
        project_dir.mkdir()
        (project_dir / "README.md").write_text("# Test Project\n")

        detector = LanguageDetector()
        result = detector.detect(project_dir)

        # Should detect unknown or infer from extensions
        assert result['language'] in ('unknown', 'python', 'nodejs')

    def test_detect_priority_python_over_nodejs(self, temp_dir):
        """Test that Python is detected when both requirements.txt and package.json exist."""
        project_dir = temp_dir / "mixed"
        project_dir.mkdir()
        (project_dir / "requirements.txt").write_text("flask\n")
        (project_dir / "package.json").write_text('{"name": "test"}')
        (project_dir / "app.py").write_text("print('hello')\n")

        detector = LanguageDetector()
        result = detector.detect(project_dir)

        # Python should win due to more indicator files
        assert result['language'] == 'python'

    def test_detect_vue_project(self, temp_dir):
        """Test detection of Vue.js project."""
        project_dir = temp_dir / "vue_project"
        project_dir.mkdir()
        (project_dir / "package.json").write_text("""{
  "name": "vue-app",
  "dependencies": {
    "vue": "^3.0.0"
  }
}""")

        detector = LanguageDetector()
        result = detector.detect(project_dir)

        assert result['language'] == 'nodejs'
        assert result['framework'] == 'vue'

    def test_detect_react_project(self, temp_dir):
        """Test detection of React project."""
        project_dir = temp_dir / "react_project"
        project_dir.mkdir()
        (project_dir / "package.json").write_text("""{
  "name": "react-app",
  "dependencies": {
    "react": "^18.0.0",
    "react-dom": "^18.0.0"
  }
}""")

        detector = LanguageDetector()
        result = detector.detect(project_dir)

        assert result['language'] == 'nodejs'
        assert result['framework'] == 'react'

    def test_detect_angular_project(self, temp_dir):
        """Test detection of Angular project."""
        project_dir = temp_dir / "angular_project"
        project_dir.mkdir()
        (project_dir / "package.json").write_text("""{
  "name": "angular-app",
  "dependencies": {
    "@angular/core": "^16.0.0"
  }
}""")

        detector = LanguageDetector()
        result = detector.detect(project_dir)

        assert result['language'] == 'nodejs'
        assert result['framework'] == 'angular'

    def test_detect_svelte_project(self, temp_dir):
        """Test detection of Svelte project."""
        project_dir = temp_dir / "svelte_project"
        project_dir.mkdir()
        (project_dir / "package.json").write_text("""{
  "name": "svelte-app",
  "dependencies": {
    "svelte": "^4.0.0"
  }
}""")

        detector = LanguageDetector()
        result = detector.detect(project_dir)

        assert result['language'] == 'nodejs'
        assert result['framework'] == 'svelte'

    def test_get_dependencies_python_requirements(self, temp_dir):
        """Test extracting Python dependencies from requirements.txt."""
        project_dir = temp_dir / "test_deps"
        project_dir.mkdir()
        (project_dir / "requirements.txt").write_text("""
flask==2.3.0
requests>=2.28.0
# This is a comment
numpy
""")

        detector = LanguageDetector()
        deps = detector._get_dependencies(project_dir, 'python')

        assert 'flask' in deps
        assert 'requests' in deps
        assert 'numpy' in deps

    def test_get_dependencies_nodejs_package_json(self, temp_dir):
        """Test extracting Node.js dependencies from package.json."""
        project_dir = temp_dir / "test_deps_node"
        project_dir.mkdir()
        (project_dir / "package.json").write_text("""{
  "dependencies": {
    "express": "^4.18.0",
    "lodash": "^4.17.21"
  },
  "devDependencies": {
    "jest": "^29.0.0"
  }
}""")

        detector = LanguageDetector()
        deps = detector._get_dependencies(project_dir, 'nodejs')

        assert 'express' in deps
        assert 'lodash' in deps
        assert 'jest' in deps

    def test_infer_from_extensions_python(self, temp_dir):
        """Test language inference from Python file extensions."""
        project_dir = temp_dir / "ext_test"
        project_dir.mkdir()
        (project_dir / "main.py").write_text("print('hello')\n")
        (project_dir / "utils.py").write_text("def helper(): pass\n")
        (project_dir / "test.txt").write_text("text file\n")

        detector = LanguageDetector()
        result = {'language': 'unknown', 'confidence': 0.0, 'details': {}}
        result = detector._infer_from_extensions(project_dir, result)

        assert result['language'] == 'python'
        assert result['confidence'] <= 0.6  # Capped at 0.6 for inference
        assert result['details'].get('inferred_from_extensions') is True

    def test_infer_from_extensions_nodejs(self, temp_dir):
        """Test language inference from Node.js file extensions."""
        project_dir = temp_dir / "ext_test_node"
        project_dir.mkdir()
        (project_dir / "index.js").write_text("console.log('hello');\n")
        (project_dir / "app.ts").write_text("const x: number = 1;\n")

        detector = LanguageDetector()
        result = {'language': 'unknown', 'confidence': 0.0, 'details': {}}
        result = detector._infer_from_extensions(project_dir, result)

        assert result['language'] == 'nodejs'
        assert result['confidence'] <= 0.6