import hashlib
import json
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


def workspace_files(workspace: Path) -> dict[str, bytes]:
    return {
        path.relative_to(workspace).as_posix(): path.read_bytes()
        for path in workspace.rglob("*")
        if path.is_file()
    }


def test_file_capture_persists_exact_bytes_relative_evidence_index_and_one_event(
    tmp_path: Path,
) -> None:
    workspace = initialized(tmp_path)
    source = tmp_path / "observed-task.txt"
    supplied = b"input -> reviewed output\r\nowner confirmed\r\n"
    source.write_bytes(supplied)
    result = RUNNER.invoke(
        app,
        ["capture", "record", "--root", str(tmp_path), "-w", "pilot", "--input", str(source)],
    )
    assert result.exit_code == 0, result.stdout
    evidence_files = list((workspace / "EVIDENCE").glob("capture-*.yaml"))
    assert len(evidence_files) == 1
    evidence = yaml.safe_load(evidence_files[0].read_text())
    digest = hashlib.sha256(supplied).hexdigest()
    source_relative = f"EVIDENCE/sources/{digest}.txt"
    assert evidence["content_sha256"] == digest
    assert evidence["type"] == "real_case"
    assert evidence["source"] == source_relative
    assert not Path(evidence["source"]).is_absolute()
    assert (workspace / source_relative).read_bytes() == supplied

    index = yaml.safe_load((workspace / ".foundry/artifact-index.yaml").read_text())
    indexed_source = next(item for item in index["entries"] if item["path"] == source_relative)
    assert indexed_source["sha256"] == digest

    source.unlink()
    validation = RUNNER.invoke(
        app, ["validate", "--root", str(tmp_path), "-w", "pilot", "--format", "json"]
    )
    assert validation.exit_code == 0, validation.stdout
    assert (workspace / source_relative).read_bytes() == supplied

    scope = EventScope(scope_id="pilot", log_path=workspace / ".foundry/events.jsonl")
    events = EventStore().replay(scope).events
    assert len(events) == 1
    assert events[0].asset_refs == (evidence["id"],)
    assert events[0].payload["relative_paths"] == [
        source_relative,
        evidence_files[0].relative_to(workspace).as_posix(),
    ]


def test_text_capture_persists_utf8_source_and_is_idempotent(tmp_path: Path) -> None:
    workspace = initialized(tmp_path)
    supplied = "用户要求把每周发布复核变成 Agent Harness"
    arguments = [
        "capture",
        "record",
        "--root",
        str(tmp_path),
        "-w",
        "pilot",
        "--text",
        supplied,
    ]

    first = RUNNER.invoke(app, arguments)
    assert first.exit_code == 0, first.stdout
    evidence = yaml.safe_load(next((workspace / "EVIDENCE").glob("capture-*.yaml")).read_text())
    source = workspace / evidence["source"]
    assert source.suffix == ".txt"
    assert source.read_bytes() == supplied.encode("utf-8")

    scope = EventScope(scope_id="pilot", log_path=workspace / ".foundry/events.jsonl")
    second = RUNNER.invoke(app, arguments)
    assert second.exit_code == 0, second.stdout
    assert len(EventStore().replay(scope).events) == 1


def test_file_capture_treats_yaml_as_raw_source_not_an_evidence_asset(tmp_path: Path) -> None:
    workspace = initialized(tmp_path)
    supplied = b"user_supplied: true\nnot_an_evidence_asset: true\n"
    source = tmp_path / "sample.yaml"
    source.write_bytes(supplied)

    result = RUNNER.invoke(
        app,
        ["capture", "record", "--root", str(tmp_path), "-w", "pilot", "--input", str(source)],
    )

    assert result.exit_code == 0, result.stdout
    evidence = yaml.safe_load(next((workspace / "EVIDENCE").glob("capture-*.yaml")).read_text())
    assert evidence["source"].endswith(".yaml")
    assert (workspace / evidence["source"]).read_bytes() == supplied
    validation = RUNNER.invoke(app, ["validate", "--root", str(tmp_path), "-w", "pilot"])
    assert validation.exit_code == 0, validation.stdout


def test_capture_rejects_conflicting_non_content_addressed_metadata(tmp_path: Path) -> None:
    workspace = initialized(tmp_path)
    supplied = "owner supplied evidence"
    arguments = [
        "capture",
        "record",
        "--root",
        str(tmp_path),
        "-w",
        "pilot",
        "--text",
        supplied,
    ]
    assert RUNNER.invoke(app, arguments).exit_code == 0
    evidence_path = next((workspace / "EVIDENCE").glob("capture-*.yaml"))
    evidence = yaml.safe_load(evidence_path.read_text())
    evidence["source"] = "EVIDENCE/sources/not-content-addressed.txt"
    evidence_path.write_text(yaml.safe_dump(evidence, sort_keys=False), encoding="utf-8")
    before = workspace_files(workspace)

    result = RUNNER.invoke(app, [*arguments, "--format", "json"])

    assert result.exit_code == 3, result.stdout
    payload = json.loads(result.stdout)
    assert payload["diagnostics"][0]["code"] == "capture.evidence_conflict"
    assert workspace_files(workspace) == before


def test_capture_requires_exactly_one_input_without_writes(tmp_path: Path) -> None:
    workspace = initialized(tmp_path)
    source = tmp_path / "source.txt"
    source.write_text("supplied file", encoding="utf-8")
    before = workspace_files(workspace)

    for arguments in (
        [],
        ["--input", str(source), "--text", "supplied text"],
    ):
        result = RUNNER.invoke(
            app,
            [
                "capture",
                "record",
                "--root",
                str(tmp_path),
                "-w",
                "pilot",
                "--format",
                "json",
                *arguments,
            ],
        )
        assert result.exit_code == 2, result.stdout
        payload = json.loads(result.stdout)
        assert payload["diagnostics"][0]["code"] == "capture.input_choice"
        assert workspace_files(workspace) == before


def test_text_capture_dry_run_writes_nothing(tmp_path: Path) -> None:
    workspace = initialized(tmp_path)
    before = workspace_files(workspace)
    result = RUNNER.invoke(
        app,
        [
            "capture",
            "record",
            "--root",
            str(tmp_path),
            "-w",
            "pilot",
            "--text",
            "Conversation supplied evidence",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert workspace_files(workspace) == before


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
