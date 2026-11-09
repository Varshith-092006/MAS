"""Central configuration loader for MAS."""

import os
from typing import Any, Dict
import yaml

_CONFIG_CACHE: Dict[str, Any] = {}


def get_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Loads and caches configuration from YAML file."""
    resolved_path = os.path.abspath(config_path)
    if resolved_path in _CONFIG_CACHE:
        return _CONFIG_CACHE[resolved_path]

    if not os.path.exists(resolved_path):
        # Fallback if called from another working dir
        candidate = os.path.join(os.path.dirname(__file__), "..", "..", config_path)
        if os.path.exists(candidate):
            resolved_path = os.path.abspath(candidate)

    if os.path.exists(resolved_path):
        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                _CONFIG_CACHE[resolved_path] = data
                return data
        except Exception:
            pass

    return {}


def clear_config_cache():
    _CONFIG_CACHE.clear()
