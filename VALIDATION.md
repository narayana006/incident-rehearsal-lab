# Local validation: 2026-11-15

Prepared with AI assistance. These results describe local checks, not production incident-response validation.

- Python 3.11 isolated development environment: `python -m pytest -q` — **35 passed**, including HTTP tests on ephemeral loopback ports. No tests skipped.
- `python -m build` — source distribution and universal wheel built successfully. The wheel contains the HTML UI and all three scenario JSON files. The source manifest also includes contribution and authoring guidance.
- `docker build -t incident-rehearsal-lab:local .` — successful using `python:3.13-slim`.
- `docker run --rm incident-rehearsal-lab:local list` — lists all three scenarios.
- Container scripted demos for `kafka-lag`, `capacity-quota`, and `stale-recovery` — JSON parsed and final recovery action executed in each. The Kafka and stale-recovery demos also record an earlier held proposal. Container UID verified as **10001**.
- Independent review exercised decision snapshots, refusal privacy, HTTP boundaries and wheel resources; browser reviewer completed evidence selection, an approved rollback, time advance, finish and debrief from an installed wheel. Independent evidence is retained by the coordinating task outside this repository.

CI is configured for Python 3.11–3.14; remote CI has not run as part of these local results. No cloud accounts, actual attacks or production workloads were used. The authored evidence policy checks IDs and simulated roles; free-text reasoning still requires a human reviewer. Sessions are local, in memory, and not host-tamperproof.
