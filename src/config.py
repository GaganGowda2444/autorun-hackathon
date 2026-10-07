"""
Configuration module for Autorun Hackathon.
Supports YAML and JSON configuration files with environment variable overrides.
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    """Configuration manager for the application."""

    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            self._load_config()

    def _load_config(self):
        """Load configuration from files and environment variables."""
        self._config = self._get_default_config()

        # Look for config files in order of precedence
        config_paths = [
            Path.cwd() / 'autorun-config.yaml',
            Path.cwd() / 'autorun-config.yml',
            Path.cwd() / 'autorun-config.json',
            Path.cwd() / '.autorun' / 'config.yaml',
            Path.cwd() / '.autorun' / 'config.json',
            Path.home() / '.config' / 'autorun' / 'config.yaml',
            Path.home() / '.config' / 'autorun' / 'config.json',
        ]

        for config_path in config_paths:
            if config_path.exists():
                self._merge_config(self._load_file(config_path))
                break

        # Apply environment variable overrides
        self._apply_env_overrides()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            'sandbox': {
                'server_startup_timeout': 10,
                'default_timeout': 120,
                'default_output_dir': './autorun-output',
            },
            'docker': {
                'enabled': True,
                'memory_limit': '500m',
                'cpu_quota': 50000,
                'cpu_period': 100000,
                'network_disabled': True,
                'read_only': True,
                'user': '1000:1000',
                'tmpfs': ['/tmp', '/var/tmp'],
            },
            'cloner': {
                'base_dir': None,
                'cleanup_on_failure': True,
            },
            'detector': {
                'confidence_threshold': 0.3,
            },
            'reporter': {
                'create_latest_symlink': True,
                'include_logs_in_summary': True,
            },
            'logging': {
                'level': 'INFO',
                'verbose': False,
            }
        }

    def _load_file(self, path: Path) -> Dict[str, Any]:
        """Load configuration from a YAML or JSON file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                if path.suffix in ('.yaml', '.yml'):
                    return yaml.safe_load(f) or {}
                elif path.suffix == '.json':
                    return json.load(f) or {}
        except Exception as e:
            print(f"[WARN] Failed to load config from {path}: {e}")
        return {}

    def _merge_config(self, new_config: Dict[str, Any]):
        """Recursively merge new configuration into existing."""
        def deep_merge(base: Dict, update: Dict):
            for key, value in update.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    deep_merge(base[key], value)
                else:
                    base[key] = value

        deep_merge(self._config, new_config)

    def _apply_env_overrides(self):
        """Apply environment variable overrides."""
        env_mapping = {
            'AUTORUN_SANDBOX_TIMEOUT': ('sandbox', 'default_timeout', int),
            'AUTORUN_OUTPUT_DIR': ('sandbox', 'default_output_dir', str),
            'AUTORUN_NO_DOCKER': ('docker', 'enabled', lambda x: x != '1'),
            'AUTORUN_DOCKER_MEMORY': ('docker', 'memory_limit', str),
            'AUTORUN_DOCKER_CPU_QUOTA': ('docker', 'cpu_quota', int),
            'AUTORUN_LOG_LEVEL': ('logging', 'level', str),
            'AUTORUN_VERBOSE': ('logging', 'verbose', lambda x: x == '1'),
        }

        for env_var, (section, key, converter) in env_mapping.items():
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    converted = converter(value)
                    if section not in self._config:
                        self._config[section] = {}
                    self._config[section][key] = converted
                except Exception as e:
                    print(f"[WARN] Failed to parse env var {env_var}: {e}")

    def get(self, *keys, default=None) -> Any:
        """Get a configuration value using dot notation keys."""
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def get_sandbox_config(self) -> Dict[str, Any]:
        """Get sandbox configuration."""
        return self._config.get('sandbox', {})

    def get_docker_config(self) -> Dict[str, Any]:
        """Get Docker configuration."""
        return self._config.get('docker', {})

    def get_cloner_config(self) -> Dict[str, Any]:
        """Get cloner configuration."""
        return self._config.get('cloner', {})

    def get_detector_config(self) -> Dict[str, Any]:
        """Get detector configuration."""
        return self._config.get('detector', {})

    def get_reporter_config(self) -> Dict[str, Any]:
        """Get reporter configuration."""
        return self._config.get('reporter', {})

    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self._config.get('logging', {})


def get_config() -> Config:
    """Get the global configuration instance."""
    return Config()


def reload_config():
    """Reload configuration from files."""
    global _config
    Config._config = None
    Config._instance = None
    return get_config()