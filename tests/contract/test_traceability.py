from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]


def test_inventory_and_traceability_are_bijective_and_evidenced() -> None:
    inventory = yaml.safe_load(
        (ROOT / "docs/traceability/requirement-inventory.yaml").read_text(encoding="utf-8")
    )["requirements"]
    rows = yaml.safe_load(
        (ROOT / "docs/traceability/pr-requirements.yaml").read_text(encoding="utf-8")
    )["requirements"]
    inventory_ids = [item["id"] for item in inventory]
    row_ids = [item["id"] for item in rows]
    locators = [f"{item['source']}#{item['locator']}" for item in inventory]
    assert len(locators) == len(set(locators))
    assert len(inventory_ids) == len(set(inventory_ids))
    assert set(inventory_ids) == set(row_ids)
    test_text = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "tests").rglob("test_*.py")
    )
    for row in rows:
        assert row["status"] == "achieved" and row["gap"] is None and row["owner"]
        assert (ROOT / row["specification"]).exists()
        assert (ROOT / row["implementation"]).exists()
        test_name = row["evidence"].split("::", 1)[1]
        assert test_name in test_text


def test_all_authoritative_sources_have_inventory_rows() -> None:
    inventory = yaml.safe_load(
        (ROOT / "docs/traceability/requirement-inventory.yaml").read_text(encoding="utf-8")
    )["requirements"]
    sources = {item["source"] for item in inventory}
    assert sources == {
        "PR/Harness Foundry PR.md",
        "PR/supplements/Agent-Harness.md",
        "PR/supplements/Know your unknowns - complete.html",
        "PR/supplements/Loop Engineering.md",
    }
    assert all((ROOT / source).is_file() for source in sources)
