# Architecture overview

Human to Agent separates four layers. Normative Markdown/YAML/JSONL in `workspaces/` is the only business source. Frozen Pydantic models enforce asset contracts and evidence semantics. Repository services canonicalize files, validate references, maintain artifact indexes, append hash-chained events, and apply locked WAL transactions. The `hta` CLI is a non-interactive boundary over those services. Deterministic `dist/` trees are disposable delivery artifacts.

State-changing operations validate a prospective tree, stage bytes, replace ordinary files, replace the artifact index last, append one event, and clean the journal. External and irreversible tools stop at an unexecuted Action Package and Human Gate decision. Codex and OpenCode adapters only discover shared Skills and Agents.
