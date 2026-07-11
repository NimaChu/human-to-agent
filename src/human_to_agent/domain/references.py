from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True, slots=True)
class ReferenceDiagnostic:
    code: str
    message: str
    source_id: str
    field: str
    target_id: str


@dataclass(frozen=True, slots=True)
class ReferenceValidation:
    errors: tuple[ReferenceDiagnostic, ...]


@dataclass(frozen=True, slots=True)
class ReferenceGraph:
    edges: Mapping[str, Mapping[str, tuple[str, ...]]]

    @classmethod
    def from_edges(
        cls,
        edges: Mapping[str, Mapping[str, tuple[str, ...]]],
    ) -> ReferenceGraph:
        normalized = {
            source: {
                field: tuple(sorted(set(targets))) for field, targets in sorted(fields.items())
            }
            for source, fields in sorted(edges.items())
        }
        return cls(edges=normalized)

    @classmethod
    def from_assets(cls, assets: Mapping[str, BaseModel]) -> ReferenceGraph:
        edges: dict[str, dict[str, tuple[str, ...]]] = {}
        for asset_id, asset in sorted(assets.items()):
            fields: dict[str, tuple[str, ...]] = {}
            for name in type(asset).model_fields:
                if name == "id":
                    continue
                value = getattr(asset, name)
                if name.endswith("_ref") and isinstance(value, str):
                    fields[name] = (value,)
                elif (name.endswith("_refs") or name in {"links", "evidence_refs"}) and isinstance(
                    value, tuple
                ):
                    fields[name] = tuple(item for item in value if isinstance(item, str))
            edges[asset_id] = fields
        return cls.from_edges(edges)

    def reverse_dependents(self, target_id: str) -> tuple[str, ...]:
        reverse: dict[str, set[str]] = defaultdict(set)
        for source, fields in self.edges.items():
            for targets in fields.values():
                for target in targets:
                    reverse[target].add(source)

        found: set[str] = set()
        seen = {target_id}
        pending = deque(sorted(reverse.get(target_id, ())))
        while pending:
            item = pending.popleft()
            if item in seen:
                continue
            seen.add(item)
            found.add(item)
            pending.extend(sorted(reverse.get(item, ())))
        return tuple(sorted(found))


def validate_references(
    graph: ReferenceGraph,
    known_ids: set[str],
) -> ReferenceValidation:
    errors: list[ReferenceDiagnostic] = []
    for source_id, fields in sorted(graph.edges.items()):
        for field, targets in sorted(fields.items()):
            for target_id in targets:
                if target_id not in known_ids:
                    errors.append(
                        ReferenceDiagnostic(
                            code="reference.missing",
                            message=f"{source_id}.{field} references missing {target_id}",
                            source_id=source_id,
                            field=field,
                            target_id=target_id,
                        )
                    )
    return ReferenceValidation(errors=tuple(errors))
