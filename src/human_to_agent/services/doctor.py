from __future__ import annotations

import re
from pathlib import Path

from human_to_agent.cli.result import CommandResult
from human_to_agent.domain.events import EventScope
from human_to_agent.repositories.events import EventStore
from human_to_agent.services.adapters import verify_adapter_sources
from human_to_agent.services.recovery import RecoveryService

SECRET_PATTERNS = (
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"(?i)(?:password|api[_-]?key|token|credential)\s*[:=]\s*[^\s]{8,}"),
    re.compile(rb"(?i)bearer\s+[a-z0-9._~+/=-]{12,}"),
)
EXCLUDED = {".foundry", ".git", ".venv", "dist", "state", "__pycache__"}


def inspect_workspace(root: Path) -> CommandResult:
    diagnostics: list[dict[str, object]] = []
    recovered = RecoveryService(root, EventStore()).recover_all()
    workspace_root = root / "workspaces"
    if workspace_root.exists():
        for path in sorted(item for item in workspace_root.rglob("*") if item.is_file()):
            if any(part in EXCLUDED for part in path.relative_to(root).parts):
                continue
            content = path.read_bytes()
            if any(pattern.search(content) for pattern in SECRET_PATTERNS):
                diagnostics.append(
                    {
                        "category": "policy",
                        "code": "policy.secret_in_normative_source",
                        "message": "Potential credential found; value redacted.",
                        "path": path.relative_to(root).as_posix(),
                    }
                )
        for workspace in sorted(path for path in workspace_root.iterdir() if path.is_dir()):
            scope = EventScope(
                scope_id=workspace.name,
                log_path=workspace / ".foundry" / "events.jsonl",
            )
            verification = EventStore().verify(scope)
            diagnostics.extend(
                {
                    "category": "event",
                    "code": "event.invalid",
                    "message": message,
                    "path": str(scope.log_path.relative_to(root)),
                }
                for message in verification.errors
            )
    if (root / "skills" / "catalog.yaml").is_file():
        diagnostics.extend(
            item.model_dump(mode="json", exclude_none=True)
            for item in verify_adapter_sources(root).diagnostics
        )
    exit_by_category = {"policy": 6, "adapter": 7, "event": 9}
    exit_code = max(
        (exit_by_category.get(str(item["category"]), 0) for item in diagnostics), default=0
    )
    return CommandResult(
        command="doctor",
        status="ok" if not diagnostics else "error",
        exit_code=exit_code,
        diagnostics=diagnostics,
        next_actions=[f"recovered_transaction={item.transaction_id}" for item in recovered],
    )
