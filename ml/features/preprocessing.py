"""Data loading and preprocessing utilities for network telemetry data (Phase 7).

Handles loading from CSV, schema validation, timestamp parsing, missing-value
handling without data fabrication, and optional feature scaling.
"""

import logging
import sys
from pathlib import Path
from typing import List, Optional, Union

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from ml.features.config import REQUIRED_COLUMNS, NUMERIC_COLUMNS

logger = logging.getLogger(__name__)


def load_network_data(filepath: Union[str, Path]) -> pd.DataFrame:
    """Load network metrics CSV produced by Phase 6 Data Ingestion.

    Validates schema presence, parses timestamps, converts numeric columns,
    and preserves missing metrics (N/A) without fabricating values.

    Args:
        filepath: Path to the CSV file.

    Returns:
        pd.DataFrame with parsed and validated columns.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If required columns are missing from the CSV.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Network metrics file not found: {path.resolve()}")

    # Read CSV with NA representations
    df = pd.read_csv(
        path,
        na_values=["N/A", "NA", "null", "None", "", "nan", "NaN"],
        keep_default_na=True,
    )

    # 1. Check required columns
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        error_msg = (
            f"Schema validation error in '{path.name}': missing {len(missing_cols)} "
            f"required column(s): {', '.join(missing_cols)}"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    # 2. Parse timestamps
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    invalid_ts_count = df["timestamp"].isna().sum()
    if invalid_ts_count > 0:
        logger.warning(
            "Found %d record(s) with unparseable timestamps; these will be dropped.",
            invalid_ts_count,
        )
        df = df.dropna(subset=["timestamp"]).copy()

    # 3. Convert numeric columns
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Clean string columns
    for str_col in ["device_id", "src_ip", "dst_ip", "protocol"]:
        if str_col in df.columns:
            df[str_col] = df[str_col].astype(str).str.strip()

    record_count = len(df)
    print(f"Loaded {record_count:,} network records from '{path.name}'.")
    logger.info("Loaded %d network records from %s", record_count, path)

    return df


def clean_network_data(df: pd.DataFrame) -> pd.DataFrame:
    """Perform basic sanitization for feature extraction.

    - Removes exact duplicate records.
    - Normalizes protocol strings (TCP/UDP).
    - Drops records with empty or invalid device IDs or timestamps.
    - Preserves missing RTT / packet loss values without zero-imputation.

    Args:
        df: Raw DataFrame loaded by load_network_data.

    Returns:
        Cleaned pd.DataFrame.
    """
    if df.empty:
        return df.copy()

    cleaned = df.copy()

    # Normalize protocol
    cleaned["protocol"] = cleaned["protocol"].str.upper()
    valid_protocols = {"TCP", "UDP"}
    cleaned = cleaned[cleaned["protocol"].isin(valid_protocols)].copy()

    # Drop records missing vital identifiers
    cleaned = cleaned.dropna(subset=["device_id", "timestamp"]).copy()
    cleaned = cleaned[cleaned["device_id"] != ""].copy()

    # Deduplicate exact rows
    cleaned = cleaned.drop_duplicates()

    return cleaned


def prepare_scaled_features(
    df: pd.DataFrame,
    feature_cols: List[str],
    scaler_type: str = "standard",
) -> pd.DataFrame:
    """Optionally scale selected numerical features for downstream ML consumption.

    Does not modify or overwrite the original input DataFrame.

    Args:
        df: Feature DataFrame.
        feature_cols: List of column names to scale.
        scaler_type: 'standard' for z-score normalization, 'minmax' for [0, 1] scaling.

    Returns:
        A new pd.DataFrame containing the scaled features with '_scaled' suffix.
    """
    scaled_df = df.copy()
    valid_cols = [c for c in feature_cols if c in df.columns]

    for col in valid_cols:
        series = df[col].astype(float)
        mean_val = series.mean()
        std_val = series.std(ddof=0)
        min_val = series.min()
        max_val = series.max()

        if scaler_type == "standard":
            if std_val and not np.isnan(std_val) and std_val > 0:
                scaled_df[f"{col}_scaled"] = (series - mean_val) / std_val
            else:
                scaled_df[f"{col}_scaled"] = 0.0
        elif scaler_type == "minmax":
            if max_val is not None and min_val is not None and max_val > min_val:
                scaled_df[f"{col}_scaled"] = (series - min_val) / (max_val - min_val)
            else:
                scaled_df[f"{col}_scaled"] = 0.0
        else:
            raise ValueError(f"Unsupported scaler_type '{scaler_type}'. Choose 'standard' or 'minmax'.")

    return scaled_df
