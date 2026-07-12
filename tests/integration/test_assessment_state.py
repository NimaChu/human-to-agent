from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import yaml
from typer.testing import CliRunner

from human_to_agent.cli.app import app
from human_to_agent.domain.assessment import AssessmentFact
from human_to_agent.repositories.filesystem import SourceRepository
from human_to_agent.services.assessment_state import load_assessment_state

RUNNER = CliRunner()
NOW = datetime(2026, 7, 12, tzinfo=UTC).isoformat().replace("+00:00", "Z")
STAGE2_FACTS = (
    AssessmentFact.third_party_understands_goal_output,
    AssessmentFact.task_contract_exists,
    AssessmentFact.skill_prototype_exists,
    AssessmentFact.original_case_rerun,
    AssessmentFact.manual_modifications_linked,
    AssessmentFact.key_unknowns_classified,
    AssessmentFact.next_case_plan_exists,
)


def initialized(root: Path) -> Path:
    assert RUNNER.invoke(app, ["init", "--root", str(root)]).exit_code == 0
    assert RUNNER.invoke(app, ["workspace", "new", "pilot", "--root", str(root)]).exit_code == 0
    return root / "workspaces/pilot"


def capture(root: Path, text: str = "Owner-confirmed task evidence") -> str:
    result = RUNNER.invoke(
        app,
        ["capture", "record", "--root", str(root), "-w", "pilot", "--text", text],
    )
    assert result.exit_code == 0, result.stdout
    path = next((root / "workspaces/pilot/EVIDENCE").glob("capture-*.yaml"))
    return str(yaml.safe_load(path.read_text(encoding="utf-8"))["id"])


def write_assessment(
    workspace: Path,
    facts: tuple[AssessmentFact, ...],
    evidence_ref: str,
    *,
    current_stage: int = 1,
) -> None:
    content = {
        "workspace_id": "pilot",
        "current_stage": current_stage,
        "facts": [fact.value for fact in facts],
        "evidence": {fact.value: [evidence_ref] for fact in facts},
        "evaluated_case_kinds": [],
        "case_evaluation_refs": [],
        "skill_count": 0,
        "readiness_result": None,
        "readiness_evidence_refs": [],
    }
    (workspace / "ASSESSMENTS/stage-state.yaml").write_text(
        yaml.safe_dump(content, sort_keys=False), encoding="utf-8"
    )


def metadata(asset_id: str, *, status: str = "validated") -> dict[str, object]:
    return {
        "schema_version": "1",
        "id": asset_id,
        "workspace_id": "pilot",
        "revision": 1,
        "status": status,
        "owners": ["owner"],
        "created_at": NOW,
        "updated_at": NOW,
        "provenance": "integration test",
        "links": [],
        "evidence_refs": [],
    }


def install_stage2_structures(workspace: Path, evidence_id: str) -> None:
    contract_path = workspace / "TASK-CONTRACT/contract.yaml"
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    contract["status"] = "validated"
    contract["evidence_refs"] = [evidence_id]
    contract_path.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")

    evaluator = metadata("evaluator.pilot") | {
        "independent_inputs": ["captured task material"],
        "pass_signals": ["expected output is reproduced"],
        "fail_signals": ["output differs"],
        "indeterminate_signals": ["evidence is incomplete"],
        "acceptable_deviation": [],
        "evidence_output": evidence_id,
    }
    case = metadata("case.pilot") | {
        "kind": "normal",
        "skill_refs": ["skill.pilot"],
        "input_refs": [evidence_id],
        "expected_output": "Owner-confirmed result",
        "evaluator_refs": ["evaluator.pilot"],
    }
    evaluation = metadata("eval.pilot") | {
        "subject_ref": "skill.pilot",
        "case_ref": "case.pilot",
        "evaluator_id": "evaluator.pilot",
        "result": "passed",
        "actual_output_ref": evidence_id,
        "criteria_results": ["owner-confirmed output reproduced"],
    }
    skill = metadata("skill.pilot") | {
        "goal": "Reproduce the owner-confirmed task",
        "inputs": ["captured task material"],
        "outputs": ["owner-confirmed result"],
        "preconditions": ["capture exists"],
        "applies_when": ["the captured task is requested"],
        "does_not_apply_when": ["the task differs materially"],
        "dependencies": [],
        "evaluator_refs": ["evaluator.pilot"],
        "error_conditions": ["source evidence is missing"],
        "stop_conditions": ["the result is evaluated"],
        "case_refs": ["case.pilot"],
    }
    assets = {
        "EVALUATORS/pilot/evaluator.yaml": evaluator,
        "CASES/pilot/case.yaml": case,
        "EVALS/pilot/eval.yaml": evaluation,
        "SKILLS/pilot/skill.yaml": skill,
    }
    for relative, content in assets.items():
        path = workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")


def install_current_run(workspace: Path) -> None:
    digest = sha256()
    for source in SourceRepository(workspace.parents[1]).snapshot("pilot").files:
        if source.path.startswith("RUNS/"):
            continue
        digest.update(source.path.encode())
        digest.update(b"\0")
        digest.update(source.sha256.encode())
        digest.update(b"\n")
    run = metadata("run.pilot") | {
        "actor_id": "verifier",
        "actor_role": "independent_verifier",
        "input_tree_digest": digest.hexdigest(),
        "steps": ["load recorded inputs", "run Skill", "evaluate result"],
        "skill_ref": "skill.pilot",
        "case_ref": "case.pilot",
        "workflow_ref": None,
        "evaluation_refs": ["eval.pilot"],
        "passed": True,
    }
    path = workspace / "RUNS/pilot/run.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(run, sort_keys=False), encoding="utf-8")


def prepare_stage2(root: Path) -> tuple[Path, str]:
    workspace = initialized(root)
    evidence_id = capture(
        root,
        "Owner confirms the Stage 2 goal, rerun, linked modifications, Unknown classification, "
        "and next-case plan.",
    )
    added = RUNNER.invoke(
        app,
        ["unknown", "add", "--root", str(root), "-w", "pilot", "--title", "Release owner"],
    )
    assert added.exit_code == 0, added.stdout
    unknown_path = next((workspace / "UNKNOWNS").glob("*.yaml"))
    unknown_id = str(yaml.safe_load(unknown_path.read_text(encoding="utf-8"))["id"])
    closed = RUNNER.invoke(
        app,
        [
            "unknown",
            "close",
            "--root",
            str(root),
            "-w",
            "pilot",
            "--id",
            unknown_id,
            "--evidence",
            evidence_id,
            "--disposition",
            "resolved",
        ],
    )
    assert closed.exit_code == 0, closed.stdout
    install_stage2_structures(workspace, evidence_id)
    write_assessment(workspace, STAGE2_FACTS, evidence_id)
    install_current_run(workspace)
    recorded = RUNNER.invoke(app, ["record-change", "--root", str(root), "-w", "pilot"])
    assert recorded.exit_code == 0, recorded.stdout
    return workspace, evidence_id


def test_handwritten_foundry_gate_cannot_advance_empty_workspace(tmp_path: Path) -> None:
    workspace = initialized(tmp_path)
    (workspace / ".foundry/stage-2-gate.yaml").write_text(
        "passed: true\nevidence_refs: [evidence.fake]\n", encoding="utf-8"
    )

    result = RUNNER.invoke(app, ["stage", "advance", "--root", str(tmp_path), "-w", "pilot"])

    assert result.exit_code == 5, result.stdout
    assert yaml.safe_load((workspace / "workspace.yaml").read_text())["current_stage"] == 1
    status = RUNNER.invoke(
        app, ["workspace", "status", "--root", str(tmp_path), "-w", "pilot", "--format", "json"]
    )
    assert status.exit_code == 0, status.stdout
    assert "gate_target=stage2" in status.stdout
    assert "gate_gaps=7" in status.stdout


def test_assessment_rejects_missing_and_draft_evidence(tmp_path: Path) -> None:
    workspace = initialized(tmp_path)
    write_assessment(
        workspace,
        (AssessmentFact.third_party_understands_goal_output,),
        "evidence.missing",
    )
    missing = RUNNER.invoke(
        app, ["stage", "assess", "--root", str(tmp_path), "-w", "pilot", "--format", "json"]
    )
    assert missing.exit_code == 4, missing.stdout

    write_assessment(workspace, (), "unused")
    evidence_id = capture(tmp_path)
    evidence_path = next((workspace / "EVIDENCE").glob("capture-*.yaml"))
    evidence = yaml.safe_load(evidence_path.read_text(encoding="utf-8"))
    evidence["status"] = "draft"
    evidence_path.write_text(yaml.safe_dump(evidence, sort_keys=False), encoding="utf-8")
    write_assessment(workspace, (AssessmentFact.third_party_understands_goal_output,), evidence_id)
    draft = RUNNER.invoke(
        app, ["stage", "assess", "--root", str(tmp_path), "-w", "pilot", "--format", "json"]
    )
    assert draft.exit_code == 5, draft.stdout


def test_unmanaged_unknown_removes_claimed_managed_facts(tmp_path: Path) -> None:
    workspace = initialized(tmp_path)
    evidence_id = capture(tmp_path)
    added = RUNNER.invoke(
        app,
        ["unknown", "add", "--root", str(tmp_path), "-w", "pilot", "--title", "Owner"],
    )
    assert added.exit_code == 0, added.stdout
    write_assessment(
        workspace,
        (AssessmentFact.key_unknowns_managed, AssessmentFact.unknowns_managed),
        evidence_id,
    )

    computed = load_assessment_state(tmp_path, "pilot").assessment

    assert AssessmentFact.initial_unknowns_recorded in computed.facts
    assert AssessmentFact.key_unknowns_managed not in computed.facts
    assert AssessmentFact.unknowns_managed not in computed.facts


def test_missing_structural_assets_remove_claimed_structural_facts(tmp_path: Path) -> None:
    workspace = initialized(tmp_path)
    evidence_id = capture(tmp_path)
    structural = (
        AssessmentFact.task_contract_complete,
        AssessmentFact.end_to_end_harness_run,
        AssessmentFact.context_defined,
        AssessmentFact.result_evaluable,
    )
    write_assessment(workspace, structural, evidence_id)

    computed = load_assessment_state(tmp_path, "pilot").assessment

    assert not set(structural) & set(computed.facts)


def test_readiness_claim_cannot_exceed_dimension_evidence(tmp_path: Path) -> None:
    workspace = initialized(tmp_path)
    readiness = {
        "assessment_id": "readiness.pilot",
        "workspace_id": "pilot",
        "policy_version": "1",
        "result": "bounded_ready",
        "dimensions": {},
        "evidence_gaps": [],
        "risks": [],
        "next_actions": [],
        "recommended_ceiling": "h5",
        "approved_autonomy": None,
    }
    (workspace / "LOOP-READINESS/assessment.yaml").write_text(
        yaml.safe_dump(readiness, sort_keys=False), encoding="utf-8"
    )

    result = RUNNER.invoke(
        app, ["stage", "assess", "--root", str(tmp_path), "-w", "pilot", "--format", "json"]
    )

    assert result.exit_code == 5, result.stdout
    assert "readiness.overstated" in result.stdout


def test_valid_recorded_assessment_advances_both_stage_records(tmp_path: Path) -> None:
    workspace, _ = prepare_stage2(tmp_path)

    result = RUNNER.invoke(app, ["stage", "advance", "--root", str(tmp_path), "-w", "pilot"])

    assert result.exit_code == 0, result.stdout
    manifest = yaml.safe_load((workspace / "workspace.yaml").read_text(encoding="utf-8"))
    assessment = yaml.safe_load(
        (workspace / "ASSESSMENTS/stage-state.yaml").read_text(encoding="utf-8")
    )
    assert manifest["current_stage"] == assessment["current_stage"] == 2
    assert assessment["skill_count"] == 1


def test_unrecorded_change_blocks_advance(tmp_path: Path) -> None:
    workspace, _ = prepare_stage2(tmp_path)
    (workspace / "README.md").write_text("unrecorded mutation\n", encoding="utf-8")

    result = RUNNER.invoke(
        app,
        ["stage", "advance", "--root", str(tmp_path), "-w", "pilot", "--format", "json"],
    )

    assert result.exit_code == 8, result.stdout
    assert "source.unrecorded" in result.stdout


def test_reopen_requires_existing_evidence_and_updates_both_records(tmp_path: Path) -> None:
    workspace, evidence_id = prepare_stage2(tmp_path)
    assert (
        RUNNER.invoke(app, ["stage", "advance", "--root", str(tmp_path), "-w", "pilot"]).exit_code
        == 0
    )

    missing = RUNNER.invoke(
        app,
        [
            "stage",
            "reopen",
            "--root",
            str(tmp_path),
            "-w",
            "pilot",
            "--target",
            "1",
            "--evidence",
            "evidence.missing",
        ],
    )
    assert missing.exit_code == 4, missing.stdout

    reopened = RUNNER.invoke(
        app,
        [
            "stage",
            "reopen",
            "--root",
            str(tmp_path),
            "-w",
            "pilot",
            "--target",
            "1",
            "--evidence",
            evidence_id,
            "--reason",
            "Contradictory owner evidence",
        ],
    )
    assert reopened.exit_code == 0, reopened.stdout
    assert yaml.safe_load((workspace / "workspace.yaml").read_text())["current_stage"] == 1
    assert (
        yaml.safe_load((workspace / "ASSESSMENTS/stage-state.yaml").read_text())["current_stage"]
        == 1
    )
