import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import docker


class EnvCache:
    """Persistent cache of successfully built Docker environments.

    Stores one JSON record per cached environment and tags the built image
    as `autorun-cache:<cache_key>` so the next run can reuse it directly.
    """

    def __init__(self, output_dir: str = "./autorun-output"):
        self.output_dir = Path(output_dir)
        self.cache_dir = self.output_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ---------- key ----------
    @staticmethod
    def make_key(repo_url: str, commit_sha: Optional[str], language: str,
                 framework: str, base_image: str,
                 startup_command: Optional[str] = None) -> str:
        raw = f"{repo_url}|{commit_sha or 'HEAD'}|{language}|{framework}|{base_image}"
        # Include the startup command so a cached image built with a different
        # entrypoint is not silently reused after detection logic changes.
        if startup_command:
            raw += f"|{startup_command}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _record_path(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key}.json"

    # ---------- docker helpers ----------
    @staticmethod
    def _docker_client():
        try:
            return docker.from_env()
        except Exception:
            return None

    def image_exists(self, image_tag: str) -> bool:
        client = self._docker_client()
        if client is None:
            return False
        try:
            client.images.get(image_tag)
            return True
        except Exception:
            return False

    # ---------- CRUD ----------
    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        path = self._record_path(cache_key)
        if not path.exists():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not self.image_exists(record.get("image_tag", "")):
            # Stale record: image was removed externally
            try:
                path.unlink()
            except Exception:
                pass
            return None
        return record

    def put(self, cache_key: str, record: Dict[str, Any]) -> None:
        record = dict(record)
        record["cache_key"] = cache_key
        record.setdefault("created_at", time.strftime("%Y%m%d_%H%M%S"))
        record.setdefault("last_used_at", record["created_at"])
        record.setdefault("hit_count", 0)
        self._record_path(cache_key).write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )

    def touch(self, cache_key: str) -> None:
        path = self._record_path(cache_key)
        if not path.exists():
            return
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            record["last_used_at"] = time.strftime("%Y%m%d_%H%M%S")
            record["hit_count"] = int(record.get("hit_count", 0)) + 1
            path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        except Exception:
            pass

    def list(self) -> List[Dict[str, Any]]:
        records = []
        for path in sorted(self.cache_dir.glob("*.json")):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return records

    def clear(self) -> int:
        """Remove all cache records and the tagged Docker images. Returns count removed."""
        records = self.list()
        for record in records:
            tag = record.get("image_tag")
            if tag:
                client = self._docker_client()
                if client is not None:
                    try:
                        client.images.remove(tag, force=True)
                    except Exception:
                        pass
        removed = 0
        for path in self.cache_dir.glob("*.json"):
            try:
                path.unlink()
                removed += 1
            except Exception:
                pass
        return removed
