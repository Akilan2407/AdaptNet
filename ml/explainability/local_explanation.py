"""Local Per-Decision SHAP Explanation Service (Phase 16).

Links Phase 15 decision traces directly to SHAP feature attributions,
generating both tabular (CSV) and structured (JSONL) local explanations.
"""

import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.explainability.config import (
    DEFAULT_LOCAL_CSV,
    DEFAULT_LOCAL_JSONL,
    DEFAULT_TRACES_CSV,
    DEFAULT_TRACES_JSONL,
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_SUCCESS,
)
from ml.explainability.explanation_validator import ExplanationValidator
from ml.explainability.feature_mapper import FeatureMapper
from ml.explainability.model_loader import ModelLoader
from ml.explainability.shap_explainer import SHAPExplainerWrapper

logger = logging.getLogger("ml.explainability.local_explanation")


class LocalExplainer:
    """Generates local SHAP explanations for individual network decision traces."""

    def __init__(
        self,
        shap_explainer: Optional[SHAPExplainerWrapper] = None,
        traces_path: Optional[Path] = None,
        output_csv: Optional[Path] = None,
        output_jsonl: Optional[Path] = None,
    ):
        self.explainer = shap_explainer or SHAPExplainerWrapper()
        self.traces_path = traces_path or DEFAULT_TRACES_CSV
        self.output_csv = output_csv or DEFAULT_LOCAL_CSV
        self.output_jsonl = output_jsonl or DEFAULT_LOCAL_JSONL

    def load_traces(self) -> pd.DataFrame:
        """Load decision traces dataset from CSV."""
        if not self.traces_path.exists():
            logger.warning("Traces file not found: %s", self.traces_path)
            return pd.DataFrame()
        return pd.read_csv(self.traces_path)

    def explain_trace(self, trace_row: Dict[str, Any]) -> Dict[str, Any]:
        """Generate local SHAP explanation for a single trace dictionary or Series.

        Returns:
            Structured dictionary with explanation status, prediction, base value,
            and ranked feature contributions.
        """
        trace_id = str(trace_row.get("trace_id", ""))
        ts = str(trace_row.get("timestamp", ""))
        device_id = str(trace_row.get("device_id", ""))
        flow_id = str(trace_row.get("flow_id", ""))
        pred_class = str(trace_row.get("predicted_congestion_class", "UNKNOWN")).strip().upper()
        completeness = str(trace_row.get("trace_completeness", "PARTIAL")).strip().upper()

        raw_score = trace_row.get("predicted_congestion_score")
        if pd.isna(raw_score) or raw_score is None or raw_score == "":
            return {
                "trace_id": trace_id,
                "timestamp": ts,
                "device_id": device_id,
                "flow_id": flow_id,
                "explanation_status": STATUS_SKIPPED,
                "explanation_error": "Incomplete trace: missing GRU congestion prediction",
                "prediction": {"score": None, "class": pred_class, "base_value": self.explainer.base_value},
                "features": [],
            }

        expected_score = float(raw_score)

        # Extract features and format sequence tensor
        raw_features = FeatureMapper.extract_raw_features_from_trace(trace_row)
        seq_tensor = self.explainer.loader.prepare_sequence_tensor(
            raw_features, device_id=device_id, timestamp=ts
        )

        try:
            shap_res = self.explainer.explain_sample(seq_tensor)
            model_score = shap_res["predicted_congestion_score"]
            base_val = shap_res["base_value"]

            # Validate explanation
            errors = ExplanationValidator.validate_explanation(
                shap_res, expected_score=expected_score
            )
            if errors:
                logger.warning("Validation warnings for %s: %s", trace_id, errors)

            # Build feature records with values
            formatted_features = []
            for item in shap_res["feature_contributions"]:
                feat_name = item["feature_name"]
                feat_val = raw_features.get(feat_name, 0.0)
                formatted_features.append({
                    "name": feat_name,
                    "value": round(float(feat_val), 4),
                    "shap_value": round(float(item["shap_value"]), 6),
                    "absolute_shap_value": round(float(item["absolute_shap_value"]), 6),
                    "direction": item["direction"],
                    "rank": item["feature_rank"],
                })

            return {
                "trace_id": trace_id,
                "timestamp": ts,
                "device_id": device_id,
                "flow_id": flow_id,
                "explanation_status": STATUS_SUCCESS,
                "explanation_error": "",
                "prediction": {
                    "score": round(model_score, 4),
                    "class": pred_class,
                    "base_value": round(base_val, 4),
                },
                "features": formatted_features,
            }
        except Exception as e:
            logger.error("Failed to explain trace %s: %s", trace_id, e)
            return {
                "trace_id": trace_id,
                "timestamp": ts,
                "device_id": device_id,
                "flow_id": flow_id,
                "explanation_status": STATUS_FAILED,
                "explanation_error": str(e),
                "prediction": {"score": expected_score, "class": pred_class, "base_value": self.explainer.base_value},
                "features": [],
            }

    def explain_all_traces(self) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
        """Generate and serialize local SHAP explanations for all traces.

        Returns:
            Tuple of (flat_csv_dataframe, structured_jsonl_records).
        """
        traces_df = self.load_traces()
        if traces_df.empty:
            logger.warning("No traces available to explain.")
            return pd.DataFrame(), []

        csv_rows: List[Dict[str, Any]] = []
        jsonl_records: List[Dict[str, Any]] = []

        for _, row in traces_df.iterrows():
            trace_dict = row.to_dict()
            res = self.explain_trace(trace_dict)
            jsonl_records.append(res)

            status = res["explanation_status"]
            tid = res["trace_id"]
            ts = res["timestamp"]
            dev = res["device_id"]
            flow = res["flow_id"]
            score = res["prediction"]["score"]
            pred_cls = res["prediction"]["class"]
            base_v = res["prediction"]["base_value"]

            if status == STATUS_SUCCESS:
                for f in res["features"]:
                    csv_rows.append({
                        "trace_id": tid,
                        "timestamp": ts,
                        "device_id": dev,
                        "flow_id": flow,
                        "predicted_congestion_score": score,
                        "predicted_congestion_class": pred_cls,
                        "base_value": base_v,
                        "feature_name": f["name"],
                        "feature_value": f["value"],
                        "shap_value": f["shap_value"],
                        "absolute_shap_value": f["absolute_shap_value"],
                        "contribution_direction": f["direction"],
                        "feature_rank": f["rank"],
                        "explanation_status": status,
                    })
            else:
                # Incomplete or failed trace: single row
                csv_rows.append({
                    "trace_id": tid,
                    "timestamp": ts,
                    "device_id": dev,
                    "flow_id": flow,
                    "predicted_congestion_score": score,
                    "predicted_congestion_class": pred_cls,
                    "base_value": base_v,
                    "feature_name": "",
                    "feature_value": None,
                    "shap_value": None,
                    "absolute_shap_value": None,
                    "contribution_direction": "",
                    "feature_rank": None,
                    "explanation_status": status,
                })

        # Export CSV
        self.output_csv.parent.mkdir(parents=True, exist_ok=True)
        csv_df = pd.DataFrame(csv_rows)
        csv_df.to_csv(self.output_csv, index=False)
        logger.info("Local SHAP explanations exported to %s", self.output_csv)

        # Export JSONL
        with open(self.output_jsonl, "w", encoding="utf-8") as f:
            for rec in jsonl_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        logger.info("Local SHAP JSONL exported to %s", self.output_jsonl)

        return csv_df, jsonl_records
