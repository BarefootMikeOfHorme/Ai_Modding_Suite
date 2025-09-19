"""
Plugin registry and loader for AI Modding Suite.
"""
from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class Plugin:
    plugin_id: str
    name: str
    description: str
    functions: Dict[str, Callable] = field(default_factory=dict)


def load_plugins() -> List[Plugin]:
    plugins: List[Plugin] = []
    pkg_name = 'plugins'
    try:
        pkg = importlib.import_module(pkg_name)
    except Exception:
        return plugins
    for finder, name, ispkg in pkgutil.iter_modules(pkg.__path__, pkg_name + '.'):
        try:
            mod = importlib.import_module(name)
            if hasattr(mod, 'get_plugin'):
                p = mod.get_plugin()
                if isinstance(p, Plugin):
                    plugins.append(p)
        except Exception:
            # Skip modules that fail to import; they can be fixed iteratively
            continue
    return plugins


def get_plugin_by_id(plugins: List[Plugin], plugin_id: str) -> Optional[Plugin]:
    for p in plugins:
        if p.plugin_id == plugin_id:
            return p
    return None
