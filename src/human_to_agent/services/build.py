from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

import yaml

from human_to_agent import __version__
from human_to_agent.domain.builds import BuildMode, BuildPlan, BuildResult
from human_to_agent.repositories.filesystem import SourceRepository, tree_digest
from human_to_agent.services.distribution_verify import verify_distribution

PUBLIC_DIRECTORIES = (
    "TASK-CONTRACT",
    "SKILLS",
    "CASES",
    "EVALS",
    "WORKFLOW",
    "CONTEXT",
    "STATE",
    "POLICIES",
    "HUMAN-GATES",
    "EXCEPTIONS",
    "UNKNOWNS",
    "LOOP-READINESS",
    "RUNS",
    "EVIDENCE",
)
PUBLIC_ROOT_FILES = ("README.md", "CHANGELOG.md")
TEMPLATE_VERSION = "1"
SCHEMA_VERSION = "1"


class Builder:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.repository = SourceRepository(self.root)

    def plan(
        self,
        slug: str,
        mode: BuildMode,
        destination: Path | None = None,
        *,
        dry_run: bool = False,
    ) -> BuildPlan:
        snapshot = self.repository.snapshot(slug)
        if mode is BuildMode.release:
            gate_path = snapshot.workspace_path / ".foundry" / "release-gate.yaml"
            if not gate_path.is_file():
                raise ValueError("release gate is missing")
            gate = yaml.safe_load(gate_path.read_text(encoding="utf-8"))
            allowed = {
                "conditional_ready",
                "controlled_ready",
                "bounded_ready",
                "production_candidate",
            }
            if (
                not isinstance(gate, dict)
                or gate.get("passed") is not True
                or gate.get("readiness") not in allowed
            ):
                raise ValueError("release gate has not passed")
            index_path = snapshot.workspace_path / ".foundry" / "artifact-index.yaml"
            if not index_path.is_file():
                raise ValueError("release gate requires recorded source digests")
            index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
            recorded = {item["path"]: item["sha256"] for item in index.get("entries", [])}
            if any(recorded.get(item.path) != item.sha256 for item in snapshot.files):
                raise ValueError("release gate rejects unrecorded source changes")
        target = destination or self.root / "dist" / slug / mode.value
        return BuildPlan(slug, mode, target.resolve(), tree_digest(snapshot), dry_run)

    def build(self, plan: BuildPlan) -> BuildResult:
        snapshot = self.repository.snapshot(plan.workspace_id)
        if tree_digest(snapshot) != plan.source_digest:
            raise ValueError("source changed after build planning")
        changed = tuple(
            sorted(
                {
                    *PUBLIC_ROOT_FILES,
                    "BUILD-MANIFEST.json",
                    *(item.path for item in snapshot.files if self._is_public(item.path)),
                }
            )
        )
        if plan.dry_run:
            return BuildResult(plan.destination, plan.mode, plan.source_digest, changed, False)
        plan.destination.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{plan.destination.name}.staging-", dir=plan.destination.parent
            )
        )
        backup = plan.destination.with_name(f".{plan.destination.name}.backup")
        try:
            self._render(staging, plan)
            report = verify_distribution(staging)
            if not report.passed:
                raise ValueError("generated distribution failed standalone validation")
            if backup.exists():
                shutil.rmtree(backup)
            if plan.destination.exists():
                os.replace(plan.destination, backup)
            try:
                os.replace(staging, plan.destination)
            except BaseException:
                if backup.exists() and not plan.destination.exists():
                    os.replace(backup, plan.destination)
                raise
            if backup.exists():
                shutil.rmtree(backup)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return BuildResult(plan.destination, plan.mode, plan.source_digest, changed, True)

    @staticmethod
    def _is_public(relative: str) -> bool:
        parts = Path(relative).parts
        return bool(parts) and (parts[0] in PUBLIC_DIRECTORIES or relative in PUBLIC_ROOT_FILES)

    def _render(self, staging: Path, plan: BuildPlan) -> None:
        for directory in PUBLIC_DIRECTORIES:
            (staging / directory).mkdir(parents=True, exist_ok=True)
        snapshot = self.repository.snapshot(plan.workspace_id)
        for source in snapshot.files:
            if not self._is_public(source.path):
                continue
            target = staging / source.path
            target.parent.mkdir(parents=True, exist_ok=True)
            content = source.canonical_content
            if source.path == "README.md" and plan.mode is BuildMode.draft:
                content = b"# DRAFT - NOT RELEASE READY\n\n" + content
            target.write_bytes(content)
        readme = staging / "README.md"
        if not readme.exists():
            warning = "DRAFT - NOT RELEASE READY\n\n" if plan.mode is BuildMode.draft else ""
            readme.write_text(
                f"# {plan.workspace_id}\n\n{warning}Evidence-backed Agent workspace.\n",
                newline="\n",
            )
        changelog = staging / "CHANGELOG.md"
        if not changelog.exists():
            changelog.write_text("# Changelog\n\n- Initial deterministic build.\n", newline="\n")
        files: dict[str, str] = {}
        for path in sorted(item for item in staging.rglob("*") if item.is_file()):
            relative = path.relative_to(staging).as_posix()
            files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest = {
            "adapter_versions": {},
            "cli_version": __version__,
            "files": files,
            "mode": plan.mode.value,
            "schema_version": SCHEMA_VERSION,
            "source_tree_digest": plan.source_digest,
            "template_version": TEMPLATE_VERSION,
        }
        (staging / "BUILD-MANIFEST.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
