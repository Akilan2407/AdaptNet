"""Core dispatcher and interface for network control intents (converted from control_interface.h/.c)."""

from dataclasses import dataclass
from enum import IntEnum
import threading
from typing import Dict, List, Optional, Tuple

from network.controller.control_config import (
    DEFAULT_CONTROL_ACTIONS_CSV,
    DEFAULT_CONTROL_STATE_CSV,
    PriorityLevel,
)
from network.controller.control_logger import (
    ControlLogEntry,
    ControlStateEntry,
    close_control_logger,
    init_control_logger,
    log_control_action,
    record_control_state,
)
from network.controller.flow_mapper import (
    FlowTuple,
    is_allowlisted_interface,
    is_known_device,
    is_valid_ipv4,
    is_valid_port,
    is_valid_protocol,
    resolve_device_interface,
)
from network.controller.rollback import register_managed_interface, rollback_all
from network.controller.tc_manager import (
    priority_to_tc_class,
    tc_apply_filter,
    tc_remove_filter,
    tc_update_filter,
)


class CommandType(IntEnum):
    CMD_APPLY = 0
    CMD_REMOVE = 1
    CMD_UPDATE = 2
    CMD_STATUS = 3
    CMD_RESET = 4
    CMD_UNKNOWN = -1


class ControlScope(IntEnum):
    SCOPE_FLOW = 0
    SCOPE_DEVICE = 1


class ControlStatus(IntEnum):
    CTRL_STATUS_SUCCESS = 0
    CTRL_STATUS_FAILED = 1
    CTRL_STATUS_SKIPPED = 2
    CTRL_STATUS_DRY_RUN = 3


def parse_command_type(cmd_str: Optional[str]) -> CommandType:
    if not cmd_str:
        return CommandType.CMD_UNKNOWN
    s = cmd_str.strip().upper()
    if s == "APPLY":
        return CommandType.CMD_APPLY
    elif s == "REMOVE":
        return CommandType.CMD_REMOVE
    elif s == "UPDATE":
        return CommandType.CMD_UPDATE
    elif s == "STATUS":
        return CommandType.CMD_STATUS
    elif s in ("RESET", "ROLLBACK"):
        return CommandType.CMD_RESET
    return CommandType.CMD_UNKNOWN


def command_type_to_string(cmd: CommandType) -> str:
    mapping = {
        CommandType.CMD_APPLY: "APPLY",
        CommandType.CMD_REMOVE: "REMOVE",
        CommandType.CMD_UPDATE: "UPDATE",
        CommandType.CMD_STATUS: "STATUS",
        CommandType.CMD_RESET: "RESET",
    }
    return mapping.get(cmd, "UNKNOWN")


def control_status_to_string(status: ControlStatus) -> str:
    mapping = {
        ControlStatus.CTRL_STATUS_SUCCESS: "SUCCESS",
        ControlStatus.CTRL_STATUS_FAILED: "FAILED",
        ControlStatus.CTRL_STATUS_SKIPPED: "SKIPPED",
        ControlStatus.CTRL_STATUS_DRY_RUN: "DRY_RUN",
    }
    return mapping.get(status, "UNKNOWN")


@dataclass
class ControlRequest:
    command: CommandType = CommandType.CMD_APPLY
    device_id: str = ""
    flow_id: str = ""
    src_ip: str = ""
    dst_ip: str = ""
    src_port: int = 0
    dst_port: int = 0
    protocol: str = ""
    traffic_class: str = ""
    predicted_congestion_class: str = ""
    priority: PriorityLevel = PriorityLevel.PRIO_LEVEL_NORMAL
    requested_scope: ControlScope = ControlScope.SCOPE_FLOW
    interface: str = ""
    dry_run: bool = True


@dataclass
class ControlResponse:
    status: ControlStatus = ControlStatus.CTRL_STATUS_SUCCESS
    status_str: str = "SUCCESS"
    rule_identifier: str = ""
    target_class: str = ""
    executed_command: str = ""
    error_message: str = ""


@dataclass
class ActiveRule:
    flow_id: str
    interface: str
    priority: PriorityLevel
    filter_handle: int
    target_class: str
    rule_id: str
    active: bool = True


class ControlSubsystem:
    """Thread-safe control subsystem managing active rule table and dispatching commands."""

    def __init__(self):
        self.lock = threading.Lock()
        self.rule_table: Dict[str, ActiveRule] = {}
        self.next_filter_id: int = 0x100
        self.ready: bool = False

    def init(self, dry_run: bool = True) -> bool:
        with self.lock:
            self.rule_table.clear()
            self.next_filter_id = 0x100
            init_control_logger(DEFAULT_CONTROL_ACTIONS_CSV, DEFAULT_CONTROL_STATE_CSV)
            self.ready = True
            return True

    def shutdown(self) -> None:
        with self.lock:
            close_control_logger()
            self.ready = False

    def dispatch(self, req: ControlRequest) -> Tuple[bool, ControlResponse]:
        with self.lock:
            if not self.ready:
                self.init(req.dry_run)

            resp = ControlResponse()

            # Handle RESET / ROLLBACK command directly
            if req.command == CommandType.CMD_RESET:
                rolled_back, err = rollback_all(req.dry_run)
                for r in self.rule_table.values():
                    r.active = False
                self.rule_table.clear()

                resp.status = ControlStatus.CTRL_STATUS_DRY_RUN if req.dry_run else ControlStatus.CTRL_STATUS_SUCCESS
                resp.status_str = control_status_to_string(resp.status)
                resp.rule_identifier = "all_interfaces_reset"
                resp.executed_command = f"rollback_all({rolled_back} interfaces)"
                return True, resp

            # 1. Validate Input Parameters (Safety Requirement)
            if not is_known_device(req.device_id):
                resp.status = ControlStatus.CTRL_STATUS_FAILED
                resp.status_str = "FAILED"
                resp.error_message = f"Unknown device_id '{req.device_id}'"

                err_log = ControlLogEntry(
                    device_id=req.device_id,
                    flow_id=req.flow_id,
                    action=command_type_to_string(req.command),
                    status="FAILED",
                    dry_run=req.dry_run,
                    error_message=resp.error_message,
                )
                log_control_action(err_log)
                return False, resp

            # Resolve interface if empty
            iface = req.interface if req.interface else (resolve_device_interface(req.device_id) or "")

            if not is_allowlisted_interface(iface):
                resp.status = ControlStatus.CTRL_STATUS_FAILED
                resp.status_str = "FAILED"
                resp.error_message = f"Interface '{iface}' not allowlisted"

                err_log = ControlLogEntry(
                    device_id=req.device_id,
                    flow_id=req.flow_id,
                    action=command_type_to_string(req.command),
                    status="FAILED",
                    dry_run=req.dry_run,
                    error_message=resp.error_message,
                )
                log_control_action(err_log)
                return False, resp

            # Validate 5-tuple
            if (
                not is_valid_ipv4(req.src_ip)
                or not is_valid_ipv4(req.dst_ip)
                or not is_valid_port(req.src_port)
                or not is_valid_port(req.dst_port)
                or not is_valid_protocol(req.protocol)
            ):
                resp.status = ControlStatus.CTRL_STATUS_FAILED
                resp.status_str = "FAILED"
                resp.error_message = (
                    f"Invalid 5-tuple attributes (src={req.src_ip}:{req.src_port}, "
                    f"dst={req.dst_ip}:{req.dst_port}, proto={req.protocol})"
                )

                err_log = ControlLogEntry(
                    device_id=req.device_id,
                    flow_id=req.flow_id,
                    action=command_type_to_string(req.command),
                    status="FAILED",
                    dry_run=req.dry_run,
                    error_message=resp.error_message,
                )
                log_control_action(err_log)
                return False, resp

            # Validate priority
            if req.priority == PriorityLevel.PRIO_LEVEL_UNKNOWN:
                resp.status = ControlStatus.CTRL_STATUS_FAILED
                resp.status_str = "FAILED"
                resp.error_message = "Invalid priority level"

                err_log = ControlLogEntry(
                    device_id=req.device_id,
                    flow_id=req.flow_id,
                    action=command_type_to_string(req.command),
                    status="FAILED",
                    dry_run=req.dry_run,
                    error_message=resp.error_message,
                )
                log_control_action(err_log)
                return False, resp

            target_class = priority_to_tc_class(req.priority)
            resp.target_class = target_class

            flow_tuple = FlowTuple(
                device_id=req.device_id,
                src_ip=req.src_ip,
                dst_ip=req.dst_ip,
                src_port=req.src_port,
                dst_port=req.dst_port,
                protocol=req.protocol,
                interface=iface,
            )

            existing_rule = self.rule_table.get(req.flow_id)

            # 2. Process Command Logic
            if req.command == CommandType.CMD_APPLY:
                if existing_rule is not None and existing_rule.active:
                    if existing_rule.priority == req.priority:
                        # Duplicate rule with identical priority: skip
                        resp.status = ControlStatus.CTRL_STATUS_SKIPPED
                        resp.status_str = "SKIPPED"
                        resp.rule_identifier = existing_rule.rule_id
                        resp.error_message = "Identical rule already active"

                        log_entry = ControlLogEntry(
                            device_id=req.device_id,
                            flow_id=req.flow_id,
                            src_ip=req.src_ip,
                            dst_ip=req.dst_ip,
                            src_port=req.src_port,
                            dst_port=req.dst_port,
                            protocol=req.protocol,
                            traffic_class=req.traffic_class,
                            predicted_congestion_class=req.predicted_congestion_class,
                            final_priority=target_class,
                            action="APPLY",
                            target_class=target_class,
                            interface=iface,
                            dry_run=req.dry_run,
                            status="SKIPPED",
                            rule_identifier=resp.rule_identifier,
                            error_message=resp.error_message,
                        )
                        log_control_action(log_entry)
                        return True, resp
                    else:
                        # Priority updated: dynamically update existing filter
                        handle = existing_rule.filter_handle
                        ok, tc_res = tc_update_filter(iface, flow_tuple, target_class, handle, req.dry_run)

                        resp.status = ControlStatus.CTRL_STATUS_DRY_RUN if req.dry_run else (
                            ControlStatus.CTRL_STATUS_SUCCESS if ok else ControlStatus.CTRL_STATUS_FAILED
                        )
                        resp.status_str = control_status_to_string(resp.status)
                        resp.rule_identifier = tc_res.rule_identifier
                        resp.executed_command = tc_res.generated_command
                        resp.error_message = tc_res.error_message

                        existing_rule.priority = req.priority
                        existing_rule.target_class = target_class

                        log_entry = ControlLogEntry(
                            device_id=req.device_id,
                            flow_id=req.flow_id,
                            src_ip=req.src_ip,
                            dst_ip=req.dst_ip,
                            src_port=req.src_port,
                            dst_port=req.dst_port,
                            protocol=req.protocol,
                            traffic_class=req.traffic_class,
                            predicted_congestion_class=req.predicted_congestion_class,
                            final_priority=target_class,
                            action="UPDATE",
                            target_class=target_class,
                            interface=iface,
                            dry_run=req.dry_run,
                            status=resp.status_str,
                            rule_identifier=resp.rule_identifier,
                            error_message=resp.error_message,
                        )
                        log_control_action(log_entry)
                        return ok, resp
                else:
                    # New rule application
                    register_managed_interface(iface)
                    handle = self.next_filter_id
                    self.next_filter_id += 1

                    ok, tc_res = tc_apply_filter(iface, flow_tuple, target_class, handle, req.dry_run)

                    resp.status = ControlStatus.CTRL_STATUS_DRY_RUN if req.dry_run else (
                        ControlStatus.CTRL_STATUS_SUCCESS if ok else ControlStatus.CTRL_STATUS_FAILED
                    )
                    resp.status_str = control_status_to_string(resp.status)
                    resp.rule_identifier = tc_res.rule_identifier
                    resp.executed_command = tc_res.generated_command
                    resp.error_message = tc_res.error_message

                    self.rule_table[req.flow_id] = ActiveRule(
                        flow_id=req.flow_id,
                        interface=iface,
                        priority=req.priority,
                        filter_handle=handle,
                        target_class=target_class,
                        rule_id=resp.rule_identifier,
                        active=True,
                    )

                    log_entry = ControlLogEntry(
                        device_id=req.device_id,
                        flow_id=req.flow_id,
                        src_ip=req.src_ip,
                        dst_ip=req.dst_ip,
                        src_port=req.src_port,
                        dst_port=req.dst_port,
                        protocol=req.protocol,
                        traffic_class=req.traffic_class,
                        predicted_congestion_class=req.predicted_congestion_class,
                        final_priority=target_class,
                        action="APPLY",
                        target_class=target_class,
                        interface=iface,
                        dry_run=req.dry_run,
                        status=resp.status_str,
                        rule_identifier=resp.rule_identifier,
                        error_message=resp.error_message,
                    )
                    log_control_action(log_entry)

                    state_entry = ControlStateEntry(
                        device_id=req.device_id,
                        flow_id=req.flow_id,
                        interface=iface,
                        priority=target_class,
                        traffic_class=req.traffic_class,
                        control_class=target_class,
                        action="APPLY",
                        status=resp.status_str,
                        rule_identifier=resp.rule_identifier,
                        dry_run=req.dry_run,
                        error_message=resp.error_message,
                    )
                    record_control_state(state_entry)
                    return ok, resp

            elif req.command == CommandType.CMD_REMOVE:
                if existing_rule is None or not existing_rule.active:
                    resp.status = ControlStatus.CTRL_STATUS_SKIPPED
                    resp.status_str = "SKIPPED"
                    resp.error_message = "Flow rule not found for removal"
                    return True, resp

                handle = existing_rule.filter_handle
                ok, tc_res = tc_remove_filter(iface, handle, req.dry_run)
                existing_rule.active = False

                resp.status = ControlStatus.CTRL_STATUS_DRY_RUN if req.dry_run else (
                    ControlStatus.CTRL_STATUS_SUCCESS if ok else ControlStatus.CTRL_STATUS_FAILED
                )
                resp.status_str = control_status_to_string(resp.status)
                resp.rule_identifier = tc_res.rule_identifier
                resp.executed_command = tc_res.generated_command

                log_entry = ControlLogEntry(
                    device_id=req.device_id,
                    flow_id=req.flow_id,
                    action="REMOVE",
                    interface=iface,
                    dry_run=req.dry_run,
                    status=resp.status_str,
                    rule_identifier=resp.rule_identifier,
                )
                log_control_action(log_entry)
                return ok, resp

            elif req.command == CommandType.CMD_STATUS:
                resp.status = ControlStatus.CTRL_STATUS_SUCCESS
                resp.status_str = "SUCCESS"
                active_count = sum(1 for r in self.rule_table.values() if r.active)
                resp.executed_command = f"active_rules={active_count}"
                return True, resp

            return False, resp


_global_subsystem = ControlSubsystem()


def init_control_subsystem(dry_run: bool = True) -> bool:
    return _global_subsystem.init(dry_run)


def shutdown_control_subsystem() -> None:
    _global_subsystem.shutdown()


def dispatch_control_request(req: ControlRequest) -> Tuple[bool, ControlResponse]:
    return _global_subsystem.dispatch(req)
