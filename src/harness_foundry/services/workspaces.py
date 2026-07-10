from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from harness_foundry.cli.errors import FoundryError
from harness_foundry.cli.result import CommandResult
from harness_foundry.repositories.filesystem import SourceRepository
from harness_foundry.services.changes import build_artifact_index, render_artifact_index

SOURCE_DIRECTORIES = (
    "TASK-CONTRACT",
    "SKILLS",
    "CASES",
    "EVALS",
    "WORKFLOW",
    "TOOLS",
    "CONTEXT",
    "STATE",
    "EVALUATORS",
    "POLICIES",
    "HUMAN-GATES",
    "EXCEPTIONS",
    "UNKNOWNS",
    "LOOP-READINESS",
    "RUNS",
    "EVIDENCE",
)


def initialize(root: Path, *, dry_run: bool) -> CommandResult:
    targets = ("workspaces", "state/transactions", "state/locks", "dist")
    if not dry_run:
        for relative in targets:
            (root / relative).mkdir(parents=True, exist_ok=True)
        config = root / "foundry.yaml"
        if not config.exists():
            config.write_text(
                'schema_version: "1"\nworkspace_root: workspaces\n'
                "distribution_root: dist\nstate_root: state\n",
                encoding="utf-8",
                newline="\n",
            )
    return CommandResult(
        command="init",
        changed_files=[] if dry_run else [str(root / "foundry.yaml")],
        next_actions=["Create a child workspace with `hf workspace new <slug>`."],
    )


def create_workspace(root: Path, slug: str, *, owner: str, dry_run: bool) -> CommandResult:
    if not (root / "foundry.yaml").is_file():
        raise FoundryError("config", "config.missing", "Run `hf init` before creating workspaces.")
    workspace = root / "workspaces" / slug
    if workspace.exists() and not dry_run:
        raise FoundryError("filesystem", "workspace.exists", f"Workspace already exists: {slug}")
    changed = [str(workspace / "workspace.yaml")]
    if not dry_run:
        for directory in SOURCE_DIRECTORIES:
            (workspace / directory).mkdir(parents=True, exist_ok=True)
        (workspace / ".foundry").mkdir(parents=True, exist_ok=True)
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        manifest = {
            "schema_version": "1",
            "id": f"workspace.{slug}",
            "workspace_id": slug,
            "revision": 1,
            "status": "draft",
            "owners": [owner],
            "created_at": now,
            "updated_at": now,
            "provenance": "hf workspace new",
            "links": [],
            "evidence_refs": [],
            "name": slug,
            "purpose": "Purpose pending evidence-backed capture",
            "current_stage": 1,
            "risk_level": "unassessed",
            "owner_id": owner,
            "autonomy_level": "H0",
        }
        (workspace / "workspace.yaml").write_text(
            yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
            newline="\n",
        )
        snapshot = SourceRepository(root).snapshot(slug)
        (workspace / ".foundry" / "artifact-index.yaml").write_bytes(
            render_artifact_index(build_artifact_index(snapshot))
        )
    return CommandResult(command="workspace new", changed_files=[] if dry_run else changed)


def list_workspaces(root: Path) -> CommandResult:
    workspace_root = root / "workspaces"
    names = (
        sorted(path.name for path in workspace_root.iterdir() if path.is_dir())
        if workspace_root.exists()
        else []
    )
    return CommandResult(command="workspace list", next_actions=names)


def require_workspace(root: Path, slug: str) -> Path:
    workspace = root / "workspaces" / slug
    if not (workspace / "workspace.yaml").is_file():
        raise FoundryError("schema", "workspace.missing", f"Workspace manifest is missing: {slug}")
    return workspace


def status(root: Path, slug: str) -> CommandResult:
    workspace = require_workspace(root, slug)
    raw = yaml.safe_load((workspace / "workspace.yaml").read_text(encoding="utf-8"))
    return CommandResult(
        command="workspace status",
        next_actions=[f"stage={raw.get('current_stage')}", f"autonomy={raw.get('autonomy_level')}"],
    )
