"""Decision loader for Phase 14 Adaptive Traffic Control.

Loads Phase 13 QoS decisions, extracts flow 5-tuple metadata,
resolves topology interfaces, and prepares structured control intent records.
"""

from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.control.config import (
    DEFAULT_DECISIONS_PATH,
    DEVICE_TO_INTERFACE,
    PRIORITY_TO_CLASS,
)

# Regex to parse flow_id: <device>_<src_ip>:<src_port>-><dst_ip>:<dst_port>_<proto>
FLOW_ID_PATTERN = re.compile(
    r"^(?P<device>[^_]+)_(?P<src_ip>[^:]+):(?P<src_port>\d+)->(?P<dst_ip>[^:]+):(?P<dst_port>\d+)_(?P<protocol>[A-Za-z]+)$"
)


class DecisionLoader:
    """Loads and transforms Phase 13 policy decisions into network control intents."""

    def __init__(self, decisions_path: Optional[Path] = None):
        self.decisions_path = decisions_path or DEFAULT_DECISIONS_PATH

    @staticmethod
    def parse_flow_id(flow_id: str) -> Optional[Dict[str, Any]]:
        """Parse structured 5-tuple attributes from flow_id string."""
        if not flow_id or not isinstance(flow_id, str):
            return None
        match = FLOW_ID_PATTERN.match(flow_id.strip())
        if not match:
            return None
        gd = match.groupdict()
        return {
            "device_id": gd["device"],
            "src_ip": gd["src_ip"],
            "src_port": int(gd["src_port"]),
            "dst_ip": gd["dst_ip"],
            "dst_port": int(gd["dst_port"]),
            "protocol": gd["protocol"].upper(),
        }

    def load_decisions(self) -> List[Dict[str, Any]]:
        """Load decisions from CSV and augment with network attributes.

        Returns:
            List of control intent dictionaries.
        """
        if not Path(self.decisions_path).exists():
            raise FileNotFoundError(f"Decisions CSV not found at {self.decisions_path}")

        df = pd.read_csv(self.decisions_path)
        records: List[Dict[str, Any]] = []

        for _, row in df.iterrows():
            flow_id = str(row.get("flow_id", "")).strip()
            device_id = str(row.get("device_id", "")).strip()
            final_prio = str(row.get("final_priority", "NORMAL")).strip().upper()
            completeness = str(row.get("input_completeness", "COMPLETE")).strip().upper()
            traffic_class = str(row.get("traffic_class", "OTHER")).strip()
            cong_class = str(row.get("predicted_congestion_class", "UNKNOWN")).strip()
            ts = str(row.get("timestamp", "")) if pd.notna(row.get("timestamp")) else ""

            parsed_flow = self.parse_flow_id(flow_id)
            if not parsed_flow:
                # If flow_id regex failed, use device_id and empty 5-tuple
                src_ip = ""
                dst_ip = ""
                src_port = 0
                dst_port = 0
                protocol = "TCP"
            else:
                src_ip = parsed_flow["src_ip"]
                dst_ip = parsed_flow["dst_ip"]
                src_port = parsed_flow["src_port"]
                dst_port = parsed_flow["dst_port"]
                protocol = parsed_flow["protocol"]

            # Interface resolution
            iface = DEVICE_TO_INTERFACE.get(device_id, "s1-eth1")
            target_class = PRIORITY_TO_CLASS.get(final_prio, "1:30")

            intent: Dict[str, Any] = {
                "timestamp": ts,
                "device_id": device_id,
                "flow_id": flow_id,
                "src_ip": src_ip,
                "dst_ip": dst_ip,
                "src_port": src_port,
                "dst_port": dst_port,
                "protocol": protocol,
                "traffic_class": traffic_class,
                "predicted_congestion_class": cong_class,
                "final_priority": final_prio,
                "target_class": target_class,
                "interface": iface,
                "input_completeness": completeness,
                "is_fallback": (completeness != "COMPLETE"),
            }
            records.append(intent)

        return records
