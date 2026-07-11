import json
from pathlib import Path

from human_to_agent.domain.common import AssetMetadata
from human_to_agent.domain.evidence import Evidence
from human_to_agent.services.schema_catalog import build_schema_documents

ROOT = Path(__file__).parents[2]


def test_generated_schemas_equal_committed_v1() -> None:
    generated = build_schema_documents({"asset-metadata": AssetMetadata, "evidence": Evidence})
    committed = {
        name: json.loads(
            (ROOT / "schemas" / "v1" / f"{name}.schema.json").read_text(encoding="utf-8")
        )
        for name in generated
    }
    assert generated == committed
