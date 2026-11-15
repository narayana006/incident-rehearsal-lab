"""Command-line entrypoints; all exercise actions stay in process."""
import argparse
import json
from pathlib import Path

from .engine import RehearsalError, Session, load_scenario, scenario_ids
from .server import create_server


def demo(scenario_id: str) -> dict:
    session = Session(load_scenario(scenario_id))
    if scenario_id == "kafka-lag":
        # A premature proposal is held; the same action may be justified later.
        session.decide("declare-recovery", ["lag-alert"], "Lag exists, but I have not verified recovery.")
        session.advance(5)
        session.decide("rollback-api", ["db-latency", "rollback-ready"],
                       "Write latency followed the deployment; the prior version is schema-compatible.",
                       "service_owner")
        session.advance(5)
        session.decide("declare-recovery", ["rollback-verified"],
                       "Fresh customer checks and event age both match the baseline.")
    elif scenario_id == "capacity-quota":
        session.advance(5)
        session.decide("failover", ["provider-error", "quota-headroom", "secondary-readiness"],
                       "Capacity is constrained while quota has headroom; the approved region meets the RPO.",
                       "incident_commander")
        session.advance(3)
        session.decide("declare-recovery", ["failover-observed"],
                       "The bounded shift reduced queue age and errors with acceptable replication lag.")
    else:
        session.decide("declare-recovery", ["green-dashboard"],
                       "The green chart alone does not establish freshness; this should be held.")
        session.advance(5)
        session.decide("restore-route", ["customer-probe", "config-diff"],
                       "Current failures and the verified routing diff support a bounded restore.", "service_owner")
        session.decide("restore-telemetry", ["telemetry-gap"],
                       "The ingestion gap explains the stale dashboard, so restore fresh measurements.")
        session.advance(3)
        session.decide("declare-recovery", ["fresh-probe", "fresh-metrics"],
                       "Fresh independent probes and current metrics now support recovery.")
    return session.finish()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline incident rehearsal with synthetic evidence")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List bundled exercises")
    run = sub.add_parser("demo", help="Run a reproducible scripted exercise and export its debrief")
    run.add_argument("scenario", choices=scenario_ids(), nargs="?", default="kafka-lag")
    run.add_argument("--output", type=Path, help="Write JSON to this new file (never overwrite)")
    serve = sub.add_parser("serve", help="Open a single-session local browser API")
    serve.add_argument("--scenario", choices=scenario_ids(), default="kafka-lag")
    serve.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            for sid in scenario_ids():
                print(f"{sid}: {load_scenario(sid)['title']}")
        elif args.command == "demo":
            text = json.dumps(demo(args.scenario), indent=2) + "\n"
            if args.output:
                with args.output.open("x", encoding="utf-8") as handle:
                    handle.write(text)
                print(f"Saved {args.output}")
            else:
                print(text, end="")
        else:
            if not 0 <= args.port <= 65535:
                raise RehearsalError("Port must be between 0 and 65535")
            with create_server(args.scenario, port=args.port) as server:
                print(f"Incident Rehearsal Lab: http://127.0.0.1:{server.server_port}", flush=True)
                print("One local learner session. Ctrl-C to stop. Actions are simulated.", flush=True)
                try:
                    server.serve_forever()
                except KeyboardInterrupt:
                    pass
    except (RehearsalError, OSError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
