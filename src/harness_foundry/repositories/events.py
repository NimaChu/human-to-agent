from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from pydantic import ValidationError

from harness_foundry.domain.events import (
    EventDraft,
    EventScope,
    EventVerification,
    ReplayResult,
    StoredEvent,
)
from harness_foundry.repositories.canonical import canonical_bytes

GENESIS_DIGEST = "0" * 64


def _event_digest(record: dict[str, Any]) -> str:
    covered = {key: value for key, value in record.items() if key != "digest"}
    return hashlib.sha256(canonical_bytes(covered)).hexdigest()


class EventStore:
    def append(self, scope: EventScope, draft: EventDraft) -> StoredEvent:
        verification = self.verify(scope)
        if not verification.valid:
            raise ValueError(
                "cannot append to invalid event chain: " + "; ".join(verification.errors)
            )
        replay = self.replay(scope)
        if any(item.event_id == draft.event_id for item in replay.events):
            raise ValueError(f"duplicate event_id: {draft.event_id}")
        record = draft.model_dump(mode="json")
        record["sequence"] = len(replay.events) + 1
        record["prev_digest"] = verification.last_digest or GENESIS_DIGEST
        record["digest"] = _event_digest(record)
        stored = StoredEvent.model_validate(record)
        scope.log_path.parent.mkdir(parents=True, exist_ok=True)
        with scope.log_path.open("ab") as stream:
            stream.write(canonical_bytes(stored.model_dump(mode="json")))
            stream.flush()
            os.fsync(stream.fileno())
        return stored

    def replay(self, scope: EventScope) -> ReplayResult:
        if not scope.log_path.exists():
            return ReplayResult()
        events: list[StoredEvent] = []
        for raw_line in scope.log_path.read_bytes().splitlines():
            if not raw_line.strip():
                continue
            try:
                events.append(StoredEvent.model_validate_json(raw_line))
            except (ValidationError, ValueError, json.JSONDecodeError):
                continue
        return ReplayResult(events=tuple(events))

    def verify(self, scope: EventScope) -> EventVerification:
        if not scope.log_path.exists():
            return EventVerification(valid=True, event_count=0)
        data = scope.log_path.read_bytes()
        errors: list[str] = []
        if data and not data.endswith(b"\n"):
            errors.append("truncated event log: missing terminal newline")
        previous = GENESIS_DIGEST
        count = 0
        for line_number, raw_line in enumerate(data.splitlines(), start=1):
            if not raw_line.strip():
                continue
            try:
                raw = json.loads(raw_line)
                event = StoredEvent.model_validate(raw)
            except (ValidationError, ValueError, json.JSONDecodeError) as error:
                errors.append(f"line {line_number}: invalid event: {error}")
                continue
            count += 1
            if event.sequence != count:
                errors.append(
                    f"line {line_number}: sequence {event.sequence} does not match expected {count}"
                )
            if event.prev_digest != previous:
                errors.append(f"line {line_number}: previous digest mismatch")
            expected = _event_digest(raw)
            if event.digest != expected:
                errors.append(f"line {line_number}: digest mismatch")
            previous = event.digest
        return EventVerification(
            valid=not errors,
            errors=tuple(errors),
            event_count=count,
            last_digest=previous if count else None,
        )
