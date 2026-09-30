"""Primary Pipeline Coordinator and CLI for Phase 17 Natural-Language Explanations."""

import argparse
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

from ml.explanation.config import (
    DEFAULT_EXPLANATIONS_CSV,
    DEFAULT_EXPLANATIONS_JSONL,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REPORT_TXT,
    DEFAULT_STATUS_PLOT,
    DEFAULT_SUMMARY_JSON,
    DEFAULT_TOP_SHAP_PLOT,
    STATUS_FAILED,
    STATUS_PARTIAL,
    STATUS_SKIPPED,
    STATUS_SUCCESS,
)
from ml.explanation.control_loader import ControlLoader
from ml.explanation.explanation_builder import ExplanationBuilder, ExplanationRecord
from ml.explanation.policy_loader import PolicyLoader
from ml.explanation.report_generator import ReportGenerator
from ml.explanation.shap_loader import SHAPLoader
from ml.explanation.trace_loader import TraceLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ml.explanation.generator")


class ExplanationGenerator:
    """Coordinates loading, synthesis, export, and verification of natural-language explanations."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.trace_loader = TraceLoader()
        self.shap_loader = SHAPLoader()
        self.policy_loader = PolicyLoader()
        self.control_loader = ControlLoader()
        self.report_generator = ReportGenerator(output_dir=self.output_dir)

    def generate_all_explanations(self) -> Tuple[List[ExplanationRecord], Dict[str, Any]]:
        """Generate and persist natural-language explanations for all traces."""
        traces_df = self.trace_loader.load_traces()
        shap_records_map = self.shap_loader.load_explanation_records_map()
        global_shap_df = self.shap_loader.load_global_importance_df()

        if traces_df.empty:
            logger.warning("No traces found to generate explanations.")
            return [], {}

        explanation_records: List[ExplanationRecord] = []
        for _, row in traces_df.iterrows():
            trace_dict = row.to_dict()
            tid = str(trace_dict.get("trace_id", ""))
            shap_rec = shap_records_map.get(tid)
            rec = ExplanationBuilder.build_record(trace_dict, shap_record=shap_rec)
            explanation_records.append(rec)

        # 1. Export CSV
        csv_rows = [r.to_flat_dict() for r in explanation_records]
        csv_df = pd.DataFrame(csv_rows)
        csv_path = self.output_dir / "natural_language_explanations.csv"
        csv_df.to_csv(csv_path, index=False)
        logger.info("Exported natural-language explanations CSV to %s", csv_path)

        # 2. Export JSONL
        jsonl_path = self.output_dir / "natural_language_explanations.jsonl"
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for r in explanation_records:
                f.write(r.to_jsonl() + "\n")
        logger.info("Exported natural-language explanations JSONL to %s", jsonl_path)

        # 3. Export Human-Readable Text Report
        self.report_generator.generate_text_report(explanation_records)

        # 4. Generate Visualizations
        self.report_generator.generate_status_chart(explanation_records)
        self.report_generator.generate_top_shap_chart(global_shap_df)

        # 5. Compile Summary Statistics
        summary = self._compile_summary(explanation_records, traces_df, global_shap_df)
        summary_path = self.output_dir / "explanation_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        logger.info("Exported explanation summary JSON to %s", summary_path)

        return explanation_records, summary

    def _compile_summary(
        self,
        records: List[ExplanationRecord],
        traces_df: pd.DataFrame,
        global_shap_df: pd.DataFrame,
    ) -> Dict[str, Any]:
        """Compute coverage, distributions, and summary statistics."""
        total = len(records)
        succ = sum(1 for r in records if r.explanation_status == STATUS_SUCCESS)
        part = sum(1 for r in records if r.explanation_status == STATUS_PARTIAL)
        skip = sum(1 for r in records if r.explanation_status == STATUS_SKIPPED)
        fail = sum(1 for r in records if r.explanation_status == STATUS_FAILED)

        # Coverage
        pred_cov = sum(1 for r in records if r.prediction.get("score") is not None) / total if total > 0 else 0.0
        policy_cov = sum(1 for r in records if r.policy_decision.get("rule_id")) / total if total > 0 else 0.0
        ctrl_cov = sum(1 for r in records if r.network_action.get("status") in ("SUCCESS", "DRY_RUN")) / total if total > 0 else 0.0

        # Distributions
        traffic_dist = traces_df["traffic_class"].value_counts().to_dict() if "traffic_class" in traces_df else {}
        prio_dist = traces_df["final_priority"].value_counts().to_dict() if "final_priority" in traces_df else {}
        ctrl_dist = traces_df["control_status"].value_counts().to_dict() if "control_status" in traces_df else {}

        top_feats = []
        if not global_shap_df.empty:
            for _, row in global_shap_df.head(5).iterrows():
                top_feats.append({
                    "feature_name": row["feature_name"],
                    "mean_absolute_shap": row["mean_absolute_shap"],
                })

        return {
            "total_traces": total,
            "successful_explanations": succ,
            "partial_explanations": part,
            "skipped_explanations": skip,
            "failed_explanations": fail,
            "prediction_explanation_coverage": round(pred_cov * 100.0, 2),
            "policy_explanation_coverage": round(policy_cov * 100.0, 2),
            "control_explanation_coverage": round(ctrl_cov * 100.0, 2),
            "top_features": top_feats,
            "traffic_class_distribution": traffic_dist,
            "priority_distribution": prio_dist,
            "control_status_distribution": ctrl_dist,
        }


def main():
    parser = argparse.ArgumentParser(description="Phase 17: Natural-Language Explanation CLI")
    parser.add_argument("--trace-id", type=str, help="Explain specific trace ID (e.g. TRC-000047)")
    parser.add_argument("--device", type=str, help="Filter explanations by device ID (e.g. h1)")
    parser.add_argument("--status", type=str, help="Filter by explanation status (SUCCESS, PARTIAL, etc.)")
    parser.add_argument("--limit", type=int, default=10, help="Limit number of explanations displayed")
    parser.add_argument("--run-all", action="store_true", help="Execute complete explanation pipeline and export all files")
    args = parser.parse_args()

    generator = ExplanationGenerator()

    if args.trace_id:
        traces_df = generator.trace_loader.load_traces()
        matches = traces_df[traces_df["trace_id"] == args.trace_id]
        if matches.empty:
            print(f"Error: Trace ID '{args.trace_id}' not found.")
            return
        shap_map = generator.shap_loader.load_explanation_records_map()
        rec = ExplanationBuilder.build_record(matches.iloc[0].to_dict(), shap_record=shap_map.get(args.trace_id))
        print(f"\n================================================================================")
        print(f"DECISION EXPLANATION: {rec.trace_id}")
        print(f"Status: {rec.explanation_status} | Timestamp: {rec.timestamp} | Device: {rec.device_id}")
        print(f"Flow: {rec.flow_id}")
        print(f"--------------------------------------------------------------------------------")
        print(rec.explanation_text)
        print(f"================================================================================\n")
    else:
        records, summary = generator.generate_all_explanations()
        print("\nPhase 17 Explanation Pipeline Completed. Summary:")
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
