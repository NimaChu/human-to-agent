from pathlib import Path

from human_to_agent.repositories.filesystem import SourceRepository
from human_to_agent.services.changes import build_artifact_index


def test_autonomy_approval_has_a_distinct_artifact_index_identity(tmp_path: Path) -> None:
    workspace = tmp_path / "workspaces/pilot"
    readiness = workspace / "LOOP-READINESS"
    readiness.mkdir(parents=True)
    (workspace / "workspace.yaml").write_text(
        "schema_version: '1'\nid: workspace.pilot\n", encoding="utf-8"
    )
    (readiness / "assessment.yaml").write_text("assessment_id: readiness.pilot\n", encoding="utf-8")
    (readiness / "autonomy-approval.yaml").write_text(
        "workspace_id: pilot\nassessment_id: readiness.pilot\nlevel: h0\n",
        encoding="utf-8",
    )

    index = build_artifact_index(SourceRepository(tmp_path).snapshot("pilot"))
    by_path = {entry.path: entry.asset_id for entry in index.entries}

    assert by_path["LOOP-READINESS/assessment.yaml"] == "readiness.pilot"
    assert by_path["LOOP-READINESS/autonomy-approval.yaml"] == ("autonomy-approval.pilot.h0")
    assert len(set(by_path.values())) == len(by_path)
