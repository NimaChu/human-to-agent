from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from human_to_agent.domain.events import EventScope
from human_to_agent.repositories.events import EventStore
from human_to_agent.repositories.transactions import TransactionPhase


@dataclass(frozen=True)
class RecoveryResult:
    transaction_id: str
    outcome: str


class RecoveryService:
    def __init__(self, root: Path, event_store: EventStore) -> None:
        self.root = root
        self.event_store = event_store

    def recover_all(self) -> tuple[RecoveryResult, ...]:
        transactions = self.root / "state" / "transactions"
        if not transactions.exists():
            return ()
        results: list[RecoveryResult] = []
        for tx_dir in sorted(path for path in transactions.iterdir() if path.is_dir()):
            results.append(self._recover(tx_dir))
        return tuple(results)

    def _recover(self, tx_dir: Path) -> RecoveryResult:
        journal = json.loads((tx_dir / "journal.json").read_text(encoding="utf-8"))
        scope = EventScope.model_validate(journal["event_scope"])
        committed = journal["phase"] == TransactionPhase.event_committed.value or any(
            item.event_id == journal["event_id"] for item in self.event_store.replay(scope).events
        )
        if committed:
            outcome = "kept-committed"
        else:
            self._rollback(journal)
            outcome = "rolled-back"
        shutil.rmtree(tx_dir)
        return RecoveryResult(transaction_id=journal["transaction_id"], outcome=outcome)

    def _rollback(self, journal: dict[str, Any]) -> None:
        workspace = self.root / "workspaces" / journal["workspace_id"]
        for change in reversed(journal["changes"]):
            target = workspace / Path(change["relative_path"])
            backup = Path(change["backup"])
            if change["existed"]:
                target.parent.mkdir(parents=True, exist_ok=True)
                if backup.exists():
                    os.replace(backup, target)
            elif target.exists():
                target.unlink()
        log_path = Path(journal["event_scope"]["log_path"])
        if log_path.exists() and log_path.stat().st_size > journal["event_log_offset"]:
            with log_path.open("r+b") as stream:
                stream.truncate(journal["event_log_offset"])
                stream.flush()
                os.fsync(stream.fileno())
