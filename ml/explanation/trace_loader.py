"""Trace data loader for Phase 17 Explanation Module."""

from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.explanation.config import DEFAULT_TRACES_CSV, DEFAULT_TRACES_JSONL


class TraceLoader:
    """Loads and indexes Phase 15 decision traces."""

    def __init__(self, traces_path: Optional[Path] = None):
        self.traces_path = traces_path or DEFAULT_TRACES_CSV

    def load_traces(self) -> pd.DataFrame:
        """Load decision traces as a DataFrame."""
        if not self.traces_path.exists():
            return pd.DataFrame()
        return pd.read_csv(self.traces_path)

    def load_trace_map(self) -> Dict[str, Dict[str, Any]]:
        """Load traces indexed by trace_id."""
        df = self.load_traces()
        if df.empty or "trace_id" not in df.columns:
            return {}
        return df.set_index("trace_id").to_dict(orient="index")
