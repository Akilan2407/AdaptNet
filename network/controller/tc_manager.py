"""Linux tc subsystem wrapper and safe simulation fallback for other platforms."""

from dataclasses import dataclass
import platform
import subprocess
from typing import Optional, Tuple

from network.controller.control_config import (
    CEIL_HIGH,
    CEIL_LOW,
    CEIL_MEDIUM,
    CEIL_NORMAL,
    HTB_CLASS_HIGH,
    HTB_CLASS_LOW,
    HTB_CLASS_MEDIUM,
    HTB_CLASS_NORMAL,
    HTB_DEFAULT_CLASS_NUM,
    PriorityLevel,
    RATE_HIGH,
    RATE_LOW,
    RATE_MEDIUM,
    RATE_NORMAL,
    RATE_ROOT_TOTAL,
    TC_PRIO_HIGH,
    TC_PRIO_LOW,
    TC_PRIO_MEDIUM,
    TC_PRIO_NORMAL,
)
from network.controller.flow_mapper import (
    FlowTuple,
    is_allowlisted_interface,
    is_valid_ipv4,
    is_valid_port,
)


@dataclass
class TCOperationResult:
    """Outcome of a Linux Traffic Control command invocation."""
    rule_identifier: str = ""
    interface: str = "unknown"
    target_class: str = ""
    generated_command: str = ""
    status_code: int = 0
    error_message: str = ""
    executed: bool = False


def priority_to_tc_class(prio: PriorityLevel) -> str:
    """Map PriorityLevel to HTB leaf class ID."""
    if prio == PriorityLevel.PRIO_LEVEL_HIGH:
        return HTB_CLASS_HIGH
    elif prio == PriorityLevel.PRIO_LEVEL_MEDIUM:
        return HTB_CLASS_MEDIUM
    elif prio == PriorityLevel.PRIO_LEVEL_NORMAL:
        return HTB_CLASS_NORMAL
    elif prio == PriorityLevel.PRIO_LEVEL_LOW:
        return HTB_CLASS_LOW
    return HTB_CLASS_NORMAL


def parse_priority_string(s: Optional[str]) -> PriorityLevel:
    """Parse string representation of priority into PriorityLevel enum."""
    if not s:
        return PriorityLevel.PRIO_LEVEL_UNKNOWN
    val = s.strip().upper()
    if val == "HIGH":
        return PriorityLevel.PRIO_LEVEL_HIGH
    elif val == "MEDIUM":
        return PriorityLevel.PRIO_LEVEL_MEDIUM
    elif val == "NORMAL":
        return PriorityLevel.PRIO_LEVEL_NORMAL
    elif val == "LOW":
        return PriorityLevel.PRIO_LEVEL_LOW
    return PriorityLevel.PRIO_LEVEL_UNKNOWN


def _execute_or_simulate_cmd(cmd: str, dry_run: bool) -> Tuple[int, str]:
    """Execute tc on Linux or simulate it on platforms without Linux tc."""
    if dry_run:
        return 0, ""

    if platform.system() == "Linux":
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if res.returncode != 0:
                err = res.stderr.strip() or f"Command exited with status {res.returncode}"
                return res.returncode, err
            return 0, ""
        except Exception as exc:
            return -1, str(exc)
    else:
        return 0, f"tc is Linux-only on {platform.system()}; simulated execution"


def tc_init_interface(interface: str, dry_run: bool) -> Tuple[bool, TCOperationResult]:
    """Initialize root HTB qdisc and standard priority classes on interface."""
    res = TCOperationResult(interface=interface or "unknown")

    if not is_allowlisted_interface(interface):
        res.error_message = f"Interface '{interface}' not in allowlist"
        res.status_code = -1
        return False, res

    batch_cmd = (
        f"tc qdisc add dev {interface} root handle 1: htb default {HTB_DEFAULT_CLASS_NUM} && "
        f"tc class add dev {interface} parent 1: classid 1:1 htb rate {RATE_ROOT_TOTAL} ceil {RATE_ROOT_TOTAL} && "
        f"tc class add dev {interface} parent 1:1 classid 1:10 htb rate {RATE_HIGH} ceil {CEIL_HIGH} prio {TC_PRIO_HIGH} && "
        f"tc class add dev {interface} parent 1:1 classid 1:20 htb rate {RATE_MEDIUM} ceil {CEIL_MEDIUM} prio {TC_PRIO_MEDIUM} && "
        f"tc class add dev {interface} parent 1:1 classid 1:30 htb rate {RATE_NORMAL} ceil {CEIL_NORMAL} prio {TC_PRIO_NORMAL} && "
        f"tc class add dev {interface} parent 1:1 classid 1:40 htb rate {RATE_LOW} ceil {CEIL_LOW} prio {TC_PRIO_LOW}"
    )

    res.generated_command = batch_cmd
    res.rule_identifier = f"{interface}_htb_root"
    res.executed = not dry_run

    status, err = _execute_or_simulate_cmd(batch_cmd, dry_run)
    res.status_code = status
    res.error_message = err
    return status == 0, res


def tc_reset_interface(interface: str, dry_run: bool) -> Tuple[bool, TCOperationResult]:
    """Remove root qdisc from interface, returning it to default FIFO/pfifo_fast."""
    res = TCOperationResult(interface=interface or "unknown")

    if not is_allowlisted_interface(interface):
        res.error_message = f"Interface '{interface}' not in allowlist"
        res.status_code = -1
        return False, res

    cmd = f"tc qdisc del dev {interface} root handle 1:"
    res.generated_command = cmd
    res.rule_identifier = f"{interface}_reset"
    res.executed = not dry_run

    status, err = _execute_or_simulate_cmd(cmd, dry_run)
    res.status_code = status
    res.error_message = err
    return status == 0, res


def tc_apply_filter(
    interface: str,
    flow: Optional[FlowTuple],
    target_class: str,
    filter_handle: int,
    dry_run: bool,
) -> Tuple[bool, TCOperationResult]:
    """Attach u32 filter matching flow 5-tuple to specified HTB target class."""
    res = TCOperationResult(
        interface=interface or "unknown",
        target_class=target_class or HTB_CLASS_NORMAL,
    )

    if not is_allowlisted_interface(interface):
        res.error_message = f"Interface '{interface}' not allowlisted"
        res.status_code = -1
        return False, res

    if flow is None or not is_valid_ipv4(flow.src_ip) or not is_valid_port(flow.dst_port):
        res.error_message = "Invalid flow parameters"
        res.status_code = -1
        return False, res

    cmd = (
        f"tc filter add dev {interface} protocol ip parent 1:0 prio 1 handle 0x{filter_handle:x} "
        f"u32 match ip src {flow.src_ip}/32 match ip dport {flow.dst_port} 0xffff flowid {res.target_class}"
    )

    res.generated_command = cmd
    res.rule_identifier = f"{interface}_0x{filter_handle:x}_{res.target_class}"
    res.executed = not dry_run

    status, err = _execute_or_simulate_cmd(cmd, dry_run)
    res.status_code = status
    res.error_message = err
    return status == 0, res


def tc_update_filter(
    interface: str,
    flow: Optional[FlowTuple],
    new_target_class: str,
    filter_handle: int,
    dry_run: bool,
) -> Tuple[bool, TCOperationResult]:
    """Change destination HTB class of an existing u32 filter."""
    res = TCOperationResult(
        interface=interface or "unknown",
        target_class=new_target_class or HTB_CLASS_NORMAL,
    )

    if not is_allowlisted_interface(interface):
        res.error_message = f"Interface '{interface}' not allowlisted"
        res.status_code = -1
        return False, res

    if flow is None:
        res.error_message = "Invalid flow parameters"
        res.status_code = -1
        return False, res

    cmd = (
        f"tc filter change dev {interface} protocol ip parent 1:0 prio 1 handle 0x{filter_handle:x} "
        f"u32 match ip src {flow.src_ip}/32 match ip dport {flow.dst_port} 0xffff flowid {res.target_class}"
    )

    res.generated_command = cmd
    res.rule_identifier = f"{interface}_0x{filter_handle:x}_{res.target_class}"
    res.executed = not dry_run

    status, err = _execute_or_simulate_cmd(cmd, dry_run)
    res.status_code = status
    res.error_message = err
    return status == 0, res


def tc_remove_filter(
    interface: str,
    filter_handle: int,
    dry_run: bool,
) -> Tuple[bool, TCOperationResult]:
    """Delete u32 filter from interface."""
    res = TCOperationResult(interface=interface or "unknown")

    if not is_allowlisted_interface(interface):
        res.error_message = f"Interface '{interface}' not allowlisted"
        res.status_code = -1
        return False, res

    cmd = f"tc filter del dev {interface} protocol ip parent 1:0 prio 1 handle 0x{filter_handle:x} u32"
    res.generated_command = cmd
    res.rule_identifier = f"{interface}_0x{filter_handle:x}_del"
    res.executed = not dry_run

    status, err = _execute_or_simulate_cmd(cmd, dry_run)
    res.status_code = status
    res.error_message = err
    return status == 0, res
