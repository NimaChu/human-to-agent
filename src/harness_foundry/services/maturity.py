from __future__ import annotations

from typing import Any

from harness_foundry.domain.stages import GateReport, GateStatus


def render_maturity_json(report: GateReport) -> dict[str, Any]:
    return report.model_dump(mode="json")


def render_maturity_markdown(report: GateReport) -> str:
    lines = [f"# Maturity gate: {report.target}", ""]
    for status in GateStatus:
        lines.extend((f"## {status.value}", ""))
        checks = [check for check in report.checks if check.status is status]
        if not checks:
            lines.extend(("- None", ""))
            continue
        for check in checks:
            lines.append(f"- **{check.requirement_id}** — {check.message}")
            if check.evidence_refs:
                lines.append(f"  - Evidence: {', '.join(check.evidence_refs)}")
            if check.next_action:
                lines.append(f"  - Next action: {check.next_action}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
