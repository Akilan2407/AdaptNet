"""Rollback and teardown mechanism for traffic control rules (converted from rollback.h/.c)."""

import threading
from typing import List, Tuple

from network.controller.control_logger import (
    ControlLogEntry,
    get_current_iso_timestamp,
    log_control_action,
)
from network.controller.tc_manager import tc_reset_interface


_rollback_lock = threading.Lock()
_managed_interfaces: List[str] = []


def register_managed_interface(interface: str) -> bool:
    """Register interface as having active project QoS rules."""
    if not interface:
        return False
    with _rollback_lock:
        if interface not in _managed_interfaces:
            _managed_interfaces.append(interface)
        return True


def unregister_managed_interface(interface: str) -> bool:
    """Remove interface from managed list after teardown."""
    if not interface:
        return False
    with _rollback_lock:
        if interface in _managed_interfaces:
            _managed_interfaces.remove(interface)
            return True
        return False


def get_managed_interfaces() -> List[str]:
    """Retrieve list of all interfaces currently marked as managed."""
    with _rollback_lock:
        return list(_managed_interfaces)


def rollback_interface(interface: str, dry_run: bool) -> Tuple[bool, str]:
    """Execute reset on a specific network interface and log action."""
    if not interface:
        return False, "Null interface"

    ok, tc_res = tc_reset_interface(interface, dry_run)

    log_entry = ControlLogEntry(
        timestamp=get_current_iso_timestamp(),
        action="RESET",
        interface=interface,
        dry_run=dry_run,
        status="DRY_RUN" if dry_run else ("SUCCESS" if ok else "FAILED"),
        rule_identifier=tc_res.rule_identifier,
        error_message=tc_res.error_message,
    )
    log_control_action(log_entry)

    if ok:
        unregister_managed_interface(interface)

    return ok, tc_res.error_message


def rollback_all(dry_run: bool) -> Tuple[int, str]:
    """Reset all managed interfaces."""
    ifaces = get_managed_interfaces()
    rolled_back = 0
    last_err = ""

    for iface in ifaces:
        ok, err = rollback_interface(iface, dry_run)
        if ok:
            rolled_back += 1
        elif err:
            last_err = err

    return rolled_back, last_err
