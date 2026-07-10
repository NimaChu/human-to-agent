from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import yaml

from harness_foundry.cli.errors import FoundryError
from harness_foundry.cli.result import CommandResult
from harness_foundry.domain.evidence import Evidence, EvidenceBasis, EvidenceType
from harness_foundry.domain.unknowns import (
    Unknown,
    UnknownCategory,
    UnknownClosure,
    UnknownDisposition,
    UnknownStatus,
    close_unknown,
    reopen_unknown,
)
from harness_foundry.services.asset_writer import write_asset


def add_unknown(
    root: Path,
    workspace_id: str,
    *,
    title: str,
    description: str,
    category: UnknownCategory,
    owner: str,
    actor: str,
    dry_run: bool,
) -> CommandResult:
    digest = hashlib.sha256(title.strip().encode()).hexdigest()
    now = datetime.now(UTC)
    asset_id = f"unknown.{digest[:16]}"
    item = Unknown(
        schema_version="1",
        id=asset_id,
        workspace_id=workspace_id,
        revision=1,
        status="open",
        owners=(owner,),
        created_at=now,
        updated_at=now,
        provenance="hf unknown add",
        links=(),
        evidence_refs=(),
        title=title,
        description=description,
        category=category,
        unknown_status=UnknownStatus.new,
        impact_dimensions=("not_yet_established",),
        impact_narrative="Impact is not yet established; automation remains restricted.",
        occurrence_conditions=("The unresolved question affects a task decision.",),
        affected_assets=(f"workspace.{workspace_id}",),
        confidence_basis=EvidenceBasis.unverified,
        owner_id=owner,
        expected_responder_role="responsible owner",
        cheapest_probe="Ask the named owner for one direct decision or source locator.",
        prompt_patch="State the Unknown explicitly and stop before relying on it.",
        automation_restriction="Do not automate decisions that depend on this Unknown.",
        allowed_closure_evidence=(
            EvidenceType.formal_rule,
            EvidenceType.real_case,
            EvidenceType.owner_confirmation,
            EvidenceType.repeatable_validation,
            EvidenceType.risk_decision,
        ),
    )
    rendered = yaml.safe_dump(
        item.model_dump(mode="json"), sort_keys=False, allow_unicode=True
    ).encode()
    return write_asset(
        root,
        workspace_id,
        f"UNKNOWNS/{digest[:16]}.yaml",
        rendered,
        command="unknown add",
        asset_id=asset_id,
        actor=actor,
        dry_run=dry_run,
    )


def close_unknown_asset(
    root: Path,
    workspace_id: str,
    *,
    unknown_id: str,
    evidence_id: str,
    disposition: UnknownDisposition,
    conclusion: str,
    actor: str,
    dry_run: bool,
) -> CommandResult:
    relative, item = _find_unknown(root, workspace_id, unknown_id)
    evidence = _load_evidence(root, workspace_id)
    now = datetime.now(UTC)
    try:
        updated = close_unknown(
            item,
            UnknownClosure(
                disposition=disposition,
                owner_id=item.owner_id,
                actor=actor,
                at=now,
                conclusion=conclusion,
                impact="Closure is propagated to the workspace and affected assets.",
                evidence_refs=(evidence_id,),
                propagated_to=(f"workspace.{workspace_id}", *item.affected_assets),
            ),
            evidence,
        )
    except ValueError as error:
        raise FoundryError("evidence", "unknown.closure_invalid", str(error)) from error
    return _write_unknown(root, workspace_id, relative, updated, actor, dry_run, "unknown close")


def update_unknown_asset(
    root: Path,
    workspace_id: str,
    *,
    unknown_id: str,
    input_path: Path | None,
    actor: str,
    dry_run: bool,
) -> CommandResult:
    relative, current = _find_unknown(root, workspace_id, unknown_id)
    if input_path is None or not input_path.is_file():
        raise FoundryError(
            "usage", "unknown.input_missing", "--input must name a candidate YAML file."
        )
    candidate = Unknown.model_validate(yaml.safe_load(input_path.read_text(encoding="utf-8")))
    if candidate.id != current.id or candidate.workspace_id != workspace_id:
        raise FoundryError("schema", "unknown.identity_changed", "Unknown identity cannot change.")
    if candidate.revision <= current.revision:
        raise FoundryError(
            "schema", "unknown.revision_not_advanced", "Unknown revision must increase."
        )
    return _write_unknown(root, workspace_id, relative, candidate, actor, dry_run, "unknown update")


def reopen_unknown_asset(
    root: Path,
    workspace_id: str,
    *,
    unknown_id: str,
    evidence_id: str,
    reason: str,
    actor: str,
    dry_run: bool,
) -> CommandResult:
    relative, item = _find_unknown(root, workspace_id, unknown_id)
    if evidence_id not in _load_evidence(root, workspace_id):
        raise FoundryError("evidence", "unknown.evidence_missing", "Reopen evidence is missing.")
    updated = reopen_unknown(
        item,
        reason=reason,
        actor=actor,
        at=datetime.now(UTC),
        evidence_refs=(evidence_id,),
    )
    return _write_unknown(root, workspace_id, relative, updated, actor, dry_run, "unknown reopen")


def _find_unknown(root: Path, workspace_id: str, unknown_id: str) -> tuple[str, Unknown]:
    directory = root / "workspaces" / workspace_id / "UNKNOWNS"
    for path in sorted(directory.glob("*.yaml")):
        item = Unknown.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        if item.id == unknown_id:
            return path.relative_to(directory.parent).as_posix(), item
    raise FoundryError("schema", "unknown.missing", f"Unknown does not exist: {unknown_id}")


def _load_evidence(root: Path, workspace_id: str) -> dict[str, Evidence]:
    directory = root / "workspaces" / workspace_id / "EVIDENCE"
    items: dict[str, Evidence] = {}
    for path in sorted(directory.glob("*.yaml")):
        item = Evidence.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        items[item.id] = item
    return items


def _write_unknown(
    root: Path,
    workspace_id: str,
    relative: str,
    item: Unknown,
    actor: str,
    dry_run: bool,
    command: str,
) -> CommandResult:
    rendered = yaml.safe_dump(
        item.model_dump(mode="json"), sort_keys=False, allow_unicode=True
    ).encode()
    return write_asset(
        root,
        workspace_id,
        relative,
        rendered,
        command=command,
        asset_id=item.id,
        actor=actor,
        dry_run=dry_run,
    )
