from harness_foundry.domain.assets import CaseKind
from harness_foundry.domain.readiness import ReadinessResult
from harness_foundry.domain.stages import (
    AssessmentFact,
    AssessmentSnapshot,
    GateStatus,
    Stage,
    assess_stage,
)
from harness_foundry.services.maturity import render_maturity_json, render_maturity_markdown


def mixed_report():
    facts = frozenset({AssessmentFact.real_task, AssessmentFact.inputs_identified})
    snapshot = AssessmentSnapshot(
        workspace_id="ws-report",
        current_stage=Stage.stage1,
        facts=facts,
        evidence={AssessmentFact.real_task: ("ev-task",)},
        evaluated_case_kinds=frozenset({CaseKind.normal}),
        case_evaluation_refs=(),
        skill_count=0,
        readiness_result=ReadinessResult.not_ready,
        readiness_evidence_refs=(),
    )
    return assess_stage(Stage.stage1, snapshot)


def test_report_separates_satisfied_gap_and_indeterminate() -> None:
    report = mixed_report()
    payload = render_maturity_json(report)
    assert {item["status"] for item in payload["checks"]} == {
        GateStatus.satisfied.value,
        GateStatus.gap.value,
        GateStatus.indeterminate.value,
    }


def test_markdown_report_contains_next_actions_without_fake_percentage() -> None:
    markdown = render_maturity_markdown(mixed_report())
    assert "Next action" in markdown
    assert "% complete" not in markdown
    assert "indeterminate" in markdown
