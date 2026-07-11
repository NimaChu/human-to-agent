from pathlib import Path

from human_to_agent.services.schema_catalog import main


def test_schema_catalog_write_and_check_detects_drift(tmp_path: Path) -> None:
    assert main(["--write", str(tmp_path)]) == 0
    assert main(["--check", str(tmp_path)]) == 0

    evidence_path = tmp_path / "evidence.schema.json"
    evidence_path.write_text("{}\n", encoding="utf-8")

    assert main(["--check", str(tmp_path)]) == 1
    assert main(["--write", str(tmp_path)]) == 0
    assert main(["--check", str(tmp_path)]) == 0
