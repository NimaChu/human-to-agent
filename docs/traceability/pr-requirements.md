# PR requirement traceability

| ID | Source locator | Status | Evidence |
|---|---|---|---|
| H2A-001 | PR/Harness Foundry PR.md#搂1 Product goal | achieved | tests/e2e/test_reference_pilot.py::test_pilot_contract_uses_exact_goal |
| H2A-002 | PR/Harness Foundry PR.md#搂4 Principles | achieved | tests/e2e/test_reference_pilot.py::test_pilot_validates_from_normative_files |
| H2A-003 | PR/Harness Foundry PR.md#搂8 Stage 1 | achieved | tests/e2e/test_reference_pilot.py::test_init_capture_five_stage_advance_and_release |
| H2A-004 | PR/Harness Foundry PR.md#搂9 Stage 2 | achieved | tests/e2e/test_reference_pilot.py::test_same_skill_passes_three_evaluated_cases |
| H2A-005 | PR/Harness Foundry PR.md#搂10 Stage 3 | achieved | tests/e2e/test_reference_pilot.py::test_pilot_has_normal_boundary_failure_cases |
| H2A-006 | PR/Harness Foundry PR.md#搂11 Stage 4 | achieved | tests/e2e/test_reference_pilot.py::test_e2e_harness_run_is_traceable |
| H2A-007 | PR/Harness Foundry PR.md#搂12 Stage 5 | achieved | tests/e2e/test_reference_pilot.py::test_pilot_is_conditionally_ready_or_better |
| H2A-008 | PR/Harness Foundry PR.md#搂13 Consistency | achieved | tests/e2e/test_reference_pilot.py::test_init_capture_five_stage_advance_and_release |
| H2A-009 | PR/Harness Foundry PR.md#搂14 Build | achieved | tests/e2e/test_reference_pilot.py::test_pilot_release_is_byte_stable |
| H2A-010 | PR/Harness Foundry PR.md#搂15 Agents and Skills | achieved | tests/e2e/test_reference_pilot.py::test_all_method_skills_follow_contract |
| H2A-011 | PR/Harness Foundry PR.md#搂16 Permissions | achieved | tests/e2e/test_reference_pilot.py::test_release_prepares_package_but_never_executes_external_action |
| H2A-012 | PR/Harness Foundry PR.md#搂18 Verification | achieved | tests/e2e/test_reference_pilot.py::test_pilot_is_independently_reproduced |
| H2A-013 | PR/supplements/Agent-Harness.md#Harness semantic model | achieved | tests/e2e/test_reference_pilot.py::test_same_skill_passes_three_evaluated_cases |
| H2A-014 | PR/supplements/know-your-unknowns-method-cards.md#Discovery | achieved | tests/e2e/test_reference_pilot.py::test_unknown_skill_contains_all_discovery_cards |
| H2A-015 | PR/supplements/Loop Engineering.md#Loop readiness | achieved | tests/e2e/test_reference_pilot.py::test_pilot_is_conditionally_ready_or_better |
| H2A-016 | PR/Harness Foundry PR.md#搂12 CLI | achieved | tests/e2e/test_reference_pilot.py::test_every_command_is_registered_and_supports_json_help |
| H2A-017 | PR/Harness Foundry PR.md#搂17 Change impact | achieved | tests/e2e/test_reference_pilot.py::test_source_change_requires_adapter_recertification |
| H2A-018 | PR/Harness Foundry PR.md#搂20 First release | achieved | tests/e2e/test_reference_pilot.py::test_forbidden_actions_cannot_be_prepared |
| H2A-019 | PR/Harness Foundry PR.md#§8.5 stage-1 outputs | achieved | tests/unit/domain/test_stage_gates.py::test_stage1_requires_real_trace_baseline_unknown_and_owner |
| H2A-020 | PR/Harness Foundry PR.md#§8.6 stage-1 promotion | achieved | tests/unit/domain/test_stage_gates.py::test_stage1_requires_real_trace_baseline_unknown_and_owner |
| H2A-021 | PR/Harness Foundry PR.md#§9.2 task-contract fields | achieved | tests/e2e/test_reference_pilot.py::test_pilot_contract_uses_exact_goal |
| H2A-022 | PR/Harness Foundry PR.md#§9.4 Unknown handling | achieved | tests/integration/test_capture_unknown_commands.py::test_unknown_add_creates_valid_explicit_unknown |
| H2A-023 | PR/Harness Foundry PR.md#§9.6 stage-2 promotion | achieved | tests/unit/domain/test_stage_gates.py::test_stage2_requires_contract_skill_rerun_and_case_plan |
| H2A-024 | PR/Harness Foundry PR.md#§10.2 case expansion | achieved | tests/e2e/test_reference_pilot.py::test_pilot_has_normal_boundary_failure_cases |
| H2A-025 | PR/Harness Foundry PR.md#§10.3 validation questions | achieved | tests/e2e/test_reference_pilot.py::test_same_skill_passes_three_evaluated_cases |
| H2A-026 | PR/Harness Foundry PR.md#§10.4 Unknown closure | achieved | tests/unit/domain/test_unknowns.py::test_close_requires_allowed_evidence_owner_and_propagation |
| H2A-027 | PR/Harness Foundry PR.md#§10.5 Skill maturity | achieved | tests/unit/domain/test_assets.py::test_skill_requires_boundary_evaluation_and_stop_semantics |
| H2A-028 | PR/Harness Foundry PR.md#§10.7 stage-3 promotion | achieved | tests/unit/domain/test_stage_gates.py::test_stage3_requires_normal_boundary_failure_cases_and_independent_review |
| H2A-029 | PR/Harness Foundry PR.md#§11.3 Harness controls | achieved | tests/unit/domain/test_stage_gates.py::test_stage4_single_skill_still_requires_complete_harness_controls |
| H2A-030 | PR/Harness Foundry PR.md#§11.4 autonomy levels | achieved | tests/unit/domain/test_readiness.py::test_recommendation_never_auto_approves_autonomy |
| H2A-031 | PR/Harness Foundry PR.md#§11.5 stage-4 outputs | achieved | tests/e2e/test_reference_pilot.py::test_e2e_harness_run_is_traceable |
| H2A-032 | PR/Harness Foundry PR.md#§11.6 stage-4 promotion | achieved | tests/unit/domain/test_stage_gates.py::test_stage4_single_skill_still_requires_complete_harness_controls |
| H2A-033 | PR/Harness Foundry PR.md#§12.2.1 Goal | achieved | tests/unit/domain/test_readiness.py::test_all_ten_core_and_six_supplemental_dimensions_are_assessed |
| H2A-034 | PR/Harness Foundry PR.md#§12.2.2 State | achieved | tests/unit/domain/test_readiness.py::test_all_ten_core_and_six_supplemental_dimensions_are_assessed |
| H2A-035 | PR/Harness Foundry PR.md#§12.2.3 Action | achieved | tests/integration/test_human_gates.py::test_forbidden_actions_cannot_be_prepared |
| H2A-036 | PR/Harness Foundry PR.md#§12.2.4 Evaluator | achieved | tests/e2e/test_reference_pilot.py::test_e2e_harness_run_is_traceable |
| H2A-037 | PR/Harness Foundry PR.md#§12.2.5 Stop | achieved | tests/unit/domain/test_readiness.py::test_missing_dimension_is_indeterminate_and_blocks_conditional_ready |
| H2A-038 | PR/Harness Foundry PR.md#§12.2.6 Budget | achieved | tests/e2e/test_reference_pilot.py::test_pilot_is_conditionally_ready_or_better |
| H2A-039 | PR/Harness Foundry PR.md#§12.2.7 Retry | achieved | tests/e2e/test_reference_pilot.py::test_pilot_is_conditionally_ready_or_better |
| H2A-040 | PR/Harness Foundry PR.md#§12.2.8 Escalation | achieved | tests/e2e/test_reference_pilot.py::test_unknowns_gates_and_exceptions_are_managed |
| H2A-041 | PR/Harness Foundry PR.md#§12.2.9 Recovery | achieved | tests/integration/test_recovery.py::test_crash_each_phase_recovers_all_old_or_all_new |
| H2A-042 | PR/Harness Foundry PR.md#§12.2.10 Observability | achieved | tests/e2e/test_reference_pilot.py::test_e2e_harness_run_is_traceable |
| H2A-043 | PR/Harness Foundry PR.md#§12.3 readiness results | achieved | tests/unit/domain/test_readiness.py::test_readiness_rank_is_monotonic_but_not_a_score |
| H2A-044 | PR/Harness Foundry PR.md#§12.4 stage-5 outputs | achieved | tests/e2e/test_reference_pilot.py::test_pilot_is_conditionally_ready_or_better |
| H2A-045 | PR/Harness Foundry PR.md#§12.5 complete delivery | achieved | tests/unit/domain/test_stage_gates.py::test_release_requires_pr_12_5_18_3_and_conditional_ready |
| H2A-046 | PR/Harness Foundry PR.md#§13.1 Unknown lifecycle | achieved | tests/unit/domain/test_unknowns.py::test_reopen_preserves_closure_and_appends_history |
| H2A-047 | PR/Harness Foundry PR.md#§13.2 Unknown states | achieved | tests/integration/test_capture_unknown_commands.py::test_unknown_close_and_reopen_preserve_evidence_history |
| H2A-048 | PR/Harness Foundry PR.md#§13.3 Unknown priority | achieved | tests/unit/domain/test_unknowns.py::test_unknown_model_carries_discovery_and_automation_controls |
| H2A-049 | PR/Harness Foundry PR.md#§13.4 Unknown asset links | achieved | tests/unit/domain/test_unknowns.py::test_close_requires_allowed_evidence_owner_and_propagation |
| H2A-050 | PR/Harness Foundry PR.md#§13.5 managed Unknowns | achieved | tests/unit/domain/test_unknowns.py::test_accepted_risk_is_managed_not_known |
| H2A-051 | PR/Harness Foundry PR.md#§14.1 child workspace creation | achieved | tests/e2e/test_reference_pilot.py::test_init_capture_five_stage_advance_and_release |
| H2A-052 | PR/Harness Foundry PR.md#§14.2 stage navigation | achieved | tests/e2e/test_reference_pilot.py::test_init_capture_five_stage_advance_and_release |
| H2A-053 | PR/Harness Foundry PR.md#§14.3 work reproduction guidance | achieved | tests/integration/test_capture_unknown_commands.py::test_capture_records_hashed_evidence_and_event |
| H2A-054 | PR/Harness Foundry PR.md#§14.4 Task Contract generation | achieved | tests/contract/test_method_assets.py::test_all_method_skills_follow_contract |
| H2A-055 | PR/Harness Foundry PR.md#§14.5 Skill candidate identification | achieved | tests/contract/test_method_assets.py::test_all_method_skills_follow_contract |
| H2A-056 | PR/Harness Foundry PR.md#§14.6 case and evaluation management | achieved | tests/e2e/test_reference_pilot.py::test_same_skill_passes_three_evaluated_cases |
| H2A-057 | PR/Harness Foundry PR.md#§14.7 Unknown pool | achieved | tests/integration/test_capture_unknown_commands.py::test_unknown_close_and_reopen_preserve_evidence_history |
| H2A-058 | PR/Harness Foundry PR.md#§14.8 Harness composition guidance | achieved | tests/unit/domain/test_stage_gates.py::test_stage4_single_skill_still_requires_complete_harness_controls |
| H2A-059 | PR/Harness Foundry PR.md#§14.9 maturity dashboard | achieved | tests/contract/test_cli_commands.py::test_workspace_status_is_a_noninteractive_maturity_dashboard |
| H2A-060 | PR/Harness Foundry PR.md#§14.10 child workspace output | achieved | tests/contract/test_child_template.py::test_template_manifest_declares_complete_source_scaffold |
| H2A-061 | PR/Harness Foundry PR.md#§15.1 incomplete start | achieved | tests/integration/test_capture_unknown_commands.py::test_unknown_add_creates_valid_explicit_unknown |
| H2A-062 | PR/Harness Foundry PR.md#§15.2 case-first interaction | achieved | tests/contract/test_method_assets.py::test_all_method_skills_follow_contract |
| H2A-063 | PR/Harness Foundry PR.md#§15.3 progress visibility | achieved | tests/unit/services/test_maturity_report.py::test_report_separates_satisfied_gap_and_indeterminate |
| H2A-064 | PR/Harness Foundry PR.md#§15.4 no fake completeness | achieved | tests/unit/domain/test_stage_gates.py::test_indeterminate_gate_cannot_advance |
| H2A-065 | PR/Harness Foundry PR.md#§15.5 autonomy is not sole goal | achieved | tests/unit/domain/test_readiness.py::test_recommendation_never_auto_approves_autonomy |
| H2A-066 | PR/Harness Foundry PR.md#§16 roles and collaboration | achieved | tests/contract/test_method_assets.py::test_agents_are_separated_and_verifier_is_read_only |
| H2A-067 | PR/Harness Foundry PR.md#§17 user stories | achieved | tests/e2e/test_reference_pilot.py::test_non_creator_can_run_validate_and_maintain_from_documented_entrypoint |
| H2A-068 | PR/Harness Foundry PR.md#§18.1 mother-workspace acceptance | achieved | tests/contract/test_cli_commands.py::test_every_command_is_registered_and_supports_json_help |
| H2A-069 | PR/Harness Foundry PR.md#§18.2 methodology acceptance | achieved | tests/contract/test_method_assets.py::test_all_method_skills_follow_contract |
| H2A-070 | PR/Harness Foundry PR.md#§18.3 child-workspace acceptance | achieved | tests/e2e/test_reference_pilot.py::test_unknowns_gates_and_exceptions_are_managed |
| H2A-071 | PR/Harness Foundry PR.md#§20.1 false promotion risk | achieved | tests/unit/domain/test_stage_gates.py::test_indeterminate_gate_cannot_advance |
| H2A-072 | PR/Harness Foundry PR.md#§20.2 Skill sprawl risk | achieved | tests/contract/test_method_assets.py::test_all_method_skills_follow_contract |
| H2A-073 | PR/Harness Foundry PR.md#§20.3 early Harness risk | achieved | tests/unit/domain/test_stage_gates.py::test_stage4_single_skill_still_requires_complete_harness_controls |
| H2A-074 | PR/Harness Foundry PR.md#§20.4 early Loop risk | achieved | tests/unit/domain/test_readiness.py::test_missing_dimension_is_indeterminate_and_blocks_conditional_ready |
| H2A-075 | PR/Harness Foundry PR.md#§20.5 hidden Unknown risk | achieved | tests/unit/domain/test_unknowns.py::test_unknown_model_carries_discovery_and_automation_controls |
| H2A-076 | PR/Harness Foundry PR.md#§20.6 creator-dependency risk | achieved | tests/e2e/test_reference_pilot.py::test_pilot_is_independently_reproduced |
| H2A-077 | PR/Harness Foundry PR.md#§22 core principles | achieved | tests/contract/test_documentation.py::test_agent_guidance_has_boundaries_and_verification |
| H2A-078 | PR/Harness Foundry PR.md#§5 non-goals | achieved | tests/integration/test_human_gates.py::test_release_prepares_package_but_never_executes_external_action |
| H2A-079 | PR/supplements/Agent-Harness.md#Harness concept mapping | achieved | tests/e2e/test_reference_pilot.py::test_e2e_harness_run_is_traceable |
| H2A-080 | PR/supplements/know-your-unknowns-method-cards.md#Discovery | achieved | tests/contract/test_method_assets.py::test_unknown_skill_contains_all_discovery_cards |
| H2A-081 | PR/supplements/Loop Engineering.md#Extended loop controls | achieved | tests/unit/domain/test_readiness.py::test_all_ten_core_and_six_supplemental_dimensions_are_assessed |
| H2A-082 | PR/Harness Foundry PR.md#§5 first-release interface boundary | achieved | tests/contract/test_cli_contract.py::test_version_uses_stable_json_envelope |
| H2A-083 | PR/Harness Foundry PR.md#§14 command operations | achieved | tests/contract/test_cli_commands.py::test_every_command_is_registered_and_supports_json_help |
| H2A-084 | PR/Harness Foundry PR.md#§14 asset contracts | achieved | tests/schema/test_domain_schema_catalog.py::test_generated_schemas_equal_committed_v1 |
| H2A-085 | PR/Harness Foundry PR.md#§20 consistency and audit | achieved | tests/integration/test_recovery.py::test_crash_each_phase_recovers_all_old_or_all_new |
| H2A-086 | PR/Harness Foundry PR.md#§14 deterministic release | achieved | tests/e2e/test_reference_pilot.py::test_pilot_release_is_byte_stable |
| H2A-087 | PR/Harness Foundry PR.md#§16 tool portability | achieved | tests/contract/test_tool_adapters.py::test_each_source_skill_has_thin_codex_and_opencode_adapter |
| H2A-088 | PR/Harness Foundry PR.md#§19 pilot input provenance | achieved | tests/contract/test_traceability.py::test_all_authoritative_sources_have_inventory_rows |
| H2A-089 | PR/Harness Foundry PR.md#§18.3 independent input integrity | achieved | tests/e2e/test_reference_pilot.py::test_pilot_is_independently_reproduced |
| H2A-090 | PR/Harness Foundry PR.md#§18 evidence traceability | achieved | tests/contract/test_traceability.py::test_inventory_and_traceability_are_bijective_and_evidenced |
