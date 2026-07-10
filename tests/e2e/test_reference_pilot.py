import json
from hashlib import sha256
from pathlib import Path

import yaml
from typer.testing import CliRunner

from harness_foundry.cli.app import app
from harness_foundry.domain.assets import CaseRecord, RunRecord, TaskContract
from harness_foundry.domain.builds import BuildMode
from harness_foundry.domain.readiness import ReadinessAssessment, ReadinessResult
from harness_foundry.domain.recertification import (
    ChangeKind,
    MaterialChange,
    default_recertification_catalog,
    plan_recertification,
)
from harness_foundry.domain.references import ReferenceGraph
from harness_foundry.services.build import Builder
from harness_foundry.services.validation import validate_root

ROOT = Path(__file__).parents[2]
PILOT = ROOT / "workspaces/harness-foundry-pilot"
RUNNER = CliRunner()


def load(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def tree_digest(path: Path) -> str:
    digest = sha256()
    for item in sorted(file for file in path.rglob("*") if file.is_file()):
        digest.update(item.relative_to(path).as_posix().encode())
        digest.update(item.read_bytes())
    return digest.hexdigest()


def test_pilot_contract_uses_exact_goal() -> None:
    contract = TaskContract.model_validate(load(PILOT / "TASK-CONTRACT/contract.yaml"))
    assert contract.business_goal == (
        "Transform the supplied Harness Foundry product requirement and three theory supplements "
        "into an executable, verifiable, transferable mother workspace."
    )


def test_pilot_validates_from_normative_files() -> None:
    assert validate_root(ROOT, "harness-foundry-pilot").exit_code == 0


def test_pilot_has_normal_boundary_failure_cases() -> None:
    cases = [CaseRecord.model_validate(load(path)) for path in PILOT.glob("CASES/*/case.yaml")]
    assert {case.kind.value for case in cases} >= {"normal", "boundary", "failure"}


def test_pilot_is_independently_reproduced() -> None:
    run = RunRecord.model_validate(load(PILOT / "RUNS/independent-verification/run.yaml"))
    assert run.actor_role == "independent_verifier"
    assert run.actor_id not in {"creator", "maintainer"}
    assert run.input_tree_digest == "a" * 64
    assert run.steps and run.evaluation_refs and run.passed


def test_pilot_is_conditionally_ready_or_better() -> None:
    readiness = ReadinessAssessment.model_validate(load(PILOT / "LOOP-READINESS/assessment.yaml"))
    assert readiness.result.rank >= ReadinessResult.conditional_ready.rank


def test_pilot_release_is_byte_stable(tmp_path: Path) -> None:
    builder = Builder(ROOT)
    first = builder.build(
        builder.plan("harness-foundry-pilot", BuildMode.release, tmp_path / "one")
    )
    second = builder.build(
        builder.plan("harness-foundry-pilot", BuildMode.release, tmp_path / "two")
    )
    assert tree_digest(first.path) == tree_digest(second.path)


def test_same_skill_passes_three_evaluated_cases() -> None:
    runs = [RunRecord.model_validate(load(path)) for path in PILOT.glob("RUNS/*/run.yaml")]
    case_runs = [item for item in runs if item.id != "run.independent-verification"]
    assert {item.case_ref for item in case_runs} >= {
        "case.pr-mainline",
        "case.harness-semantics-conflict",
        "case.acme-default-rejection",
    }
    assert all(
        item.skill_ref == "skill.source-to-requirement-mapping" and item.passed
        for item in case_runs
    )


def test_e2e_harness_run_is_traceable() -> None:
    workflow = load(PILOT / "WORKFLOW/workflow.yaml")
    run = RunRecord.model_validate(load(PILOT / "RUNS/independent-verification/run.yaml"))
    assert run.workflow_ref == workflow["id"]
    assert len(workflow["steps"]) == 7 and run.evaluation_refs and run.passed


def test_unknowns_gates_and_exceptions_are_managed() -> None:
    unknown = load(PILOT / "UNKNOWNS/release-environment.yaml")
    gate = load(PILOT / "HUMAN-GATES/human-gates.yaml")
    exception = load(PILOT / "EXCEPTIONS/exceptions.yaml")
    assert unknown["owner_id"] and unknown["closure"]["disposition"] == "accepted_risk"
    assert gate["recovery_entry"] and exception["creates_unknown"] is True


def test_init_capture_five_stage_advance_and_release(tmp_path: Path) -> None:
    assert RUNNER.invoke(app, ["init", "--root", str(tmp_path)]).exit_code == 0
    assert RUNNER.invoke(app, ["workspace", "new", "pilot", "--root", str(tmp_path)]).exit_code == 0
    assert (
        RUNNER.invoke(app, ["capture", "record", "--root", str(tmp_path), "-w", "pilot"]).exit_code
        == 0
    )
    foundry = tmp_path / "workspaces/pilot/.foundry"
    for target in range(2, 6):
        (foundry / f"stage-{target}-gate.yaml").write_text(
            "passed: true\nevidence_refs: [evidence.owner]\n"
        )
        result = RUNNER.invoke(app, ["stage", "advance", "--root", str(tmp_path), "-w", "pilot"])
        assert result.exit_code == 0, result.stdout
    (foundry / "release-gate.yaml").write_text("passed: true\nreadiness: conditional_ready\n")
    release = RUNNER.invoke(
        app, ["build", "--root", str(tmp_path), "-w", "pilot", "--release", "--format", "json"]
    )
    assert release.exit_code == 0, release.stdout
    verify = RUNNER.invoke(
        app, ["events", "verify", "--root", str(tmp_path), "-w", "pilot", "--format", "json"]
    )
    assert json.loads(verify.stdout)["next_actions"] == ["events=4"]


def test_new_contradictory_case_reopens_prior_stage() -> None:
    plan = plan_recertification(
        MaterialChange(kind=ChangeKind.golden_case, asset_id="case.new-conflict"),
        ReferenceGraph.from_edges({}),
        default_recertification_catalog(),
    )
    assert {"skill_cases", "stage4_e2e"} <= set(plan.required_evaluations)


def test_harness_change_runs_stage4_and_readiness_recertification() -> None:
    plan = plan_recertification(
        MaterialChange(kind=ChangeKind.harness_core, asset_id="harness.pilot"),
        ReferenceGraph.from_edges({}),
        default_recertification_catalog(),
    )
    assert {"stage4_e2e", "stage5_readiness"} <= set(plan.required_evaluations)


def test_non_creator_can_run_validate_and_maintain_from_documented_entrypoint(
    tmp_path: Path,
) -> None:
    result = RUNNER.invoke(
        app, ["validate", "--root", str(ROOT), "-w", "harness-foundry-pilot", "--format", "json"]
    )
    assert result.exit_code == 0
    build = Builder(ROOT).build(
        Builder(ROOT).plan("harness-foundry-pilot", BuildMode.draft, tmp_path / "review")
    )
    assert (build.path / "README.md").is_file()
