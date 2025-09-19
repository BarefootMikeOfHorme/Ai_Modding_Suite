"""
Utility helpers for hashing and system info.
"""
from __future__ import annotations

import getpass
import hashlib
import os
import platform
from pathlib import Path
from typing import Tuple


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def get_user_host() -> Tuple[str, str]:
    try:
        user = getpass.getuser()
    except Exception:
        user = os.environ.get('USERNAME') or os.environ.get('USER') or 'unknown'
    host = platform.node() or 'unknown-host'
    return user, host
