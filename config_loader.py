#!/usr/bin/env python3
"""
Load factors/parameters configuration from a TOML file for the DOE generator.

This module prefers the standard library `tomllib` (Python 3.11+). If not available, it uses the `toml` package if installed.

Config format (example):
[factors]
Input Rate = ["32k", "34k", "36k", "38k", "40k"]
Gas Valve Location = [2, 3, 4, 5, 6]
...

It returns a dict mapping factor name -> list of values.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

try:
    import tomllib as _toml
except Exception:
    try:
        import toml as _toml
    except Exception:
        _toml = None


def load_config(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"TOML config not found: {p}")
    # read as text or bytes depending on tomllib vs toml
    if hasattr(_toml, 'loads'):
        text = p.read_text(encoding='utf-8')
        parsed = _toml.loads(text)
    else:
        # toml module has load()
        parsed = _toml.load(p)
    if not isinstance(parsed, dict):
        raise RuntimeError('Unsupported TOML structure: expected a table of keys')
    return parsed


def load_factors_from_config(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Return the factors mapping from the parsed TOML config. Either top-level keys or under 'factors' table."""
    if 'factors' in parsed and isinstance(parsed['factors'], dict):
        return parsed['factors']
    # otherwise assume that parsed contains only factor keys (no other top-level options)
    # Filter out keys that aren't mapping to lists
    factors = {k: v for k, v in parsed.items() if isinstance(v, list)}
    return factors
