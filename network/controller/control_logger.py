"""Control action logger and authoritative control state tracker (converted from control_logger.h/.c)."""

from dataclasses import dataclass
from pathlib import Path
import threading
import time
from typing import Optional

from network.controller.control_config import (
    DEFAULT_CONTROL_ACTIONS_CSV,
    DEFAULT_CONTROL_STATE_CSV,
)


@dataclass
class ControlLogEntry:
    timestamp: str = ""
    device_id: str = ""
    flow_id: str = ""
    src_ip: str = ""
    dst_ip: str = ""
    src_port: int = 0
    dst_port: int = 0
    protocol: str = ""
    traffic_class: str = ""
    predicted_congestion_class: str = ""
    final_priority: str = ""
    action: str = ""  # APPLY, UPDATE, REMOVE, RESET
    target_class: str = ""
    interface: str = ""
    dry_run: bool = True
    status: str = ""  # SUCCESS, FAILED, SKIPPED, DRY_RUN
    rule_identifier: str = ""
    error_message: str = ""


@dataclass
class ControlStateEntry:
    timestamp: str = ""
    device_id: str = ""
    flow_id: str = ""
    interface: str = ""
    priority: str = ""
    traffic_class: str = ""
    control_class: str = ""
    action: str = ""
    status: str = ""
    rule_identifier: str = ""
    dry_run: bool = True
    error_message: str = ""


_log_lock = threading.Lock()
_actions_path = DEFAULT_CONTROL_ACTIONS_CSV
_state_path = DEFAULT_CONTROL_STATE_CSV
_logger_initialized = False


def get_current_iso_timestamp() -> str:
    """Return ISO formatted timestamp string (YYYY-MM-DD HH:MM:SS)."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def init_control_logger(
    act_path: Optional[str] = None,
    st_path: Optional[str] = None,
) -> bool:
    """Initialize CSV logs and write headers if files are missing or empty."""
    global _actions_path, _state_path, _logger_initialized
    with _log_lock:
        if act_path:
            _actions_path = act_path
        if st_path:
            _state_path = st_path

        p_act = Path(_actions_path)
        p_act.parent.mkdir(parents=True, exist_ok=True)
        if not p_act.exists() or p_act.stat().st_size == 0:
            with open(p_act, "w", encoding="utf-8") as f:
                f.write(
                    "timestamp,device_id,flow_id,src_ip,dst_ip,src_port,dst_port,"
                    "protocol,traffic_class,predicted_congestion_class,final_priority,"
                    "action,target_class,interface,dry_run,status,rule_identifier,error_message\n"
                )

        p_st = Path(_state_path)
        p_st.parent.mkdir(parents=True, exist_ok=True)
        if not p_st.exists() or p_st.stat().st_size == 0:
            with open(p_st, "w", encoding="utf-8") as f:
                f.write(
                    "timestamp,device_id,flow_id,interface,priority,traffic_class,"
                    "control_class,action,status,rule_identifier,dry_run,error_message\n"
                )

        _logger_initialized = True
        return True


def close_control_logger() -> None:
    """Close logger and reset initialized flag."""
    global _logger_initialized
    with _log_lock:
        _logger_initialized = False


def log_control_action(entry: ControlLogEntry) -> bool:
    """Append a row to control_actions.csv."""
    global _logger_initialized
    with _log_lock:
        if not _logger_initialized:
            init_control_logger(_actions_path, _state_path)

        ts = entry.timestamp if entry.timestamp else get_current_iso_timestamp()
        dry_str = "true" if entry.dry_run else "false"

        line = (
            f"{ts},{entry.device_id},{entry.flow_id},{entry.src_ip},{entry.dst_ip},"
            f"{entry.src_port},{entry.dst_port},{entry.protocol},{entry.traffic_class},"
            f"{entry.predicted_congestion_class},{entry.final_priority},{entry.action},"
            f"{entry.target_class},{entry.interface},{dry_str},{entry.status},"
            f"{entry.rule_identifier},{entry.error_message}\n"
        )
        try:
            with open(_actions_path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
            return True
        except Exception:
            return False


def record_control_state(entry: ControlStateEntry) -> bool:
    """Append an active rule record to control_state.csv."""
    global _logger_initialized
    with _log_lock:
        if not _logger_initialized:
            init_control_logger(_actions_path, _state_path)

        ts = entry.timestamp if entry.timestamp else get_current_iso_timestamp()
        dry_str = "true" if entry.dry_run else "false"

        line = (
            f"{ts},{entry.device_id},{entry.flow_id},{entry.interface},{entry.priority},"
            f"{entry.traffic_class},{entry.control_class},{entry.action},{entry.status},"
            f"{entry.rule_identifier},{dry_str},{entry.error_message}\n"
        )
        try:
            with open(_state_path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
            return True
        except Exception:
            return False
