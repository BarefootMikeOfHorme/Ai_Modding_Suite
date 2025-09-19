"""
Local-only secure gateway for Warp terminal integrations.
Disabled by default; requires AMS_GATEWAY_ENABLE=1 and AMS_GATEWAY_TOKEN to run.
"""
from __future__ import annotations

import os
from functools import wraps
from typing import Callable

from flask import Flask, jsonify, request

from validators import CfgValidator


VERSION = "0.1.0"


def require_token(token: str):
    def decorator(fn: Callable):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            hdr = request.headers.get("X-AMS-Token")
            if hdr != token:
                return jsonify({"error": "unauthorized"}), 401
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def create_app(token: str) -> Flask:
    app = Flask(__name__)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/version")
    def version():
        return jsonify({"version": VERSION})

    @app.post("/validate")
    @require_token(token)
    def validate_text():
        data = request.get_json(silent=True) or {}
        text = data.get("text", "")
        validator = CfgValidator()
        result = validator.validate(text)
        return jsonify({
            "ok": result.is_ok,
            "issues": [
                {"rule_id": i.rule_id, "message": i.message, "severity": i.severity.value, "line": i.line}
                for i in result.issues
            ]
        })

    return app


def start() -> None:
    if os.environ.get("AMS_GATEWAY_ENABLE") != "1":
        print("Gateway disabled. Set AMS_GATEWAY_ENABLE=1 to enable.")
        return
    token = os.environ.get("AMS_GATEWAY_TOKEN")
    if not token:
        print("AMS_GATEWAY_TOKEN is required.")
        return
    host = "127.0.0.1"
    port = int(os.environ.get("AMS_GATEWAY_PORT", "8787"))
    app = create_app(token)
    # No debug, local-only
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    start()
