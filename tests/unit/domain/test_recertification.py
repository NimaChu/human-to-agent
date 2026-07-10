from harness_foundry.domain.recertification import (
    ChangeKind,
    MaterialChange,
    VersionVector,
    default_recertification_catalog,
    plan_recertification,
)
from harness_foundry.domain.references import ReferenceGraph


def graph() -> ReferenceGraph:
    return ReferenceGraph.from_edges(
        {
            "skill.extract": {},
            "workflow.main": {"skills": ("skill.extract",)},
            "harness.main": {"workflow": ("workflow.main",)},
            "readiness.main": {"harness": ("harness.main",)},
        }
    )


def test_skill_contract_change_selects_reverse_dependents() -> None:
    plan = plan_recertification(
        MaterialChange(kind=ChangeKind.skill_contract, asset_id="skill.extract"),
        graph(),
        default_recertification_catalog(),
    )
    assert plan.asset_ids == (
        "harness.main",
        "readiness.main",
        "skill.extract",
        "workflow.main",
    )
    assert "skill_cases" in plan.required_evaluations


def test_core_harness_change_forces_stage4_e2e_and_readiness() -> None:
    plan = plan_recertification(
        MaterialChange(kind=ChangeKind.harness_core, asset_id="harness.main"),
        graph(),
        default_recertification_catalog(),
    )
    assert {"stage4_e2e", "stage5_readiness"} <= set(plan.required_evaluations)
    assert plan.blocking is True


def test_schema_major_or_invalidated_assumption_triggers_full_validation() -> None:
    for kind in (ChangeKind.schema_major, ChangeKind.invalidated_assumption):
        plan = plan_recertification(
            MaterialChange(kind=kind, asset_id="workspace.pilot"),
            graph(),
            default_recertification_catalog(),
        )
        assert "full_schema_validation" in plan.required_evaluations
        assert "stage5_readiness" in plan.required_evaluations
        assert plan.blocking is True


def test_tool_permission_change_forces_policy_and_human_gate_checks() -> None:
    plan = plan_recertification(
        MaterialChange(kind=ChangeKind.tool_permission, asset_id="tool.send"),
        graph(),
        default_recertification_catalog(),
    )
    assert {"policy_matrix", "human_gate_matrix"} <= set(plan.required_evaluations)


def test_version_dimensions_are_independent() -> None:
    original = VersionVector(
        cli="0.1.0",
        schema_version="1.0.0",
        templates="1.0.0",
        skill_catalog="1.0.0",
        harness="1.0.0",
        tool_contracts="1.0.0",
        model_assumptions="1.0.0",
        environment_assumptions="1.0.0",
    )
    changed = original.model_copy(update={"model_assumptions": "2.0.0"})
    assert changed.schema_version == original.schema_version
    assert changed.skill_catalog == original.skill_catalog
    assert changed.harness == original.harness
