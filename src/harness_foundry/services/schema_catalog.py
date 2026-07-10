from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from harness_foundry.domain.assets import ASSET_MODELS
from harness_foundry.domain.common import AssetMetadata
from harness_foundry.domain.evidence import Evidence
from harness_foundry.domain.readiness import READINESS_MODELS
from harness_foundry.domain.recertification import RECERTIFICATION_MODELS
from harness_foundry.domain.stages import STAGE_MODELS
from harness_foundry.domain.unknowns import UNKNOWN_MODELS

DEFAULT_MODELS: dict[str, type[BaseModel]] = {
    "asset-metadata": AssetMetadata,
    "evidence": Evidence,
    **ASSET_MODELS,
    **UNKNOWN_MODELS,
    **READINESS_MODELS,
    **RECERTIFICATION_MODELS,
    **STAGE_MODELS,
}


def build_schema_documents(
    models: Mapping[str, type[BaseModel]],
) -> dict[str, dict[str, Any]]:
    return {
        name: model.model_json_schema(mode="validation") for name, model in sorted(models.items())
    }


def _schema_text(document: Mapping[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_schema_documents(
    output_dir: Path,
    documents: Mapping[str, Mapping[str, Any]],
) -> tuple[Path, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, document in sorted(documents.items()):
        path = output_dir / f"{name}.schema.json"
        path.write_text(_schema_text(document), encoding="utf-8", newline="\n")
        written.append(path)
    return tuple(written)


def check_schema_documents(
    output_dir: Path,
    documents: Mapping[str, Mapping[str, Any]],
) -> bool:
    for name, document in sorted(documents.items()):
        path = output_dir / f"{name}.schema.json"
        if not path.is_file() or path.read_text(encoding="utf-8") != _schema_text(document):
            return False
    expected = {f"{name}.schema.json" for name in documents}
    actual = {path.name for path in output_dir.glob("*.schema.json")}
    return actual == expected


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write or check Harness Foundry JSON Schemas")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", type=Path)
    group.add_argument("--check", type=Path)
    args = parser.parse_args(argv)
    documents = build_schema_documents(DEFAULT_MODELS)
    if args.write is not None:
        write_schema_documents(args.write, documents)
        return 0
    return 0 if check_schema_documents(args.check, documents) else 1


if __name__ == "__main__":
    raise SystemExit(main())
