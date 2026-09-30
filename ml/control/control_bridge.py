"""Control Bridge connecting Python ML/Policy pipeline to Network Controller."""

import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.control.config import (
    C_CONTROLLER_BIN,
    DEFAULT_ACTIONS_PATH,
    DEFAULT_DECISIONS_PATH,
    DEFAULT_DRY_RUN,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_STATE_PATH,
    DEFAULT_SUMMARY_PATH,
)
from ml.control.decision_loader import DecisionLoader
from ml.control.dry_run import DryRunExecutor


class ControlBridge:
    """Coordinates execution of network control intents across Python and C controller layers."""

    def __init__(
        self,
        decisions_path: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        dry_run: bool = DEFAULT_DRY_RUN,
        use_c_controller: bool = True,
    ):
        self.decisions_path = decisions_path or DEFAULT_DECISIONS_PATH
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self.dry_run = dry_run
        self.use_c_controller = use_c_controller and C_CONTROLLER_BIN.exists()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def execute_c_controller(self) -> Tuple[int, str]:
        """Invoke the C adaptive controller binary with appropriate flags."""
        cmd = [str(C_CONTROLLER_BIN), "--apply-csv", str(self.decisions_path)]
        if self.dry_run:
            cmd.append("--dry-run")
        else:
            cmd.append("--enforce")

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return res.returncode, res.stdout + res.stderr
        except Exception as exc:
            return -1, f"Failed to execute C controller: {exc}"

    def run_bridge(self) -> Dict[str, Any]:
        """Execute end-to-end control processing, generate logs and summary JSON.

        Returns:
            Control summary statistics dictionary.
        """
        # If C controller is available, run it to ensure C network architecture compatibility
        if self.use_c_controller:
            ret_code, c_output = self.execute_c_controller()
            if ret_code != 0 and not self.dry_run:
                print(f"[!] Warning: C controller exited with code {ret_code}:\n{c_output}")

        # In parallel, evaluate using Python dry-run engine to verify state and create summary
        loader = DecisionLoader(self.decisions_path)
        intents = loader.load_decisions()
        executor = DryRunExecutor()

        actions_list: List[Dict[str, Any]] = []
        state_list: List[Dict[str, Any]] = []

        total_decisions = len(intents)
        total_applied = 0
        total_updated = 0
        total_skipped = 0
        total_failed = 0
        dry_run_ops = 0

        priority_dist = {"HIGH": 0, "MEDIUM": 0, "NORMAL": 0, "LOW": 0}

        for intent in intents:
            prio = intent["final_priority"]
            if prio in priority_dist:
                priority_dist[prio] += 1

            result = executor.process_intent(intent)
            status = result["status"]
            action = result["action"]

            if status == "DRY_RUN":
                dry_run_ops += 1
                if action == "APPLY":
                    total_applied += 1
                elif action == "UPDATE":
                    total_updated += 1
            elif status == "SUCCESS":
                if action == "APPLY":
                    total_applied += 1
                elif action == "UPDATE":
                    total_updated += 1
            elif status == "SKIPPED":
                total_skipped += 1
            else:
                total_failed += 1

            action_row = {
                "timestamp": intent["timestamp"],
                "device_id": intent["device_id"],
                "flow_id": intent["flow_id"],
                "src_ip": intent["src_ip"],
                "dst_ip": intent["dst_ip"],
                "src_port": intent["src_port"],
                "dst_port": intent["dst_port"],
                "protocol": intent["protocol"],
                "traffic_class": intent["traffic_class"],
                "predicted_congestion_class": intent["predicted_congestion_class"],
                "final_priority": intent["final_priority"],
                "action": action,
                "target_class": result["target_class"],
                "interface": result["interface"],
                "dry_run": self.dry_run,
                "status": status,
                "rule_identifier": result["rule_identifier"],
                "error_message": result["error_message"],
            }
            actions_list.append(action_row)

            if status in ("SUCCESS", "DRY_RUN") and action in ("APPLY", "UPDATE"):
                state_row = {
                    "timestamp": intent["timestamp"],
                    "device_id": intent["device_id"],
                    "flow_id": intent["flow_id"],
                    "interface": result["interface"],
                    "priority": intent["final_priority"],
                    "traffic_class": intent["traffic_class"],
                    "control_class": result["target_class"],
                    "action": action,
                    "status": status,
                    "rule_identifier": result["rule_identifier"],
                    "dry_run": self.dry_run,
                    "error_message": result["error_message"],
                }
                state_list.append(state_row)

        # Export CSVs (overwriting or creating fresh authoritative dataset for this batch)
        pd.DataFrame(actions_list).to_csv(DEFAULT_ACTIONS_PATH, index=False)
        pd.DataFrame(state_list).to_csv(DEFAULT_STATE_PATH, index=False)

        # Calculate success rate
        evaluated_valid = total_applied + total_updated + total_failed
        success_rate = (
            round((total_applied + total_updated) / evaluated_valid * 100.0, 2)
            if evaluated_valid > 0
            else 100.0
        )

        summary = {
            "total_decisions": total_decisions,
            "total_applied": total_applied,
            "total_updated": total_updated,
            "total_removed": 0,
            "total_skipped": total_skipped,
            "total_failed": total_failed,
            "dry_run_operations": dry_run_ops,
            "priority_distribution": priority_dist,
            "control_success_rate": success_rate,
        }

        with open(DEFAULT_SUMMARY_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return summary


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Phase 14 Control Bridge")
    parser.add_argument("--decisions", type=str, default=str(DEFAULT_DECISIONS_PATH), help="Decisions CSV path")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Run in dry-run mode (default: True)")
    parser.add_argument("--enforce", action="store_true", help="Execute actual kernel commands on Linux")

    args = parser.parse_args()
    dry_run = not args.enforce

    print("========================================")
    print("PHASE 14 — CONTROL BRIDGE")
    print("========================================")
    bridge = ControlBridge(decisions_path=Path(args.decisions), dry_run=dry_run)
    summary = bridge.run_bridge()

    print(f"Decisions Loaded       : {summary['total_decisions']}")
    print(f"Rules Applied          : {summary['total_applied']}")
    print(f"Rules Updated          : {summary['total_updated']}")
    print(f"Rules Skipped          : {summary['total_skipped']}")
    print(f"Operations Failed      : {summary['total_failed']}")
    print(f"Dry-Run Operations     : {summary['dry_run_operations']}")
    print(f"Control Success Rate   : {summary['control_success_rate']}%")
    print(f"Actions CSV            : {DEFAULT_ACTIONS_PATH}")
    print(f"Summary JSON           : {DEFAULT_SUMMARY_PATH}")
    print("========================================")


if __name__ == "__main__":
    main()
