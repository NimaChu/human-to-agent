from __future__ import annotations

import re
from pathlib import Path

from harness_foundry.cli.result import CommandResult

SECRET_PATTERNS = (
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"(?i)(?:password|api[_-]?key|token|credential)\s*[:=]\s*[^\s]{8,}"),
    re.compile(rb"(?i)bearer\s+[a-z0-9._~+/=-]{12,}"),
)
EXCLUDED = {".foundry", ".git", ".venv", "dist", "state", "__pycache__"}


def inspect_workspace(root: Path) -> CommandResult:
    diagnostics: list[dict[str, object]] = []
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
    return CommandResult(
        command="doctor",
        status="ok" if not diagnostics else "error",
        exit_code=0 if not diagnostics else 6,
        diagnostics=diagnostics,
    )
