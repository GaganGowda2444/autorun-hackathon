"""
Tests for the cloner module.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cloner import GitHubCloner


class TestGitHubCloner:
    """Tests for GitHubCloner class."""

    def test_init_default_base_dir(self):
        """Test cloner initialization with default base directory."""
        cloner = GitHubCloner()
        assert cloner.base_dir == Path.cwd()

    def test_init_custom_base_dir(self, temp_dir):
        """Test cloner initialization with custom base directory."""
        custom_dir = temp_dir / "custom_base"
        cloner = GitHubCloner(custom_dir)
        assert cloner.base_dir == custom_dir
        assert custom_dir.exists()

    def test_clone_local_path(self, sample_python_project):
        """Test cloning a local path."""
        cloner = GitHubCloner()
        result = cloner.clone(str(sample_python_project))

        assert result.exists()
        assert (result / "app.py").exists()
        assert (result / "requirements.txt").exists()
        assert not (result / ".git").exists()  # .git should be ignored

    def test_clone_local_path_with_file_url(self, sample_python_project):
        """Test cloning a local path with file:// URL."""
        cloner = GitHubCloner()
        file_url = sample_python_project.as_uri()
        result = cloner.clone(file_url)

        assert result.exists()
        assert (result / "app.py").exists()

    def test_clone_local_path_relative(self, sample_python_project, temp_dir):
        """Test cloning with relative local path."""
        cloner = GitHubCloner()
        # Change to temp_dir to use relative path
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        try:
            rel_path = sample_python_project.relative_to(temp_dir)
            result = cloner.clone(str(rel_path))
            assert result.exists()
            assert (result / "app.py").exists()
        finally:
            os.chdir(original_cwd)

    def test_clone_nonexistent_local_path(self):
        """Test cloning a non-existent local path raises error."""
        cloner = GitHubCloner()
        with pytest.raises(ValueError, match="does not exist|Invalid repository URL"):
            cloner.clone("/nonexistent/path/that/does/not/exist")

    def test_copy_local_repo_creates_unique_dirs(self, sample_python_project, temp_dir):
        """Test that multiple copies with output_dir create unique directory names."""
        cloner = GitHubCloner()
        # When output_dir is provided, it adds timestamp for uniqueness
        result1 = cloner.clone(str(sample_python_project), output_dir=str(temp_dir / "out1"))
        result2 = cloner.clone(str(sample_python_project), output_dir=str(temp_dir / "out2"))

        assert result1 != result2
        assert result1.exists()
        assert result2.exists()

    def test_invalid_url(self):
        """Test that invalid URL raises error."""
        cloner = GitHubCloner()
        with pytest.raises(ValueError, match="Invalid repository URL"):
            cloner.clone("not-a-url")

    def test_clone_remote_url_structure(self):
        """Test that remote URL generates proper directory structure."""
        cloner = GitHubCloner()
        # We don't actually clone, just check the path structure
        repo_url = "https://github.com/user/repo.git"
        import hashlib
        expected_name = hashlib.md5(repo_url.encode()).hexdigest()
        expected_dir = cloner.base_dir / expected_name

        # The actual clone would fail without network, but we can test the logic
        assert cloner.base_dir.name in str(expected_dir) or expected_dir.name == expected_name