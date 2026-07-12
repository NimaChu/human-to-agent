from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

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
            if not isinstance(relative, str) or not isinstance(expected, str):
                raise ValueError("file paths and digests must be strings")
            relative_path = PurePosixPath(relative)
            if (
                not relative_path.parts
                or relative_path.is_absolute()
                or ".." in relative_path.parts
                or "\\" in relative
                or any(":" in part for part in relative_path.parts)
                or relative == "BUILD-MANIFEST.json"
            ):
                diagnostics.append(
                    Diagnostic(
                        category="filesystem",
                        code="distribution.path_invalid",
                        message="Manifest file path must stay inside the distribution.",
                        path=relative,
                    )
                )
                continue
            target = path.joinpath(*relative_path.parts)
            if target.is_symlink():
                diagnostics.append(
                    Diagnostic(
                        category="filesystem",
                        code="distribution.path_invalid",
                        message="Distribution files cannot be symbolic links.",
                        path=relative,
                    )
                )
                continue
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
        listed = {item for item in files if isinstance(item, str)}
        actual_files = {
            item.relative_to(path).as_posix()
            for item in path.rglob("*")
            if item.is_file() and item != manifest_path
        }
        for relative in sorted(actual_files - listed):
            diagnostics.append(
                Diagnostic(
                    category="filesystem",
                    code="distribution.file_unlisted",
                    message="Published file is not listed in BUILD-MANIFEST.json.",
                    path=relative,
                )
            )
        if manifest.get("mode") == "release":
            required_files = {"workspace.yaml", "ASSESSMENTS/stage-state.yaml"}
            required_prefixes = (
                "TASK-CONTRACT/",
                "SKILLS/",
                "CASES/",
                "EVALS/",
                "WORKFLOW/",
                "HARNESS/",
                "TOOLS/",
                "CONTEXT/",
                "STATE/",
                "EVALUATORS/",
                "POLICIES/",
                "HUMAN-GATES/",
                "EXCEPTIONS/",
                "UNKNOWNS/",
                "LOOP-READINESS/",
                "RUNS/",
                "EVIDENCE/",
            )
            missing = sorted(required_files - listed)
            missing.extend(
                prefix
                for prefix in required_prefixes
                if not any(item.startswith(prefix) for item in listed)
            )
            for relative in missing:
                diagnostics.append(
                    Diagnostic(
                        category="filesystem",
                        code="distribution.required_missing",
                        message="Release distribution lacks a required Harness asset.",
                        path=relative,
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
