from __future__ import annotations

import json
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import TypeAlias

import yaml

JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


def _jsonable(value: object) -> JsonValue:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Enum):
        return _jsonable(value.value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    raise TypeError(f"cannot canonicalize {type(value).__name__}")


def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            _jsonable(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def canonical_text(text: str) -> bytes:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    return (normalized + "\n").encode("utf-8")


def canonical_file(path: Path) -> bytes:
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return canonical_bytes(yaml.safe_load(path.read_text(encoding="utf-8")))
    if suffix == ".json":
        return canonical_bytes(json.loads(path.read_text(encoding="utf-8")))
    if suffix == ".jsonl":
        values = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return b"".join(canonical_bytes(value) for value in values)
    if suffix in {".md", ".txt", ".toml"}:
        return canonical_text(path.read_text(encoding="utf-8"))
    return path.read_bytes()
