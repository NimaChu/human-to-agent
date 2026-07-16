from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import yaml

from human_to_agent.cli.errors import FoundryError
from human_to_agent.cli.result import CommandResult
from human_to_agent.domain.evidence import Evidence, EvidenceBasis, EvidenceType
from human_to_agent.domain.unknowns import (
    Unknown,
    UnknownCategory,
    UnknownClosure,
    UnknownDisposition,
    UnknownStatus,
    close_unknown,
    reopen_unknown,
)
from human_to_agent.repositories.filesystem import SourceRepository, SourceSnapshot, tree_digest
from human_to_agent.services.asset_writer import write_asset


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
    asset_id = f"unknown.{digest[:16]}"
    relative = f"UNKNOWNS/{digest[:16]}.yaml"
    snapshot = _safe_snapshot(root, workspace_id)
    expected_digest = tree_digest(snapshot)
    existing = snapshot.by_path().get(relative)
    if existing is not None:
        return _reuse_or_reject_unknown(
            root,
            workspace_id,
            relative,
            existing.source_path.read_bytes(),
            title=title,
            description=description,
            category=category,
            owner=owner,
            actor=actor,
            dry_run=dry_run,
            expected_digest=expected_digest,
        )
    now = datetime.now(UTC)
    item = _initial_unknown(workspace_id, asset_id, title, description, category, owner, now)
    try:
        return _write_unknown(
            root,
            workspace_id,
            relative,
            item,
            actor,
            dry_run,
            "unknown add",
            expected_digest,
        )
    except FoundryError as error:
        if error.code != "asset.stale_source":
            raise
        current = _safe_snapshot(root, workspace_id)
        raced = current.by_path().get(relative)
        if raced is None:
            raise
        return _reuse_or_reject_unknown(
            root,
            workspace_id,
            relative,
            raced.source_path.read_bytes(),
            title=title,
            description=description,
            category=category,
            owner=owner,
            actor=actor,
            dry_run=dry_run,
            expected_digest=tree_digest(current),
        )


def _initial_unknown(
    workspace_id: str,
    asset_id: str,
    title: str,
    description: str,
    category: UnknownCategory,
    owner: str,
    now: datetime,
) -> Unknown:
    return Unknown(
        schema_version="1",
        id=asset_id,
        workspace_id=workspace_id,
        revision=1,
        status="open",
        owners=(owner,),
        created_at=now,
        updated_at=now,
        provenance="hta unknown add",
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
        expected_responder_role="agent probe or responsible owner",
        cheapest_probe=(
            "Inspect available workspace evidence first; ask the named owner only for an "
            "unresolved decision."
        ),
        prompt_patch=(
            "Resolve observable facts from evidence; for an owner decision, ask one question "
            "with a recommended answer and its impact or tradeoff."
        ),
        automation_restriction=(
            "Continue only unaffected work; do not automate decisions that depend on this Unknown."
        ),
        allowed_closure_evidence=(
            EvidenceType.formal_rule,
            EvidenceType.real_case,
            EvidenceType.owner_confirmation,
            EvidenceType.repeatable_validation,
            EvidenceType.risk_decision,
        ),
    )


def _reuse_or_reject_unknown(
    root: Path,
    workspace_id: str,
    relative: str,
    content: bytes,
    *,
    title: str,
    description: str,
    category: UnknownCategory,
    owner: str,
    actor: str,
    dry_run: bool,
    expected_digest: str,
) -> CommandResult:
    try:
        existing = Unknown.model_validate(yaml.safe_load(content))
    except (ValueError, yaml.YAMLError) as error:
        raise FoundryError(
            "schema", "unknown.already_exists", "Existing Unknown metadata is invalid."
        ) from error
    expected = _initial_unknown(
        workspace_id,
        existing.id,
        title,
        description,
        category,
        owner,
        existing.created_at,
    )
    if existing != expected:
        raise FoundryError(
            "schema",
            "unknown.already_exists",
            "An Unknown with this title already exists; use unknown update with a higher revision.",
        )
    return write_asset(
        root,
        workspace_id,
        relative,
        content,
        command="unknown add",
        asset_id=existing.id,
        actor=actor,
        dry_run=dry_run,
        expected_source_digest=expected_digest,
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
    relative, item, expected_digest = _find_unknown(root, workspace_id, unknown_id)
    evidence, evidence_digest = _load_evidence(root, workspace_id)
    _require_same_source(expected_digest, evidence_digest)
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
    return _write_unknown(
        root,
        workspace_id,
        relative,
        updated,
        actor,
        dry_run,
        "unknown close",
        expected_digest,
    )


def update_unknown_asset(
    root: Path,
    workspace_id: str,
    *,
    unknown_id: str,
    input_path: Path | None,
    actor: str,
    dry_run: bool,
) -> CommandResult:
    relative, current, expected_digest = _find_unknown(root, workspace_id, unknown_id)
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
    if candidate.revision != current.revision + 1:
        raise FoundryError(
            "schema", "unknown.revision_gap", "Unknown revision must increase by exactly one."
        )
    if (
        candidate.schema_version != current.schema_version
        or candidate.status != current.status
        or candidate.owners != current.owners
        or candidate.created_at != current.created_at
        or candidate.provenance != current.provenance
        or candidate.owner_id != current.owner_id
    ):
        raise FoundryError(
            "schema",
            "unknown.metadata_changed",
            "Unknown identity, ownership, creation, and provenance metadata are immutable.",
        )
    if (
        candidate.unknown_status != current.unknown_status
        or candidate.fact_resolved != current.fact_resolved
        or candidate.closure != current.closure
        or candidate.history != current.history
    ):
        raise FoundryError(
            "evidence",
            "unknown.lifecycle_changed",
            "Unknown lifecycle fields may only change through close or reopen operations.",
        )
    if candidate.updated_at <= current.updated_at:
        raise FoundryError(
            "schema", "unknown.updated_at_not_advanced", "Unknown updated_at must advance."
        )
    return _write_unknown(
        root,
        workspace_id,
        relative,
        candidate,
        actor,
        dry_run,
        "unknown update",
        expected_digest,
    )


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
    relative, item, expected_digest = _find_unknown(root, workspace_id, unknown_id)
    evidence, evidence_digest = _load_evidence(root, workspace_id)
    _require_same_source(expected_digest, evidence_digest)
    if evidence_id not in evidence:
        raise FoundryError("evidence", "unknown.evidence_missing", "Reopen evidence is missing.")
    updated = reopen_unknown(
        item,
        reason=reason,
        actor=actor,
        at=datetime.now(UTC),
        evidence_refs=(evidence_id,),
    )
    return _write_unknown(
        root,
        workspace_id,
        relative,
        updated,
        actor,
        dry_run,
        "unknown reopen",
        expected_digest,
    )


def _find_unknown(root: Path, workspace_id: str, unknown_id: str) -> tuple[str, Unknown, str]:
    snapshot = _safe_snapshot(root, workspace_id)
    for source in snapshot.files:
        if not source.path.startswith("UNKNOWNS/") or not source.path.endswith(".yaml"):
            continue
        item = Unknown.model_validate(yaml.safe_load(source.canonical_content))
        if item.id == unknown_id:
            return source.path, item, tree_digest(snapshot)
    raise FoundryError("schema", "unknown.missing", f"Unknown does not exist: {unknown_id}")


def _load_evidence(root: Path, workspace_id: str) -> tuple[dict[str, Evidence], str]:
    items: dict[str, Evidence] = {}
    snapshot = _safe_snapshot(root, workspace_id)
    for source in snapshot.files:
        if not source.path.startswith("EVIDENCE/") or not source.path.endswith(".yaml"):
            continue
        item = Evidence.model_validate(yaml.safe_load(source.canonical_content))
        items[item.id] = item
    return items, tree_digest(snapshot)


def _require_same_source(expected: str, actual: str) -> None:
    if expected != actual:
        raise FoundryError(
            "filesystem",
            "asset.stale_source",
            "Workspace source changed while the Unknown operation was reading it; retry.",
        )


def _safe_snapshot(root: Path, workspace_id: str) -> SourceSnapshot:
    try:
        return SourceRepository(root).snapshot(workspace_id)
    except FileNotFoundError as error:
        raise FoundryError("schema", "workspace.missing", str(error)) from error
    except (OSError, ValueError) as error:
        raise FoundryError(
            "filesystem",
            "unknown.path_unsafe",
            "Unknown operation cannot read an unsafe workspace path.",
        ) from error


def _write_unknown(
    root: Path,
    workspace_id: str,
    relative: str,
    item: Unknown,
    actor: str,
    dry_run: bool,
    command: str,
    expected_source_digest: str | None = None,
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
        expected_source_digest=expected_source_digest,
    )
