from datetime import UTC, datetime
from pathlib import Path

import yaml

from harness_foundry.repositories.filesystem import SourceRepository
from harness_foundry.repositories.index import ArtifactIndex, ArtifactIndexEntry
from harness_foundry.services.schema_catalog import DEFAULT_MODELS
from harness_foundry.validators.workspace import validate_workspace

NOW = datetime(2026, 7, 10, tzinfo=UTC)


def manifest() -> dict[str, object]:
    return {
        "schema_version": "1",
        "id": "workspace.pilot",
        "workspace_id": "workspace.pilot",
        "revision": 1,
        "status": "active",
        "owners": ["owner"],
        "created_at": NOW.isoformat(),
        "updated_at": NOW.isoformat(),
        "provenance": "human",
        "links": [],
        "evidence_refs": [],
        "name": "Pilot",
        "purpose": "Validate the source repository",
        "current_stage": 1,
        "risk_level": "low",
        "owner_id": "owner",
        "autonomy_level": "h0",
    }


def write_workspace(root: Path, data: dict[str, object]) -> SourceRepository:
    workspace = root / "workspaces" / "pilot"
    workspace.mkdir(parents=True)
    (workspace / "workspace.yaml").write_text(
        yaml.safe_dump(data, sort_keys=True),
        encoding="utf-8",
    )
    return SourceRepository(root)


def test_valid_workspace_has_no_diagnostics(tmp_path: Path) -> None:
    repository = write_workspace(tmp_path, manifest())
    report = validate_workspace(repository.snapshot("pilot"), DEFAULT_MODELS)
    assert report.passed
    assert report.diagnostics == ()


def test_schema_errors_are_reported_without_stopping_other_files(tmp_path: Path) -> None:
    repository = write_workspace(tmp_path, manifest() | {"name": ""})
    workspace = tmp_path / "workspaces" / "pilot"
    (workspace / "TASK-CONTRACT").mkdir()
    (workspace / "TASK-CONTRACT" / "contract.yaml").write_text("business_goal: ''\n")
    report = validate_workspace(repository.snapshot("pilot"), DEFAULT_MODELS)
    assert len(report.diagnostics) >= 2
    assert all(item.category == "schema" for item in report.diagnostics)


def test_missing_cross_asset_reference_is_reported(tmp_path: Path) -> None:
    data = manifest() | {"links": ["skill.missing"]}
    repository = write_workspace(tmp_path, data)
    report = validate_workspace(repository.snapshot("pilot"), DEFAULT_MODELS)
    assert any(
        item.category == "reference" and item.target_id == "skill.missing"
        for item in report.diagnostics
    )


def test_artifact_index_detects_unrecorded_source_change(tmp_path: Path) -> None:
    repository = write_workspace(tmp_path, manifest())
    snapshot = repository.snapshot("pilot")
    source = snapshot.files[0]
    index = ArtifactIndex(
        schema_version="1",
        entries=(
            ArtifactIndexEntry(
                asset_id="workspace.pilot",
                path=source.path,
                revision=1,
                asset_schema_version="1",
                sha256="0" * 64,
            ),
        ),
    )
    report = validate_workspace(snapshot, DEFAULT_MODELS, recorded_index=index)
    assert any(
        item.category == "filesystem" and item.code == "source.unrecorded"
        for item in report.diagnostics
    )
