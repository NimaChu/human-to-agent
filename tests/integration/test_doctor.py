from pathlib import Path

from harness_foundry.services.doctor import inspect_workspace


def test_doctor_blocks_secret_without_echoing_value(tmp_path: Path) -> None:
    secret = "AKIAIOSFODNN7EXAMPLE"
    workspace = tmp_path / "workspaces" / "pilot"
    workspace.mkdir(parents=True)
    (workspace / "POLICIES.md").write_text(f"credential: {secret}\n")
    result = inspect_workspace(tmp_path)
    assert result.exit_code == 6
    rendered = str(result.as_dict())
    assert secret not in rendered
    assert result.diagnostics[0]["category"] == "policy"
