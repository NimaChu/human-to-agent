import json
from datetime import UTC, datetime
from pathlib import Path

from harness_foundry.domain.events import EventDraft, EventScope
from harness_foundry.repositories.events import EventStore

NOW = datetime(2026, 7, 10, tzinfo=UTC)


def draft(event_id: str, *, actor: str = "maintainer") -> EventDraft:
    return EventDraft(
        event_id=event_id,
        workspace_id="workspace.pilot",
        at=NOW,
        actor=actor,
        command="record-change",
        asset_refs=("workspace.pilot",),
        before_digest="0" * 64,
        after_digest="1" * 64,
        result="committed",
        payload={"reason": "test"},
    )


def scope(tmp_path: Path, name: str = "root") -> EventScope:
    return EventScope(scope_id=name, log_path=tmp_path / name / "events.jsonl")


def test_event_digest_covers_sequence_previous_digest_and_payload(tmp_path: Path) -> None:
    store = EventStore()
    target = scope(tmp_path)
    first = store.append(target, draft("event-1"))
    second = store.append(target, draft("event-2"))
    assert first.sequence == 1
    assert second.sequence == 2
    assert second.prev_digest == first.digest
    assert store.verify(target).valid

    records = [json.loads(line) for line in target.log_path.read_text().splitlines()]
    records[0]["actor"] = "tampered"
    target.log_path.write_text("\n".join(json.dumps(item) for item in records) + "\n")
    verification = store.verify(target)
    assert not verification.valid
    assert any("digest" in error for error in verification.errors)


def test_detects_truncation_and_sequence_gap(tmp_path: Path) -> None:
    store = EventStore()
    target = scope(tmp_path)
    store.append(target, draft("event-1"))
    store.append(target, draft("event-2"))
    data = target.log_path.read_bytes()
    target.log_path.write_bytes(data[:-1])
    assert "truncated" in " ".join(store.verify(target).errors)

    events = list(store.replay(target).events)
    records = [event.model_dump(mode="json") for event in events]
    records[1]["sequence"] = 4
    target.log_path.write_text("\n".join(json.dumps(item) for item in records) + "\n")
    assert "sequence" in " ".join(store.verify(target).errors)


def test_root_and_workspace_chains_share_workspace_id_without_duplication(tmp_path: Path) -> None:
    store = EventStore()
    root = scope(tmp_path, "root")
    workspace = scope(tmp_path, "workspace")
    root_event = store.append(root, draft("root-1"))
    workspace_event = store.append(workspace, draft("workspace-1"))
    assert root_event.workspace_id == workspace_event.workspace_id
    assert tuple(item.event_id for item in store.replay(root).events) == ("root-1",)
    assert tuple(item.event_id for item in store.replay(workspace).events) == ("workspace-1",)
