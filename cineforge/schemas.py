"""JSON 스키마 로드·검증. jsonschema가 있으면 사용하고, 없으면 내장 최소 검증기(type/required/properties/items/enum/minimum/minItems)."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from cineforge.data_loader import DATA_DIR

SCHEMA_DIR = DATA_DIR / "schemas"
_TYPES = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float), "boolean": bool, "null": type(None)}


@lru_cache(maxsize=None)
def load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def list_schemas() -> list[str]:
    return sorted(p.name.replace(".schema.json", "") for p in SCHEMA_DIR.glob("*.schema.json"))


def _check(value: Any, schema: dict[str, Any], path: str, errors: list[str]) -> None:
    expected = schema.get("type")
    if expected:
        types = expected if isinstance(expected, list) else [expected]
        ok = any(isinstance(value, _TYPES[t]) and not (t in ("integer", "number") and isinstance(value, bool)) for t in types)
        if not ok:
            errors.append(f"{path or '$'}: {types} 타입이어야 합니다")
            return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path or '$'}: {schema['enum']} 중 하나여야 합니다")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and "minimum" in schema and value < schema["minimum"]:
        errors.append(f"{path}: {schema['minimum']} 이상이어야 합니다")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: 필수 항목 누락" if path else f"{key}: 필수 항목 누락")
        for key, sub in schema.get("properties", {}).items():
            if key in value:
                _check(value[key], sub, f"{path}.{key}" if path else key, errors)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: 최소 {schema['minItems']}개")
        if "items" in schema:
            for i, item in enumerate(value):
                _check(item, schema["items"], f"{path}[{i}]", errors)


def validate_with_schema(value: Any, schema: dict[str, Any]) -> list[str]:
    try:
        import jsonschema  # type: ignore
    except ImportError:  # pragma: no cover - 환경에 따라
        errors: list[str] = []
        _check(value, schema, "", errors)
        return errors
    validator = jsonschema.Draft202012Validator(schema)
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '$'}: {e.message}" for e in validator.iter_errors(value)]


def validate(value: Any, name: str) -> list[str]:
    return validate_with_schema(value, load_schema(name))
