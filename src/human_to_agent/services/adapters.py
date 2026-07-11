from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from human_to_agent.validators.report import Diagnostic, ValidationReport


def verify_adapter_sources(root: Path) -> ValidationReport:
    catalog = yaml.safe_load((root / "skills" / "catalog.yaml").read_text(encoding="utf-8"))
    diagnostics: list[Diagnostic] = []
    for name in catalog["skills"]:
        source = root / "skills" / name / "SKILL.md"
        expected = catalog["source_digests"].get(name)
        actual = hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None
        if actual != expected:
            diagnostics.append(
                Diagnostic(
                    category="adapter",
                    code="adapter.recertification_required",
                    message="Shared method changed; adapters require re-certification.",
                    path=f"skills/{name}/SKILL.md",
                )
            )
        for relative in (
            Path(".codex") / "skills" / name / "SKILL.md",
            Path(".opencode") / "skills" / name / "SKILL.md",
        ):
            adapter = root / relative
            if not adapter.is_file() or f"skills/{name}/SKILL.md" not in adapter.read_text(
                encoding="utf-8"
            ):
                diagnostics.append(
                    Diagnostic(
                        category="adapter",
                        code="adapter.missing_or_unlinked",
                        message="Tool adapter is missing or does not resolve to its shared source.",
                        path=relative.as_posix(),
                    )
                )
    return ValidationReport(diagnostics=tuple(diagnostics))
