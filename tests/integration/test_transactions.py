from datetime import UTC, datetime
from pathlib import Path

import pytest
from filelock import FileLock

from harness_foundry.domain.events import EventDraft, EventScope
from harness_foundry.repositories.events import EventStore
from harness_foundry.repositories.transactions import (
    FileMutation,
    MutationPlan,
    TransactionBusyError,
    TransactionManager,
)

NOW = datetime(2026, 7, 10, tzinfo=UTC)


def event() -> EventDraft:
    return EventDraft(
        event_id="event-tx-1",
        workspace_id="pilot",
        at=NOW,
        actor="maintainer",
        command="record-change",
        asset_refs=("workspace.pilot",),
        before_digest="0" * 64,
        after_digest="1" * 64,
        result="committed",
        payload={},
    )


def plan(root: Path) -> MutationPlan:
    workspace = root / "workspaces" / "pilot"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "a.txt").write_text("old-a")
    (workspace / ".foundry").mkdir(exist_ok=True)
    (workspace / ".foundry" / "artifact-index.yaml").write_text("old-index")
    return MutationPlan(
        transaction_id="tx-1",
        workspace_id="pilot",
        event_scope=EventScope(
            scope_id="pilot",
            log_path=workspace / ".foundry" / "events.jsonl",
        ),
        mutations=(
            FileMutation(relative_path="a.txt", after=b"new-a"),
            FileMutation(relative_path=".foundry/artifact-index.yaml", after=b"new-index"),
        ),
        index_relative_path=".foundry/artifact-index.yaml",
    )


def test_index_is_replaced_last_and_commit_event_appended_once(tmp_path: Path) -> None:
    mutation_plan = plan(tmp_path)
    manager = TransactionManager(tmp_path, EventStore())
    result = manager.commit(mutation_plan, event())
    assert result.applied_paths[-1] == ".foundry/artifact-index.yaml"
    assert (tmp_path / "workspaces" / "pilot" / "a.txt").read_text() == "new-a"
    replay = EventStore().replay(mutation_plan.event_scope)
    assert tuple(item.event_id for item in replay.events) == ("event-tx-1",)


def test_concurrent_writer_is_rejected_as_lock_error(tmp_path: Path) -> None:
    mutation_plan = plan(tmp_path)
    manager = TransactionManager(tmp_path, EventStore(), lock_timeout=0.01)
    lock_path = tmp_path / "state" / "locks" / "pilot.lock"
    lock_path.parent.mkdir(parents=True)
    with FileLock(lock_path, timeout=0), pytest.raises(TransactionBusyError) as error:
        manager.commit(mutation_plan, event())
    assert error.value.category == "lock"
