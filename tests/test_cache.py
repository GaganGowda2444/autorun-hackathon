import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cache import EnvCache


@pytest.fixture
def cache(tmp_path):
    return EnvCache(str(tmp_path / "out"))


def test_make_key_deterministic():
    k1 = EnvCache.make_key("https://example/repo", "abc123", "python", "flask", "python:3.9-slim")
    k2 = EnvCache.make_key("https://example/repo", "abc123", "python", "flask", "python:3.9-slim")
    k3 = EnvCache.make_key("https://example/repo", "def456", "python", "flask", "python:3.9-slim")
    assert k1 == k2
    assert k1 != k3
    assert len(k1) == 16


def test_put_get_roundtrip(cache, monkeypatch):
    monkeypatch.setattr(EnvCache, "image_exists", lambda self, tag: True)
    cache.put("deadbeefdeadbeef", {
        "repo_url": "https://example/repo",
        "commit_sha": "abc",
        "language": "python",
        "framework": "flask",
        "base_image": "python:3.9-slim",
        "image_tag": "autorun-cache:deadbeefdeadbeef",
        "startup_command": "python app.py",
    })
    rec = cache.get("deadbeefdeadbeef")
    assert rec is not None
    assert rec["language"] == "python"
    assert rec["hit_count"] == 0
    assert rec["cache_key"] == "deadbeefdeadbeef"


def test_get_returns_none_for_missing(cache):
    assert cache.get("nope") is None


def test_get_drops_stale_record_when_image_gone(cache, monkeypatch):
    monkeypatch.setattr(EnvCache, "image_exists", lambda self, tag: False)
    cache.put("stale", {"image_tag": "autorun-cache:stale"})
    assert cache.get("stale") is None
    assert not (cache.cache_dir / "stale.json").exists()


def test_touch_increments_hit_count(cache, monkeypatch):
    monkeypatch.setattr(EnvCache, "image_exists", lambda self, tag: True)
    cache.put("k", {"image_tag": "autorun-cache:k"})
    cache.touch("k")
    cache.touch("k")
    rec = cache.get("k")
    assert rec["hit_count"] == 2


def test_list_and_clear(cache, monkeypatch):
    monkeypatch.setattr(EnvCache, "image_exists", lambda self, tag: True)
    monkeypatch.setattr(EnvCache, "_docker_client", staticmethod(lambda: None))
    cache.put("a", {"image_tag": "autorun-cache:a"})
    cache.put("b", {"image_tag": "autorun-cache:b"})
    assert len(cache.list()) == 2
    removed = cache.clear()
    assert removed == 2
    assert cache.list() == []
