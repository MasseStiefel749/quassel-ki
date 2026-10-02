# -*- coding: utf-8 -*-
"""Konfiguration: quassel.yaml lesen, mit Defaults vereinen. Fehlt die Datei, gelten Defaults."""
from __future__ import annotations
from pathlib import Path

try:
    import yaml
    _HAT_YAML = True
except ImportError:
    _HAT_YAML = False

DEFAULTS = {
    "quassel": {"intelligence_mode": "SMART", "sprache": "de"},
    "hardware": {"auto_detect": True},
    "modelle": {
        "auto_select": True,
        "rollen": {
            "fast": ["llama3.1:latest", "llama3.1"],
            "coding": ["quassel-ki:latest", "quassel-ki"],
            "reasoning": ["quassel-ki:latest", "quassel-ki"],
            "vision": ["moondream:latest", "moondream"],
            "fallback": ["llama3.1:latest", "llama3.1"],
        },
    },
    "memory": {"enabled": True, "retrieval": True, "limit_fakten": 8},
    "context": {"adaptive": True, "verlauf_limit": 10},
    "agent": {"enabled": True, "max_runden": 8, "self_check": True},
    "safety": {"confirmations": True},
    "speed": {"modus": "SMART"},
}


def _tief_vereinen(basis, oben):
    erg = dict(basis)
    for k, v in (oben or {}).items():
        if isinstance(v, dict) and isinstance(erg.get(k), dict):
            erg[k] = _tief_vereinen(erg[k], v)
        else:
            erg[k] = v
    return erg


def laden(pfad=None):
    cfg = dict(DEFAULTS)
    p = Path(str(pfad)) if pfad else (Path.cwd() / "quassel.yaml")
    try:
        if p.exists() and _HAT_YAML:
            import yaml as _yaml
            oben = _yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            cfg = _tief_vereinen(DEFAULTS, oben)
    except Exception:
        pass
    return cfg


def hat_yaml():
    return _HAT_YAML
