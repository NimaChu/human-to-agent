import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]


def test_every_inventory_requirement_has_direct_proved_audit_row() -> None:
    inventory = yaml.safe_load(
        (ROOT / "docs/traceability/requirement-inventory.yaml").read_text(encoding="utf-8")
    )["requirements"]
    audit = (ROOT / "docs/traceability/completion-audit.md").read_text(encoding="utf-8")
    for item in inventory:
        row = next(line for line in audit.splitlines() if line.startswith(f"| {item['id']} |"))
        assert "| proved |" in row
        assert "test_" in row
        assert "pytest -q |" not in row


def test_audit_uses_only_allowed_proof_statuses_and_current_paths() -> None:
    audit = (ROOT / "docs/traceability/completion-audit.md").read_text(encoding="utf-8")
    rows = [line for line in audit.splitlines() if re.match(r"\| HF-\d+ \|", line)]
    assert rows
    allowed = {"proved", "contradicted", "incomplete", "indirect", "missing"}
    for row in rows:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        assert cells[2] in allowed
        evidence_path = cells[3].split("::", 1)[0]
        assert (ROOT / evidence_path).is_file()
