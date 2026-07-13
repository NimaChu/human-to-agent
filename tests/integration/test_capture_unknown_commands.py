import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from threading import Barrier, Event, Lock, get_ident

import pytest
import yaml
from typer.testing import CliRunner

from human_to_agent.cli.app import app
from human_to_agent.cli.errors import FoundryError
from human_to_agent.domain.events import EventScope
from human_to_agent.domain.unknowns import UnknownCategory
from human_to_agent.repositories.events import EventStore
from human_to_agent.repositories.filesystem import SourceRepository, tree_digest
from human_to_agent.repositories.transactions import TransactionManager
from human_to_agent.services import capture as capture_service
from human_to_agent.services import changes as change_service
from human_to_agent.services import unknown_operations as unknown_service
from human_to_agent.services.asset_writer import write_asset
from human_to_agent.services.capture import record_capture

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


def test_capture_records_hashed_evidence_and_event(
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


def test_same_capture_is_idempotent_when_repeated_by_another_maintainer(tmp_path: Path) -> None:
    workspace = initialized(tmp_path)
    first = record_capture(
        tmp_path,
        "pilot",
        None,
        text="same owner-supplied evidence",
        actor="first-maintainer",
        dry_run=False,
    )
    second = record_capture(
        tmp_path,
        "pilot",
        None,
        text="same owner-supplied evidence",
        actor="second-maintainer",
        dry_run=False,
    )

    assert first.status == second.status == "ok"
    scope = EventScope(scope_id="pilot", log_path=workspace / ".foundry/events.jsonl")
    assert len(EventStore().replay(scope).events) == 1


def test_same_concurrent_capture_preserves_first_writer_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = initialized(tmp_path)
    original_existing = capture_service._existing_capture
    both_observed = Barrier(2)
    counter_lock = Lock()
    calls = 0

    def synchronized_existing(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        nonlocal calls
        result = original_existing(*args, **kwargs)  # type: ignore[arg-type]
        with counter_lock:
            calls += 1
            synchronize = calls <= 2
        if synchronize:
            both_observed.wait(timeout=10)
        return result

    monkeypatch.setattr(capture_service, "_existing_capture", synchronized_existing)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                capture_service.record_capture,
                tmp_path,
                "pilot",
                None,
                text="one concurrently supplied fact",
                actor=actor,
                dry_run=False,
            )
            for actor in ("first-maintainer", "second-maintainer")
        ]
        results = [future.result(timeout=20) for future in futures]

    assert all(result.status == "ok" for result in results)
    evidence = yaml.safe_load(next((workspace / "EVIDENCE").glob("capture-*.yaml")).read_text())
    assert evidence["captured_by"] in {"first-maintainer", "second-maintainer"}
    assert evidence["owners"] == [evidence["captured_by"]]
    assert evidence["created_at"] == evidence["updated_at"] == evidence["captured_at"]
    scope = EventScope(scope_id="pilot", log_path=workspace / ".foundry/events.jsonl")
    assert len(EventStore().replay(scope).events) == 1


def test_capture_reports_unsafe_workspace_path_as_filesystem_error(tmp_path: Path) -> None:
    assert RUNNER.invoke(app, ["init", "--root", str(tmp_path)]).exit_code == 0

    result = RUNNER.invoke(
        app,
        [
            "capture",
            "record",
            "--root",
            str(tmp_path),
            "-w",
            "../outside",
            "--text",
            "supplied evidence",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 8, result.stdout
    payload = json.loads(result.stdout)
    assert payload["diagnostics"][0]["code"] == "capture.path_unsafe"


def test_two_concurrent_captures_preserve_both_artifact_index_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = initialized(tmp_path)
    original_commit = TransactionManager.commit
    both_plans_are_prepared = Barrier(2)

    def synchronized_commit(manager: TransactionManager, plan: object, event: object) -> object:
        both_plans_are_prepared.wait(timeout=10)
        return original_commit(manager, plan, event)  # type: ignore[arg-type]

    monkeypatch.setattr(TransactionManager, "commit", synchronized_commit)
    supplied = ("first independently supplied fact", "second independently supplied fact")
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(
                lambda text: record_capture(
                    tmp_path,
                    "pilot",
                    None,
                    text=text,
                    actor="maintainer",
                    dry_run=False,
                ),
                supplied,
            )
        )
    assert all(result.status == "ok" for result in results)

    index = yaml.safe_load((workspace / ".foundry/artifact-index.yaml").read_text())
    indexed_paths = {entry["path"] for entry in index["entries"]}
    for text in supplied:
        digest = hashlib.sha256(text.encode()).hexdigest()
        assert f"EVIDENCE/sources/{digest}.txt" in indexed_paths
        assert f"EVIDENCE/capture-{digest[:16]}.yaml" in indexed_paths


def test_record_change_cannot_overwrite_a_concurrent_capture_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = initialized(tmp_path)
    prepared = Event()
    release_record = Event()
    record_thread: dict[str, int] = {}
    original_render = change_service.render_artifact_index
    original_read_bytes = Path.read_bytes

    def delayed_render(index: object) -> bytes:
        rendered = original_render(index)  # type: ignore[arg-type]
        prepared.set()
        assert release_record.wait(timeout=10)
        return rendered

    def force_record_attempt(path: Path) -> bytes:
        if get_ident() == record_thread.get("id") and path.name == "artifact-index.yaml":
            return b""
        return original_read_bytes(path)

    monkeypatch.setattr(change_service, "render_artifact_index", delayed_render)
    monkeypatch.setattr(Path, "read_bytes", force_record_attempt)

    def record() -> object:
        record_thread["id"] = get_ident()
        return change_service.record_change(tmp_path, "pilot")

    with ThreadPoolExecutor(max_workers=2) as executor:
        record_future = executor.submit(record)
        assert prepared.wait(timeout=10)
        capture_future = executor.submit(
            record_capture,
            tmp_path,
            "pilot",
            None,
            text="concurrent captured fact",
            actor="maintainer",
            dry_run=False,
        )
        try:
            capture_result = capture_future.result(timeout=2)
        except TimeoutError:
            capture_result = None
        release_record.set()
        record_future.result(timeout=10)
        if capture_result is None:
            capture_result = capture_future.result(timeout=10)
    assert capture_result.status == "ok"

    digest = hashlib.sha256(b"concurrent captured fact").hexdigest()
    index = yaml.safe_load((workspace / ".foundry/artifact-index.yaml").read_text())
    indexed_paths = {entry["path"] for entry in index["entries"]}
    assert f"EVIDENCE/sources/{digest}.txt" in indexed_paths
    assert f"EVIDENCE/capture-{digest[:16]}.yaml" in indexed_paths


def test_capture_rejects_unrelated_unrecorded_changes_without_laundering_them(
    tmp_path: Path,
) -> None:
    workspace = initialized(tmp_path)
    (workspace / "README.md").write_text("unrecorded owner edit\n", encoding="utf-8")
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
            "new supplied evidence",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 8, result.stdout
    payload = json.loads(result.stdout)
    assert payload["diagnostics"][0]["code"] == "asset.unrecorded_changes"
    assert workspace_files(workspace) == before


def test_capture_reports_malformed_artifact_index_without_writing(tmp_path: Path) -> None:
    workspace = initialized(tmp_path)
    index = workspace / ".foundry/artifact-index.yaml"
    index.write_text("entries: [unterminated\n", encoding="utf-8")
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
            "new supplied evidence",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 8, result.stdout
    payload = json.loads(result.stdout)
    assert payload["diagnostics"][0]["code"] == "asset.unrecorded_changes"
    assert workspace_files(workspace) == before


def test_asset_writer_rejects_a_stale_read_before_replacing_source(tmp_path: Path) -> None:
    workspace = initialized(tmp_path)
    expected = tree_digest(SourceRepository(tmp_path).snapshot("pilot"))
    changed = RUNNER.invoke(
        app,
        ["capture", "record", "--root", str(tmp_path), "-w", "pilot", "--text", "new fact"],
    )
    assert changed.exit_code == 0, changed.stdout
    before = workspace_files(workspace)

    with pytest.raises(FoundryError) as captured:
        write_asset(
            tmp_path,
            "pilot",
            "UNKNOWNS/stale.yaml",
            b"stale: true\n",
            command="unknown update",
            asset_id="unknown.stale",
            actor="maintainer",
            dry_run=False,
            expected_source_digest=expected,
        )

    assert captured.value.category == "filesystem"
    assert captured.value.code == "asset.stale_source"
    assert workspace_files(workspace) == before


def test_asset_writer_rejects_tampered_existing_target_instead_of_recording_it(
    tmp_path: Path,
) -> None:
    workspace = initialized(tmp_path)
    readme = workspace / "README.md"
    readme.write_text("tampered before the requested update\n", encoding="utf-8")
    before = workspace_files(workspace)

    with pytest.raises(FoundryError) as error:
        write_asset(
            tmp_path,
            "pilot",
            "README.md",
            b"requested replacement\n",
            command="test write",
            asset_id="file.readme",
            actor="maintainer",
            dry_run=False,
        )

    assert error.value.code == "asset.unrecorded_changes"
    assert workspace_files(workspace) == before


def test_capture_rejects_tampered_artifact_index_metadata_instead_of_repairing_it(
    tmp_path: Path,
) -> None:
    workspace = initialized(tmp_path)
    index_path = workspace / ".foundry/artifact-index.yaml"
    index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    index["entries"][0]["asset_id"] = "forged.asset.id"
    index_path.write_text(yaml.safe_dump(index, sort_keys=False), encoding="utf-8")
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
            "new supplied evidence",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 8, result.stdout
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "asset.unrecorded_changes"
    assert workspace_files(workspace) == before


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


@pytest.mark.parametrize(
    ("field", "tampered_value"),
    [
        ("claim", "A claim that was never captured."),
        ("status", "draft"),
        ("provenance", "manually rewritten"),
        ("captured_by", "different-actor"),
        ("created_at", "2020-01-01T00:00:00Z"),
        ("updated_at", "2030-01-01T00:00:00Z"),
        ("captured_at", "2020-01-01T00:00:00Z"),
    ],
)
def test_repeated_capture_rejects_tampered_canonical_metadata(
    tmp_path: Path, field: str, tampered_value: str
) -> None:
    workspace = initialized(tmp_path)
    arguments = [
        "capture",
        "record",
        "--root",
        str(tmp_path),
        "-w",
        "pilot",
        "--text",
        "owner supplied immutable evidence",
    ]
    assert RUNNER.invoke(app, arguments).exit_code == 0
    evidence_path = next((workspace / "EVIDENCE").glob("capture-*.yaml"))
    evidence = yaml.safe_load(evidence_path.read_text(encoding="utf-8"))
    evidence[field] = tampered_value
    evidence_path.write_text(yaml.safe_dump(evidence, sort_keys=False), encoding="utf-8")
    before = workspace_files(workspace)

    result = RUNNER.invoke(app, [*arguments, "--format", "json"])

    assert result.exit_code == 3, result.stdout
    payload = json.loads(result.stdout)
    assert payload["diagnostics"][0]["code"] == "capture.evidence_conflict"
    assert workspace_files(workspace) == before


def test_stage_assessment_rejects_tampered_captured_source(tmp_path: Path) -> None:
    workspace = initialized(tmp_path)
    assert (
        RUNNER.invoke(
            app,
            ["capture", "record", "--root", str(tmp_path), "-w", "pilot", "--text", "original"],
        ).exit_code
        == 0
    )
    evidence = yaml.safe_load(next((workspace / "EVIDENCE").glob("capture-*.yaml")).read_text())
    (workspace / evidence["source"]).write_bytes(b"tampered")

    result = RUNNER.invoke(
        app, ["stage", "assess", "--root", str(tmp_path), "-w", "pilot", "--format", "json"]
    )

    assert result.exit_code == 5, result.stdout
    assert "evidence.source_hash" in result.stdout


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
    before_root = workspace_files(tmp_path)
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
    assert workspace_files(tmp_path) == before_root


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


def test_unknown_add_is_idempotent_only_for_the_exact_same_initial_unknown(tmp_path: Path) -> None:
    workspace = initialized(tmp_path)
    arguments = [
        "unknown",
        "add",
        "--root",
        str(tmp_path),
        "-w",
        "pilot",
        "--title",
        "Which role owns release?",
        "--description",
        "Owner is not established.",
    ]
    assert RUNNER.invoke(app, arguments).exit_code == 0
    original = next((workspace / "UNKNOWNS").glob("*.yaml")).read_bytes()

    repeated = RUNNER.invoke(app, arguments)
    conflict = RUNNER.invoke(
        app,
        [*arguments[:-1], "A different description must use unknown update.", "--format", "json"],
    )

    assert repeated.exit_code == 0, repeated.stdout
    assert conflict.exit_code == 3, conflict.stdout
    assert "unknown.already_exists" in conflict.stdout
    assert next((workspace / "UNKNOWNS").glob("*.yaml")).read_bytes() == original
    scope = EventScope(scope_id="pilot", log_path=workspace / ".foundry/events.jsonl")
    assert len(EventStore().replay(scope).events) == 1


def test_concurrent_conflicting_unknown_add_preserves_one_first_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = initialized(tmp_path)
    original_snapshot = unknown_service._safe_snapshot
    both_observed = Barrier(2)
    counter_lock = Lock()
    calls = 0

    def synchronized_snapshot(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        nonlocal calls
        snapshot = original_snapshot(*args, **kwargs)  # type: ignore[arg-type]
        with counter_lock:
            calls += 1
            synchronize = calls <= 2
        if synchronize:
            both_observed.wait(timeout=10)
        return snapshot

    monkeypatch.setattr(unknown_service, "_safe_snapshot", synchronized_snapshot)

    def add(description: str) -> object:
        return unknown_service.add_unknown(
            tmp_path,
            "pilot",
            title="Shared title",
            description=description,
            category=UnknownCategory.judgment,
            owner="owner",
            actor="maintainer",
            dry_run=False,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(add, value) for value in ("first meaning", "second meaning")]
        outcomes: list[object] = []
        for future in futures:
            try:
                outcomes.append(future.result(timeout=20))
            except FoundryError as error:
                outcomes.append(error)

    assert sum(not isinstance(item, FoundryError) for item in outcomes) == 1
    conflicts = [item for item in outcomes if isinstance(item, FoundryError)]
    assert len(conflicts) == 1 and conflicts[0].code == "unknown.already_exists"
    stored = yaml.safe_load(next((workspace / "UNKNOWNS").glob("*.yaml")).read_text())
    assert stored["description"] in {"first meaning", "second meaning"}


def test_unknown_close_rejects_draft_evidence(tmp_path: Path) -> None:
    workspace = initialized(tmp_path)
    assert (
        RUNNER.invoke(
            app,
            ["capture", "record", "--root", str(tmp_path), "-w", "pilot", "--text", "draft fact"],
        ).exit_code
        == 0
    )
    assert (
        RUNNER.invoke(
            app,
            ["unknown", "add", "--root", str(tmp_path), "-w", "pilot", "--title", "Draft gate"],
        ).exit_code
        == 0
    )
    evidence_path = next((workspace / "EVIDENCE").glob("capture-*.yaml"))
    evidence = yaml.safe_load(evidence_path.read_text())
    evidence["status"] = "draft"
    evidence_path.write_text(yaml.safe_dump(evidence, sort_keys=False), encoding="utf-8")
    unknown_id = yaml.safe_load(next((workspace / "UNKNOWNS").glob("*.yaml")).read_text())["id"]

    result = RUNNER.invoke(
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
            evidence["id"],
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 5, result.stdout
    assert "unknown.closure_invalid" in result.stdout
    stored = yaml.safe_load(next((workspace / "UNKNOWNS").glob("*.yaml")).read_text())
    assert stored["unknown_status"] == "new"


@pytest.mark.parametrize(
    ("patch", "expected_code"),
    [
        ({"unknown_status": "resolved", "fact_resolved": True}, "unknown.lifecycle_changed"),
        (
            {
                "history": [
                    {
                        "from_status": "new",
                        "to_status": "clarification",
                        "reason": "Forged direct lifecycle edit",
                        "actor": "attacker",
                        "at": "2029-01-01T00:00:00Z",
                        "evidence_refs": ["evidence.forged"],
                    }
                ]
            },
            "unknown.lifecycle_changed",
        ),
        ({"created_at": "2020-01-01T00:00:00Z"}, "unknown.metadata_changed"),
        ({"owner_id": "different-owner"}, "unknown.metadata_changed"),
    ],
)
def test_unknown_update_cannot_bypass_lifecycle_or_rewrite_history(
    tmp_path: Path, patch: dict[str, object], expected_code: str
) -> None:
    workspace = initialized(tmp_path)
    assert (
        RUNNER.invoke(
            app,
            ["unknown", "add", "--root", str(tmp_path), "-w", "pilot", "--title", "Guarded"],
        ).exit_code
        == 0
    )
    unknown_path = next((workspace / "UNKNOWNS").glob("*.yaml"))
    current = yaml.safe_load(unknown_path.read_text())
    candidate = dict(current)
    candidate["revision"] = current["revision"] + 1
    candidate["updated_at"] = "2030-01-01T00:00:00Z"
    candidate.update(patch)
    input_path = tmp_path / "candidate-unknown.yaml"
    input_path.write_text(yaml.safe_dump(candidate, sort_keys=False), encoding="utf-8")

    result = RUNNER.invoke(
        app,
        [
            "unknown",
            "update",
            "--root",
            str(tmp_path),
            "-w",
            "pilot",
            "--id",
            current["id"],
            "--input",
            str(input_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code != 0, result.stdout
    assert expected_code in result.stdout
    assert yaml.safe_load(unknown_path.read_text()) == current


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
