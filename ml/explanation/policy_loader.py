"""Policy decision loader for Phase 17 Explanation Module."""

from pathlib import Path
import sys
from typing import Any, Dict, Optional
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.explanation.config import DEFAULT_POLICY_CSV


class PolicyLoader:
    """Loads Phase 13 QoS policy decisions."""

    def __init__(self, policy_path: Optional[Path] = None):
        self.policy_path = policy_path or DEFAULT_POLICY_CSV

    def load_policy_df(self) -> pd.DataFrame:
        """Load policy decisions DataFrame."""
        if not self.policy_path.exists():
            return pd.DataFrame()
        return pd.read_csv(self.policy_path)
