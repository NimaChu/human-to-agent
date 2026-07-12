from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path

import yaml

from human_to_agent.cli.errors import FoundryError
from human_to_agent.cli.result import CommandResult
from human_to_agent.domain.stages import GateStatus, Stage, assess_complete_release, assess_stage
from human_to_agent.renderers.workspace import render_template
from human_to_agent.repositories.filesystem import SourceRepository
from human_to_agent.services.changes import build_artifact_index, render_artifact_index

WORKSPACE_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
WORKSPACE_SLUG_MAX_LENGTH = 64
REPOSITORY_CHILD_TEMPLATE_ROOT = (
    Path(__file__).resolve().parents[3] / "templates" / "child-workspace"
)
ARTIFACT_INDEX_PATH = ".foundry/artifact-index.yaml"


@dataclass(frozen=True, slots=True)
class ChildTemplateManifest:
    template_version: str
    directories: tuple[str, ...]
    templates: tuple[str, ...]
    state_files: tuple[str, ...]


def _child_template_root() -> Traversable:
    if REPOSITORY_CHILD_TEMPLATE_ROOT.joinpath("manifest.yaml").is_file():
        return REPOSITORY_CHILD_TEMPLATE_ROOT
    packaged = resources.files("human_to_agent").joinpath("templates", "child-workspace")
    if not packaged.joinpath("manifest.yaml").is_file():
        raise FoundryError(
            "config",
            "template.missing",
            "Child workspace templates are missing from this installation.",
        )
    return packaged


def _load_child_template_manifest() -> ChildTemplateManifest:
    path = _child_template_root().joinpath("manifest.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise FoundryError("config", "template.invalid", "Child template manifest is invalid.")

    values: dict[str, tuple[str, ...]] = {}
    for key in ("directories", "templates", "state_files"):
        items = raw.get(key)
        if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
            raise FoundryError(
                "config", "template.invalid", f"Child template manifest {key} must be a list."
            )
        values[key] = tuple(items)
    template_version = raw.get("template_version")
    if not isinstance(template_version, str):
        raise FoundryError("config", "template.invalid", "Child template version must be a string.")
    return ChildTemplateManifest(
        template_version=template_version,
        directories=values["directories"],
        templates=values["templates"],
        state_files=values["state_files"],
    )


def _render_child_templates(
    manifest: ChildTemplateManifest,
    *,
    slug: str,
    owner: str,
    purpose: str,
    created_at: str,
) -> dict[str, str]:
    template_root = _child_template_root()
    context: dict[str, object] = {
        "slug": slug,
        "name": slug,
        "name_yaml": json.dumps(slug, ensure_ascii=False),
        "owner_yaml": json.dumps(owner, ensure_ascii=False),
        "purpose": purpose,
        "purpose_yaml": json.dumps(purpose, ensure_ascii=False),
        "created_at": created_at,
        "template_version": manifest.template_version,
    }
    return {
        relative: render_template(
            template_root.joinpath(f"{relative}.j2").read_text(encoding="utf-8"), context
        )
        for relative in manifest.templates
    }


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


def create_workspace(
    root: Path,
    slug: str,
    *,
    owner: str,
    purpose: str = "Purpose pending evidence-backed capture",
    dry_run: bool,
) -> CommandResult:
    if len(slug) > WORKSPACE_SLUG_MAX_LENGTH or WORKSPACE_SLUG_PATTERN.fullmatch(slug) is None:
        raise FoundryError(
            "usage",
            "workspace.slug_invalid",
            "Workspace slug must match ^[a-z0-9]+(?:-[a-z0-9]+)*$ and be at most 64 characters.",
        )
    if not owner.strip() or not purpose.strip():
        raise FoundryError(
            "usage",
            "workspace.metadata_invalid",
            "Workspace owner and purpose must be non-empty.",
        )
    if not (root / "human-to-agent.yaml").is_file():
        raise FoundryError("config", "config.missing", "Run `hta init` before creating workspaces.")
    workspace = root / "workspaces" / slug
    if workspace.exists() and not dry_run:
        raise FoundryError("filesystem", "workspace.exists", f"Workspace already exists: {slug}")
    manifest = _load_child_template_manifest()
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    rendered = _render_child_templates(
        manifest, slug=slug, owner=owner, purpose=purpose, created_at=now
    )
    changed = [
        str(workspace / relative) for relative in (*manifest.templates, *manifest.state_files)
    ]
    if not dry_run:
        for directory in manifest.directories:
            (workspace / directory).mkdir(parents=True, exist_ok=True)
        for relative, content in rendered.items():
            target = workspace / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
        for relative in manifest.state_files:
            if relative == ARTIFACT_INDEX_PATH:
                continue
            target = workspace / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"")
        snapshot = SourceRepository(root).snapshot(slug)
        (workspace / ARTIFACT_INDEX_PATH).write_bytes(
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
    from human_to_agent.services.assessment_state import load_assessment_state

    assessment_state = load_assessment_state(root, slug)
    gate_report = (
        assess_complete_release(assessment_state.assessment)
        if assessment_state.manifest.current_stage == Stage.stage5
        else assess_stage(
            Stage(assessment_state.manifest.current_stage + 1),
            assessment_state.assessment,
        )
    )
    gate_gaps = sum(check.status is not GateStatus.satisfied for check in gate_report.checks)
    blocking = unmanaged + readiness_gaps + (0 if harness_complete else 1) + gate_gaps
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
            f"gate_target={gate_report.target}",
            f"gate_gaps={gate_gaps}",
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
