from __future__ import annotations

import os
import shutil
import stat as stat_module
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any, TypeVar

from filelock import FileLock, Timeout

from human_to_agent.domain.events import EventDraft, EventScope
from human_to_agent.repositories.canonical import canonical_bytes
from human_to_agent.repositories.events import EventStore

T = TypeVar("T")


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
        if (
            not path.parts
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in self.relative_path
            or any(":" in part for part in path.parts)
        ):
            raise ValueError("mutation path must be a workspace-relative POSIX path")


@dataclass(frozen=True)
class MutationPlan:
    transaction_id: str
    workspace_id: str
    event_scope: EventScope
    mutations: tuple[FileMutation, ...]
    index_relative_path: str

    def __post_init__(self) -> None:
        FileMutation(self.index_relative_path, b"")
        paths = tuple(mutation.relative_path for mutation in self.mutations)
        if len(set(paths)) != len(paths):
            raise ValueError("transaction mutation paths must be unique")
        if paths.count(self.index_relative_path) != 1:
            raise ValueError("transaction requires exactly one artifact-index mutation")


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
        self.root = root.resolve()
        self.event_store = event_store
        self.lock_timeout = lock_timeout
        self.fault_injector = fault_injector

    @staticmethod
    def _is_link(path: Path) -> bool:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if is_junction is not None and is_junction():
            return True
        try:
            attributes = getattr(path.lstat(), "st_file_attributes", 0)
        except FileNotFoundError:
            return False
        reparse_point = getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        return bool(attributes & reparse_point)

    @classmethod
    def _safe_child(cls, root: Path, relative_path: str) -> Path:
        relative = PurePosixPath(relative_path)
        FileMutation(relative.as_posix(), b"")
        root = root.resolve()
        candidate = root
        for part in relative.parts:
            candidate /= part
            if cls._is_link(candidate):
                raise ValueError(
                    f"transaction target contains a symlink or junction: {relative.as_posix()}"
                )
            if not candidate.resolve(strict=False).is_relative_to(root):
                raise ValueError(
                    f"transaction target resolves outside its allowed root: {relative.as_posix()}"
                )
        return candidate

    def _workspace(self, workspace_id: str) -> Path:
        identifier = PurePosixPath(workspace_id)
        if len(identifier.parts) != 1 or identifier.as_posix() in {"", "."}:
            raise ValueError("workspace id must be one safe path component")
        workspace = self._safe_child(self.root, f"workspaces/{workspace_id}")
        if not workspace.is_dir():
            raise FileNotFoundError(f"workspace does not exist: {workspace_id}")
        return workspace.resolve()

    def _validate_event_scope(self, workspace: Path, scope: EventScope) -> None:
        try:
            relative = scope.log_path.relative_to(workspace)
        except ValueError as error:
            raise ValueError("event log path is outside its workspace") from error
        safe = self._safe_child(workspace, PurePosixPath(*relative.parts).as_posix())
        if safe != scope.log_path:
            raise ValueError("event log path is not a canonical workspace path")

    def run_locked(self, workspace_id: str, operation: Callable[[], T]) -> T:
        self._workspace(workspace_id)
        lock_path = self._safe_child(self.root, f"state/locks/{workspace_id}.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with FileLock(lock_path, timeout=self.lock_timeout):
                return operation()
        except Timeout as error:
            raise TransactionBusyError(f"workspace {workspace_id} is busy") from error

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
        return self.run_locked(plan.workspace_id, lambda: self._commit_locked(plan, event))

    def _commit_locked(self, plan: MutationPlan, event: EventDraft) -> CommitResult:
        workspace = self._workspace(plan.workspace_id)
        if (
            event.workspace_id != plan.workspace_id
            or plan.event_scope.scope_id != plan.workspace_id
        ):
            raise ValueError("transaction, event, and event scope workspace ids must match")
        self._validate_event_scope(workspace, plan.event_scope)
        verification = self.event_store.verify(plan.event_scope)
        if not verification.valid:
            raise ValueError(
                "cannot start transaction with invalid event chain: "
                + "; ".join(verification.errors)
            )
        if any(
            stored.event_id == event.event_id
            for stored in self.event_store.replay(plan.event_scope).events
        ):
            raise ValueError(f"duplicate event_id: {event.event_id}")
        targets = {
            mutation.relative_path: self._safe_child(workspace, mutation.relative_path)
            for mutation in plan.mutations
        }
        tx_identifier = PurePosixPath(plan.transaction_id)
        if len(tx_identifier.parts) != 1 or tx_identifier.as_posix() in {"", "."}:
            raise ValueError("transaction id must be one safe path component")
        tx_dir = self._safe_child(self.root, f"state/transactions/{plan.transaction_id}")
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
            target = targets[mutation.relative_path]
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
        self._validate_event_scope(workspace, plan.event_scope)
        self.event_store.append(plan.event_scope, event)
        self._checkpoint(journal_path, journal, TransactionPhase.event_committed)
        shutil.rmtree(tx_dir)
        return CommitResult(
            transaction_id=plan.transaction_id,
            applied_paths=tuple(item["relative_path"] for item in non_index + index_changes),
        )

    @classmethod
    def _replace(cls, workspace: Path, change: dict[str, Any]) -> None:
        target = cls._safe_child(workspace, change["relative_path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(change["staged"], target)
