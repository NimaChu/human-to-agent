from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from human_to_agent.domain.events import EventScope
from human_to_agent.repositories.events import EventStore
from human_to_agent.repositories.transactions import (
    FileMutation,
    TransactionManager,
    TransactionPhase,
)


@dataclass(frozen=True)
class RecoveryResult:
    transaction_id: str
    outcome: str


@dataclass(frozen=True)
class _RecoveryChange:
    relative_path: str
    target: Path
    backup: Path
    backup_relative_path: str
    existed: bool


@dataclass(frozen=True)
class _ValidatedJournal:
    transaction_id: str
    workspace_id: str
    workspace: Path
    phase: TransactionPhase
    event_id: str
    event_log_offset: int
    scope: EventScope
    changes: tuple[_RecoveryChange, ...]


class RecoveryService:
    def __init__(
        self,
        root: Path,
        event_store: EventStore,
        *,
        lock_timeout: float = 10,
    ) -> None:
        self.root = root.resolve()
        self.event_store = event_store
        self.manager = TransactionManager(
            self.root,
            event_store,
            lock_timeout=lock_timeout,
        )

    def recover_all(self) -> tuple[RecoveryResult, ...]:
        transactions = self.manager._safe_child(self.root, "state/transactions")
        if not transactions.exists():
            return ()
        results: list[RecoveryResult] = []
        for tx_dir in sorted(path for path in transactions.iterdir() if path.is_dir()):
            safe_tx_dir = self.manager._safe_child(transactions, tx_dir.name)
            if safe_tx_dir != tx_dir:
                raise ValueError("transaction directory is outside the recovery root")
            workspace_id = self._peek_workspace_id(tx_dir)
            result = self.manager.run_locked(
                workspace_id,
                partial(self._recover, tx_dir, workspace_id),
            )
            if result is not None:
                results.append(result)
        return tuple(results)

    def _peek_workspace_id(self, tx_dir: Path) -> str:
        journal_path = self.manager._safe_child(tx_dir, "journal.json")
        if not journal_path.is_file():
            raise ValueError(f"transaction journal is missing: {tx_dir.name}")
        try:
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ValueError(f"transaction journal is invalid: {tx_dir.name}") from error
        if not isinstance(journal, dict):
            raise ValueError("transaction journal must be a JSON object")
        workspace_id = journal.get("workspace_id")
        if not isinstance(workspace_id, str):
            raise ValueError("transaction journal workspace id is invalid")
        self.manager._workspace(workspace_id)
        return workspace_id

    def _recover(self, tx_dir: Path, expected_workspace_id: str) -> RecoveryResult | None:
        if not tx_dir.exists():
            return None
        journal = self._validate_journal(tx_dir)
        if journal.workspace_id != expected_workspace_id:
            raise ValueError("transaction journal workspace id changed while acquiring its lock")
        verification = self.event_store.verify(journal.scope)
        if not verification.valid:
            raise ValueError(
                "transaction event chain is invalid: " + "; ".join(verification.errors)
            )
        committed = any(
            item.event_id == journal.event_id
            for item in self.event_store.replay(journal.scope).events
        )
        if journal.phase is TransactionPhase.event_committed and not committed:
            raise ValueError("transaction committed phase has no recorded event")
        if committed:
            outcome = "kept-committed"
        else:
            self._rollback(tx_dir, journal)
            outcome = "rolled-back"
        safe_tx_dir = self.manager._safe_child(tx_dir.parent, tx_dir.name)
        if safe_tx_dir != tx_dir:
            raise ValueError("transaction directory changed during recovery")
        shutil.rmtree(tx_dir)
        return RecoveryResult(transaction_id=journal.transaction_id, outcome=outcome)

    def _validate_journal(self, tx_dir: Path) -> _ValidatedJournal:
        journal_path = self.manager._safe_child(tx_dir, "journal.json")
        try:
            raw: Any = json.loads(journal_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ValueError(f"transaction journal is invalid: {tx_dir.name}") from error
        if not isinstance(raw, dict):
            raise ValueError("transaction journal must be a JSON object")
        transaction_id = self._required_string(raw, "transaction_id")
        if transaction_id != tx_dir.name:
            raise ValueError("transaction id does not match its recovery directory")
        workspace_id = self._required_string(raw, "workspace_id")
        workspace = self.manager._workspace(workspace_id)
        try:
            phase = TransactionPhase(self._required_string(raw, "phase"))
        except ValueError as error:
            raise ValueError("transaction journal phase is invalid") from error
        event_id = self._required_string(raw, "event_id")
        event_log_offset = raw.get("event_log_offset")
        if (
            not isinstance(event_log_offset, int)
            or isinstance(event_log_offset, bool)
            or event_log_offset < 0
        ):
            raise ValueError("transaction journal event log offset is invalid")
        scope = EventScope.model_validate(raw.get("event_scope"))
        if scope.scope_id != workspace_id:
            raise ValueError("event log scope does not match the recovery workspace")
        self.manager._validate_event_scope(workspace, scope)
        changes_raw = raw.get("changes")
        if not isinstance(changes_raw, list):
            raise ValueError("transaction journal changes must be a list")
        changes = tuple(
            self._validate_change(tx_dir, workspace, item, index)
            for index, item in enumerate(changes_raw)
        )
        relative_paths = tuple(change.relative_path for change in changes)
        if len(set(relative_paths)) != len(relative_paths):
            raise ValueError("transaction journal change paths must be unique")
        index_relative_path = self._required_string(raw, "index_relative_path")
        FileMutation(index_relative_path, b"")
        index_change_count = relative_paths.count(index_relative_path)
        if (
            not (phase is TransactionPhase.prepared and not relative_paths)
            and index_change_count != 1
        ):
            raise ValueError("transaction journal requires exactly one artifact-index change")
        return _ValidatedJournal(
            transaction_id=transaction_id,
            workspace_id=workspace_id,
            workspace=workspace,
            phase=phase,
            event_id=event_id,
            event_log_offset=event_log_offset,
            scope=scope,
            changes=changes,
        )

    def _validate_change(
        self,
        tx_dir: Path,
        workspace: Path,
        raw: object,
        index: int,
    ) -> _RecoveryChange:
        if not isinstance(raw, dict):
            raise ValueError("transaction journal change must be a JSON object")
        relative_path = self._required_string(raw, "relative_path")
        FileMutation(relative_path, b"")
        target = self.manager._safe_child(workspace, relative_path)
        backup_relative = f"backup/{index}"
        backup = self._validate_transaction_file(
            tx_dir,
            raw.get("backup"),
            backup_relative,
            "backup path",
        )
        self._validate_transaction_file(
            tx_dir,
            raw.get("staged"),
            f"staged/{index}",
            "staged path",
        )
        existed = raw.get("existed")
        if not isinstance(existed, bool):
            raise ValueError("transaction journal existed flag is invalid")
        if existed and not backup.is_file():
            raise ValueError("transaction recovery backup is missing")
        return _RecoveryChange(
            relative_path=relative_path,
            target=target,
            backup=backup,
            backup_relative_path=backup_relative,
            existed=existed,
        )

    def _validate_transaction_file(
        self,
        tx_dir: Path,
        raw_path: object,
        expected_relative_path: str,
        label: str,
    ) -> Path:
        if not isinstance(raw_path, str):
            raise ValueError(f"transaction journal {label} is invalid")
        supplied = Path(raw_path)
        expected = self.manager._safe_child(tx_dir, expected_relative_path)
        if supplied != expected:
            raise ValueError(f"transaction journal {label} is outside its transaction")
        return expected

    @staticmethod
    def _required_string(raw: dict[str, Any], key: str) -> str:
        value = raw.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"transaction journal {key} is invalid")
        return value

    def _rollback(self, tx_dir: Path, journal: _ValidatedJournal) -> None:
        for change in reversed(journal.changes):
            target = self.manager._safe_child(journal.workspace, change.relative_path)
            backup = self.manager._safe_child(tx_dir, change.backup_relative_path)
            if target != change.target or backup != change.backup:
                raise ValueError("transaction paths changed during recovery")
            if change.existed:
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(backup, target)
            elif target.exists():
                target.unlink()
        self.manager._validate_event_scope(journal.workspace, journal.scope)
        log_path = journal.scope.log_path
        if log_path.exists() and log_path.stat().st_size > journal.event_log_offset:
            with log_path.open("r+b") as stream:
                stream.truncate(journal.event_log_offset)
                stream.flush()
                os.fsync(stream.fileno())
