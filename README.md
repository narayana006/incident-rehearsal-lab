# Incident Rehearsal Lab

An offline incident simulator for a single learner. Investigate synthetic evidence, cite observations, propose bounded actions, and review what your decisions were supported by **when you made them**.

Three complete exercises ship in v0.1:

| Exercise | Practice |
| --- | --- |
| `kafka-lag` | Separate downstream write latency from consumer capacity; verify rollback with customer signals. |
| `capacity-quota` | Distinguish account quota from regional capacity; consider replication lag before a bounded regional shift. |
| `stale-recovery` | Detect stale green dashboards and require independent, fresh recovery evidence. |

No accounts, keys, cloud API calls, external model, attack traffic or paid resources are required. The runtime uses only Python's standard library. This project is independently usable; it does not depend on GameDay Arena.

## Install the published release

Python 3.11 or newer:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install https://github.com/narayana006/incident-rehearsal-lab/releases/download/v0.1.0/incident_rehearsal_lab-0.1.0-py3-none-any.whl
incident-lab list
```

[Release downloads and checksums](https://github.com/narayana006/incident-rehearsal-lab/releases/tag/v0.1.0)
include the wheel and source archive.

The public container supports Linux amd64 and arm64 and can be pulled without a
GitHub login:

```sh
docker run --rm --read-only --network none --cap-drop ALL ghcr.io/narayana006/incident-rehearsal-lab:0.1.0 list
```

## Run locally

Python 3.11 or later:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
incident-lab list
incident-lab demo kafka-lag --output debrief.json
incident-lab serve --scenario kafka-lag --port 8765
```

Open **http://127.0.0.1:8765**. Select available evidence, describe your reasoning, choose an action and, where required, record a simulated approver role. Advance the deterministic clock to release evidence. Finish to review and download the debrief. Restart the command for a fresh session or a different scenario. `--port 0` selects an available local port and prints its URL.

The scripted `demo` command exercises held and accepted proposals and exports reproducible JSON. Output files use exclusive creation: an existing file is never overwritten. Omit `--output` to print the report.

## What the model does

- The simulation clock advances only on explicit requests; no real-time timing races or random outcomes.
- The browser receives only evidence released by the current minute. Unknown and future citations are rejected on the server.
- An action has an authored evidence policy and optional simulated approval role. A proposal missing either is recorded as held and produces no effects. The learner may retry after learning more.
- Executed actions produce a bounded list of authored follow-up observations after defined delays. Actions execute at most once. Failed strategies can still satisfy an evidence policy: the capacity exercise demonstrates that compliance and effectiveness are different.
- Each decision stores the clock, rationale, cited text and availability times, visible IDs, approval, policy result, and simulated action result. Later evidence cannot change that snapshot or retrospectively improve its result.
- Finishing locks all mutations. The debrief includes only observed evidence; it does not reveal unseen future observations. Pending observations are counted, not asserted as outcomes.

**Supported** means the proposal cited the IDs required by the authored policy. It does not mean the prose rationale is logically correct or that the action will succeed. The system records prose for a person to assess. “Approval” is a learner's self-attestation of an exercise role, not authentication or real operational authorization.

## Scope and limitations

This is a local teaching aid, not a production response agent, compliance product, tamperproof audit log, or predictor of cloud behavior. The host owner can inspect scenario files, edit code and process memory, or invent approvals. Frozen records and defensive copies prevent accidental edits through the application API, not host tampering.

Sessions are held in memory and lost when the server stops. Export before closing. There is one learner session per process, with no multi-user accounts, collaboration or persistent storage. The server deliberately supports only `127.0.0.1` and has no remote-hosting mode. Host/Origin/token checks, bounded JSON bodies, no-store responses and a restrictive content policy defend the local browser boundary; they are not a full security assessment.

Scenario errors, metrics and outcomes are synthetic. No real incident dataset or book mechanism is claimed to prove production safety. Related reading: [AI incident-management book](https://play.google.com/store/books/details?id=et4rEgAAQBAJ) and [companion materials](https://github.com/narayana006/ai-incident-management-companion).

## Develop and verify

```sh
python -m pip install -e '.[dev]'
python -m pytest -q
python -m build
```

Tests cover decision-time visibility, immutable snapshots, simulation branching, approvals, clock/lifecycle bounds, loader traversal rejection, HTTP origin/token checks, bounded bodies and installed CLI behavior. HTTP tests open ephemeral loopback ports. CI runs Python 3.11–3.14 plus a separate wheel-install smoke test outside the source checkout.

See [scenario authoring](SCENARIOS.md) for the schema and [contribution guidance](CONTRIBUTING.md) for changes.

## Container

```sh
docker build -t incident-rehearsal-lab:local .
docker run --rm incident-rehearsal-lab:local list
docker run --rm incident-rehearsal-lab:local demo stale-recovery > debrief.json
```

The non-root container defaults to a scripted demo. Use the host Python command for the browser UI: its loopback-only listener intentionally does not accept Docker port forwarding.

The **Container release** workflow tests both Linux amd64 and arm64 packages and images before publishing to `ghcr.io/narayana006/incident-rehearsal-lab`. Start it with `publish` disabled for a verification-only run. Published versions use `:0.1.0` and `:latest`; check the successful workflow run and the repository's Packages panel for availability.

## License and authorship

MIT. Maintained by Narayana Vemburaj. Initial implementation and tests were prepared with AI assistance and require human review before operational adaptation.
