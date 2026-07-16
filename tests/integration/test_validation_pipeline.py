from datetime import UTC, datetime
from pathlib import Path

import yaml

from human_to_agent.repositories.filesystem import SourceRepository
from human_to_agent.repositories.index import ArtifactIndex, ArtifactIndexEntry
from human_to_agent.services.changes import build_artifact_index
from human_to_agent.services.schema_catalog import DEFAULT_MODELS
from human_to_agent.validators.workspace import validate_workspace

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


def test_non_normative_asset_yaml_is_indexed_without_schema_or_yaml_parsing(
    tmp_path: Path,
) -> None:
    repository = write_workspace(tmp_path, manifest())
    workspace = tmp_path / "workspaces" / "pilot"
    asset = workspace / "ASSETS" / "roles.yaml"
    asset.parent.mkdir()
    asset_bytes = b"roles:\n  - !custom-role\n    name: editor\n"
    asset.write_bytes(asset_bytes)

    snapshot = repository.snapshot("pilot")
    report = validate_workspace(snapshot, DEFAULT_MODELS)
    index = build_artifact_index(snapshot)

    source = snapshot.by_path()["ASSETS/roles.yaml"]
    assert source.canonical_content == asset_bytes
    assert report.passed
    assert index.by_path()["ASSETS/roles.yaml"].sha256 == source.sha256


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


def test_every_asset_workspace_id_must_match_manifest(tmp_path: Path) -> None:
    repository = write_workspace(tmp_path, manifest())
    workspace = tmp_path / "workspaces" / "pilot"
    readiness: dict[str, object] = {
        "assessment_id": "readiness.pilot",
        "workspace_id": "different-workspace",
        "policy_version": "1",
        "result": "not_ready",
        "dimensions": {},
        "evidence_gaps": [],
        "risks": [],
        "next_actions": [],
        "recommended_ceiling": "h0",
        "approved_autonomy": None,
    }
    (workspace / "LOOP-READINESS").mkdir()
    (workspace / "LOOP-READINESS/assessment.yaml").write_text(
        yaml.safe_dump(readiness, sort_keys=False), encoding="utf-8"
    )

    report = validate_workspace(repository.snapshot("pilot"), DEFAULT_MODELS)

    assert any(
        item.code == "asset.workspace_mismatch" and item.path == "LOOP-READINESS/assessment.yaml"
        for item in report.diagnostics
    )
