from datetime import UTC, datetime
from pathlib import Path

import yaml

from human_to_agent.repositories.events import EventStore
from human_to_agent.services.migrations import Migration, MigrationService

NOW = datetime(2026, 7, 10, tzinfo=UTC)


def workspace(root: Path) -> Path:
    target = root / "workspaces" / "pilot"
    (target / ".foundry").mkdir(parents=True)
    (target / "workspace.yaml").write_text("schema_version: '1'\nname: pilot\n")
    (target / ".foundry" / "artifact-index.yaml").write_text("schema_version: '1'\nentries: []\n")
    return target


def migrations() -> tuple[Migration, ...]:
    return (
        Migration("1", "2", lambda raw: {**raw, "schema_version": "2", "first": True}),
        Migration("2", "3", lambda raw: {**raw, "schema_version": "3", "second": raw["first"]}),
    )


def test_migrations_are_sequential_pure_and_dry_run_changes_no_bytes(tmp_path: Path) -> None:
    target = workspace(tmp_path)
    before = (target / "workspace.yaml").read_bytes()
    service = MigrationService(tmp_path, EventStore(), validator=lambda _: True)
    result = service.migrate(
        "pilot", migrations(), target_version="3", actor="owner", at=NOW, dry_run=True
    )
    assert result.from_version == "1" and result.to_version == "3"
    assert (target / "workspace.yaml").read_bytes() == before
    assert not (target / ".foundry" / "events.jsonl").exists()


def test_failed_candidate_validation_preserves_original_tree(tmp_path: Path) -> None:
    target = workspace(tmp_path)
    before = (target / "workspace.yaml").read_bytes()
    service = MigrationService(tmp_path, EventStore(), validator=lambda _: False)
    result = service.migrate("pilot", migrations(), target_version="3", actor="owner", at=NOW)
    assert not result.applied
    assert (target / "workspace.yaml").read_bytes() == before


def test_success_records_versions_and_one_event(tmp_path: Path) -> None:
    target = workspace(tmp_path)
    service = MigrationService(tmp_path, EventStore(), validator=lambda _: True)
    result = service.migrate("pilot", migrations(), target_version="3", actor="owner", at=NOW)
    assert result.applied
    raw = yaml.safe_load((target / "workspace.yaml").read_text())
    assert raw["schema_version"] == "3" and raw["second"] is True
    events = EventStore().replay(result.event_scope).events
    assert len(events) == 1
    assert events[0].payload["from_version"] == "1"
    assert events[0].payload["to_version"] == "3"
