"""SHAP explanation data loader for Phase 17 Explanation Module."""

import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.explanation.config import (
    DEFAULT_EXPLANATION_RECORDS_JSONL,
    DEFAULT_SHAP_GLOBAL_CSV,
    DEFAULT_SHAP_LOCAL_CSV,
    DEFAULT_SHAP_LOCAL_JSONL,
)


class SHAPLoader:
    """Loads Phase 16 local SHAP explanations, global importance, and structured records."""

    def __init__(
        self,
        local_csv_path: Optional[Path] = None,
        records_jsonl_path: Optional[Path] = None,
        global_csv_path: Optional[Path] = None,
    ):
        self.local_csv_path = local_csv_path or DEFAULT_SHAP_LOCAL_CSV
        self.records_jsonl_path = records_jsonl_path or DEFAULT_EXPLANATION_RECORDS_JSONL
        self.global_csv_path = global_csv_path or DEFAULT_SHAP_GLOBAL_CSV

    def load_local_shap_df(self) -> pd.DataFrame:
        """Load tabular local SHAP explanations."""
        if not self.local_csv_path.exists():
            return pd.DataFrame()
        return pd.read_csv(self.local_csv_path)

    def load_explanation_records_map(self) -> Dict[str, Dict[str, Any]]:
        """Load Phase 16 structured explanation records indexed by trace_id."""
        if not self.records_jsonl_path.exists():
            return {}

        records_map = {}
        with open(self.records_jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    tid = obj.get("trace_id")
                    if tid:
                        records_map[tid] = obj
                except Exception:
                    pass
        return records_map

    def load_global_importance_df(self) -> pd.DataFrame:
        """Load global feature importance rankings."""
        if not self.global_csv_path.exists():
            return pd.DataFrame()
        return pd.read_csv(self.global_csv_path)
