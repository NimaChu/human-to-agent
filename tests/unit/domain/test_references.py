from human_to_agent.domain.references import ReferenceGraph, validate_references


def test_missing_reference_is_reported_with_source_and_field() -> None:
    graph = ReferenceGraph.from_edges({"skill.extract": {"cases": ("case.missing",)}})
    report = validate_references(graph, known_ids={"skill.extract"})
    assert report.errors[0].code == "reference.missing"
    assert report.errors[0].source_id == "skill.extract"
    assert report.errors[0].field == "cases"
    assert report.errors[0].target_id == "case.missing"


def test_reverse_dependents_are_transitive_sorted_and_cycle_safe() -> None:
    graph = ReferenceGraph.from_edges(
        {
            "skill.extract": {},
            "workflow.main": {"skills": ("skill.extract",)},
            "readiness.main": {"workflow": ("workflow.main",)},
            "cycle.one": {"next": ("cycle.two",)},
            "cycle.two": {"next": ("cycle.one",)},
        }
    )
    assert graph.reverse_dependents("skill.extract") == (
        "readiness.main",
        "workflow.main",
    )
    assert graph.reverse_dependents("cycle.one") == ("cycle.two",)


def test_valid_references_have_no_errors() -> None:
    graph = ReferenceGraph.from_edges(
        {"workflow.main": {"skills": ("skill.extract",)}, "skill.extract": {}}
    )
    report = validate_references(graph, known_ids={"workflow.main", "skill.extract"})
    assert report.errors == ()
