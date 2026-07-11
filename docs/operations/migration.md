# Schema migration

Run migration with `--dry-run` first. Migrations form a sequential version chain and each transform is pure: it receives a copy and must declare the next Schema version. Human to Agent renders the candidate into an isolated tree and validates it before touching the source.

If candidate validation fails, the original bytes remain unchanged. An applied migration updates the assets and index in one transaction and appends exactly one event containing before/after Schema versions. A pre-commit interruption follows normal rollback and recovery; an `event_committed` interruption retains the all-new migration. Never edit generated distribution files to simulate a migration.
