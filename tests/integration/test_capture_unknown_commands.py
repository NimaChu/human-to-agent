from pathlib import Path

import yaml
from typer.testing import CliRunner

from human_to_agent.cli.app import app
from human_to_agent.domain.events import EventScope
from human_to_agent.repositories.events import EventStore

RUNNER = CliRunner()


def initialized(root: Path) -> Path:
    assert RUNNER.invoke(app, ["init", "--root", str(root)]).exit_code == 0
    assert RUNNER.invoke(app, ["workspace", "new", "pilot", "--root", str(root)]).exit_code == 0
    return root / "workspaces/pilot"


def test_capture_records_hashed_evidence_and_event(tmp_path: Path) -> None:
    workspace = initialized(tmp_path)
    source = tmp_path / "observed-task.txt"
    source.write_text("input -> reviewed output\n")
    result = RUNNER.invoke(
        app,
        ["capture", "record", "--root", str(tmp_path), "-w", "pilot", "--input", str(source)],
    )
    assert result.exit_code == 0, result.stdout
    evidence_files = list((workspace / "EVIDENCE").glob("capture-*.yaml"))
    assert len(evidence_files) == 1
    evidence = yaml.safe_load(evidence_files[0].read_text())
    assert evidence["content_sha256"] and evidence["type"] == "real_case"
    scope = EventScope(scope_id="pilot", log_path=workspace / ".foundry/events.jsonl")
    assert len(EventStore().replay(scope).events) == 1


def test_unknown_add_creates_valid_explicit_unknown(tmp_path: Path) -> None:
    workspace = initialized(tmp_path)
    result = RUNNER.invoke(
        app,
        [
            "unknown",
            "add",
            "--root",
            str(tmp_path),
            "-w",
            "pilot",
            "--title",
            "Which approval role owns release?",
            "--category",
            "responsibility",
        ],
    )
    assert result.exit_code == 0, result.stdout
    unknown_files = list((workspace / "UNKNOWNS").glob("*.yaml"))
    assert len(unknown_files) == 1
    unknown = yaml.safe_load(unknown_files[0].read_text())
    assert unknown["unknown_status"] == "new"
    assert unknown["confidence_basis"] == "unverified"
    assert unknown["cheapest_probe"]


def test_unknown_close_and_reopen_preserve_evidence_history(tmp_path: Path) -> None:
    workspace = initialized(tmp_path)
    source = tmp_path / "owner-decision.txt"
    source.write_text("Owner confirms the release role.\n")
    assert (
        RUNNER.invoke(
            app,
            ["capture", "record", "--root", str(tmp_path), "-w", "pilot", "--input", str(source)],
        ).exit_code
        == 0
    )
    assert (
        RUNNER.invoke(
            app,
            ["unknown", "add", "--root", str(tmp_path), "-w", "pilot", "--title", "Release role"],
        ).exit_code
        == 0
    )
    unknown_path = next((workspace / "UNKNOWNS").glob("*.yaml"))
    unknown_id = yaml.safe_load(unknown_path.read_text())["id"]
    evidence_id = yaml.safe_load(next((workspace / "EVIDENCE").glob("*.yaml")).read_text())["id"]
    close = RUNNER.invoke(
        app,
        [
            "unknown",
            "close",
            "--root",
            str(tmp_path),
            "-w",
            "pilot",
            "--id",
            unknown_id,
            "--evidence",
            evidence_id,
            "--disposition",
            "resolved",
        ],
    )
    assert close.exit_code == 0, close.stdout
    reopen = RUNNER.invoke(
        app,
        [
            "unknown",
            "reopen",
            "--root",
            str(tmp_path),
            "-w",
            "pilot",
            "--id",
            unknown_id,
            "--evidence",
            evidence_id,
            "--reason",
            "A contradictory case appeared",
        ],
    )
    assert reopen.exit_code == 0, reopen.stdout
    current = yaml.safe_load(unknown_path.read_text())
    assert current["unknown_status"] == "reopened"
    assert current["closure"]["disposition"] == "resolved"
    assert len(current["history"]) == 2
