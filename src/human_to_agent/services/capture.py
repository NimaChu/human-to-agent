from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import yaml

from human_to_agent.cli.errors import FoundryError
from human_to_agent.cli.result import CommandResult
from human_to_agent.domain.evidence import Evidence, EvidenceBasis, EvidenceType
from human_to_agent.repositories.filesystem import SourceRepository
from human_to_agent.services.asset_writer import write_assets

SAFE_SOURCE_SUFFIX = re.compile(r"^\.[a-z0-9]{1,16}$")


def _source_bytes_and_suffix(input_path: Path | None, text: str | None) -> tuple[bytes, str]:
    if (input_path is None) == (text is None):
        raise FoundryError(
            "usage",
            "capture.input_choice",
            "Choose exactly one of --input and --text.",
        )
    if text is not None:
        return text.encode("utf-8"), ".txt"
    if input_path is None or not input_path.is_file():
        raise FoundryError("usage", "capture.input_missing", "--input must name a readable file.")
    try:
        content = input_path.read_bytes()
    except OSError as error:
        raise FoundryError(
            "usage", "capture.input_missing", "--input must name a readable file."
        ) from error
    suffix = input_path.suffix.lower()
    return content, suffix if SAFE_SOURCE_SUFFIX.fullmatch(suffix) else ".bin"


def _existing_capture(
    root: Path,
    workspace_id: str,
    *,
    evidence_relative: str,
    asset_id: str,
    digest: str,
) -> tuple[str, bytes] | None:
    try:
        workspace = SourceRepository(root).workspace_path(workspace_id)
    except (FileNotFoundError, ValueError) as error:
        raise FoundryError("schema", "workspace.missing", str(error)) from error
    evidence_path = workspace / evidence_relative
    if not evidence_path.is_file():
        return None
    try:
        raw = yaml.safe_load(evidence_path.read_text(encoding="utf-8"))
        existing = Evidence.model_validate(raw)
    except (ValueError, yaml.YAMLError) as error:
        raise FoundryError(
            "schema",
            "capture.evidence_conflict",
            f"Existing capture metadata is invalid: {evidence_relative}",
        ) from error
    source = PurePosixPath(existing.source)
    if (
        existing.id != asset_id
        or existing.content_sha256 != digest
        or source.is_absolute()
        or source.parts[:2] != ("EVIDENCE", "sources")
        or len(source.parts) != 3
        or not source.name.startswith(f"{digest}.")
        or ".." in source.parts
    ):
        raise FoundryError(
            "schema",
            "capture.evidence_conflict",
            f"Existing capture conflicts with supplied content: {evidence_relative}",
        )
    return source.as_posix(), evidence_path.read_bytes()


def record_capture(
    root: Path,
    workspace_id: str,
    input_path: Path | None,
    *,
    text: str | None = None,
    actor: str,
    dry_run: bool,
) -> CommandResult:
    content, suffix = _source_bytes_and_suffix(input_path, text)
    digest = hashlib.sha256(content).hexdigest()
    source_relative = f"EVIDENCE/sources/{digest}{suffix}"
    captured_at = datetime.now(UTC)
    asset_id = f"evidence.capture.{digest[:16]}"
    evidence_relative = f"EVIDENCE/capture-{digest[:16]}.yaml"
    existing = _existing_capture(
        root,
        workspace_id,
        evidence_relative=evidence_relative,
        asset_id=asset_id,
        digest=digest,
    )
    if existing is not None:
        source_relative, rendered = existing
        return write_assets(
            root,
            workspace_id,
            ((source_relative, content), (evidence_relative, rendered)),
            command="capture record",
            asset_ids=(asset_id,),
            actor=actor,
            dry_run=dry_run,
        )
    evidence = Evidence(
        schema_version="1",
        id=asset_id,
        workspace_id=workspace_id,
        revision=1,
        status="captured",
        owners=(actor,),
        created_at=captured_at,
        updated_at=captured_at,
        provenance="hta capture record",
        links=(),
        evidence_refs=(),
        type=EvidenceType.real_case,
        source=source_relative,
        locator="entire normative source copy",
        captured_by=actor,
        captured_at=captured_at,
        content_summary="Exact bytes supplied to Human to Agent and copied into this workspace.",
        claim="The recorded bytes were supplied to the capture operation.",
        basis=EvidenceBasis.observed,
        applicability_scope=(workspace_id,),
        validity_conditions=("The normative source copy matches the recorded content hash.",),
        invalidation_conditions=(
            "The normative source copy changes or the owner withdraws the capture.",
        ),
        content_sha256=digest,
    )
    rendered = yaml.safe_dump(
        evidence.model_dump(mode="json"), sort_keys=False, allow_unicode=True
    ).encode()
    return write_assets(
        root,
        workspace_id,
        ((source_relative, content), (evidence_relative, rendered)),
        command="capture record",
        asset_ids=(asset_id,),
        actor=actor,
        dry_run=dry_run,
    )
