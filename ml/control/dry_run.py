"""Dry-Run simulation engine for Phase 14 Adaptive Traffic Control.

Generates exact, safe Linux tc command representations and validates control logic
without executing mutating commands in the kernel.
"""

from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.control.config import (
    CLASS_RATES,
    PRIORITY_TO_CLASS,
)
from ml.control.control_validator import ControlValidator


class DryRunExecutor:
    """Simulates Linux tc traffic control operations and tracks synthetic state."""

    def __init__(self):
        self.active_rules: Dict[str, Dict[str, Any]] = {}
        self.initialized_interfaces: set[str] = set()
        self.next_handle = 0x100

    def generate_qdisc_init_cmd(self, interface: str) -> str:
        """Generate root qdisc and HTB class hierarchy command."""
        return (
            f"tc qdisc add dev {interface} root handle 1: htb default 30 && "
            f"tc class add dev {interface} parent 1: classid 1:1 htb rate 100mbit ceil 100mbit && "
            f"tc class add dev {interface} parent 1:1 classid 1:10 htb rate 100mbit ceil 100mbit prio 1 && "
            f"tc class add dev {interface} parent 1:1 classid 1:20 htb rate 60mbit ceil 80mbit prio 2 && "
            f"tc class add dev {interface} parent 1:1 classid 1:30 htb rate 30mbit ceil 50mbit prio 3 && "
            f"tc class add dev {interface} parent 1:1 classid 1:40 htb rate 10mbit ceil 20mbit prio 4"
        )

    def generate_filter_add_cmd(
        self, interface: str, handle: int, src_ip: str, dst_port: int, target_class: str
    ) -> str:
        """Generate tc u32 filter addition command."""
        return (
            f"tc filter add dev {interface} protocol ip parent 1:0 prio 1 handle 0x{handle:x} "
            f"u32 match ip src {src_ip}/32 match ip dport {dst_port} 0xffff flowid {target_class}"
        )

    def generate_filter_change_cmd(
        self, interface: str, handle: int, src_ip: str, dst_port: int, new_class: str
    ) -> str:
        """Generate tc u32 filter update command."""
        return (
            f"tc filter change dev {interface} protocol ip parent 1:0 prio 1 handle 0x{handle:x} "
            f"u32 match ip src {src_ip}/32 match ip dport {dst_port} 0xffff flowid {new_class}"
        )

    def generate_reset_cmd(self, interface: str) -> str:
        """Generate tc qdisc reset command."""
        return f"tc qdisc del dev {interface} root handle 1:"

    def process_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single control intent record in dry-run mode.

        Args:
            intent: Control intent dictionary.

        Returns:
            Structured execution result dictionary.
        """
        flow_id = intent.get("flow_id", "")
        iface = intent.get("interface", "s1-eth1")
        prio = intent.get("final_priority", "NORMAL")
        target_class = PRIORITY_TO_CLASS.get(prio, "1:30")

        # Fallback check (Section 19)
        if intent.get("is_fallback", False):
            return {
                "action": "APPLY",
                "status": "SKIPPED",
                "target_class": target_class,
                "interface": iface,
                "rule_identifier": f"{iface}_fallback_skip",
                "command": "",
                "error_message": "Input completeness PARTIAL; default handling retained",
            }

        # Input validation
        is_valid, err_msg = ControlValidator.validate_record(intent)
        if not is_valid:
            return {
                "action": "APPLY",
                "status": "FAILED",
                "target_class": target_class,
                "interface": iface,
                "rule_identifier": "",
                "command": "",
                "error_message": err_msg,
            }

        # Check existing rule
        if flow_id in self.active_rules:
            existing = self.active_rules[flow_id]
            if existing["priority"] == prio:
                # Duplicate rule with identical priority
                return {
                    "action": "APPLY",
                    "status": "SKIPPED",
                    "target_class": target_class,
                    "interface": iface,
                    "rule_identifier": existing["rule_identifier"],
                    "command": "",
                    "error_message": "Identical rule already active",
                }
            else:
                # Priority update (UPDATE)
                handle = existing["handle"]
                cmd = self.generate_filter_change_cmd(
                    iface, handle, intent["src_ip"], intent["dst_port"], target_class
                )
                rule_id = f"{iface}_0x{handle:x}_{target_class}"
                existing["priority"] = prio
                existing["target_class"] = target_class
                existing["rule_identifier"] = rule_id
                return {
                    "action": "UPDATE",
                    "status": "DRY_RUN",
                    "target_class": target_class,
                    "interface": iface,
                    "rule_identifier": rule_id,
                    "command": cmd,
                    "error_message": "",
                }

        # New Rule Application (APPLY)
        self.initialized_interfaces.add(iface)
        handle = self.next_handle
        self.next_handle += 1

        cmd = self.generate_filter_add_cmd(
            iface, handle, intent["src_ip"], intent["dst_port"], target_class
        )
        rule_id = f"{iface}_0x{handle:x}_{target_class}"

        self.active_rules[flow_id] = {
            "flow_id": flow_id,
            "interface": iface,
            "priority": prio,
            "target_class": target_class,
            "handle": handle,
            "rule_identifier": rule_id,
        }

        return {
            "action": "APPLY",
            "status": "DRY_RUN",
            "target_class": target_class,
            "interface": iface,
            "rule_identifier": rule_id,
            "command": cmd,
            "error_message": "",
        }

    def rollback(self) -> List[Dict[str, Any]]:
        """Simulate complete rollback across all initialized interfaces."""
        results = []
        for iface in list(self.initialized_interfaces):
            cmd = self.generate_reset_cmd(iface)
            results.append({
                "action": "RESET",
                "status": "DRY_RUN",
                "interface": iface,
                "rule_identifier": f"{iface}_reset",
                "command": cmd,
            })
        self.initialized_interfaces.clear()
        self.active_rules.clear()
        self.next_handle = 0x100
        return results
