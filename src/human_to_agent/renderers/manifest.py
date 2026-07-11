from __future__ import annotations

import json
from collections.abc import Mapping


def render_manifest(value: Mapping[str, object]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
