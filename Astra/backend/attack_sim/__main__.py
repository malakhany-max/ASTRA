"""Attack evaluation CLI; supports ``python -m attack_sim run --attack all``."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

import astra_security as sec
from . import SCENARIOS, run_evaluation


def main() -> None:
    parser = argparse.ArgumentParser(description="Run offline ASTRA security attack scenarios")
    parser.add_argument("command", nargs="?", default="run", help="run, an attack name, or all")
    parser.add_argument("scenario", nargs="?", help="optional attack name when command is 'run'")
    parser.add_argument("--attack", choices=(*SCENARIOS, "all"), help="attack to execute")
    args = parser.parse_args()

    if args.command == "run":
        target = args.attack or args.scenario or "all"
    else:
        target = args.attack or args.command
    if target != "all" and target not in SCENARIOS:
        parser.error(f"unknown attack {target!r}; choose from: {', '.join(SCENARIOS)}, all")

    old_db = os.environ.get("ASTRA_DB")
    old_keys = os.environ.get("ASTRA_KEYS_DIR")
    with tempfile.TemporaryDirectory(prefix=".attack-sim-", dir=Path(__file__).resolve().parents[1]) as state_dir:
        os.environ["ASTRA_DB"] = str(Path(state_dir) / "security.db")
        os.environ["ASTRA_KEYS_DIR"] = str(Path(state_dir) / "keys")
        try:
            report = run_evaluation() if target == "all" else run_evaluation((target,))
        finally:
            sec.reset_store()
            if old_db is None:
                os.environ.pop("ASTRA_DB", None)
            else:
                os.environ["ASTRA_DB"] = old_db
            if old_keys is None:
                os.environ.pop("ASTRA_KEYS_DIR", None)
            else:
                os.environ["ASTRA_KEYS_DIR"] = old_keys

    print("ASTRA Attack Evaluation")
    print("-" * 105)
    print(f"{'ATTACK':31} {'DETECTED':9} {'CLASSIFICATION':17} {'LATENCY (MS)':13} {'EVENT':7} {'UPLINK':7}")
    for item in report["attacks"]:
        print(f"{item['scenario']:31} {str(item['detected']):9} {item['classification']:17} "
              f"{item['latency_ms']:13.3f} {str(item['security_event_created']):7} "
              f"{str(item['uplink_envelope_created']):7}")
    print("\nJSON report:")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
