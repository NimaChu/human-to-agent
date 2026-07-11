from __future__ import annotations

import hashlib
import json
from pathlib import Path

from human_to_agent.validators.report import Diagnostic, ValidationReport


def verify_distribution(path: Path) -> ValidationReport:
    diagnostics: list[Diagnostic] = []
    manifest_path = path / "BUILD-MANIFEST.json"
    if not manifest_path.is_file():
        return ValidationReport(
            diagnostics=(
                Diagnostic(
                    category="filesystem",
                    code="distribution.manifest_missing",
                    message="BUILD-MANIFEST.json is missing.",
                    path="BUILD-MANIFEST.json",
                ),
            )
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = manifest["files"]
        if not isinstance(files, dict):
            raise ValueError("files must be a mapping")
        for relative, expected in sorted(files.items()):
            target = path / relative
            actual = hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else None
            if actual != expected:
                diagnostics.append(
                    Diagnostic(
                        category="filesystem",
                        code="distribution.digest_mismatch",
                        message="Published file is missing or differs from its manifest digest.",
                        path=str(relative),
                    )
                )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        diagnostics.append(
            Diagnostic(
                category="schema",
                code="distribution.manifest_invalid",
                message=str(error),
                path="BUILD-MANIFEST.json",
            )
        )
    return ValidationReport(diagnostics=tuple(diagnostics))
