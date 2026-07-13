from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import yaml

from human_to_agent.cli.errors import FoundryError
from human_to_agent.cli.result import CommandResult
from human_to_agent.domain.evidence import Evidence, EvidenceBasis, EvidenceType
from human_to_agent.repositories.filesystem import SourceRepository, tree_digest
from human_to_agent.repositories.index import ArtifactIndex
from human_to_agent.services.asset_writer import write_assets

SAFE_SOURCE_SUFFIX = re.compile(r"^\.[a-z0-9]{1,16}$")


def _capture_evidence(
    *,
    workspace_id: str,
    asset_id: str,
    source_relative: str,
    digest: str,
    actor: str,
    captured_at: datetime,
    evidence_type: EvidenceType = EvidenceType.real_case,
) -> Evidence:
    return Evidence(
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
        type=evidence_type,
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
    source_relative: str,
) -> tuple[str, bytes] | None:
    try:
        snapshot = SourceRepository(root).snapshot(workspace_id)
        workspace = snapshot.workspace_path
    except FileNotFoundError as error:
        raise FoundryError("schema", "workspace.missing", str(error)) from error
    except ValueError as error:
        raise FoundryError("filesystem", "capture.path_unsafe", str(error)) from error
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
    expected = _capture_evidence(
        workspace_id=workspace_id,
        asset_id=asset_id,
        source_relative=source_relative,
        digest=digest,
        actor=existing.captured_by,
        captured_at=existing.captured_at,
        evidence_type=existing.type,
    )
    if (
        existing != expected
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
    index_path = workspace / ".foundry/artifact-index.yaml"
    try:
        index = ArtifactIndex.model_validate(yaml.safe_load(index_path.read_text(encoding="utf-8")))
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise FoundryError(
            "schema",
            "capture.evidence_conflict",
            f"Existing capture is not anchored by a valid artifact index: {evidence_relative}",
        ) from error
    current_source = snapshot.by_path().get(evidence_relative)
    recorded = index.by_path().get(evidence_relative)
    if current_source is None or recorded is None or current_source.sha256 != recorded.sha256:
        raise FoundryError(
            "schema",
            "capture.evidence_conflict",
            f"Existing capture differs from its recorded metadata: {evidence_relative}",
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
    evidence_type: EvidenceType = EvidenceType.real_case,
) -> CommandResult:
    content, suffix = _source_bytes_and_suffix(input_path, text)
    digest = hashlib.sha256(content).hexdigest()
    source_relative = f"EVIDENCE/sources/{digest}{suffix}"
    asset_id = f"evidence.capture.{digest[:16]}"
    evidence_relative = f"EVIDENCE/capture-{digest[:16]}.yaml"
    try:
        expected_source_digest = tree_digest(SourceRepository(root).snapshot(workspace_id))
    except FileNotFoundError as error:
        raise FoundryError("schema", "workspace.missing", str(error)) from error
    except (OSError, ValueError) as error:
        raise FoundryError("filesystem", "capture.path_unsafe", str(error)) from error
    existing = _existing_capture(
        root,
        workspace_id,
        evidence_relative=evidence_relative,
        asset_id=asset_id,
        digest=digest,
        source_relative=source_relative,
    )
    if existing is not None:
        existing_metadata = Evidence.model_validate(yaml.safe_load(existing[1]))
        if existing_metadata.type is not evidence_type:
            raise FoundryError(
                "schema",
                "capture.evidence_conflict",
                "Existing capture has a different evidence type.",
            )
        source_relative, rendered = existing
        return write_assets(
            root,
            workspace_id,
            ((source_relative, content), (evidence_relative, rendered)),
            command="capture record",
            asset_ids=(asset_id,),
            actor=actor,
            dry_run=dry_run,
            expected_source_digest=expected_source_digest,
        )
    captured_at = datetime.now(UTC)
    evidence = _capture_evidence(
        workspace_id=workspace_id,
        asset_id=asset_id,
        source_relative=source_relative,
        digest=digest,
        actor=actor,
        captured_at=captured_at,
        evidence_type=evidence_type,
    )
    rendered = yaml.safe_dump(
        evidence.model_dump(mode="json"), sort_keys=False, allow_unicode=True
    ).encode()
    try:
        return write_assets(
            root,
            workspace_id,
            ((source_relative, content), (evidence_relative, rendered)),
            command="capture record",
            asset_ids=(asset_id,),
            actor=actor,
            dry_run=dry_run,
            expected_source_digest=expected_source_digest,
        )
    except FoundryError as error:
        if error.code != "asset.stale_source":
            raise
        raced = _existing_capture(
            root,
            workspace_id,
            evidence_relative=evidence_relative,
            asset_id=asset_id,
            digest=digest,
            source_relative=source_relative,
        )
        if raced is None:
            current_digest = tree_digest(SourceRepository(root).snapshot(workspace_id))
            return write_assets(
                root,
                workspace_id,
                ((source_relative, content), (evidence_relative, rendered)),
                command="capture record",
                asset_ids=(asset_id,),
                actor=actor,
                dry_run=dry_run,
                expected_source_digest=current_digest,
            )
        raced_metadata = Evidence.model_validate(yaml.safe_load(raced[1]))
        if raced_metadata.type is not evidence_type:
            raise FoundryError(
                "schema",
                "capture.evidence_conflict",
                "Concurrent capture recorded a different evidence type.",
            ) from error
        raced_source, raced_rendered = raced
        return write_assets(
            root,
            workspace_id,
            ((raced_source, content), (evidence_relative, raced_rendered)),
            command="capture record",
            asset_ids=(asset_id,),
            actor=actor,
            dry_run=dry_run,
        )
