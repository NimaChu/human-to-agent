from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any

from filelock import FileLock, Timeout

from harness_foundry.domain.events import EventDraft, EventScope
from harness_foundry.repositories.canonical import canonical_bytes
from harness_foundry.repositories.events import EventStore


class TransactionPhase(StrEnum):
    prepared = "prepared"
    staged = "staged"
    files_replaced = "files_replaced"
    index_replaced = "index_replaced"
    event_committed = "event_committed"


class TransactionBusyError(RuntimeError):
    category = "lock"


class InjectedCrash(RuntimeError):
    def __init__(self, phase: TransactionPhase) -> None:
        self.phase = phase
        super().__init__(f"injected crash after {phase.value}")


@dataclass(frozen=True)
class FileMutation:
    relative_path: str
    after: bytes

    def __post_init__(self) -> None:
        path = PurePosixPath(self.relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("mutation path must be workspace-relative")


@dataclass(frozen=True)
class MutationPlan:
    transaction_id: str
    workspace_id: str
    event_scope: EventScope
    mutations: tuple[FileMutation, ...]
    index_relative_path: str


@dataclass(frozen=True)
class CommitResult:
    transaction_id: str
    applied_paths: tuple[str, ...]


class TransactionManager:
    def __init__(
        self,
        root: Path,
        event_store: EventStore,
        *,
        lock_timeout: float = 10,
        fault_injector: Callable[[TransactionPhase], None] | None = None,
    ) -> None:
        self.root = root
        self.event_store = event_store
        self.lock_timeout = lock_timeout
        self.fault_injector = fault_injector

    def _checkpoint(
        self, journal_path: Path, journal: dict[str, Any], phase: TransactionPhase
    ) -> None:
        journal["phase"] = phase.value
        journal_path.write_bytes(canonical_bytes(journal))
        with journal_path.open("r+b") as stream:
            os.fsync(stream.fileno())
        if self.fault_injector is not None:
            self.fault_injector(phase)

    def commit(self, plan: MutationPlan, event: EventDraft) -> CommitResult:
        lock_path = self.root / "state" / "locks" / f"{plan.workspace_id}.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with FileLock(lock_path, timeout=self.lock_timeout):
                return self._commit_locked(plan, event)
        except Timeout as error:
            raise TransactionBusyError(f"workspace {plan.workspace_id} is busy") from error

    def _commit_locked(self, plan: MutationPlan, event: EventDraft) -> CommitResult:
        workspace = self.root / "workspaces" / plan.workspace_id
        tx_dir = self.root / "state" / "transactions" / plan.transaction_id
        staged_dir = tx_dir / "staged"
        backup_dir = tx_dir / "backup"
        tx_dir.mkdir(parents=True, exist_ok=False)
        journal_path = tx_dir / "journal.json"
        changes: list[dict[str, Any]] = []
        journal: dict[str, Any] = {
            "transaction_id": plan.transaction_id,
            "workspace_id": plan.workspace_id,
            "event_scope": {
                "scope_id": plan.event_scope.scope_id,
                "log_path": str(plan.event_scope.log_path),
            },
            "event_id": event.event_id,
            "event_log_offset": (
                plan.event_scope.log_path.stat().st_size
                if plan.event_scope.log_path.exists()
                else 0
            ),
            "index_relative_path": plan.index_relative_path,
            "changes": changes,
        }
        self._checkpoint(journal_path, journal, TransactionPhase.prepared)
        for index, mutation in enumerate(plan.mutations):
            target = workspace / Path(mutation.relative_path)
            staged = staged_dir / str(index)
            backup = backup_dir / str(index)
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(mutation.after)
            existed = target.exists()
            if existed:
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            changes.append(
                {
                    "relative_path": mutation.relative_path,
                    "staged": str(staged),
                    "backup": str(backup),
                    "existed": existed,
                }
            )
        self._checkpoint(journal_path, journal, TransactionPhase.staged)
        ordered = sorted(
            changes,
            key=lambda item: item["relative_path"] == plan.index_relative_path,
        )
        non_index = [item for item in ordered if item["relative_path"] != plan.index_relative_path]
        index_changes = [
            item for item in ordered if item["relative_path"] == plan.index_relative_path
        ]
        for item in non_index:
            self._replace(workspace, item)
        self._checkpoint(journal_path, journal, TransactionPhase.files_replaced)
        for item in index_changes:
            self._replace(workspace, item)
        self._checkpoint(journal_path, journal, TransactionPhase.index_replaced)
        self.event_store.append(plan.event_scope, event)
        self._checkpoint(journal_path, journal, TransactionPhase.event_committed)
        shutil.rmtree(tx_dir)
        return CommitResult(
            transaction_id=plan.transaction_id,
            applied_paths=tuple(item["relative_path"] for item in non_index + index_changes),
        )

    @staticmethod
    def _replace(workspace: Path, change: dict[str, Any]) -> None:
        target = workspace / Path(change["relative_path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(change["staged"], target)
