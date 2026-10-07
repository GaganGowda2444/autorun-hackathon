import os
import git
import hashlib
from pathlib import Path
from urllib.parse import urlparse, unquote


class GitHubCloner:
    """Handles cloning of GitHub repositories."""

    def __init__(self, base_dir=None):
        """
        Initialize the cloner.

        Args:
            base_dir (str or Path): Base directory for cloning repositories.
                                   If None, uses current working directory.
        """
        if base_dir is None:
            base_dir = Path.cwd()
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def clone(self, repo_url, output_dir=None):
        """
        Clone a GitHub repository.

        Args:
            repo_url (str): URL of the GitHub repository to clone.
            output_dir (str or Path): Directory to clone into. If None, uses a
                                     hash-based directory name under base_dir.

        Returns:
            Path: Path to the cloned repository.

        Raises:
            ValueError: If the repository URL is invalid.
            Exception: If cloning fails.
        """
        # Handle local file paths (with or without file:// prefix)
        is_local_path = False
        local_path = None

        if repo_url.startswith('file://'):
            # Convert file:// URL to local path
            local_path = unquote(repo_url[7:])  # Remove 'file://' prefix and decode URL encoding
            is_local_path = True
        elif os.path.exists(repo_url) and not repo_url.startswith(('http://', 'https://', 'git://', 'ssh://')):
            # It's a local path (relative or absolute)
            local_path = repo_url
            is_local_path = True

        if is_local_path:
            # Handle Windows paths from file:// URLs
            # file:///c:/path -> c:/path
            if local_path.startswith('/') and len(local_path) > 2 and local_path[2] == ':':
                drive_letter = local_path[1]
                rest_of_path = local_path[3:]
                local_path = f"{drive_letter}:/{rest_of_path}"

            # Convert to absolute path to handle relative paths and normalize
            repo_path = Path(local_path)
            repo_path = repo_path.resolve()
            if not repo_path.exists():
                raise ValueError(f"Local repository path does not exist: {local_path}")

            # For local paths, we'll copy the directory instead of cloning
            return self._copy_local_repo(repo_path, output_dir)

        # Validate the URL (basic check) for remote repositories
        parsed = urlparse(repo_url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid repository URL: {repo_url}")

        # Determine the clone directory
        if output_dir is None:
            # Create a hash-based directory name to avoid conflicts
            repo_name = hashlib.md5(repo_url.encode()).hexdigest()
            clone_dir = self.base_dir / repo_name
        else:
            # Use a subdirectory under output_dir to avoid conflicts with existing content
            repo_name = hashlib.md5(repo_url.encode()).hexdigest()
            clone_dir = Path(output_dir) / repo_name
            # Ensure the output directory exists
            clone_dir.parent.mkdir(parents=True, exist_ok=True)

        # If the directory already exists, remove it to start fresh
        if clone_dir.exists():
            import shutil
            try:
                shutil.rmtree(clone_dir)
            except Exception as e:
                print(f"   Warning: Could not remove existing directory: {e}")

        try:
            # Clone the repository
            git.Repo.clone_from(repo_url, clone_dir)
            print(f"   Cloned to: {clone_dir}")
            return clone_dir
        except Exception as e:
            # Clean up if cloning failed
            if clone_dir.exists():
                import shutil
                shutil.rmtree(clone_dir)
            raise Exception(f"Failed to clone repository: {str(e)}")

    def _copy_local_repo(self, repo_path: Path, output_dir=None) -> Path:
        """
        Copy a local repository instead of cloning.

        Args:
            repo_path (Path): Path to the local repository.
            output_dir (str or Path): Directory to copy into. If None, uses a
                                         hash-based directory name under base_dir.

        Returns:
            Path: Path to the copied repository.
        """
        import shutil
        import time

        # Determine the clone directory - use timestamp + hash for uniqueness
        if output_dir is None:
            # Create a hash-based directory name to avoid conflicts
            repo_name = hashlib.md5(str(repo_path).encode()).hexdigest()
            clone_dir = self.base_dir / repo_name
        else:
            # Use a subdirectory under output_dir with timestamp to avoid conflicts
            repo_hash = hashlib.md5(str(repo_path).encode()).hexdigest()[:8]
            timestamp = int(time.time() * 1000)
            clone_dir = Path(output_dir) / f"repo_{repo_hash}_{timestamp}"
            # Ensure the output directory exists
            clone_dir.parent.mkdir(parents=True, exist_ok=True)

        # If the directory already exists (unlikely with timestamp), remove it
        if clone_dir.exists():
            try:
                shutil.rmtree(clone_dir, ignore_errors=True)
            except Exception as e:
                print(f"   Warning: Could not remove existing directory: {e}")

        try:
            # Copy the repository, ignoring .git directory
            shutil.copytree(repo_path, clone_dir, ignore=shutil.ignore_patterns('.git'))
            print(f"   Copied local repository to: {clone_dir}")
            return clone_dir
        except Exception as e:
            # Clean up if copying failed
            if clone_dir.exists():
                try:
                    shutil.rmtree(clone_dir, ignore_errors=True)
                except:
                    pass
            raise Exception(f"Failed to copy local repository: {str(e)}")