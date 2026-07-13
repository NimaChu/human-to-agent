from __future__ import annotations

import re
from pathlib import Path

from human_to_agent.cli.errors import FoundryError
from human_to_agent.cli.result import CommandResult
from human_to_agent.domain.events import EventScope
from human_to_agent.repositories.events import EventStore
from human_to_agent.repositories.transactions import TransactionBusyError
from human_to_agent.services.adapters import verify_adapter_sources
from human_to_agent.services.recovery import RecoveryService
from human_to_agent.services.workspaces import _is_link_or_junction, _safe_workspace_root

SECRET_PATTERNS = (
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"(?i)(?:password|api[_-]?key|token|credential)\s*[:=]\s*[^\s]{8,}"),
    re.compile(rb"(?i)bearer\s+[a-z0-9._~+/=-]{12,}"),
)
EXCLUDED = {".foundry", ".git", ".venv", "dist", "__pycache__"}


def inspect_workspace(root: Path) -> CommandResult:
    diagnostics: list[dict[str, object]] = []
    try:
        recovered = RecoveryService(root, EventStore()).recover_all()
    except ValueError as error:
        recovered = ()
        diagnostics.append(
            {
                "category": "transaction",
                "code": "transaction.recovery_invalid",
                "message": f"Recovery state is invalid: {error}",
                "path": "state/transactions",
            }
        )
    except (OSError, TransactionBusyError) as error:
        recovered = ()
        diagnostics.append(
            {
                "category": "transaction",
                "code": "transaction.recovery_unavailable",
                "message": f"Recovery could not be completed: {error}",
                "path": "state/transactions",
            }
        )
    try:
        workspace_root = _safe_workspace_root(root)
    except FoundryError as error:
        diagnostics.append(
            {
                "category": "filesystem",
                "code": error.code,
                "message": error.message,
                "path": "workspaces",
            }
        )
        workspace_root = None
    if workspace_root is not None and workspace_root.exists():
        for workspace in sorted(workspace_root.iterdir()):
            if workspace.name.startswith("."):
                continue
            if _is_link_or_junction(workspace):
                diagnostics.append(
                    {
                        "category": "filesystem",
                        "code": "filesystem.unsafe_workspace_path",
                        "message": (
                            "Workspace source contains a symlink, junction, or out-of-bound path."
                        ),
                        "path": workspace.relative_to(root).as_posix(),
                    }
                )
                continue
            if not workspace.is_dir():
                continue
            try:
                files = _safe_workspace_files(workspace)
            except (OSError, ValueError):
                diagnostics.append(
                    {
                        "category": "filesystem",
                        "code": "filesystem.unsafe_workspace_path",
                        "message": (
                            "Workspace source contains a symlink, junction, or out-of-bound path."
                        ),
                        "path": workspace.relative_to(root).as_posix(),
                    }
                )
                continue
            for path in files:
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
            event_log = workspace / ".foundry" / "events.jsonl"
            try:
                _require_safe_event_log(event_log, workspace)
            except (OSError, ValueError):
                diagnostics.append(
                    {
                        "category": "filesystem",
                        "code": "filesystem.unsafe_workspace_path",
                        "message": (
                            "Workspace source contains a symlink, junction, or out-of-bound path."
                        ),
                        "path": workspace.relative_to(root).as_posix(),
                    }
                )
                continue
            scope = EventScope(
                scope_id=workspace.name,
                log_path=event_log,
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
    exit_by_category = {
        "policy": 6,
        "adapter": 7,
        "filesystem": 8,
        "transaction": 8,
        "event": 9,
    }
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


def _safe_workspace_files(workspace: Path) -> tuple[Path, ...]:
    if _is_link_or_junction(workspace):
        raise ValueError("workspace cannot be a symlink or junction")
    files: list[Path] = []
    pending = [workspace]
    resolved_workspace = workspace.resolve()
    while pending:
        current = pending.pop()
        for path in current.iterdir():
            relative = path.relative_to(workspace)
            if _is_link_or_junction(path):
                raise ValueError(f"unsafe workspace path: {relative.as_posix()}")
            if not path.resolve().is_relative_to(resolved_workspace):
                raise ValueError(
                    f"workspace path resolves outside workspace: {relative.as_posix()}"
                )
            if path.is_dir():
                if any(part in EXCLUDED for part in relative.parts):
                    continue
                pending.append(path)
            elif path.is_file() and not any(part in EXCLUDED for part in relative.parts):
                files.append(path)
    return tuple(sorted(files))


def _require_safe_event_log(event_log: Path, workspace: Path) -> None:
    foundry = event_log.parent
    if _is_link_or_junction(foundry) or _is_link_or_junction(event_log):
        raise ValueError("event log cannot be a symlink or junction")
    if not foundry.resolve().is_relative_to(
        workspace.resolve()
    ) or not event_log.resolve().is_relative_to(workspace.resolve()):
        raise ValueError("event log resolves outside workspace")
