# Harness Foundry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete, file-first Harness Foundry mother workspace that guides and verifies the five-stage evolution from a real task to a transferable, Loop-ready child workspace.

**Architecture:** Markdown, YAML, and JSONL are the only business source of truth. A Python 3.11+ package provides pure domain rules, filesystem repositories, evidence-backed gates, append-only events, recoverable transactions, deterministic rendering, and a non-interactive `hf` CLI; Codex and OpenCode remain thin adapters over shared Skills and Agents.

**Tech Stack:** Python 3.11+, uv, Pydantic v2, PyYAML, Typer, Rich, Jinja2, filelock, pytest, Hypothesis, Ruff, mypy, GitHub Actions.

## Global Constraints

- No interactive UI, database, network dependency at runtime, production Loop executor, or direct external high-risk action.
- Source assets under `workspaces/` are authoritative; `dist/` is generated, reproducible, and never read as business input.
- Same source tree, CLI version, Schema version, and template version must produce byte-identical output.
- Every state-changing command is non-interactive, supports `--dry-run`, and validates the prospective tree before modification.
- CLI exit codes are fixed: `0` success, `2` usage/config, `3` Schema, `4` references, `5` evidence/gate, `6` policy/Human Gate, `7` version/migration/adapter, `8` filesystem/lock/transaction, `9` event/replay.
- Stage 3 needs at least normal, boundary, and failure/exception cases plus independent review.
- A complete release needs all PR §12.5/§18.3 evidence and at least `conditional_ready` Loop Readiness.
- The ten PR readiness dimensions and six supplement dimensions are assessed individually; no aggregate score auto-approves H0–H5 autonomy.
- Acme names, paths, numbers, TTLs, permissions, performance figures, rate-limit constants, and formulas from supplements are examples only.
- New behavior follows strict red-green-refactor TDD. Every task ends with targeted tests, full regression tests, and a focused commit.
- Windows and Linux paths are handled with `pathlib`; canonical relative paths always use POSIX separators.

---

## File Responsibility Map

| Area | Files | Responsibility |
|---|---|---|
| Project contract | `README.md`, `AGENTS.md`, `foundry.yaml`, `pyproject.toml` | User entry, durable agent rules, root configuration, toolchain |
| Domain | `src/harness_foundry/domain/*.py` | Pure immutable models and business decisions; no filesystem access |
| Schemas | `schemas/v1/*.schema.json` | Committed, deterministic JSON Schema generated from domain models |
| Repositories | `src/harness_foundry/repositories/*.py` | Canonical reads, reference index, event chains, locks, transactions |
| Services | `src/harness_foundry/services/*.py` | Validation, gates, reporting, recovery, migration, build orchestration |
| Rendering | `src/harness_foundry/renderers/*.py`, `templates/child-workspace/` | Deterministic release tree and manifest |
| CLI | `src/harness_foundry/cli/*.py` | Stable command envelope, exit-code mapping, text/JSON presentation |
| Method source | `skills/`, `agents/` | Cross-tool authoritative workflows and roles |
| Tool adapters | `.codex/`, `.opencode/` | Thin discovery/permission/command entrypoints only |
| State | `state/`, `workspaces/*/.foundry/` | Root registry/events and child events/checkpoints/transactions |
| Pilot | `examples/harness-foundry-pilot/`, `workspaces/harness-foundry-pilot/` | Real, complete five-stage trial using the supplied PR and supplements |
| Proof | `tests/`, `docs/traceability/`, `.github/workflows/ci.yml` | Behavior evidence, requirement mapping, completion audit, CI |

---

### Task 1: Reproducible project baseline and CLI result envelope

**Files:**
- Create: `.python-version`
- Create: `.editorconfig`
- Create: `.gitattributes`
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `foundry.yaml`
- Create: `README.md`
- Create: `AGENTS.md`
- Create: `state/registry.yaml`
- Create: `state/events.jsonl`
- Create: `state/runs/.gitkeep`
- Create: `state/transactions/.gitkeep`
- Create: `state/locks/.gitkeep`
- Create: `workspaces/.gitkeep`
- Create: `src/harness_foundry/__init__.py`
- Create: `src/harness_foundry/py.typed`
- Create: `src/harness_foundry/cli/__init__.py`
- Create: `src/harness_foundry/cli/result.py`
- Create: `src/harness_foundry/cli/app.py`
- Create: `tests/contract/test_project_baseline.py`
- Create: `tests/contract/test_cli_contract.py`

**Interfaces:**
- Produces: `harness_foundry.__version__: str`
- Produces: `CommandResult(command, status, exit_code, diagnostics, changed_files, next_actions)`
- Produces: Typer application `harness_foundry.cli.app:app`
- Produces: console script `hf`

- [ ] **Step 1: Add the build/test harness and failing baseline tests**

Create `pyproject.toml` with this complete baseline:

```toml
[build-system]
requires = ["hatchling>=1.27,<2"]
build-backend = "hatchling.build"

[project]
name = "harness-foundry"
version = "0.1.0"
description = "File-first incubator for evidence-backed Agent workspaces"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "filelock>=3.18,<4",
  "jinja2>=3.1,<4",
  "pydantic>=2.11,<3",
  "pyyaml>=6.0,<7",
  "rich>=14,<15",
  "typer>=0.16,<1",
]

[dependency-groups]
dev = [
  "hypothesis>=6.135,<7",
  "mypy>=1.16,<2",
  "pytest>=8.4,<9",
  "pytest-cov>=6.2,<7",
  "ruff>=0.12,<1",
  "types-pyyaml>=6.0.12,<7",
]

[project.scripts]
hf = "harness_foundry.cli.app:main"

[tool.hatch.build.targets.wheel]
packages = ["src/harness_foundry"]

[tool.pytest.ini_options]
addopts = "--strict-config --strict-markers"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]

[tool.mypy]
python_version = "3.11"
strict = true
packages = ["harness_foundry"]
```

Create tests that import the not-yet-existing package:

```python
# tests/contract/test_cli_contract.py
import json

from typer.testing import CliRunner

from harness_foundry.cli.app import app


runner = CliRunner()


def test_version_uses_stable_json_envelope() -> None:
    result = runner.invoke(app, ["version", "--format", "json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "changed_files": [],
        "command": "version",
        "diagnostics": [],
        "exit_code": 0,
        "next_actions": [],
        "status": "ok",
    }


def test_invalid_format_is_usage_error() -> None:
    result = runner.invoke(app, ["version", "--format", "xml"])
    assert result.exit_code == 2
```

```python
# tests/contract/test_project_baseline.py
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_required_root_layout_exists() -> None:
    required = {
        "README.md", "AGENTS.md", "foundry.yaml", "pyproject.toml",
        "PR", "docs", "state", "workspaces",
    }
    assert required <= {path.name for path in ROOT.iterdir()}


def test_runtime_dependencies_are_offline_safe() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "requests" not in text
    assert "httpx" not in text
    assert 'requires-python = ">=3.11"' in text
```

- [ ] **Step 2: Install uv, resolve the environment, and verify RED**

Run:

```powershell
python -m pip install uv
uv sync --no-install-project --all-groups
uv run --no-sync pytest tests/contract/test_cli_contract.py -q
```

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'harness_foundry'`; dependency/bootstrap metadata must not fail first.

- [ ] **Step 3: Implement the minimal package and CLI envelope**

```python
# src/harness_foundry/__init__.py
__version__ = "0.1.0"
```

```python
# src/harness_foundry/cli/result.py
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True, slots=True)
class CommandResult:
    command: str
    status: str = "ok"
    exit_code: int = 0
    diagnostics: list[dict[str, object]] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)
```

```python
# src/harness_foundry/cli/app.py
from __future__ import annotations

import json
from enum import Enum

import typer

from harness_foundry import __version__
from harness_foundry.cli.result import CommandResult


class OutputFormat(str, Enum):
    text = "text"
    json = "json"


app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def version(output_format: OutputFormat = typer.Option(OutputFormat.text, "--format")) -> None:
    result = CommandResult(command="version")
    if output_format is OutputFormat.json:
        typer.echo(json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True))
    else:
        typer.echo(f"Harness Foundry {__version__}")


def main() -> None:
    app()
```

Create the declared root files with UTF-8, LF line endings; `foundry.yaml` must contain `schema_version: "1"`, `workspace_root: workspaces`, `distribution_root: dist`, and `state_root: state`. Initialize `state/registry.yaml` as `schema_version: "1"` plus an empty `workspaces` mapping, and `state/events.jsonl` as an empty UTF-8 file.

- [ ] **Step 4: Verify GREEN and lock the environment**

Run:

```powershell
uv lock
uv run pytest tests/contract/test_project_baseline.py tests/contract/test_cli_contract.py -q
uv run ruff check src tests
uv run mypy src
```

Expected: all tests PASS, Ruff and mypy exit 0, and `uv.lock` exists.

- [ ] **Step 5: Commit**

```powershell
git add .python-version .editorconfig .gitattributes .gitignore pyproject.toml uv.lock foundry.yaml README.md AGENTS.md state workspaces src tests/contract
git commit -m "chore: establish reproducible Harness Foundry baseline"
```

---

### Task 2: Common asset metadata, evidence semantics, and deterministic Schema catalog

**Files:**
- Create: `src/harness_foundry/domain/__init__.py`
- Create: `src/harness_foundry/domain/common.py`
- Create: `src/harness_foundry/domain/evidence.py`
- Create: `src/harness_foundry/services/schema_catalog.py`
- Create: `tests/unit/domain/test_evidence.py`
- Create: `tests/schema/test_domain_schema_catalog.py`
- Create: `tests/contract/test_schema_catalog_cli.py`
- Create: `schemas/v1/asset-metadata.schema.json`
- Create: `schemas/v1/evidence.schema.json`

**Interfaces:**
- Produces: `AssetMetadata`, `Evidence`, `EvidenceBasis`, `EvidenceType`
- Produces: `build_schema_documents(models) -> dict[str, dict[str, Any]]`
- Produces: `write_schema_documents(output_dir, documents) -> tuple[Path, ...]`
- Produces: `python -m harness_foundry.services.schema_catalog --write schemas/v1` and `--check schemas/v1`

- [ ] **Step 1: Write failing evidence and Schema-drift tests**

```python
# tests/unit/domain/test_evidence.py
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from harness_foundry.domain.evidence import Evidence, EvidenceBasis, EvidenceType


BASE = {
    "schema_version": "1",
    "id": "ev-rule-1",
    "workspace_id": "ws-pilot",
    "revision": 1,
    "status": "active",
    "owners": ("business-owner",),
    "created_at": datetime(2026, 7, 10, tzinfo=UTC),
    "updated_at": datetime(2026, 7, 10, tzinfo=UTC),
    "provenance": "human",
    "links": (),
    "evidence_refs": (),
    "type": EvidenceType.formal_rule,
    "source": "PR/Harness Foundry PR.md",
    "locator": "§10.4",
    "captured_by": "requirements-reviewer",
    "captured_at": datetime(2026, 7, 10, tzinfo=UTC),
    "content_summary": "The PR requires evidence-backed Unknown closure.",
    "claim": "Unknown closure requires evidence",
    "basis": EvidenceBasis.observed,
    "applicability_scope": ("Harness Foundry workspaces",),
    "validity_conditions": ("PR remains normative",),
    "invalidation_conditions": ("The Owner supersedes PR §10.4",),
    "content_sha256": "0" * 64,
}


def test_low_confidence_claim_requires_cheapest_probe() -> None:
    with pytest.raises(ValidationError, match="cheapest_probe"):
        Evidence(**(BASE | {"basis": EvidenceBasis.assumption}))


def test_evidence_requires_exact_source_and_validity() -> None:
    with pytest.raises(ValidationError):
        Evidence(**(BASE | {"locator": "", "validity_conditions": ()}))
```

```python
# tests/schema/test_domain_schema_catalog.py
import json
from pathlib import Path

from harness_foundry.domain.common import AssetMetadata
from harness_foundry.domain.evidence import Evidence
from harness_foundry.services.schema_catalog import build_schema_documents


ROOT = Path(__file__).parents[2]


def test_generated_schemas_equal_committed_v1() -> None:
    generated = build_schema_documents({"asset-metadata": AssetMetadata, "evidence": Evidence})
    committed = {
        name: json.loads((ROOT / "schemas" / "v1" / f"{name}.schema.json").read_text())
        for name in generated
    }
    assert generated == committed
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/domain/test_evidence.py tests/schema/test_domain_schema_catalog.py -q`

Expected: FAIL because `harness_foundry.domain.common` and `evidence` do not exist.

- [ ] **Step 3: Implement immutable metadata and evidence models**

Implement `AssetMetadata` as a frozen Pydantic model with the shared fields from design §9, UTC-aware timestamps, non-empty owners, immutable tuple references, and `extra="forbid"`. Implement these evidence enums exactly:

```python
class EvidenceBasis(StrEnum):
    observed = "observed"
    inferred = "inferred"
    assumption = "assumption"
    unverified = "unverified"


class EvidenceType(StrEnum):
    formal_rule = "formal_rule"
    real_case = "real_case"
    owner_confirmation = "owner_confirmation"
    system_definition = "system_definition"
    historical_data = "historical_data"
    risk_decision = "risk_decision"
    repeatable_validation = "repeatable_validation"
```

`Evidence` extends `AssetMetadata` with `type`, `source`, `locator`, `captured_by`, `captured_at`, `content_summary`, `claim`, `basis`, `applicability_scope`, `validity_conditions`, `invalidation_conditions`, `content_sha256`, and optional `cheapest_probe`. A model validator must require UTC-aware capture time, exact source/locator, non-empty applicability and validity data, and `cheapest_probe` for `assumption` or `unverified` evidence.

Implement Schema output with sorted keys, UTF-8, LF, two-space indentation, and one terminal newline:

```python
def build_schema_documents(models: Mapping[str, type[BaseModel]]) -> dict[str, dict[str, Any]]:
    return {name: model.model_json_schema(mode="validation") for name, model in sorted(models.items())}


def write_schema_documents(output_dir: Path, documents: Mapping[str, dict[str, Any]]) -> tuple[Path, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, document in sorted(documents.items()):
        path = output_dir / f"{name}.schema.json"
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        written.append(path)
    return tuple(written)
```

Add `DEFAULT_MODELS: dict[str, type[BaseModel]]`, a small `argparse` `main(argv: Sequence[str] | None = None) -> int`, and module entrypoint tests. `--write PATH` writes the default model catalog; `--check PATH` compares generated documents to disk and exits nonzero on drift. Every later domain-model task extends the explicit default catalog. Add valid, invalid, and boundary fixtures for every registered asset type; the Schema suite must parameterize over the full catalog.

`tests/contract/test_schema_catalog_cli.py` invokes `main(["--write", path])`, mutates one generated byte, proves `main(["--check", path]) == 1`, rewrites, then proves check returns 0.

- [ ] **Step 4: Generate Schemas and verify GREEN**

Run:

```powershell
uv run python -c "from pathlib import Path; from harness_foundry.domain.common import AssetMetadata; from harness_foundry.domain.evidence import Evidence; from harness_foundry.services.schema_catalog import build_schema_documents, write_schema_documents; write_schema_documents(Path('schemas/v1'), build_schema_documents({'asset-metadata': AssetMetadata, 'evidence': Evidence}))"
uv run pytest tests/unit/domain/test_evidence.py tests/schema/test_domain_schema_catalog.py tests/contract/test_schema_catalog_cli.py -q
uv run pytest -q
```

Expected: targeted and full suites PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/harness_foundry/domain src/harness_foundry/services/schema_catalog.py schemas/v1 tests/unit/domain tests/schema tests/contract/test_schema_catalog_cli.py
git commit -m "feat: define evidence-backed asset foundation"
```

---

### Task 3: Business asset contracts and reference graph

**Files:**
- Create: `src/harness_foundry/domain/assets.py`
- Create: `src/harness_foundry/domain/references.py`
- Create: `tests/unit/domain/test_assets.py`
- Create: `tests/unit/domain/test_references.py`
- Create: `schemas/v1/workspace.schema.json`
- Create: `schemas/v1/task-contract.schema.json`
- Create: `schemas/v1/skill.schema.json`
- Create: `schemas/v1/case.schema.json`
- Create: `schemas/v1/evaluation.schema.json`
- Create: `schemas/v1/workflow.schema.json`
- Create: `schemas/v1/harness.schema.json`
- Create: `schemas/v1/tool.schema.json`
- Create: `schemas/v1/context.schema.json`
- Create: `schemas/v1/state-model.schema.json`
- Create: `schemas/v1/evaluator.schema.json`
- Create: `schemas/v1/policy.schema.json`
- Create: `schemas/v1/human-gate.schema.json`
- Create: `schemas/v1/action-package.schema.json`
- Create: `schemas/v1/human-gate-decision.schema.json`
- Create: `schemas/v1/exception.schema.json`
- Create: `schemas/v1/run.schema.json`

**Interfaces:**
- Produces: `WorkspaceManifest`, `TaskContract`, `SkillSpec`, `CaseRecord`, `EvaluationRecord`, `WorkflowSpec`, `HarnessSpec`, `ToolSpec`, `ContextSpec`, `StateModelSpec`, `EvaluatorSpec`, `PolicySpec`, `HumanGateSpec`, `ActionPackage`, `HumanGateDecision`, `ExceptionSpec`, `RunRecord`
- Produces: `ReferenceGraph.from_assets(assets)`, `validate_references(graph)`, `reverse_dependents(asset_id)`

- [ ] **Step 1: Write failing asset-boundary and reference tests**

```python
# tests/unit/domain/test_references.py
from harness_foundry.domain.references import ReferenceGraph, validate_references


def test_missing_reference_is_reported_with_source_and_field() -> None:
    graph = ReferenceGraph.from_edges({"skill.extract": {"cases": ("case.missing",)}})
    report = validate_references(graph, known_ids={"skill.extract"})
    assert report.errors[0].code == "reference.missing"
    assert report.errors[0].source_id == "skill.extract"
    assert report.errors[0].field == "cases"


def test_reverse_dependents_are_transitive_and_sorted() -> None:
    graph = ReferenceGraph.from_edges({
        "skill.extract": {},
        "workflow.main": {"skills": ("skill.extract",)},
        "readiness.main": {"workflow": ("workflow.main",)},
    })
    assert graph.reverse_dependents("skill.extract") == ("readiness.main", "workflow.main")
```

`tests/unit/domain/test_assets.py` must assert that a Skill without applicability, non-applicability, evaluator, and stop/error semantics is rejected; a Case without expected output is rejected; a Workflow without state, permissions, Human Gates, exceptions, and final evaluator is rejected; a Tool without typed input/output, permission, side effects, idempotency, and retry semantics is rejected; and a Harness missing any `E,T,C,S,L,V` reference is rejected.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/domain/test_assets.py tests/unit/domain/test_references.py -q`

Expected: FAIL because the asset and reference models are absent.

- [ ] **Step 3: Implement focused immutable models and reference diagnostics**

Each model extends `AssetMetadata`, uses `extra="forbid"`, and owns only its domain fields. Use these required shapes:

```python
class CaseKind(StrEnum):
    normal = "normal"
    boundary = "boundary"
    failure = "failure"
    golden = "golden"


class ActionClass(StrEnum):
    read_only = "read_only"
    internal_write = "internal_write"
    external_send = "external_send"
    irreversible = "irreversible"
    forbidden = "forbidden"


class SkillSpec(AssetMetadata):
    goal: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    preconditions: tuple[str, ...]
    applies_when: tuple[str, ...]
    does_not_apply_when: tuple[str, ...]
    dependencies: tuple[str, ...]
    evaluator_refs: tuple[str, ...]
    error_conditions: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    case_refs: tuple[str, ...]


class WorkflowSpec(AssetMetadata):
    goal: str
    skill_refs: tuple[str, ...]
    steps: tuple[dict[str, object], ...]
    state_model_ref: str
    policy_refs: tuple[str, ...]
    human_gate_refs: tuple[str, ...]
    exception_refs: tuple[str, ...]
    final_evaluator_ref: str


class HarnessSpec(AssetMetadata):
    goal: str
    execution_loop_ref: str
    tool_refs: tuple[str, ...]
    context_refs: tuple[str, ...]
    state_model_ref: str
    lifecycle_hooks: tuple[str, ...]
    evaluator_refs: tuple[str, ...]
    workflow_ref: str


class ToolSpec(AssetMetadata):
    name: str
    input_schema_ref: str
    output_schema_ref: str
    action_class: ActionClass
    required_permissions: tuple[str, ...]
    side_effects: tuple[str, ...]
    idempotent: bool
    retry_semantics: str
    human_gate_ref: str | None = None
```

`ContextSpec` classifies fixed, task, organizational, preference, historical, and ephemeral inputs plus retention; `StateModelSpec` declares states, transitions, checkpoints, persistence, and restore semantics; `EvaluatorSpec` declares independent inputs, pass/fail/indeterminate signals, acceptable deviation, and evidence output. `ActionPackage` contains a proposed external/irreversible action, inputs, expected side effects, idempotency key, required Human Gate, and no executed flag; `HumanGateDecision` records approve, reject, or modify plus actor, evidence, recovery entry, and resulting Run/Unknown references. Implement reference diagnostics as frozen records with `code`, `message`, `source_id`, `field`, and `target_id`. Graph traversal must be cycle-safe and deterministic. A forbidden Tool may not have an executable adapter; external or irreversible Tools require a Human Gate.

- [ ] **Step 4: Generate Schemas and verify GREEN**

Add all models to the Schema catalog, regenerate `schemas/v1`, then run:

```powershell
uv run pytest tests/unit/domain/test_assets.py tests/unit/domain/test_references.py tests/schema -q
uv run pytest -q
```

Expected: all tests PASS and committed Schema files equal generated documents.

- [ ] **Step 5: Commit**

```powershell
git add src/harness_foundry/domain schemas/v1 tests/unit/domain tests/schema
git commit -m "feat: model child workspace business assets"
```

---

### Task 4: Unknown lifecycle, evidence closure, and reopen history

**Files:**
- Create: `src/harness_foundry/domain/unknowns.py`
- Create: `tests/unit/domain/test_unknowns.py`
- Create: `tests/factories.py`
- Create: `tests/conftest.py`
- Create: `schemas/v1/unknown.schema.json`

**Interfaces:**
- Consumes: `Evidence`, `AssetMetadata`
- Produces: `Unknown`, `UnknownClosure`, `UnknownHistoryEntry`
- Produces: `close_unknown(item, closure, evidence) -> Unknown`
- Produces: `reopen_unknown(item, reason, actor, at, evidence_refs) -> Unknown`

- [ ] **Step 1: Write the failing lifecycle tests**

```python
# tests/unit/domain/test_unknowns.py
from datetime import UTC, datetime

import pytest

from harness_foundry.domain.unknowns import (
    UnknownDisposition,
    UnknownStatus,
    close_unknown,
    reopen_unknown,
)


NOW = datetime(2026, 7, 10, tzinfo=UTC)


def test_close_requires_allowed_evidence_owner_and_propagation(unknown, closure, evidence) -> None:
    with pytest.raises(ValueError, match="owner"):
        close_unknown(unknown, closure.model_copy(update={"owner_id": ""}), evidence)
    with pytest.raises(ValueError, match="propagation"):
        close_unknown(unknown, closure.model_copy(update={"propagated_to": ()}), evidence)


def test_accepted_risk_is_managed_not_known(unknown, closure, evidence) -> None:
    managed = close_unknown(
        unknown,
        closure.model_copy(update={"disposition": UnknownDisposition.accepted_risk}),
        evidence,
    )
    assert managed.status is UnknownStatus.accepted_risk
    assert managed.fact_resolved is False


def test_reopen_preserves_closure_and_appends_history(closed_unknown) -> None:
    reopened = reopen_unknown(
        closed_unknown,
        reason="A contradictory case appeared",
        actor="reviewer",
        at=NOW,
        evidence_refs=("ev-contradiction",),
    )
    assert reopened.status is UnknownStatus.reopened
    assert reopened.closure == closed_unknown.closure
    assert reopened.history[-1].reason == "A contradictory case appeared"
```

Provide fixtures that build valid Evidence and Unknown instances; do not mock domain behavior.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/domain/test_unknowns.py -q`

Expected: FAIL because `domain.unknowns` does not exist.

- [ ] **Step 3: Implement the complete PR lifecycle**

Define exactly 12 categories (`goal`, `input`, `rule`, `judgment`, `exception`, `acceptance`, `permission`, `tool`, `state`, `boundary`, `risk`, `responsibility`) and 10 states (`new`, `clarification`, `evidence`, `business_confirmation`, `validation`, `resolved`, `accepted_risk`, `human_only`, `out_of_scope`, `reopened`).

`Unknown` stores impact dimensions and narrative, occurrence conditions, affected assets, current evidence and confidence basis, owner, expected responder role, cheapest probe, prompt patch, and automation restriction. `close_unknown` must verify every closure evidence reference exists; at least one evidence type is allowed by the Unknown's closure policy; owner, conclusion, impact, and propagation targets are non-empty. `accepted_risk`, `human_only`, and `out_of_scope` set `fact_resolved=False`. `reopen_unknown` keeps prior closure immutable and appends a timestamped history entry. `tests/factories.py` provides typed builders for metadata, evidence, Unknowns, task contracts, Skills, cases, evaluations, Harness controls, runs, and readiness facts; `tests/conftest.py` exposes these builders without hiding domain assertions in mocks.

- [ ] **Step 4: Generate Schema and verify GREEN**

Run:

```powershell
uv run python -m harness_foundry.services.schema_catalog --write schemas/v1
uv run pytest tests/unit/domain/test_unknowns.py tests/schema -q
uv run pytest -q
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/harness_foundry/domain/unknowns.py schemas/v1/unknown.schema.json tests/unit/domain/test_unknowns.py
git commit -m "feat: enforce evidence-backed unknown lifecycle"
```

---

### Task 5: Sixteen-dimension Loop Readiness and separate autonomy approval

**Files:**
- Create: `src/harness_foundry/domain/readiness.py`
- Create: `tests/unit/domain/test_readiness.py`
- Create: `schemas/v1/readiness-policy.schema.json`
- Create: `schemas/v1/readiness-assessment.schema.json`
- Create: `schemas/v1/autonomy-approval.schema.json`

**Interfaces:**
- Consumes: evidence references from Task 2
- Produces: `assess_readiness(facts, policy) -> ReadinessAssessment`
- Produces: `record_autonomy_approval(assessment, level, owner_id, at, evidence_refs) -> AutonomyApproval`

- [ ] **Step 1: Write failing readiness and authority-separation tests**

```python
# tests/unit/domain/test_readiness.py
from datetime import UTC, datetime

import pytest

from harness_foundry.domain.readiness import (
    AutonomyLevel,
    DimensionResult,
    ReadinessDimension,
    ReadinessResult,
    assess_readiness,
    record_autonomy_approval,
)


def test_all_ten_core_and_six_supplemental_dimensions_are_assessed(policy, complete_facts) -> None:
    assessment = assess_readiness(complete_facts, policy)
    assert set(assessment.dimensions) == set(ReadinessDimension)
    assert len(assessment.dimensions) == 16


def test_indeterminate_dimension_prevents_conditional_ready(policy, complete_facts) -> None:
    facts = complete_facts.with_dimension(
        ReadinessDimension.evaluator,
        DimensionResult.indeterminate("No independent result", ()),
    )
    assert assess_readiness(facts, policy).result is ReadinessResult.not_ready


def test_recommendation_never_auto_approves_autonomy(policy, complete_facts) -> None:
    assessment = assess_readiness(complete_facts, policy)
    assert assessment.recommended_ceiling is AutonomyLevel.h3
    assert assessment.approved_autonomy is None
    with pytest.raises(ValueError, match="owner"):
        record_autonomy_approval(
            assessment,
            AutonomyLevel.h3,
            owner_id="",
            at=datetime(2026, 7, 10, tzinfo=UTC),
            evidence_refs=("ev-owner",),
        )
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/domain/test_readiness.py -q`

Expected: FAIL because `domain.readiness` does not exist.

- [ ] **Step 3: Implement explicit dimensions, policy, assessment, and approval**

Use these exact dimensions:

```python
class ReadinessDimension(StrEnum):
    goal = "goal"
    state = "state"
    action = "action"
    evaluator = "evaluator"
    stop = "stop"
    budget = "budget"
    retry = "retry"
    escalation = "escalation"
    recovery = "recovery"
    observability = "observability"
    trigger_cadence = "trigger_cadence"
    discovery_triage = "discovery_triage"
    concurrency_isolation = "concurrency_isolation"
    tool_connector_availability = "tool_connector_availability"
    independent_verifier = "independent_verifier"
    version_drift_recertification = "version_drift_recertification"
```

Each `DimensionAssessment` stores status (`satisfied`, `gap`, `indeterminate`), evidence refs, gaps, risks, and next action. `ReadinessPolicy` is versioned and explicitly maps dimension predicates to `not_ready`, `conditional_ready`, `controlled_ready`, `bounded_ready`, or `production_candidate`. `ReadinessResult.rank` is a fixed monotonic integer used only for threshold comparison, never as a maturity score. `assess_readiness` returns a recommended H0–H5 ceiling but never an approval. `record_autonomy_approval` requires a business Owner, evidence, and a level not above the recommendation.

- [ ] **Step 4: Generate Schemas and verify GREEN**

Run:

```powershell
uv run pytest tests/unit/domain/test_readiness.py -q
uv run pytest tests/schema -q
uv run pytest -q
```

Expected: all tests PASS; no aggregate numeric maturity score exists.

- [ ] **Step 5: Commit**

```powershell
git add src/harness_foundry/domain/readiness.py schemas/v1 tests/unit/domain/test_readiness.py
git commit -m "feat: assess loop readiness without auto-approving autonomy"
```

---

### Task 6: Five-stage hard gates and explainable maturity report

**Files:**
- Create: `src/harness_foundry/domain/assessment.py`
- Create: `src/harness_foundry/domain/stages.py`
- Create: `src/harness_foundry/services/maturity.py`
- Create: `tests/unit/domain/test_stage_gates.py`
- Create: `tests/unit/services/test_maturity_report.py`
- Create: `schemas/v1/stage-state.schema.json`
- Create: `schemas/v1/gate-report.schema.json`

**Interfaces:**
- Consumes: all business assets, Unknowns, evidence, Readiness, independent runs
- Produces: `assess_stage(target, snapshot) -> GateReport`
- Produces: `assess_complete_release(snapshot) -> GateReport`
- Produces: `decide_stage_transition(current, target, report, actor, at, reason) -> StageTransition`
- Produces: `render_maturity_markdown(report) -> str`, `render_maturity_json(report) -> dict[str, object]`

- [ ] **Step 1: Write one failing test for every normative gate**

Create tests named exactly:

```text
test_stage1_requires_real_trace_baseline_unknown_and_owner
test_stage2_requires_contract_skill_rerun_and_case_plan
test_stage3_requires_normal_boundary_failure_cases_and_independent_review
test_stage4_single_skill_still_requires_complete_harness_controls
test_stage5_requires_readiness_assessment
test_release_requires_pr_12_5_18_3_and_conditional_ready
test_indeterminate_gate_cannot_advance
test_new_evidence_can_reopen_an_earlier_stage
test_report_separates_satisfied_gap_and_indeterminate
```

Use real Pydantic asset objects built by fixture factories; only clocks and IDs may be injected test doubles.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/domain/test_stage_gates.py tests/unit/services/test_maturity_report.py -q`

Expected: FAIL because gate assessment is absent.

- [ ] **Step 3: Implement data-driven hard gates**

Use these core result types:

```python
class GateStatus(StrEnum):
    satisfied = "satisfied"
    gap = "gap"
    indeterminate = "indeterminate"


class GateCheck(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    requirement_id: str
    status: GateStatus
    evidence_refs: tuple[str, ...]
    message: str
    next_action: str | None = None


class GateReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    target: str
    checks: tuple[GateCheck, ...]

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(check.status is GateStatus.satisfied for check in self.checks)
```

Gate definitions must carry PR requirement IDs and return `indeterminate` when evidence cannot prove a condition. Stage transition only succeeds when `report.passed`; reopening records reason and evidence without deleting history. Maturity Markdown/JSON reports show gates, case coverage, independent validation, Unknown risk/owners, autonomy/readiness, review backlog, drift, and next actions.

- [ ] **Step 4: Verify GREEN and regression coverage**

Run:

```powershell
uv run pytest tests/unit/domain/test_stage_gates.py tests/unit/services/test_maturity_report.py -q
uv run pytest -q
```

Expected: all tests PASS and reports contain no unsupported “percent complete” claim.

- [ ] **Step 5: Commit**

```powershell
git add src/harness_foundry/domain src/harness_foundry/services/maturity.py schemas/v1 tests/unit
git commit -m "feat: enforce evidence-backed five-stage gates"
```

---

### Task 7: Version vectors and dependency-scoped re-certification

**Files:**
- Create: `src/harness_foundry/domain/recertification.py`
- Create: `tests/unit/domain/test_recertification.py`
- Create: `schemas/v1/version-vector.schema.json`
- Create: `schemas/v1/recertification-plan.schema.json`

**Interfaces:**
- Consumes: `ReferenceGraph` from Task 3
- Produces: `plan_recertification(change, graph, catalog) -> RecertificationPlan`

- [ ] **Step 1: Write failing impact-propagation tests**

```python
# tests/unit/domain/test_recertification.py
from harness_foundry.domain.recertification import ChangeKind, MaterialChange, plan_recertification


def test_skill_contract_change_selects_reverse_dependents(graph, catalog) -> None:
    plan = plan_recertification(
        MaterialChange(kind=ChangeKind.skill_contract, asset_id="skill.extract"),
        graph,
        catalog,
    )
    assert plan.asset_ids == ("skill.extract", "workflow.main", "readiness.main")


def test_core_harness_change_forces_stage4_e2e_and_readiness(graph, catalog) -> None:
    plan = plan_recertification(
        MaterialChange(kind=ChangeKind.harness_core, asset_id="workflow.main"),
        graph,
        catalog,
    )
    assert {"stage4_e2e", "stage5_readiness"} <= set(plan.required_evaluations)


def test_version_dimensions_are_independent(version_vector) -> None:
    changed = version_vector.model_copy(update={"model_assumptions": "2.0.0"})
    assert changed.schema == version_vector.schema
    assert changed.skill_catalog == version_vector.skill_catalog
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/domain/test_recertification.py -q`

Expected: FAIL because the re-certification domain is absent.

- [ ] **Step 3: Implement explicit version dimensions and change rules**

`VersionVector` stores CLI, Schema, templates, Skill catalog, Harness, tool contracts, model assumptions, and environment assumptions independently. `MaterialChange` must distinguish Skill contract, Harness core, tool side effect/permission, Schema major, golden case, and invalidated assumption. The planner traverses reverse dependencies, returns sorted impacted assets, required evaluations, reasons, and blocking status; core Harness changes always include stage 4 E2E and stage 5 Readiness.

- [ ] **Step 4: Generate Schemas and verify GREEN**

Run: `uv run pytest tests/unit/domain/test_recertification.py tests/schema -q && uv run pytest -q`

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/harness_foundry/domain/recertification.py schemas/v1 tests/unit/domain/test_recertification.py
git commit -m "feat: plan dependency-scoped recertification"
```

---

### Task 8: Canonical filesystem repository, artifact index, and validation pipeline

**Files:**
- Create: `src/harness_foundry/repositories/__init__.py`
- Create: `src/harness_foundry/repositories/canonical.py`
- Create: `src/harness_foundry/repositories/filesystem.py`
- Create: `src/harness_foundry/repositories/index.py`
- Create: `src/harness_foundry/validators/report.py`
- Create: `src/harness_foundry/validators/workspace.py`
- Create: `tests/unit/repositories/test_canonical.py`
- Create: `tests/integration/test_workspace_repository.py`
- Create: `tests/integration/test_validation_pipeline.py`

**Interfaces:**
- Produces: `canonical_bytes(value) -> bytes`, `canonical_text(text) -> bytes`
- Produces: `SourceRepository.snapshot(slug) -> SourceSnapshot`
- Produces: `tree_digest(snapshot) -> str`
- Produces: `validate_workspace(snapshot, schema_catalog) -> ValidationReport`

- [ ] **Step 1: Write failing canonicalization and source-boundary tests**

```python
# tests/unit/repositories/test_canonical.py
from harness_foundry.repositories.canonical import canonical_bytes, canonical_text


def test_mapping_digest_input_ignores_key_order() -> None:
    assert canonical_bytes({"b": 2, "a": 1}) == canonical_bytes({"a": 1, "b": 2})


def test_markdown_normalizes_crlf_and_terminal_newline() -> None:
    assert canonical_text("# A\r\n\r\nBody") == b"# A\n\nBody\n"
```

Integration tests must assert POSIX relative paths, exclusion of `dist/`, locks, transactions, and caches, detection of unrecorded source changes, stable artifact-index digests, and diagnostic categories for Schema, reference, evidence, gate, policy, version, and filesystem errors.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/repositories/test_canonical.py tests/integration/test_workspace_repository.py tests/integration/test_validation_pipeline.py -q`

Expected: FAIL because repository modules do not exist.

- [ ] **Step 3: Implement canonical reads without rewriting source files**

```python
def canonical_bytes(value: JsonValue) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def canonical_text(text: str) -> bytes:
    return (text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n").encode("utf-8")
```

`SourceRepository` accepts root paths in its constructor, resolves them before use, rejects traversal outside the workspace root, parses YAML with `yaml.safe_load`, validates Pydantic models, and never imports from `dist/`. `artifact-index.yaml` maps stable asset IDs to source paths, revision, Schema version, and canonical SHA-256. Validation composes diagnostics without discarding later errors.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
uv run pytest tests/unit/repositories tests/integration/test_workspace_repository.py tests/integration/test_validation_pipeline.py -q
uv run pytest -q
```

Expected: all tests PASS; source fixture bytes remain unchanged after validation.

- [ ] **Step 5: Commit**

```powershell
git add src/harness_foundry/repositories src/harness_foundry/validators tests/unit/repositories tests/integration
git commit -m "feat: add canonical source repository and validation"
```

---

### Task 9: Append-only event chains, file locks, write-ahead transactions, and recovery

**Files:**
- Create: `src/harness_foundry/domain/events.py`
- Create: `src/harness_foundry/repositories/events.py`
- Create: `src/harness_foundry/repositories/locks.py`
- Create: `src/harness_foundry/repositories/transactions.py`
- Create: `src/harness_foundry/services/recovery.py`
- Create: `tests/unit/repositories/test_events.py`
- Create: `tests/integration/test_transactions.py`
- Create: `tests/integration/test_recovery.py`

**Interfaces:**
- Produces: `EventStore.append(scope, draft) -> StoredEvent`
- Produces: `EventStore.verify(scope) -> EventVerification`
- Produces: `EventStore.replay(scope, checkpoint=None) -> ReplayResult`
- Produces: `TransactionManager.commit(plan, event) -> CommitResult`
- Produces: `RecoveryService.recover(transaction_id) -> RecoveryResult`
- Produces: `RecoveryService.recover_all() -> tuple[RecoveryResult, ...]`

- [ ] **Step 1: Write failing integrity, concurrency, and crash-point tests**

Tests must prove:

```text
event digest covers sequence, previous digest, scope, actor, command, asset refs, before/after digests, result
tamper, truncation, duplicate sequence, and gaps are detected
root and workspace chains share workspace ID but never duplicate events
second concurrent writer receives filesystem/lock error 8
crash after each WAL phase recovers to all-old or all-new
artifact index is replaced last
commit event is appended exactly once
```

Inject `Clock` and `IdFactory`; do not patch global time or randomness.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/unit/repositories/test_events.py tests/integration/test_transactions.py tests/integration/test_recovery.py -q`

Expected: FAIL because event and transaction infrastructure is absent.

- [ ] **Step 3: Implement the hash chain and WAL protocol**

Canonical event hashing excludes only the event's own `digest` and includes `prev_digest`. Each WAL stores transaction ID, event ID, event-log path, pre-append byte offset, previous event digest, expected event digest, per-file old/new digests, staged/backup paths, and current phase. Transaction phases are the exact ordered enum:

```python
class TransactionPhase(StrEnum):
    prepared = "prepared"
    staged = "staged"
    files_replaced = "files_replaced"
    index_replaced = "index_replaced"
    event_committed = "event_committed"
    cleaned = "cleaned"
```

Commit sequence: acquire per-workspace `filelock`; validate current tree and chain; calculate and validate prospective tree; write WAL and staged files; `fsync`; atomically replace source files; replace index last; append commit event; mark clean; remove transaction directory. Recovery reads the journal, byte offset, event ID, and digests to truncate an incomplete append or recognize an already committed event, then deterministically completes or restores the transaction without duplicate events. `recover_all()` processes journals in stable transaction-ID order. Partial terminal JSONL lines are integrity failures until recovery resolves them.

- [ ] **Step 4: Verify GREEN on Windows semantics**

Run:

```powershell
uv run pytest tests/unit/repositories/test_events.py tests/integration/test_transactions.py tests/integration/test_recovery.py -q
uv run pytest -q
```

Expected: all crash-point and concurrency tests PASS without sleeps longer than polling backoff.

- [ ] **Step 5: Commit**

```powershell
git add src/harness_foundry/domain/events.py src/harness_foundry/repositories src/harness_foundry/services/recovery.py tests/unit/repositories tests/integration
git commit -m "feat: add auditable events and recoverable transactions"
```

---

### Task 10: Application services and complete non-interactive CLI

**Files:**
- Modify: `src/harness_foundry/cli/app.py`
- Modify: `src/harness_foundry/cli/result.py`
- Create: `src/harness_foundry/cli/errors.py`
- Create: `src/harness_foundry/cli/output.py`
- Create: `src/harness_foundry/cli/commands/__init__.py`
- Create: `src/harness_foundry/cli/commands/init.py`
- Create: `src/harness_foundry/cli/commands/workspace.py`
- Create: `src/harness_foundry/cli/commands/capture.py`
- Create: `src/harness_foundry/cli/commands/unknown.py`
- Create: `src/harness_foundry/cli/commands/validate.py`
- Create: `src/harness_foundry/cli/commands/stage.py`
- Create: `src/harness_foundry/cli/commands/readiness.py`
- Create: `src/harness_foundry/cli/commands/change.py`
- Create: `src/harness_foundry/cli/commands/diff.py`
- Create: `src/harness_foundry/cli/commands/events.py`
- Create: `src/harness_foundry/cli/commands/migrate.py`
- Create: `src/harness_foundry/cli/commands/doctor.py`
- Create: `src/harness_foundry/services/workspaces.py`
- Create: `src/harness_foundry/services/capture.py`
- Create: `src/harness_foundry/services/unknowns.py`
- Create: `src/harness_foundry/services/stages.py`
- Create: `src/harness_foundry/services/readiness.py`
- Create: `src/harness_foundry/services/events.py`
- Create: `src/harness_foundry/services/diff.py`
- Create: `src/harness_foundry/services/actions.py`
- Create: `src/harness_foundry/services/changes.py`
- Create: `src/harness_foundry/services/migrations.py`
- Create: `src/harness_foundry/services/doctor.py`
- Modify: `tests/contract/test_cli_contract.py`
- Create: `tests/contract/test_cli_commands.py`
- Create: `tests/integration/test_migrations.py`
- Create: `tests/integration/test_human_gates.py`

**Interfaces:**
- Consumes: Tasks 2–9 domain/repository/services
- Produces: every CLI command from design §12 except `build`, which Task 11 registers
- Produces: stable JSON envelope and exit-code translation

- [ ] **Step 1: Write failing command-matrix and error-mapping tests**

```python
# tests/contract/test_cli_commands.py
import json

import pytest
from typer.testing import CliRunner

from harness_foundry.cli.app import app


runner = CliRunner()
COMMANDS = (
    ("init",),
    ("workspace", "new"), ("workspace", "list"), ("workspace", "status"),
    ("capture", "record"),
    ("unknown", "add"), ("unknown", "update"), ("unknown", "close"), ("unknown", "reopen"),
    ("validate",),
    ("stage", "assess"), ("stage", "advance"), ("stage", "reopen"),
    ("readiness", "assess"),
    ("diff",), ("record-change",),
    ("migrate",),
    ("events", "verify"), ("events", "replay"),
    ("doctor",),
)


@pytest.mark.parametrize("command", COMMANDS)
def test_every_command_is_registered_and_supports_json_help(command: tuple[str, ...]) -> None:
    result = runner.invoke(app, [*command, "--format", "json", "--help"])
    assert result.exit_code == 0


def test_schema_failure_maps_to_exit_3(tmp_path) -> None:
    result = runner.invoke(app, ["validate", "--root", str(tmp_path), "--format", "json"])
    payload = json.loads(result.stdout)
    assert result.exit_code == payload["exit_code"] == 3
    assert payload["diagnostics"][0]["category"] == "schema"
```

Add one fixture-driven test for every exit code 2–9 and one test proving each state-changing command accepts `--dry-run` and reports no changed files.

`tests/integration/test_migrations.py` must prove migrations are sequential and pure, `--dry-run` changes no bytes, failed candidate validation restores the original tree, and a successful migration records before/after Schema versions and an event exactly once.

`tests/integration/test_human_gates.py` must prove the first release only prepares action packages, approval never marks an external action executed, rejection is written to the Run and creates or links an Unknown, modifications require revalidation, forbidden actions have no executable mapping, and each decision exposes a recovery entry. Add secret-pattern fixtures proving `doctor` blocks credentials in normative sources without printing the secret value.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/contract/test_cli_contract.py tests/contract/test_cli_commands.py -q`

Expected: FAIL because command groups and error mapping are absent.

- [ ] **Step 3: Implement the stable service/error boundary**

Use one exception-to-exit mapping and forbid individual commands from choosing exit codes:

```python
EXIT_BY_CATEGORY = {
    "usage": 2,
    "config": 2,
    "schema": 3,
    "reference": 4,
    "evidence": 5,
    "gate": 5,
    "policy": 6,
    "human_gate": 6,
    "version": 7,
    "migration": 7,
    "adapter": 7,
    "filesystem": 8,
    "lock": 8,
    "transaction": 8,
    "event": 9,
    "replay": 9,
}
```

Each leaf command owns a reusable `--format text|json` option after the command name, constructs a service request, calls one service method, and renders `CommandResult`. Text and JSON renderers consume the same result. The service layer receives root paths, actor, clock, ID factory, and dry-run explicitly. Unknown creation accepts incomplete facts and creates a valid `new` Unknown rather than inventing values. `stage advance` and `record-change` commit through `TransactionManager` only after prospective validation. `workspace new` creates the canonical source layout directly from the versioned layout manifest; `diff` initially compares source against `artifact-index.yaml`; Task 11 extends it with generated-distribution comparison, and Task 12 extends `doctor` with adapter drift checks.

- [ ] **Step 4: Verify the whole CLI contract GREEN**

Run:

```powershell
uv run pytest tests/contract/test_cli_contract.py tests/contract/test_cli_commands.py -q
uv run hf --help
uv run hf doctor --format json
uv run pytest -q
```

Expected: command tests PASS; `doctor` returns a valid envelope even when it reports environment diagnostics.

- [ ] **Step 5: Commit**

```powershell
git add src/harness_foundry/cli src/harness_foundry/services tests/contract
git commit -m "feat: expose the complete deterministic hf command surface"
```

---

### Task 11: Complete child-workspace templates and deterministic draft/release builder

**Files:**
- Create: `templates/child-workspace/manifest.yaml`
- Create: `templates/child-workspace/workspace.yaml.j2`
- Create: `templates/child-workspace/README.md.j2`
- Create: `templates/child-workspace/TASK-CONTRACT/contract.yaml.j2`
- Create: `templates/child-workspace/TASK-CONTRACT/narrative.md.j2`
- Create: `templates/child-workspace/WORKFLOW/workflow.yaml.j2`
- Create: `templates/child-workspace/STATE/state-model.yaml.j2`
- Create: `templates/child-workspace/POLICIES/policies.yaml.j2`
- Create: `templates/child-workspace/HUMAN-GATES/human-gates.yaml.j2`
- Create: `templates/child-workspace/EXCEPTIONS/exceptions.yaml.j2`
- Create: `templates/child-workspace/LOOP-READINESS/assessment.yaml.j2`
- Create: `templates/child-workspace/CHANGELOG.md.j2`
- Create: `src/harness_foundry/domain/builds.py`
- Create: `src/harness_foundry/renderers/workspace.py`
- Create: `src/harness_foundry/renderers/manifest.py`
- Create: `src/harness_foundry/services/build.py`
- Create: `src/harness_foundry/services/distribution_verify.py`
- Create: `src/harness_foundry/cli/commands/build.py`
- Create: `tests/contract/test_child_template.py`
- Create: `tests/integration/test_build.py`
- Create: `tests/golden/minimal-draft/`
- Create: `tests/fixtures/workspaces/minimal-fixture/`

**Interfaces:**
- Produces: `Builder.plan(slug, mode, destination=None) -> BuildPlan`
- Produces: `Builder.build(plan) -> BuildResult`
- Produces: `verify_distribution(path) -> ValidationReport`
- Produces: `hf build --workspace <slug> --draft|--release [--output PATH] [--dry-run]`

- [ ] **Step 1: Write failing completeness and determinism tests**

```python
# tests/integration/test_build.py
from hashlib import sha256

import pytest

from harness_foundry.domain.builds import BuildMode


def digest_tree(path) -> str:
    digest = sha256()
    for file in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(file.relative_to(path).as_posix().encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()


def test_same_inputs_build_byte_identical_trees(builder, valid_workspace, tmp_path) -> None:
    first = builder.build(builder.plan(valid_workspace.slug, BuildMode.draft, tmp_path / "one"))
    second = builder.build(builder.plan(valid_workspace.slug, BuildMode.draft, tmp_path / "two"))
    assert digest_tree(first.path) == digest_tree(second.path)


def test_release_rejects_unrecorded_change_or_failed_gate(builder, incomplete_workspace) -> None:
    with pytest.raises(ValueError, match="release gate"):
        builder.plan(incomplete_workspace.slug, BuildMode.release)
```

Contract tests must assert the PR §14.10 directories plus `RUNS`, `EVIDENCE`, and `BUILD-MANIFEST.json`; `DRAFT` markers on draft outputs; no time/random fields in build manifests; no business-input reads under `dist/`; standalone distribution validation; `--dry-run` changes no bytes; and interruption at each staging/backup/target publication phase restores either the old or new complete non-empty directory on Windows semantics.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/contract/test_child_template.py tests/integration/test_build.py -q`

Expected: FAIL because templates and builder do not exist.

- [ ] **Step 3: Implement manifest-driven deterministic rendering**

`manifest.yaml` declares the canonical source scaffold, including every static template and dynamic directory (`SKILLS`, `CASES`, `EVALS`, `CONTEXT`, `UNKNOWNS`, `RUNS`, `EVIDENCE`, `.foundry/checkpoints`) plus `.foundry/artifact-index.yaml` and `.foundry/events.jsonl`. The release manifest declares exactly the design §14 public release set and excludes `.foundry` internals. Contract tests assert both exact sets and non-empty README, CHANGELOG, and CONTEXT semantics. Jinja uses `StrictUndefined`, stable sorted iteration, LF output, and no global clock/random functions. Draft builds contain a visible warning in README and manifest. Release builds require recorded source digests, passing complete-release gate, and at least conditional Readiness.

`BUILD-MANIFEST.json` contains only source tree digest, CLI version, Schema version, template version, adapter versions, mode, and per-file SHA-256; the per-file table explicitly excludes `BUILD-MANIFEST.json` itself. Builder writes to a temporary sibling directory and verifies it. Publication uses a WAL-recorded `target → backup`, `staging → target`, cleanup sequence that works when a non-empty target already exists on Windows and can restore the backup after interruption. `--dry-run` returns the planned file/digest diff without writing. The Builder never uses existing `dist/` as business input; the diff service may read it only as a comparison target and labels any divergence as generated-output drift.

- [ ] **Step 4: Verify RED-GREEN determinism and golden output**

Run:

```powershell
uv run pytest tests/contract/test_child_template.py tests/integration/test_build.py -q
uv run hf build --workspace minimal-fixture --draft
uv run pytest -q
```

Expected: all tests PASS and rebuilding produces no Git diff in golden files.

- [ ] **Step 5: Commit**

```powershell
git add templates src/harness_foundry/domain/builds.py src/harness_foundry/renderers src/harness_foundry/services src/harness_foundry/cli/commands/build.py tests/contract tests/integration tests/golden
git commit -m "feat: generate deterministic complete child workspaces"
```

---

### Task 12: Shared method Skills, separated Agents, and thin Codex/OpenCode adapters

**Files:**
- Create: `skills/catalog.yaml`
- Create: `skills/_shared/method-contract.md`
- Create: `skills/work-reproduction/SKILL.md`
- Create: `skills/task-contract/SKILL.md`
- Create: `skills/unknown-evidence/SKILL.md`
- Create: `skills/skill-candidates/SKILL.md`
- Create: `skills/case-evaluation/SKILL.md`
- Create: `skills/harness-composition/SKILL.md`
- Create: `skills/stage-review/SKILL.md`
- Create: `skills/loop-readiness/SKILL.md`
- Create: `skills/deviation-log/SKILL.md`
- Create: `skills/independent-reproduction/SKILL.md`
- Create: `skills/workspace-maintenance/SKILL.md`
- Create: `agents/catalog.yaml`
- Create: `agents/practitioner-guide.md`
- Create: `agents/asset-maintainer.md`
- Create: `agents/maturity-reviewer.md`
- Create: `agents/independent-verifier.md`
- Create: `.codex/config.toml`
- Create: `.codex/skills/*/SKILL.md`
- Create: `.codex/agents/*.toml`
- Create: `opencode.json`
- Create: `.opencode/skills/*/SKILL.md`
- Create: `.opencode/agents/*.md`
- Create: `.opencode/commands/hf-workspace.md`
- Create: `.opencode/commands/hf-review.md`
- Create: `.opencode/commands/hf-build.md`
- Create: `tests/contract/test_method_assets.py`
- Create: `tests/contract/test_tool_adapters.py`

**Interfaces:**
- Consumes: `hf` CLI and source asset contracts
- Produces: 11 shared Skills, four separated roles, and both tool-native discovery surfaces

- [ ] **Step 1: Write failing method/adapter contract tests**

Tests must enforce:

```text
all 11 required Skill source directories exist
every SKILL.md has lowercase hyphenated name matching its directory and a bounded description
every Skill states trigger, inputs, outputs, stop conditions, Human Gate behavior, source files, CLI verification, and evidence written
the Unknown Skill explicitly covers all 11 discovery/during/post method cards from design §10
the independent verifier is read-only and distinct from the maintainer
every source Skill and Agent has both adapters
adapter targets resolve to the source catalog
adapters contain only discovery, permission, source pointer, and hf invocation data
no Acme demonstration constant appears in source or adapter assets
```

Parse frontmatter as YAML; compare normalized semantics, not raw text duplication.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/contract/test_method_assets.py tests/contract/test_tool_adapters.py -q`

Expected: FAIL because method sources and adapters do not exist.

- [ ] **Step 3: Author the shared method contract and source assets**

Every Skill must follow this exact section contract:

```markdown
---
name: lowercase-hyphenated-name
description: Specific trigger and outcome
---

# Outcome
# Inputs
# Preconditions
# Applies when
# Does not apply when
# Dependencies
# Source-of-truth files
# Procedure
# Unknown handling
# Human gates and stop conditions
# Evaluator and acceptance
# Error semantics
# Evidence written
# Verification commands
```

The method contract requires case-first discovery; architecture-impacting questions one at a time; evidence basis and cheapest probe; no invented rules; deviation entries in plan/discovery/conservative-choice/revisit shape; independent evaluator; and `hf validate` before recording changes. The Unknown Skill must expose and test the four-quadrant inventory, blindspot pass, vocabulary teaching, contrasting design directions/mock, intervention brainstorming, blast-radius interview, reference semantics map, tweakable plan, implementation deviation log, buy-in artifact, and understanding quiz.

- [ ] **Step 4: Generate thin adapters and verify tool-specific rules**

Codex uses repo `AGENTS.md`, project `.codex/config.toml`, `.codex/skills/<name>/SKILL.md`, and `.codex/agents/<name>.toml`. OpenCode uses `opencode.json`, `.opencode/skills/<name>/SKILL.md`, `.opencode/agents/<name>.md`, and `.opencode/commands/*.md`. OpenCode permissions deny edits to normative sources and deny external/network access for maturity-reviewer and independent-verifier; the verifier may write only an isolated report under a command-provided temporary directory, which a separate maintainer transaction may record after review. Maintainer edits are `ask`; external actions remain denied. Do not pin provider/model IDs. Add discovery smoke fixtures for both layouts and an adapter-source digest test whose change triggers re-certification.

Run:

```powershell
uv run pytest tests/contract/test_method_assets.py tests/contract/test_tool_adapters.py -q
uv run pytest -q
```

Expected: all tests PASS and adapters contain no independent business instructions.

- [ ] **Step 5: Commit**

```powershell
git add skills agents .codex .opencode opencode.json tests/contract
git commit -m "feat: add portable method skills and agent adapters"
```

---

### Task 13: Real five-stage reference pilot and requirement traceability

**Files:**
- Create: `examples/harness-foundry-pilot/README.md`
- Create: `examples/harness-foundry-pilot/input-manifest.yaml`
- Create: `examples/harness-foundry-pilot/decision-log.md`
- Create: `workspaces/harness-foundry-pilot/` with the complete design §8 source structure
- Create: `workspaces/harness-foundry-pilot/SKILLS/source-to-requirement-mapping/SKILL.md`
- Create: `workspaces/harness-foundry-pilot/SKILLS/source-to-requirement-mapping/skill.yaml`
- Create: `workspaces/harness-foundry-pilot/CASES/pr-mainline/case.yaml`
- Create: `workspaces/harness-foundry-pilot/CASES/harness-semantics-conflict/case.yaml`
- Create: `workspaces/harness-foundry-pilot/CASES/acme-default-rejection/case.yaml`
- Create: `workspaces/harness-foundry-pilot/EVALS/source-mapping/eval.yaml`
- Create: `workspaces/harness-foundry-pilot/RUNS/pr-mainline/run.yaml`
- Create: `workspaces/harness-foundry-pilot/RUNS/harness-semantics-conflict/run.yaml`
- Create: `workspaces/harness-foundry-pilot/RUNS/acme-default-rejection/run.yaml`
- Create: `workspaces/harness-foundry-pilot/UNKNOWNS/`
- Create: `workspaces/harness-foundry-pilot/RUNS/independent-verification/run.yaml`
- Create: `docs/traceability/requirement-inventory.yaml`
- Create: `docs/traceability/pr-requirements.yaml`
- Create: `docs/traceability/pr-requirements.md`
- Create: `docs/traceability/completion-audit.md`
- Create: `tests/e2e/test_reference_pilot.py`
- Create: `tests/contract/test_traceability.py`
- Create: `tests/golden/harness-foundry-pilot/`

**Interfaces:**
- Consumes: supplied PR and all three supplements
- Produces: a real complete child workspace, release package, independent run, and direct requirement-to-evidence map

- [ ] **Step 1: Write failing pilot and traceability tests**

```python
# tests/e2e/test_reference_pilot.py
def test_pilot_has_normal_boundary_failure_cases(pilot) -> None:
    assert {case.kind.value for case in pilot.cases} >= {"normal", "boundary", "failure"}


def test_pilot_is_independently_reproduced(pilot) -> None:
    run = next(run for run in pilot.runs if run.actor_role == "independent_verifier")
    assert run.actor_id not in {pilot.creator_id, pilot.maintainer_id}
    assert run.input_tree_digest == pilot.recorded_source_digest
    assert run.reproduction_steps and run.signature_evidence_ref and run.passed


def test_pilot_is_conditionally_ready_or_better(pilot) -> None:
    assert pilot.readiness.result.rank >= pilot.readiness.result.conditional_ready.rank


def test_pilot_release_is_byte_stable(build_pilot_twice) -> None:
    assert build_pilot_twice.first_digest == build_pilot_twice.second_digest


def test_same_skill_passes_three_evaluated_cases(pilot) -> None:
    runs = [run for run in pilot.runs if run.skill_id == "skill.source-to-requirement-mapping"]
    assert {run.case_kind.value for run in runs} >= {"normal", "boundary", "failure"}
    assert all(run.evaluation_ref == "eval.source-mapping" and run.passed for run in runs)


def test_e2e_harness_run_is_traceable(pilot) -> None:
    run = pilot.end_to_end_run
    assert run.workflow_ref and run.step_events and run.final_evaluation_ref and run.passed


def test_unknowns_gates_and_exceptions_are_managed(pilot) -> None:
    assert pilot.unknowns and pilot.human_gates and pilot.exceptions
    assert all(item.owner_id and item.disposition for item in pilot.unknowns)
```

Add CLI-driven E2E tests named `test_init_capture_five_stage_advance_and_release`, `test_new_contradictory_case_reopens_prior_stage`, `test_harness_change_runs_stage4_and_readiness_recertification`, and `test_non_creator_can_run_validate_and_maintain_from_documented_entrypoint`. These tests invoke the installed Typer app with real temporary files and verify event chains, not in-memory shortcuts.

`requirement-inventory.yaml` is the independent, source-locator-keyed normative inventory derived directly from the four authoritative inputs. Traceability tests fail on duplicate locators, uncovered inventory IDs, orphan traceability rows, missing source sections, or mismatched status/evidence. Every traced requirement has ID, source locator, specification link, implementation link, direct evidence/test, status, owner, and explicit gap; achieved rows resolve to existing paths and named tests.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/e2e/test_reference_pilot.py tests/contract/test_traceability.py -q`

Expected: FAIL because pilot and traceability artifacts are absent.

- [ ] **Step 3: Build the pilot from the real project task**

Use this exact task contract goal: “Transform the supplied Harness Foundry product requirement and three theory supplements into an executable, verifiable, transferable mother workspace.” Inputs are the four existing files; outputs are the repository, specification, implementation plan, traceability matrix, test evidence, and release package.

The pilot's `source-to-requirement-mapping` Skill must separate normative requirements, inferred design implications, examples, conflicts, and non-goals. Cases are:

1. `pr-mainline` — extract and trace the PR's explicit five-stage and output requirements;
2. `harness-semantics-conflict` — preserve the product-wide definition while mapping external Harness meanings to `E,T,C,S,L,V`;
3. `acme-default-rejection` — fail if any example constant becomes a product default.

Record user approvals as Owner evidence, subagent reviews as independent evidence, and all unresolved limits as managed Unknowns. The workflow runs source inventory → requirement extraction → conflict/unknown analysis → specification → implementation → independent verification → release assessment.

- [ ] **Step 4: Generate traceability and golden release, then verify GREEN**

Run:

```powershell
uv run hf validate --workspace harness-foundry-pilot --format json
uv run hf readiness assess --workspace harness-foundry-pilot --format json
uv run hf build --workspace harness-foundry-pilot --release
uv run pytest tests/e2e/test_reference_pilot.py tests/contract/test_traceability.py -q
uv run pytest -q
```

Expected: validation and build exit 0; pilot has direct evidence for every complete claim; all tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add examples workspaces/harness-foundry-pilot docs/traceability tests/e2e tests/contract tests/golden/harness-foundry-pilot dist/harness-foundry-pilot
git commit -m "feat: prove Harness Foundry with a real five-stage pilot"
```

---

### Task 14: CI, operations documentation, and requirement-by-requirement completion audit

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `docs/architecture/overview.md`
- Create: `docs/methodology/five-stages.md`
- Create: `docs/operations/recovery.md`
- Create: `docs/operations/migration.md`
- Create: `docs/operations/recertification.md`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/traceability/completion-audit.md`
- Create: `tests/contract/test_documentation.py`
- Create: `tests/contract/test_completion_audit.py`
- Create: `scripts/verify_deterministic_build.py`
- Create: `scripts/verify_wheel_install.py`

**Interfaces:**
- Consumes: all previous tasks
- Produces: reproducible CI, operator handoff, and explicit final proof against the PR and design

- [ ] **Step 1: Write failing documentation and audit-integrity tests**

Tests must assert that README gives the exact bootstrap and five-stage happy path; AGENTS.md lists source boundaries and verification commands; recovery/migration/re-certification runbooks cover failure states; every completion-audit claim links to current evidence; and no requirement is marked achieved solely because a broad test suite passed.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/contract/test_documentation.py tests/contract/test_completion_audit.py -q`

Expected: FAIL until documentation, CI, and audit evidence are complete.

- [ ] **Step 3: Implement CI and operator documentation**

CI must run:

```yaml
strategy:
  matrix:
    os: [ubuntu-latest, windows-latest]
    python-version: ["3.11", "3.12"]
steps:
  - uses: actions/checkout@v4
  - uses: astral-sh/setup-uv@v6
    with:
      python-version: ${{ matrix.python-version }}
  - run: uv sync --frozen --all-groups
  - run: uv run ruff format --check .
  - run: uv run ruff check .
  - run: uv run mypy src tests
  - run: uv run python -m harness_foundry.services.schema_catalog --check schemas/v1
  - run: uv run pytest -q
  - run: uv run pytest tests/contract/test_traceability.py tests/contract/test_completion_audit.py -q
  - run: uv run hf doctor --format json
  - run: uv run hf validate --workspace harness-foundry-pilot --format json
  - run: uv run hf build --workspace harness-foundry-pilot --release
  - run: uv run python scripts/verify_deterministic_build.py harness-foundry-pilot
  - run: uv build --out-dir build/python-dist
  - run: uv run python scripts/verify_wheel_install.py build/python-dist
  - run: git diff --exit-code
```

Use the exact action major versions shown above. Documentation must explain draft versus complete release, all exit codes, source versus generated files, Human Gate boundaries, event verification, transaction recovery, version migration, and re-certification triggers.

- [ ] **Step 4: Run the full fresh verification suite**

Run each command separately and inspect the complete output:

```powershell
uv sync --frozen --all-groups
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest -q
uv run hf doctor --format json
uv run hf validate --workspace harness-foundry-pilot --format json
uv run hf readiness assess --workspace harness-foundry-pilot --format json
uv run hf build --workspace harness-foundry-pilot --release
uv build --out-dir build/python-dist
uv run python scripts/verify_wheel_install.py build/python-dist
```

Then create two clean temporary directories, build the pilot release into both, and compare recursive SHA-256 manifests. Expected: every command exits 0, all tests pass, both manifests match, and the only uncommitted paths are the intended Task 14 documentation, CI, and test files.

- [ ] **Step 5: Perform the completion audit against authoritative evidence**

For every PR feature, five-stage gate, final child-workspace requirement, method acceptance, pilot acceptance, core invariant, CLI command, Schema, and supplement-derived control, mark exactly one of: proved, contradicted, incomplete, indirect, or missing. Only `proved` items may become achieved. Fix every non-proved required item and rerun its direct evidence before continuing.

- [ ] **Step 6: Commit**

```powershell
git add .github README.md AGENTS.md docs tests/contract uv.lock
git commit -m "docs: complete operations and verified delivery audit"
```

- [ ] **Step 7: Verify the committed tree is reproducible and clean**

Run:

```powershell
uv run hf build --workspace harness-foundry-pilot --release
git diff --exit-code
git status --short --branch
```

Expected: build exits 0, `git diff` exits 0, and status shows only the branch header.

---

## Final Acceptance Commands

The implementation is not complete until all commands below have fresh successful output in the same verification turn:

```powershell
uv sync --frozen --all-groups
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest -q
uv run hf doctor --format json
uv run hf validate --workspace harness-foundry-pilot --format json
uv run hf readiness assess --workspace harness-foundry-pilot --format json
uv run hf build --workspace harness-foundry-pilot --release
uv build --out-dir build/python-dist
uv run python scripts/verify_wheel_install.py build/python-dist
git diff --exit-code
git status --short --branch
```

The final handoff reports exact test counts, pilot readiness, release manifest digest, remaining managed Unknowns, current autonomy approval, and any requirement whose evidence is not direct.
