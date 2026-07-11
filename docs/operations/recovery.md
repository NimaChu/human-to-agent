# Transaction and event recovery

Transactions progress through `prepared`, `staged`, `files_replaced`, `index_replaced`, and `event_committed`. Each checkpoint is written to `state/transactions/<id>/journal.json` and fsynced while a workspace file lock is held.

Run `uv run hta doctor --format json` after an interrupted writer, then inspect the journal and `uv run hta events verify --workspace <id> --format json`. Recovery before `event_committed` restores backups and truncates any partial event, producing an all-old tree. Recovery at or after `event_committed` retains the published files and event, producing an all-new tree. It never accepts half-applied state. Repeated recovery is idempotent and does not duplicate the event.

Do not manually delete a journal. Preserve it for diagnosis; copy the workspace if forensic review is needed. A lock, filesystem, or transaction failure exits 8; event integrity or replay exits 9.
