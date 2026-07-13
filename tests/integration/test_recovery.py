import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from filelock import FileLock

from human_to_agent.domain.events import EventDraft, EventScope
from human_to_agent.repositories.events import EventStore
from human_to_agent.repositories.transactions import (
    FileMutation,
    InjectedCrash,
    MutationPlan,
    TransactionBusyError,
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
        TransactionPhase.prepared,
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


def crashed_journal(tmp_path: Path) -> tuple[Path, Path]:
    workspace, _, mutation_plan, draft, manager = setup(tmp_path, TransactionPhase.files_replaced)
    with pytest.raises(InjectedCrash):
        manager.commit(mutation_plan, draft)
    journal_path = tmp_path / "state/transactions/tx-crash/journal.json"
    return workspace, journal_path


def test_recovery_rejects_tampered_relative_path_before_external_write(tmp_path: Path) -> None:
    workspace, journal_path = crashed_journal(tmp_path)
    external = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    external.write_bytes(b"outside must remain unchanged")
    try:
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        journal["changes"][0]["relative_path"] = "../../../outside.txt"
        journal_path.write_text(json.dumps(journal), encoding="utf-8")
        before_workspace = (workspace / "data.txt").read_bytes()

        with pytest.raises(ValueError, match="workspace-relative POSIX"):
            RecoveryService(tmp_path, EventStore()).recover_all()

        assert external.read_bytes() == b"outside must remain unchanged"
        assert (workspace / "data.txt").read_bytes() == before_workspace
    finally:
        external.unlink(missing_ok=True)


def test_recovery_rejects_backup_and_event_log_outside_transaction_boundaries(
    tmp_path: Path,
) -> None:
    _, journal_path = crashed_journal(tmp_path)
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    journal["changes"][0]["backup"] = str(tmp_path / "outside-backup")
    journal["event_scope"]["log_path"] = str(tmp_path / "outside-events.jsonl")
    journal_path.write_text(json.dumps(journal), encoding="utf-8")

    with pytest.raises(ValueError, match=r"backup path|event log"):
        RecoveryService(tmp_path, EventStore()).recover_all()


def test_recovery_rejects_tampered_workspace_id(tmp_path: Path) -> None:
    _, journal_path = crashed_journal(tmp_path)
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    journal["workspace_id"] = "../outside"
    journal_path.write_text(json.dumps(journal), encoding="utf-8")

    with pytest.raises(ValueError, match="workspace id"):
        RecoveryService(tmp_path, EventStore()).recover_all()


def test_recovery_uses_the_same_workspace_lock_as_live_transactions(tmp_path: Path) -> None:
    crashed_journal(tmp_path)
    lock_path = tmp_path / "state/locks/pilot.lock"
    with FileLock(lock_path, timeout=0), pytest.raises(TransactionBusyError):
        RecoveryService(tmp_path, EventStore(), lock_timeout=0.01).recover_all()


@pytest.mark.parametrize("journal_content", (None, b"not valid json"))
def test_recovery_explicitly_rejects_missing_or_invalid_journal(
    tmp_path: Path, journal_content: bytes | None
) -> None:
    tx_dir = tmp_path / "state/transactions/orphan"
    tx_dir.mkdir(parents=True)
    if journal_content is not None:
        (tx_dir / "journal.json").write_bytes(journal_content)

    with pytest.raises(ValueError, match=r"journal is missing|journal is invalid"):
        RecoveryService(tmp_path, EventStore()).recover_all()


def test_recovery_rejects_invalid_event_chain_before_rollback(tmp_path: Path) -> None:
    workspace, journal_path = crashed_journal(tmp_path)
    event_log = workspace / ".foundry/events.jsonl"
    event_log.write_bytes(b"not-an-event\n")
    before = (workspace / "data.txt").read_bytes()

    with pytest.raises(ValueError, match="event chain is invalid"):
        RecoveryService(tmp_path, EventStore()).recover_all()

    assert (workspace / "data.txt").read_bytes() == before
    assert journal_path.exists()


def test_recovery_rejects_committed_phase_without_recorded_event(tmp_path: Path) -> None:
    workspace, journal_path = crashed_journal(tmp_path)
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    journal["phase"] = TransactionPhase.event_committed.value
    journal_path.write_text(json.dumps(journal), encoding="utf-8")
    before = (workspace / "data.txt").read_bytes()

    with pytest.raises(ValueError, match="committed phase has no recorded event"):
        RecoveryService(tmp_path, EventStore()).recover_all()

    assert (workspace / "data.txt").read_bytes() == before
    assert journal_path.exists()
