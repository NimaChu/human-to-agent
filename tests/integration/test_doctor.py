import os
import subprocess
from pathlib import Path

import pytest

from human_to_agent.repositories.transactions import TransactionBusyError
from human_to_agent.services.doctor import inspect_workspace
from human_to_agent.services.recovery import RecoveryService
from human_to_agent.services.validation import validate_root


def link_directory(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as error:
        if os.name != "nt":
            pytest.skip(f"directory links are unavailable: {error}")
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode:
            pytest.skip(f"directory links are unavailable: {completed.stderr or completed.stdout}")


def unlink_directory_link(path: Path) -> None:
    if path.exists() or path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        os.rmdir(path)


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


def test_doctor_scans_normative_state_directory_for_secrets(tmp_path: Path) -> None:
    secret = "AKIAIOSFODNN7EXAMPLE"
    state = tmp_path / "workspaces/pilot/state"
    state.mkdir(parents=True)
    (state / "POLICIES.md").write_text(f"credential: {secret}\n", encoding="utf-8")

    result = inspect_workspace(tmp_path)

    assert result.exit_code == 6
    assert result.diagnostics[0]["path"] == "workspaces/pilot/state/POLICIES.md"
    assert secret not in str(result.as_dict())


def test_doctor_rejects_linked_workspace_source_before_reading_external_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspaces/pilot"
    workspace.mkdir(parents=True)
    external = tmp_path / "external-secret.txt"
    external.write_bytes(b"credential: must-never-be-read")
    linked = workspace / "POLICIES.md"
    try:
        linked.symlink_to(external)
    except OSError as error:
        pytest.skip(f"file symlinks are unavailable: {error}")
    original_read_bytes = Path.read_bytes

    def reject_external_read(path: Path) -> bytes:
        if path.resolve() == external.resolve():
            raise AssertionError("doctor read bytes through a workspace link")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", reject_external_read)

    result = inspect_workspace(tmp_path)

    assert result.exit_code == 8
    assert result.diagnostics == [
        {
            "category": "filesystem",
            "code": "filesystem.unsafe_workspace_path",
            "message": "Workspace source contains a symlink, junction, or out-of-bound path.",
            "path": "workspaces/pilot",
        }
    ]


def test_doctor_rejects_linked_workspaces_root_without_traversing_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    external = tmp_path.parent / f"{tmp_path.name}-external-workspaces"
    external_workspace = external / "pilot"
    external_workspace.mkdir(parents=True)
    secret = external_workspace / "POLICIES.md"
    secret.write_bytes(b"credential: must-never-be-read")
    workspaces_link = tmp_path / "workspaces"
    link_directory(workspaces_link, external)
    original_read_bytes = Path.read_bytes

    def reject_external_read(path: Path) -> bytes:
        if path.resolve().is_relative_to(external.resolve()):
            raise AssertionError("doctor traversed the linked workspaces root")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", reject_external_read)
    try:
        result = inspect_workspace(tmp_path)

        assert result.exit_code == 8
        assert result.diagnostics == [
            {
                "category": "filesystem",
                "code": "filesystem.unsafe_workspace_root",
                "message": "Workspace root cannot be a symlink or junction.",
                "path": "workspaces",
            }
        ]
    finally:
        unlink_directory_link(workspaces_link)
        secret.unlink()
        external_workspace.rmdir()
        external.rmdir()


def test_doctor_rejects_linked_workspace_before_reading_external_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "workspaces").mkdir()
    external = tmp_path / "external-workspace"
    external.mkdir()
    secret = external / "POLICIES.md"
    secret.write_bytes(b"credential: must-never-be-read")
    linked = tmp_path / "workspaces/pilot"
    link_directory(linked, external)
    original_read_bytes = Path.read_bytes

    def reject_external_read(path: Path) -> bytes:
        if path.resolve().is_relative_to(external.resolve()):
            raise AssertionError("doctor traversed a linked workspace")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", reject_external_read)
    try:
        result = inspect_workspace(tmp_path)

        assert result.exit_code == 8
        assert result.diagnostics[0]["category"] == "filesystem"
        assert result.diagnostics[0]["code"] == "filesystem.unsafe_workspace_path"
    finally:
        unlink_directory_link(linked)


def test_doctor_reports_invalid_recovery_journal_as_transaction_error(tmp_path: Path) -> None:
    transaction = tmp_path / "state/transactions/tampered"
    transaction.mkdir(parents=True)
    (transaction / "journal.json").write_text("{}", encoding="utf-8")

    result = inspect_workspace(tmp_path)

    assert result.status == "error"
    assert result.exit_code == 8
    assert result.diagnostics == [
        {
            "category": "transaction",
            "code": "transaction.recovery_invalid",
            "message": "Recovery state is invalid: transaction journal workspace id is invalid",
            "path": "state/transactions",
        }
    ]


@pytest.mark.parametrize(
    "error",
    (TransactionBusyError("recovery lock is busy"), OSError("recovery path is unreadable")),
)
def test_doctor_maps_unavailable_recovery_to_stable_exit_8(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def fail_recovery(_service: RecoveryService) -> tuple[object, ...]:
        raise error

    monkeypatch.setattr(RecoveryService, "recover_all", fail_recovery)

    result = inspect_workspace(tmp_path)

    assert result.status == "error"
    assert result.exit_code == 8
    assert result.diagnostics == [
        {
            "category": "transaction",
            "code": "transaction.recovery_unavailable",
            "message": f"Recovery could not be completed: {error}",
            "path": "state/transactions",
        }
    ]


def test_validate_rejects_linked_workspaces_root_as_filesystem_error(tmp_path: Path) -> None:
    (tmp_path / "human-to-agent.yaml").write_text('schema_version: "1"\n', encoding="utf-8")
    external = tmp_path.parent / f"{tmp_path.name}-external-validation"
    (external / "pilot").mkdir(parents=True)
    (external / "pilot/workspace.yaml").write_text("external: true\n", encoding="utf-8")
    workspaces_link = tmp_path / "workspaces"
    link_directory(workspaces_link, external)
    try:
        result = validate_root(tmp_path, None)

        assert result.exit_code == 8
        assert result.diagnostics[0]["category"] == "filesystem"
        assert result.diagnostics[0]["code"] == "filesystem.unsafe_workspace_root"
    finally:
        unlink_directory_link(workspaces_link)
        (external / "pilot/workspace.yaml").unlink()
        (external / "pilot").rmdir()
        external.rmdir()


def test_validate_classifies_linked_workspace_as_filesystem_error(tmp_path: Path) -> None:
    (tmp_path / "human-to-agent.yaml").write_text('schema_version: "1"\n', encoding="utf-8")
    (tmp_path / "workspaces").mkdir()
    external = tmp_path / "external-workspace"
    external.mkdir()
    (external / "workspace.yaml").write_text("external: true\n", encoding="utf-8")
    linked = tmp_path / "workspaces/pilot"
    link_directory(linked, external)
    try:
        result = validate_root(tmp_path, "pilot")

        assert result.exit_code == 8
        assert result.diagnostics[0]["category"] == "filesystem"
        assert result.diagnostics[0]["code"] == "filesystem.unsafe_workspace_path"
    finally:
        unlink_directory_link(linked)


def test_validate_ignores_hidden_staging_directories(tmp_path: Path) -> None:
    (tmp_path / "human-to-agent.yaml").write_text('schema_version: "1"\n', encoding="utf-8")
    staging = tmp_path / "workspaces/.pilot.staging-interrupted"
    staging.mkdir(parents=True)
    (staging / "workspace.yaml").write_text("not: a published workspace\n", encoding="utf-8")

    result = validate_root(tmp_path, None)

    assert result.exit_code == 0
    assert result.diagnostics == []
