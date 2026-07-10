from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import yaml

from harness_foundry.cli.errors import FoundryError
from harness_foundry.cli.result import CommandResult
from harness_foundry.domain.evidence import Evidence, EvidenceBasis, EvidenceType
from harness_foundry.services.asset_writer import write_asset


def record_capture(
    root: Path,
    workspace_id: str,
    input_path: Path | None,
    *,
    actor: str,
    dry_run: bool,
) -> CommandResult:
    if input_path is None or not input_path.is_file():
        raise FoundryError("usage", "capture.input_missing", "--input must name a readable file.")
    content = input_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    captured_at = datetime.now(UTC)
    asset_id = f"evidence.capture.{digest[:16]}"
    evidence = Evidence(
        schema_version="1",
        id=asset_id,
        workspace_id=workspace_id,
        revision=1,
        status="captured",
        owners=(actor,),
        created_at=captured_at,
        updated_at=captured_at,
        provenance="hf capture record",
        links=(),
        evidence_refs=(),
        type=EvidenceType.real_case,
        source=str(input_path.resolve()),
        locator="entire file",
        captured_by=actor,
        captured_at=captured_at,
        content_summary="Hashed real-task capture supplied to Harness Foundry.",
        claim="The captured bytes are a direct input or output from a real task.",
        basis=EvidenceBasis.observed,
        applicability_scope=(workspace_id,),
        validity_conditions=("The recorded content hash matches the supplied bytes.",),
        invalidation_conditions=("The source bytes change or the owner withdraws the capture.",),
        content_sha256=digest,
    )
    rendered = yaml.safe_dump(
        evidence.model_dump(mode="json"), sort_keys=False, allow_unicode=True
    ).encode()
    return write_asset(
        root,
        workspace_id,
        f"EVIDENCE/capture-{digest[:16]}.yaml",
        rendered,
        command="capture record",
        asset_id=asset_id,
        actor=actor,
        dry_run=dry_run,
    )
