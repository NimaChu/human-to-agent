from datetime import UTC, datetime
from pathlib import Path

import pytest

from human_to_agent.domain.events import EventDraft, EventScope
from human_to_agent.repositories.events import EventStore
from human_to_agent.repositories.transactions import (
    FileMutation,
    InjectedCrash,
    MutationPlan,
    TransactionManager,
    TransactionPhase,
)
from human_to_agent.services.recovery import RecoveryService

NOW = datetime(2026, 7, 10, tzinfo=UTC)


def setup(
    root: Path, crash_phase: TransactionPhase
) -> tuple[Path, EventScope, MutationPlan, EventDraft, TransactionManager]:
    workspace = root / "workspaces" / "pilot"
    workspace.mkdir(parents=True)
    (workspace / "data.txt").write_text("old")
    (workspace / "source.bin").write_bytes(b"old-source")
    (workspace / ".foundry").mkdir()
    (workspace / ".foundry" / "artifact-index.yaml").write_text("old-index")
    scope = EventScope(scope_id="pilot", log_path=workspace / ".foundry" / "events.jsonl")
    mutation_plan = MutationPlan(
        transaction_id="tx-crash",
        workspace_id="pilot",
        event_scope=scope,
        mutations=(
            FileMutation(relative_path="data.txt", after=b"new"),
            FileMutation(relative_path="source.bin", after=b"new-source"),
            FileMutation(relative_path=".foundry/artifact-index.yaml", after=b"new-index"),
        ),
        index_relative_path=".foundry/artifact-index.yaml",
    )
    draft = EventDraft(
        event_id="event-crash",
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

    def fault(phase: TransactionPhase) -> None:
        if phase is crash_phase:
            raise InjectedCrash(phase)

    return (
        workspace,
        scope,
        mutation_plan,
        draft,
        TransactionManager(root, EventStore(), fault_injector=fault),
    )


@pytest.mark.parametrize(
    "crash_phase",
    [
        TransactionPhase.staged,
        TransactionPhase.files_replaced,
        TransactionPhase.index_replaced,
        TransactionPhase.event_committed,
    ],
)
def test_crash_each_phase_recovers_all_old_or_all_new(
    tmp_path: Path, crash_phase: TransactionPhase
) -> None:
    workspace, scope, mutation_plan, draft, manager = setup(tmp_path, crash_phase)
    with pytest.raises(InjectedCrash):
        manager.commit(mutation_plan, draft)

    results = RecoveryService(tmp_path, EventStore()).recover_all()
    assert results and results[0].transaction_id == "tx-crash"
    event_count = len(EventStore().replay(scope).events)
    if crash_phase is TransactionPhase.event_committed:
        assert (workspace / "data.txt").read_text() == "new"
        assert (workspace / "source.bin").read_bytes() == b"new-source"
        assert (workspace / ".foundry" / "artifact-index.yaml").read_text() == "new-index"
        assert event_count == 1
    else:
        assert (workspace / "data.txt").read_text() == "old"
        assert (workspace / "source.bin").read_bytes() == b"old-source"
        assert (workspace / ".foundry" / "artifact-index.yaml").read_text() == "old-index"
        assert event_count == 0
    assert not (tmp_path / "state" / "transactions" / "tx-crash").exists()


def test_recovery_does_not_duplicate_committed_event(tmp_path: Path) -> None:
    _, scope, mutation_plan, draft, manager = setup(tmp_path, TransactionPhase.event_committed)
    with pytest.raises(InjectedCrash):
        manager.commit(mutation_plan, draft)
    service = RecoveryService(tmp_path, EventStore())
    service.recover_all()
    service.recover_all()
    assert tuple(item.event_id for item in EventStore().replay(scope).events) == ("event-crash",)
