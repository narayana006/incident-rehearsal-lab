from copy import deepcopy
import json

import pytest

from incident_rehearsal.cli import demo, main
from incident_rehearsal.engine import RehearsalError, Session, load_scenario, scenario_ids, validate_scenario


def test_all_scenarios_have_complete_deterministic_demo():
    assert len(scenario_ids()) == 3
    for sid in scenario_ids():
        assert demo(sid) == demo(sid)
        report = demo(sid)
        assert report["summary"]["executed"] >= 2
        assert report["decisions"][-1]["action_id"] == "declare-recovery"
        assert report["decisions"][-1]["executed"]


def test_future_evidence_is_withheld_and_cannot_be_cited():
    session = Session(load_scenario("kafka-lag"))
    assert [e["id"] for e in session.state()["evidence"]] == ["lag-alert"]
    assert "rollback-verified" not in json.dumps(session.state())
    for citation in ("db-latency", "made-up-id", "rollback-verified"):
        with pytest.raises(RehearsalError, match="unreleased"):
            session.decide("rollback-api", [citation], "This should not pass.", "service_owner")
    assert not session.state()["decisions"]


def test_decision_snapshot_is_not_rewritten_by_future_evidence():
    session = Session(load_scenario("kafka-lag"))
    held = session.decide("rollback-api", ["lag-alert"], "Premature rollback proposal.", "service_owner")
    assert not held["supported"] and not held["executed"]
    before = deepcopy(held)
    held["visible_ids"] = ["forged"]
    session.advance(5)
    accepted = session.decide("rollback-api", ["db-latency", "rollback-ready"],
                              "The rollback is now justified.", "service_owner")
    assert accepted["supported"] and accepted["executed"]
    assert session.state()["decisions"][0] == before
    session.advance(5)
    assert session.finish()["decisions"][0] == before


def test_approval_policy_does_not_execute_until_correct_simulated_role():
    session = Session(load_scenario("kafka-lag"))
    session.advance(5)
    for role in (None, "incident_commander"):
        decision = session.decide("rollback-api", ["db-latency", "rollback-ready"],
                                  "A compatible rollback is justified.", role)
        assert decision["supported"] and not decision["executed"]
    assert not any(e["id"].startswith("rollback-") for e in session.state()["evidence"] if e["id"] != "rollback-ready")
    assert session.decide("rollback-api", ["db-latency", "rollback-ready"],
                          "A compatible rollback is justified.", "service_owner")["executed"]


def test_branch_effect_released_at_scheduled_minute_and_only_once():
    session = Session(load_scenario("kafka-lag"))
    session.advance(5)
    session.decide("rollback-api", ["db-latency", "rollback-ready"], "Use the verified prior version.", "service_owner")
    session.advance(1)
    assert "rollback-metrics" not in {e["id"] for e in session.state()["evidence"]}
    session.advance(1)
    assert "rollback-metrics" in {e["id"] for e in session.state()["evidence"]}
    assert "rollback-verified" not in {e["id"] for e in session.state()["evidence"]}
    with pytest.raises(RehearsalError, match="already executed"):
        session.decide("rollback-api", ["db-latency", "rollback-ready"], "Try to repeat the rollback.", "service_owner")


def test_finished_session_rejects_all_mutations_and_export_does_not_reveal_future():
    session = Session(load_scenario("stale-recovery"))
    with pytest.raises(RehearsalError):
        session.debrief()
    report = session.finish()
    assert "config-diff" not in json.dumps(report)
    for operation in (lambda: session.advance(), lambda: session.finish(),
                      lambda: session.decide("declare-recovery", [], "Post-finish rewrite.")):
        with pytest.raises(RehearsalError, match="finished"):
            operation()
    report["observed_evidence"].clear()
    assert session.debrief()["observed_evidence"]


@pytest.mark.parametrize("minutes", [True, 0, -1, 31, 1.5, "1", None])
def test_clock_input_boundaries(minutes):
    with pytest.raises(RehearsalError):
        Session(load_scenario("kafka-lag")).advance(minutes)


def test_clock_cannot_pass_duration():
    session = Session(load_scenario("kafka-lag"))
    session.advance(20)
    with pytest.raises(RehearsalError):
        session.advance()
    assert session.finish()["ended_at_minute"] == 20


@pytest.mark.parametrize("change", [
    {"action_id": "unknown"}, {"evidence_ids": ["lag-alert", "lag-alert"]},
    {"evidence_ids": "lag-alert"}, {"evidence_ids": [{}]},
    {"rationale": "tiny"}, {"rationale": "a" * 2001}, {"approval": "administrator"},
])
def test_invalid_decision_inputs_do_not_create_records(change):
    session = Session(load_scenario("kafka-lag"))
    arguments = {"action_id": "declare-recovery", "evidence_ids": ["lag-alert"],
                 "rationale": "We need further verification."}
    arguments.update(change)
    with pytest.raises(RehearsalError):
        session.decide(**arguments)
    assert not session.state()["decisions"]


def test_defensive_copies_of_scenario_and_state():
    source = load_scenario("kafka-lag")
    session = Session(source)
    source["evidence"][0]["text"] = "forged"
    state = session.state()
    state["evidence"][0]["text"] = "forged again"
    assert "forged" not in json.dumps(session.state())


def test_author_schema_rejects_duplicate_and_unresolvable_evidence():
    scenario = load_scenario("kafka-lag")
    scenario["evidence"].append(deepcopy(scenario["evidence"][0]))
    with pytest.raises(RehearsalError, match="Duplicate"):
        validate_scenario(scenario)
    scenario = load_scenario("kafka-lag")
    scenario["actions"][0]["requires"].append("nonexistent")
    with pytest.raises(RehearsalError, match="unknown"):
        validate_scenario(scenario)


def test_loader_cannot_traverse():
    for sid in ("../engine", "/etc/passwd", "kafka-lag.json"):
        with pytest.raises(RehearsalError):
            load_scenario(sid)


def test_cli_exports_new_file_without_overwriting(tmp_path):
    target = tmp_path / "report.json"
    assert main(["demo", "--output", str(target)]) == 0
    assert json.loads(target.read_text())["scenario_id"] == "kafka-lag"
    with pytest.raises(SystemExit) as exc:
        main(["demo", "--output", str(target)])
    assert exc.value.code == 2


def test_policy_compliance_does_not_rewrite_ineffective_outcome_as_success():
    session = Session(load_scenario("capacity-quota"))
    session.advance(3)
    decision = session.decide("raise-quota", ["quota-headroom"],
                              "I will request more quota despite existing headroom.")
    assert decision["supported"] and decision["executed"]
    session.advance(3)
    observed = {e["id"]: e["text"] for e in session.state()["evidence"]}
    assert "still returns InsufficientInstanceCapacity" in observed["quota-result"]
    report = session.finish()
    assert report["summary"] == {"proposals": 1, "supported": 1, "executed": 1}
    assert "not production predictions" in report["evaluation"]
