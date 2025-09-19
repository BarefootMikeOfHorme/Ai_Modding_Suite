# Schema loading and validation utilities
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft7Validator, RefResolver, validate, exceptions as js_exceptions


def _load_json_file(path: Path) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _preprocess_inherits(doc: Dict[str, Any], base_dir: Path) -> Dict[str, Any]:
    # Convert a custom "inherits": "RelativePath.json" into an allOf with $ref
    inherits = doc.pop('inherits', None)
    if inherits:
        ref_path = (base_dir / inherits).resolve()
        # Keep original doc but ensure $schema/$id remain if present
        merged: Dict[str, Any] = {
            "allOf": [
                {"$ref": ref_path.as_uri()},
                doc,
            ]
        }
        return merged
    return doc


def load_validator(schema_path: str | Path) -> Draft7Validator:
    schema_path = Path(schema_path).resolve()
    raw = _load_json_file(schema_path)
    pre = _preprocess_inherits(raw, schema_path.parent)
    resolver = RefResolver(base_uri=schema_path.parent.as_uri() + '/', referrer=pre)
    try:
        validator = Draft7Validator(pre, resolver=resolver)
    except js_exceptions.SchemaError as e:
        raise RuntimeError(f"Invalid schema at {schema_path}: {e}") from e
    return validator


def validate_document(document: Dict[str, Any], schema_path: str | Path) -> list[str]:
    validator = load_validator(schema_path)
    errors: list[str] = []
    for error in sorted(validator.iter_errors(document), key=lambda e: e.path):
        loc = "/".join(map(str, error.path))
        errors.append(f"{loc or '<root>'}: {error.message}")
    return errors
