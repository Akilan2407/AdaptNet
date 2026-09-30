"""Network control loader for Phase 17 Explanation Module."""

from pathlib import Path
import sys
from typing import Any, Dict, Optional
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.explanation.config import DEFAULT_CONTROL_CSV


class ControlLoader:
    """Loads Phase 14 network traffic control action audit records."""

    def __init__(self, control_path: Optional[Path] = None):
        self.control_path = control_path or DEFAULT_CONTROL_CSV

    def load_control_df(self) -> pd.DataFrame:
        """Load network control actions DataFrame."""
        if not self.control_path.exists():
            return pd.DataFrame()
        return pd.read_csv(self.control_path)
