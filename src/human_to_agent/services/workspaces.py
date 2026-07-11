from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from human_to_agent.cli.errors import FoundryError
from human_to_agent.cli.result import CommandResult
from human_to_agent.repositories.filesystem import SourceRepository
from human_to_agent.services.changes import build_artifact_index, render_artifact_index

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
        config = root / "human-to-agent.yaml"
        if not config.exists():
            config.write_text(
                'schema_version: "1"\nworkspace_root: workspaces\n'
                "distribution_root: dist\nstate_root: state\n",
                encoding="utf-8",
                newline="\n",
            )
    return CommandResult(
        command="init",
        changed_files=[] if dry_run else [str(root / "human-to-agent.yaml")],
        next_actions=["Create a child workspace with `hta workspace new <slug>`."],
    )


def create_workspace(root: Path, slug: str, *, owner: str, dry_run: bool) -> CommandResult:
    if not (root / "human-to-agent.yaml").is_file():
        raise FoundryError("config", "config.missing", "Run `hta init` before creating workspaces.")
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
            "provenance": "hta workspace new",
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
    skills = _yaml_assets(workspace / "SKILLS")
    cases = _yaml_assets(workspace / "CASES")
    unknowns = _yaml_assets(workspace / "UNKNOWNS")
    harnesses = _yaml_assets(workspace / "HARNESS")
    readiness_assets = _yaml_assets(workspace / "LOOP-READINESS")
    validated_skills = sum(item.get("status") == "validated" for item in skills)
    case_kinds = sorted({str(item.get("kind")) for item in cases if item.get("kind")})
    managed_statuses = {"resolved", "accepted_risk", "human_only", "out_of_scope"}
    unmanaged = sum(item.get("unknown_status") not in managed_statuses for item in unknowns)
    readiness = readiness_assets[0] if readiness_assets else {}
    dimensions = readiness.get("dimensions", {})
    readiness_gaps = (
        sum(
            value.get("status") != "satisfied"
            for value in dimensions.values()
            if isinstance(value, dict)
        )
        if isinstance(dimensions, dict)
        else 1
    )
    harness_complete = bool(harnesses)
    blocking = unmanaged + readiness_gaps + (0 if harness_complete else 1)
    raw_next_actions = readiness.get("next_actions", [])
    readiness_next_actions = raw_next_actions if isinstance(raw_next_actions, list) else []
    return CommandResult(
        command="workspace status",
        next_actions=[
            f"stage={raw.get('current_stage')}",
            f"autonomy={raw.get('autonomy_level')}",
            f"skills={validated_skills}/{len(skills)} validated",
            f"case_coverage={','.join(case_kinds) or 'none'}",
            f"unknowns={len(unknowns)}; unmanaged={unmanaged}",
            f"harness={'complete' if harness_complete else 'missing'}",
            f"readiness={readiness.get('result', 'missing')}",
            f"blocking={blocking}",
            *[str(item) for item in readiness_next_actions],
        ],
    )


def _yaml_assets(directory: Path) -> list[dict[str, object]]:
    if not directory.exists():
        return []
    assets: list[dict[str, object]] = []
    for path in sorted(directory.rglob("*.yaml")):
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            assets.append(value)
    return assets
