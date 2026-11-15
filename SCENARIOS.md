# Authoring a scenario

Bundled scenarios live in `src/incident_rehearsal/scenarios/`. Add a JSON file whose name matches its `id`, then add a reproducible demo path and regression tests. There is intentionally no HTTP upload or arbitrary file loader. Scenario content is trusted author material; runtime validation catches structural errors, not factual mistakes or good incident judgment.

Required top-level fields:

- `id`, `title`, `briefing`, `learning_objective`: nonempty strings.
- `duration`: integer simulation minutes, 1–240.
- `evidence`: nonempty list of `{ "id": "unique-id", "at": 2, "text": "Synthetic observation" }`.
- `actions`: nonempty list with unique action IDs, labels, an `outcome` describing the immediate simulated request, optional `requires` evidence ID list, optional `approval`, and optional `effects`.

An action example:

```json
{
  "id": "restore-route",
  "label": "Restore verified previous route",
  "requires": ["customer-probe", "config-diff"],
  "approval": "service_owner",
  "outcome": "Simulated restore requested; verify the resulting telemetry.",
  "effects": [
    {"id": "fresh-probe", "after": 3, "text": "Current synthetic checkout success: 99.9%."}
  ]
}
```

`approval` can be omitted, `incident_commander`, or `service_owner`. These are simulated roles, not identities. Evidence IDs are globally unique across initial evidence and all action effects. Each `requires` ID must exist; authors must also check that required observations are reachable. The validator does not solve dependency cycles.

Initial `at` and effect `after` are integers 0–duration. Effects appear at decision minute + delay, capped at the scenario duration. There are at most eight effects per action. Each action executes once, each session has at most 100 proposals, and manual clock advances are 1–30 minutes. Effects never call code or cloud APIs. A refusal must not expose IDs of future evidence.

The browser receives action labels and approval roles, but not `requires`, unobserved effects or authored outcomes for unselected actions. Never place an unreleased answer in a visible label, briefing, initial evidence or request outcome. A request outcome is not proof of eventual recovery: place recovery telemetry in delayed effects and require it for a separate declaration action.

For each exercise, test at least: a premature held proposal, the availability boundary of a decisive observation, an approved action and delayed effect, and a justified final declaration. Compare decision snapshots before and after new evidence. Preserve the distinction between policy compliance, quality of a human rationale, and eventual simulated outcomes.

Use invented metrics and identifiers. Cite authoritative documentation when presenting real service semantics in future scenarios; do not add credentials, personal data, live attacks or executable action hooks.
