import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from filelock import FileLock

from human_to_agent.domain.events import EventDraft, EventScope
from human_to_agent.repositories.events import EventStore
from human_to_agent.repositories.transactions import (
    FileMutation,
    MutationPlan,
    TransactionBusyError,
    TransactionManager,
)

NOW = datetime(2026, 7, 10, tzinfo=UTC)


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


def test_transaction_rejects_invalid_event_chain_before_replacing_files(tmp_path: Path) -> None:
    mutation_plan = plan(tmp_path)
    workspace = tmp_path / "workspaces/pilot"
    mutation_plan.event_scope.log_path.write_bytes(b"not-an-event\n")

    with pytest.raises(ValueError, match="invalid event chain"):
        TransactionManager(tmp_path, EventStore()).commit(mutation_plan, event())

    assert (workspace / "a.txt").read_text() == "old-a"
    assert (workspace / ".foundry/artifact-index.yaml").read_text() == "old-index"
    assert not (tmp_path / "state/transactions/tx-1").exists()


def test_transaction_rejects_duplicate_event_id_before_replacing_files(tmp_path: Path) -> None:
    mutation_plan = plan(tmp_path)
    workspace = tmp_path / "workspaces/pilot"
    EventStore().append(mutation_plan.event_scope, event())

    with pytest.raises(ValueError, match="duplicate event_id"):
        TransactionManager(tmp_path, EventStore()).commit(mutation_plan, event())

    assert (workspace / "a.txt").read_text() == "old-a"
    assert (workspace / ".foundry/artifact-index.yaml").read_text() == "old-index"
    assert not (tmp_path / "state/transactions/tx-1").exists()


@pytest.mark.parametrize("relative_path", (r"EVIDENCE\\escape.yaml", "C:/escape.yaml"))
def test_file_mutation_rejects_non_posix_or_drive_like_paths(relative_path: str) -> None:
    with pytest.raises(ValueError, match="workspace-relative POSIX"):
        FileMutation(relative_path=relative_path, after=b"escape")


def test_mutation_plan_requires_unique_paths_and_exactly_one_index_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspaces/pilot"
    scope = EventScope(scope_id="pilot", log_path=workspace / ".foundry/events.jsonl")
    with pytest.raises(ValueError, match="exactly one artifact-index mutation"):
        MutationPlan(
            transaction_id="missing-index",
            workspace_id="pilot",
            event_scope=scope,
            mutations=(FileMutation("a.txt", b"a"),),
            index_relative_path=".foundry/artifact-index.yaml",
        )
    with pytest.raises(ValueError, match="unique"):
        MutationPlan(
            transaction_id="duplicate",
            workspace_id="pilot",
            event_scope=scope,
            mutations=(
                FileMutation(".foundry/artifact-index.yaml", b"one"),
                FileMutation(".foundry/artifact-index.yaml", b"two"),
            ),
            index_relative_path=".foundry/artifact-index.yaml",
        )


def test_transaction_rejects_symlinked_target_ancestor_without_external_write(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspaces" / "pilot"
    workspace.mkdir(parents=True)
    external = tmp_path / "external"
    external.mkdir()
    link_directory(workspace / "EVIDENCE", external)
    (workspace / ".foundry").mkdir()
    mutation_plan = MutationPlan(
        transaction_id="tx-symlink-ancestor",
        workspace_id="pilot",
        event_scope=EventScope(
            scope_id="pilot",
            log_path=workspace / ".foundry" / "events.jsonl",
        ),
        mutations=(
            FileMutation("EVIDENCE/escaped.txt", b"must stay inside"),
            FileMutation(".foundry/artifact-index.yaml", b"index"),
        ),
        index_relative_path=".foundry/artifact-index.yaml",
    )

    with pytest.raises(ValueError, match=r"symlink|junction|outside"):
        TransactionManager(tmp_path, EventStore()).commit(mutation_plan, event())

    assert not (external / "escaped.txt").exists()


def test_transaction_rejects_internal_junction_alias(tmp_path: Path) -> None:
    workspace = tmp_path / "workspaces" / "pilot"
    workspace.mkdir(parents=True)
    internal = workspace / "real-evidence"
    internal.mkdir()
    link_directory(workspace / "EVIDENCE", internal)
    (workspace / ".foundry").mkdir()
    mutation_plan = MutationPlan(
        transaction_id="tx-internal-junction",
        workspace_id="pilot",
        event_scope=EventScope(
            scope_id="pilot",
            log_path=workspace / ".foundry" / "events.jsonl",
        ),
        mutations=(
            FileMutation("EVIDENCE/aliased.txt", b"must not use an alias"),
            FileMutation(".foundry/artifact-index.yaml", b"index"),
        ),
        index_relative_path=".foundry/artifact-index.yaml",
    )

    with pytest.raises(ValueError, match=r"symlink|junction"):
        TransactionManager(tmp_path, EventStore()).commit(mutation_plan, event())

    assert not (internal / "aliased.txt").exists()


def test_transaction_rejects_symlinked_target_file_without_external_overwrite(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspaces" / "pilot"
    workspace.mkdir(parents=True)
    external = tmp_path / "external.txt"
    external.write_bytes(b"outside")
    target = workspace / "linked.txt"
    try:
        target.symlink_to(external)
    except OSError as error:
        pytest.skip(f"file symlinks are unavailable: {error}")
    (workspace / ".foundry").mkdir()
    mutation_plan = MutationPlan(
        transaction_id="tx-symlink-file",
        workspace_id="pilot",
        event_scope=EventScope(
            scope_id="pilot",
            log_path=workspace / ".foundry" / "events.jsonl",
        ),
        mutations=(
            FileMutation("linked.txt", b"must stay inside"),
            FileMutation(".foundry/artifact-index.yaml", b"index"),
        ),
        index_relative_path=".foundry/artifact-index.yaml",
    )

    with pytest.raises(ValueError, match=r"symlink|junction"):
        TransactionManager(tmp_path, EventStore()).commit(mutation_plan, event())

    assert external.read_bytes() == b"outside"
