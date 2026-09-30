"""Domain-aware stage matching algorithms for Phase 15 Decision Trace.

Links monitoring metrics, feature vectors, user profiles, congestion predictions,
traffic classifications, policy decisions, and control actions using domain identifiers.
Strictly avoids row-number / index-based joins.
"""

from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.trace.config import (
    MATCH_DEVICE_TIMESTAMP,
    MATCH_EXACT_DEVICE_FLOW,
    MATCH_EXACT_FLOW_ID,
    MATCH_FLOW_TIMESTAMP_TOLERANCE,
    MATCH_UNMATCHED,
    TRACE_TIMESTAMP_TOLERANCE_SECONDS,
)


class TraceMatcher:
    """Matches network records across multi-stage pipeline datasets using domain keys."""

    def __init__(self, tolerance_seconds: float = TRACE_TIMESTAMP_TOLERANCE_SECONDS):
        self.tolerance_seconds = tolerance_seconds

    @staticmethod
    def parse_datetime(val: Any) -> Optional[datetime]:
        """Safely parse datetime string or pandas timestamp."""
        if pd.isna(val) or val is None or val == "":
            return None
        try:
            return pd.to_datetime(val)
        except Exception:
            return None

    @classmethod
    def compute_timestamp_diff_ms(cls, ts1: Any, ts2: Any) -> float:
        """Compute absolute timestamp difference in milliseconds."""
        dt1 = cls.parse_datetime(ts1)
        dt2 = cls.parse_datetime(ts2)
        if dt1 is None or dt2 is None:
            return 0.0
        return abs((dt1 - dt2).total_seconds()) * 1000.0

    def match_monitoring_record(
        self,
        flow_id: str,
        device_id: str,
        timestamp: Any,
        monitoring_df: pd.DataFrame,
    ) -> Tuple[Optional[Dict[str, Any]], str, float]:
        """Match flow against network monitoring records (Stage 1)."""
        if monitoring_df.empty or not flow_id:
            return None, MATCH_UNMATCHED, 0.0

        ref_dt = self.parse_datetime(timestamp)

        # Prepare flow_id column in monitoring if missing
        if "flow_id" not in monitoring_df.columns:
            # Construct synthetic flow_id from 5-tuple
            constructed = (
                monitoring_df["device_id"].astype(str)
                + "_"
                + monitoring_df["src_ip"].astype(str)
                + ":"
                + monitoring_df["src_port"].astype(str)
                + "->"
                + monitoring_df["dst_ip"].astype(str)
                + ":"
                + monitoring_df["dst_port"].astype(str)
                + "_"
                + monitoring_df["protocol"].astype(str).str.upper()
            )
            candidates = monitoring_df[constructed == flow_id]
        else:
            candidates = monitoring_df[monitoring_df["flow_id"] == flow_id]

        if candidates.empty:
            # Fallback: device match within tolerance
            dev_candidates = monitoring_df[monitoring_df["device_id"] == device_id]
            if dev_candidates.empty or ref_dt is None:
                return None, MATCH_UNMATCHED, 0.0
            candidates = dev_candidates

        # Find closest candidate by timestamp
        best_row = None
        best_diff_sec = float("inf")
        match_method = MATCH_UNMATCHED

        for _, row in candidates.iterrows():
            row_dt = self.parse_datetime(row.get("timestamp"))
            if row_dt is None or ref_dt is None:
                diff_sec = 0.0
            else:
                diff_sec = abs((ref_dt - row_dt).total_seconds())

            if diff_sec <= self.tolerance_seconds and diff_sec < best_diff_sec:
                best_diff_sec = diff_sec
                best_row = row.to_dict()
                if diff_sec == 0.0:
                    match_method = MATCH_EXACT_FLOW_ID
                else:
                    match_method = MATCH_FLOW_TIMESTAMP_TOLERANCE

        diff_ms = (best_diff_sec * 1000.0) if best_diff_sec != float("inf") else 0.0
        return best_row, match_method, diff_ms

    def match_features_record(
        self,
        flow_id: str,
        timestamp: Any,
        features_df: pd.DataFrame,
    ) -> Tuple[Optional[Dict[str, Any]], str, float]:
        """Match flow against extracted feature records (Stage 2)."""
        if features_df.empty or not flow_id:
            return None, MATCH_UNMATCHED, 0.0

        ref_dt = self.parse_datetime(timestamp)
        candidates = features_df[features_df["flow_id"] == flow_id]
        if candidates.empty:
            return None, MATCH_UNMATCHED, 0.0

        best_row = None
        best_diff_sec = float("inf")
        match_method = MATCH_UNMATCHED

        for _, row in candidates.iterrows():
            row_dt = self.parse_datetime(row.get("timestamp"))
            if row_dt is None or ref_dt is None:
                diff_sec = 0.0
            else:
                diff_sec = abs((ref_dt - row_dt).total_seconds())

            if diff_sec <= self.tolerance_seconds and diff_sec < best_diff_sec:
                best_diff_sec = diff_sec
                best_row = row.to_dict()
                match_method = MATCH_EXACT_FLOW_ID if diff_sec == 0.0 else MATCH_FLOW_TIMESTAMP_TOLERANCE

        diff_ms = (best_diff_sec * 1000.0) if best_diff_sec != float("inf") else 0.0
        return best_row, match_method, diff_ms

    @staticmethod
    def match_profile_record(
        device_id: str,
        profiles_df: pd.DataFrame,
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """Match host against K-Means behavior profiles (Stage 3)."""
        if profiles_df.empty or not device_id:
            return None, MATCH_UNMATCHED

        match = profiles_df[profiles_df["device_id"] == device_id]
        if match.empty:
            return None, MATCH_UNMATCHED

        return match.iloc[0].to_dict(), MATCH_EXACT_DEVICE_FLOW

    def match_congestion_prediction(
        self,
        device_id: str,
        timestamp: Any,
        congestion_df: pd.DataFrame,
    ) -> Tuple[Optional[Dict[str, Any]], str, float]:
        """Match device against GRU congestion predictions (Stage 4)."""
        if congestion_df.empty or not device_id:
            return None, MATCH_UNMATCHED, 0.0

        ref_dt = self.parse_datetime(timestamp)
        candidates = congestion_df[congestion_df["device_id"] == device_id]
        if candidates.empty:
            return None, MATCH_UNMATCHED, 0.0

        best_row = None
        best_diff_sec = float("inf")

        for _, row in candidates.iterrows():
            ts_val = row.get("prediction_timestamp", row.get("timestamp"))
            row_dt = self.parse_datetime(ts_val)
            if row_dt is None or ref_dt is None:
                diff_sec = 0.0
            else:
                diff_sec = abs((ref_dt - row_dt).total_seconds())

            if diff_sec <= self.tolerance_seconds and diff_sec < best_diff_sec:
                best_diff_sec = diff_sec
                best_row = row.to_dict()

        if best_row:
            diff_ms = best_diff_sec * 1000.0
            return best_row, MATCH_DEVICE_TIMESTAMP, diff_ms

        return None, MATCH_UNMATCHED, 0.0

    def match_classification_record(
        self,
        flow_id: str,
        timestamp: Any,
        classification_df: pd.DataFrame,
    ) -> Tuple[Optional[Dict[str, Any]], str, float]:
        """Match flow against traffic classification records (Stage 5)."""
        if classification_df.empty or not flow_id:
            return None, MATCH_UNMATCHED, 0.0

        ref_dt = self.parse_datetime(timestamp)
        candidates = classification_df[classification_df["flow_id"] == flow_id]
        if candidates.empty:
            return None, MATCH_UNMATCHED, 0.0

        best_row = None
        best_diff_sec = float("inf")
        match_method = MATCH_UNMATCHED

        for _, row in candidates.iterrows():
            row_dt = self.parse_datetime(row.get("timestamp"))
            if row_dt is None or ref_dt is None:
                diff_sec = 0.0
            else:
                diff_sec = abs((ref_dt - row_dt).total_seconds())

            if diff_sec <= self.tolerance_seconds and diff_sec < best_diff_sec:
                best_diff_sec = diff_sec
                best_row = row.to_dict()
                match_method = MATCH_EXACT_FLOW_ID if diff_sec == 0.0 else MATCH_FLOW_TIMESTAMP_TOLERANCE

        diff_ms = (best_diff_sec * 1000.0) if best_diff_sec != float("inf") else 0.0
        return best_row, match_method, diff_ms

    def match_control_record(
        self,
        flow_id: str,
        timestamp: Any,
        control_df: pd.DataFrame,
    ) -> Tuple[Optional[Dict[str, Any]], str, float]:
        """Match flow against network control actions (Stage 7)."""
        if control_df.empty or not flow_id:
            return None, MATCH_UNMATCHED, 0.0

        ref_dt = self.parse_datetime(timestamp)
        candidates = control_df[control_df["flow_id"] == flow_id]
        if candidates.empty:
            return None, MATCH_UNMATCHED, 0.0

        best_row = None
        best_diff_sec = float("inf")
        match_method = MATCH_UNMATCHED

        for _, row in candidates.iterrows():
            row_dt = self.parse_datetime(row.get("timestamp"))
            if row_dt is None or ref_dt is None:
                diff_sec = 0.0
            else:
                diff_sec = abs((ref_dt - row_dt).total_seconds())

            if diff_sec <= self.tolerance_seconds and diff_sec < best_diff_sec:
                best_diff_sec = diff_sec
                best_row = row.to_dict()
                match_method = MATCH_EXACT_FLOW_ID if diff_sec == 0.0 else MATCH_FLOW_TIMESTAMP_TOLERANCE

        # If not within tolerance, take latest candidate matching flow_id
        if not best_row and not candidates.empty:
            best_row = candidates.iloc[-1].to_dict()
            match_method = MATCH_EXACT_FLOW_ID
            diff_ms = 0.0
        else:
            diff_ms = (best_diff_sec * 1000.0) if best_diff_sec != float("inf") else 0.0

        return best_row, match_method, diff_ms
