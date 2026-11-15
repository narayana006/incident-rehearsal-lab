"""Deterministic simulation with decision-time evidence, not hindsight scoring."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from importlib.resources import files
import json
from typing import Any


class RehearsalError(ValueError):
    """A request violates the simulation's input or lifecycle rules."""


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise RehearsalError(f"{name} must be an integer from {minimum} to {maximum}")
    return value


def scenario_ids() -> list[str]:
    return sorted(p.name[:-5] for p in files(__package__).joinpath("scenarios").iterdir()
                  if p.name.endswith(".json"))


def load_scenario(scenario_id: str) -> dict:
    # Membership check before resource lookup prevents traversal and arbitrary reads.
    if scenario_id not in scenario_ids():
        raise RehearsalError("Unknown scenario")
    result = json.loads(files(__package__).joinpath("scenarios", scenario_id + ".json").read_text())
    validate_scenario(result)
    return result


def validate_scenario(scenario: dict) -> None:
    """Validate trusted, bundled author content before opening a session."""
    if not isinstance(scenario, dict):
        raise RehearsalError("Scenario must be an object")
    for key in ("id", "title", "briefing", "learning_objective"):
        if not isinstance(scenario.get(key), str) or not scenario[key]:
            raise RehearsalError(f"Scenario needs {key}")
    _integer(scenario.get("duration"), "duration", 1, 240)
    evidence = scenario.get("evidence")
    actions = scenario.get("actions")
    if not isinstance(evidence, list) or not evidence or not isinstance(actions, list) or not actions:
        raise RehearsalError("Scenario needs evidence and actions")
    ids: set[str] = set()
    def check_evidence(item: dict, timing_key: str) -> None:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            raise RehearsalError("Evidence needs an id")
        if item["id"] in ids:
            raise RehearsalError("Duplicate evidence id")
        ids.add(item["id"])
        _integer(item.get(timing_key), timing_key, 0, scenario["duration"])
        if not isinstance(item.get("text"), str) or not item["text"]:
            raise RehearsalError("Evidence needs text")
    for item in evidence:
        check_evidence(item, "at")
    action_ids: set[str] = set()
    for action in actions:
        if not isinstance(action, dict) or not isinstance(action.get("id"), str) or not action["id"]:
            raise RehearsalError("Action needs id")
        if action["id"] in action_ids:
            raise RehearsalError("Duplicate action id")
        action_ids.add(action["id"])
        if not all(isinstance(action.get(k), str) and action[k] for k in ("label", "outcome")):
            raise RehearsalError("Action needs label and outcome")
        if action.get("approval") not in (None, "incident_commander", "service_owner"):
            raise RehearsalError("Unknown approval role")
        effects = action.get("effects", [])
        if not isinstance(effects, list) or len(effects) > 8:
            raise RehearsalError("At most eight effects per action")
        for effect in effects:
            check_evidence(effect, "after")
    for action in actions:
        required = action.get("requires", [])
        if not isinstance(required, list) or any(type(item) is not str or item not in ids for item in required):
            raise RehearsalError("Action cites unknown required evidence")


@dataclass(frozen=True)
class Decision:
    number: int
    minute: int
    action_id: str
    rationale: str
    cited_evidence: tuple[tuple[str, int, str], ...]
    visible_ids: tuple[str, ...]
    approval: str | None
    supported: bool
    executed: bool
    reasons: tuple[str, ...]
    outcome: str


class Session:
    """One learner's deterministic session. Public accessors return copies.

    Frozen records and snapshots prevent accidental mutation through public APIs.
    This is not tamperproof against a host who can modify Python or process memory.
    """
    def __init__(self, scenario: dict):
        validate_scenario(scenario)
        self._scenario = deepcopy(scenario)
        self._minute = 0
        self._finished = False
        self._decisions: list[Decision] = []
        self._events = [deepcopy(item) for item in scenario["evidence"]]
        self._executed: set[str] = set()

    def _ensure_active(self) -> None:
        if self._finished:
            raise RehearsalError("Session is finished; its record is read-only")

    def _visible(self) -> list[dict]:
        return sorted((item for item in self._events if item["at"] <= self._minute),
                      key=lambda item: (item["at"], item["id"]))

    def state(self) -> dict:
        # Only released events are serialized. Future events and outcomes never go to the browser.
        return {"scenario": {key: self._scenario[key] for key in
                            ("id", "title", "briefing", "learning_objective", "duration")},
                "minute": self._minute, "finished": self._finished,
                "evidence": deepcopy(self._visible()),
                "actions": [{"id": a["id"], "label": a["label"], "approval": a.get("approval"),
                             "executed": a["id"] in self._executed}
                            for a in self._scenario["actions"]],
                "decisions": [asdict(d) for d in self._decisions]}

    def advance(self, minutes: int = 1) -> dict:
        self._ensure_active()
        _integer(minutes, "minutes", 1, 30)
        if self._minute + minutes > self._scenario["duration"]:
            raise RehearsalError("Cannot advance beyond the scenario duration; finish the session")
        self._minute += minutes
        return self.state()

    def decide(self, action_id: str, evidence_ids: list[str], rationale: str,
               approval: str | None = None) -> dict:
        self._ensure_active()
        actions = {item["id"]: item for item in self._scenario["actions"]}
        if type(action_id) is not str or action_id not in actions:
            raise RehearsalError("Unknown action")
        if action_id in self._executed:
            raise RehearsalError("This action already executed")
        if (not isinstance(evidence_ids, list) or len(evidence_ids) > 32
                or any(type(item) is not str for item in evidence_ids)
                or len(evidence_ids) != len(set(evidence_ids))):
            raise RehearsalError("Evidence citations must be a unique list of at most 32 IDs")
        if not isinstance(rationale, str) or not 8 <= len(rationale.strip()) <= 2000:
            raise RehearsalError("Rationale must contain 8–2000 characters")
        if approval not in (None, "incident_commander", "service_owner"):
            raise RehearsalError("Unknown simulated approval role")
        visible = {item["id"]: item for item in self._visible()}
        if any(item not in visible for item in evidence_ids):
            raise RehearsalError("Unknown or unreleased evidence citation")
        if len(self._decisions) >= 100:
            raise RehearsalError("Session decision limit reached")
        action = actions[action_id]
        missing = sorted(set(action.get("requires", [])) - set(evidence_ids))
        reasons = []
        # Do not reveal unreleased evidence IDs in a refusal.
        if missing:
            reasons.append("The cited evidence does not satisfy this action's evidence policy")
        if action.get("approval") and approval != action["approval"]:
            reasons.append(f"Needs simulated {action['approval']} approval")
        supported = not missing
        executed = not reasons
        outcome = action["outcome"] if executed else "Proposal held; no simulated action was executed."
        record = Decision(len(self._decisions) + 1, self._minute, action_id, rationale.strip(),
                          tuple((key, visible[key]["at"], visible[key]["text"]) for key in evidence_ids),
                          tuple(sorted(visible)), approval, supported, executed, tuple(reasons), outcome)
        self._decisions.append(record)
        if executed:
            self._executed.add(action_id)
            for effect in action.get("effects", []):
                self._events.append({"id": effect["id"], "at": min(self._scenario["duration"],
                                          self._minute + effect["after"]), "text": effect["text"]})
        return asdict(record)

    def finish(self) -> dict:
        self._ensure_active()
        self._finished = True
        return self.debrief()

    def debrief(self) -> dict:
        if not self._finished:
            raise RehearsalError("Finish before reading the debrief")
        decisions = [asdict(d) for d in self._decisions]
        return {"scenario_id": self._scenario["id"], "ended_at_minute": self._minute,
                "learning_objective": self._scenario["learning_objective"],
                "evaluation": "Support is evaluated only against evidence cited at decision time. "
                              "Rationale prose is recorded, not automatically judged. "
                              "Outcomes are authored simulation branches, not production predictions.",
                "summary": {"proposals": len(decisions),
                            "supported": sum(d.supported for d in self._decisions),
                            "executed": sum(d.executed for d in self._decisions)},
                "decisions": decisions, "observed_evidence": deepcopy(self._visible()),
                "pending_effects": sum(e["at"] > self._minute for e in self._events)}
