"""Main CLI Pipeline and Orchestrator for Phase 8: User Behavior Profiling.

Orchestrates:
1. Telemetry feature ingestion & feature validation
2. Device-level aggregation from multi-row flow telemetry
3. Documented missing-value imputation (median with zero fallback)
4. Feature standardization via scikit-learn StandardScaler
5. Adaptive K-range evaluation (inertia & silhouette score)
6. Final K-Means model training with fixed random_state=42
7. Factual cluster summary generation & rule-based profile labeling
8. Exporting behavior_profiles.csv, cluster_summary.csv, clustering_evaluation.csv
9. Model, scaler, and feature metadata persistence
10. 2D PCA visualization plot generation
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from ml.profiling.clustering import (
    evaluate_kmeans_range,
    run_dbscan_comparison,
    select_best_k,
    train_kmeans,
)
from ml.profiling.config import (
    CORE_BEHAVIOR_FEATURES,
    DBSCAN_DEFAULT_EPS,
    DBSCAN_DEFAULT_MIN_SAMPLES,
    DEFAULT_FEATURES_JSON_PATH,
    DEFAULT_INPUT_PATH,
    DEFAULT_MAX_K,
    DEFAULT_MIN_K,
    DEFAULT_MODEL_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_OUTPUT_EVALUATION,
    DEFAULT_OUTPUT_PROFILES,
    DEFAULT_OUTPUT_SUMMARY,
    DEFAULT_SCALER_PATH,
    DEFAULT_VISUALIZATION_PATH,
    RANDOM_STATE,
)
from ml.profiling.evaluation import (
    plot_cluster_visualization,
    save_evaluation_results,
    save_model_artifacts,
)
from ml.profiling.preprocessing import (
    aggregate_device_behavior,
    handle_missing_values,
    load_feature_dataset,
    scale_features,
    validate_required_features,
)
from ml.profiling.profile_definitions import (
    assign_descriptive_profile_labels,
    build_factual_descriptions,
    compute_cluster_summary,
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("behavior_profiler")


def run_profiling_pipeline(
    input_path: Path = DEFAULT_INPUT_PATH,
    output_profiles_path: Path = DEFAULT_OUTPUT_PROFILES,
    output_summary_path: Path = DEFAULT_OUTPUT_SUMMARY,
    output_eval_path: Path = DEFAULT_OUTPUT_EVALUATION,
    model_path: Path = DEFAULT_MODEL_PATH,
    scaler_path: Path = DEFAULT_SCALER_PATH,
    features_json_path: Path = DEFAULT_FEATURES_JSON_PATH,
    visualization_path: Path = DEFAULT_VISUALIZATION_PATH,
    min_k: int = DEFAULT_MIN_K,
    max_k: int = DEFAULT_MAX_K,
    algorithm: str = "kmeans",
    eps: float = DBSCAN_DEFAULT_EPS,
    min_samples: int = DBSCAN_DEFAULT_MIN_SAMPLES,
    generate_plot: bool = True,
) -> Dict[str, Any]:
    """Execute the end-to-end User Behavior Profiling pipeline.

    Returns:
        Dictionary containing pipeline results, metrics, and artifact paths.
    """
    logger.info("==================================================")
    logger.info("Starting Phase 8: User Behavior Profiling Pipeline")
    logger.info("Input Dataset : %s", input_path)
    logger.info("Target Output : %s", output_profiles_path)
    logger.info("Algorithm     : %s", algorithm.upper())
    logger.info("==================================================")

    # 1. Load Dataset
    raw_df = load_feature_dataset(input_path)

    # 2. Validate Available Features
    available_features, missing_features = validate_required_features(raw_df)
    logger.info("Validated %d available behavior features", len(available_features))

    # 3. Aggregate Flow Telemetry to Device Level
    device_df = aggregate_device_behavior(raw_df)
    device_ids = device_df["device_id"].tolist()
    n_devices = len(device_df)
    logger.info("Discovered %d distinct LAN device(s): %s", n_devices, device_ids)

    # Filter features that are present in the aggregated device dataframe
    clustering_features = [f for f in available_features if f in device_df.columns]
    logger.info("Clustering feature vector (%d features): %s", len(clustering_features), clustering_features)

    # 4. Handle Missing Values (Median Imputation with 0.0 Fallback)
    clean_device_df, imp_report = handle_missing_values(device_df, clustering_features)

    # 5. Scale Features using StandardScaler
    X_scaled, fitted_scaler, used_features = scale_features(clean_device_df, clustering_features)

    # 6. Evaluate K-Means & Select Optimal K
    eval_df = evaluate_kmeans_range(X_scaled, min_k=min_k, max_k=max_k, random_state=RANDOM_STATE)
    save_evaluation_results(eval_df, output_eval_path)

    selected_k = select_best_k(eval_df, fallback_k=min_k)

    # 7. Train Primary K-Means Model
    kmeans_model, cluster_labels = train_kmeans(X_scaled, n_clusters=selected_k, random_state=RANDOM_STATE)

    # 8. Optional DBSCAN Comparison
    dbscan_res = None
    if algorithm.lower() == "dbscan":
        dbscan_res = run_dbscan_comparison(X_scaled, eps=eps, min_samples=min_samples)
        logger.info("DBSCAN Evaluation: %d clusters, %d noise points", dbscan_res["n_clusters"], dbscan_res["n_noise"])

    # 9. Compute Cluster Summaries and Factual Profile Labels
    summary_df = compute_cluster_summary(clean_device_df, cluster_labels, clustering_features)
    profile_labels_map = assign_descriptive_profile_labels(summary_df)
    factual_descriptions = build_factual_descriptions(summary_df)

    # Add profile_label and description to summary DataFrame
    summary_df["profile_label"] = summary_df["cluster_id"].map(profile_labels_map)
    summary_df["description"] = summary_df["cluster_id"].map(factual_descriptions)

    # Export Cluster Summary CSV
    output_summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(output_summary_path, index=False)
    logger.info("Exported cluster summary to %s", output_summary_path)

    # 10. Assemble Behavior Profiles DataFrame
    profiles_df = clean_device_df.copy()
    profiles_df["cluster_id"] = cluster_labels
    profiles_df["profile_label"] = profiles_df["cluster_id"].map(profile_labels_map)

    # Re-order columns for clarity
    front_cols = ["device_id", "cluster_id", "profile_label"]
    other_cols = [c for c in profiles_df.columns if c not in front_cols]
    profiles_df = profiles_df[front_cols + other_cols]

    output_profiles_path.parent.mkdir(parents=True, exist_ok=True)
    profiles_df.to_csv(output_profiles_path, index=False)
    logger.info("Exported behavior profiles to %s", output_profiles_path)

    # 11. Save Model, Scaler, and Feature Metadata
    saved_artifacts = save_model_artifacts(
        model=kmeans_model,
        scaler=fitted_scaler,
        feature_list=used_features,
        model_path=model_path,
        scaler_path=scaler_path,
        features_json_path=features_json_path,
    )

    # 12. Generate 2D PCA Visualization
    vis_path = None
    if generate_plot:
        vis_path = plot_cluster_visualization(
            X_scaled=X_scaled,
            cluster_labels=cluster_labels,
            device_ids=device_ids,
            output_path=visualization_path,
            title_suffix=f"K-Means (k={selected_k})",
        )

    # 13. Print Comprehensive Execution Report
    _print_execution_summary(
        n_devices=n_devices,
        device_ids=device_ids,
        features_used=used_features,
        eval_df=eval_df,
        selected_k=selected_k,
        summary_df=summary_df,
        profiles_df=profiles_df,
        dbscan_res=dbscan_res,
        artifacts={
            "profiles_csv": output_profiles_path,
            "summary_csv": output_summary_path,
            "eval_csv": output_eval_path,
            "model_pkl": model_path,
            "scaler_pkl": scaler_path,
            "features_json": features_json_path,
            "vis_png": vis_path,
        },
    )

    return {
        "n_devices": n_devices,
        "device_ids": device_ids,
        "features_used": used_features,
        "selected_k": selected_k,
        "eval_df": eval_df,
        "summary_df": summary_df,
        "profiles_df": profiles_df,
        "dbscan_res": dbscan_res,
        "artifacts": saved_artifacts,
        "visualization_path": vis_path,
    }


def _print_execution_summary(
    n_devices: int,
    device_ids: List[str],
    features_used: List[str],
    eval_df: pd.DataFrame,
    selected_k: int,
    summary_df: pd.DataFrame,
    profiles_df: pd.DataFrame,
    dbscan_res: Optional[Dict[str, Any]],
    artifacts: Dict[str, Any],
) -> None:
    """Print structured, human-readable execution summary."""
    print("\n" + "=" * 65)
    print("  PHASE 8: USER BEHAVIOR PROFILING EXECUTION REPORT")
    print("=" * 65)
    print(f"Total Network Devices : {n_devices} ({', '.join(device_ids)})")
    print(f"Features Evaluated    : {len(features_used)}")
    for f in features_used:
        print(f"  - {f}")

    print("\n--- Clustering Evaluation (K-Means) ---")
    print(f"{'K':<5} {'Inertia':<12} {'Silhouette Score':<18}")
    print("-" * 35)
    for _, row in eval_df.iterrows():
        sil = f"{row['silhouette_score']:.4f}" if pd.notna(row["silhouette_score"]) else "N/A"
        print(f"{int(row['k']):<5} {row['inertia']:<12.4f} {sil:<18}")

    print(f"\nOptimal K Selected : {selected_k}")

    print("\n--- Cluster Assignments & Profiles ---")
    for _, row in profiles_df.iterrows():
        dev = row["device_id"]
        cid = int(row["cluster_id"])
        lbl = row["profile_label"]
        tp = row.get("mean_throughput_mbps", 0.0)
        flows = row.get("total_flow_count", 0)
        tcp_r = row.get("tcp_flow_ratio", 1.0)
        print(f"Device {dev:<4} -> Cluster {cid} [{lbl}] | TP: {tp:.2f} Mbps | Flows: {flows} | TCP Ratio: {tcp_r:.2f}")

    print("\n--- Cluster Summary Statistics ---")
    for _, row in summary_df.iterrows():
        cid = int(row["cluster_id"])
        cnt = int(row["device_count"])
        lbl = row["profile_label"]
        desc = row.get("description", "")
        print(f"Cluster {cid} [{lbl}] ({cnt} device(s)):")
        print(f"  {desc}")

    if dbscan_res and dbscan_res.get("status") == "completed":
        print("\n--- Optional DBSCAN Comparison ---")
        print(f"DBSCAN Clusters: {dbscan_res['n_clusters']}, Noise Points: {dbscan_res['n_noise']}")
        print(f"Parameters: eps={dbscan_res['eps']}, min_samples={dbscan_res['min_samples']}")

    print("\n--- Generated Artifacts ---")
    for name, path in artifacts.items():
        if path:
            print(f"  {name:<15}: {path}")
    print("=" * 65 + "\n")


def build_arg_parser() -> argparse.ArgumentParser:
    """Build command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Phase 8: User Behavior Profiling Module using Unsupervised K-Means.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Path to Phase 7 network_features.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PROFILES,
        help="Path to output behavior_profiles.csv",
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=DEFAULT_OUTPUT_SUMMARY,
        help="Path to output cluster_summary.csv",
    )
    parser.add_argument(
        "--eval-output",
        type=Path,
        default=DEFAULT_OUTPUT_EVALUATION,
        help="Path to output clustering_evaluation.csv",
    )
    parser.add_argument(
        "--min-k",
        type=int,
        default=DEFAULT_MIN_K,
        help="Minimum clusters to evaluate",
    )
    parser.add_argument(
        "--max-k",
        type=int,
        default=DEFAULT_MAX_K,
        help="Maximum clusters to evaluate",
    )
    parser.add_argument(
        "--algorithm",
        type=str,
        choices=["kmeans", "dbscan"],
        default="kmeans",
        help="Primary clustering algorithm to execute (K-Means is main pipeline; DBSCAN is optional comparison)",
    )
    parser.add_argument(
        "--eps",
        type=float,
        default=DBSCAN_DEFAULT_EPS,
        help="DBSCAN epsilon neighborhood radius",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=DBSCAN_DEFAULT_MIN_SAMPLES,
        help="DBSCAN min_samples threshold",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Disable PCA 2D visualization generation",
    )
    return parser


def main():
    """CLI entry point."""
    parser = build_arg_parser()
    args = parser.parse_args()

    try:
        run_profiling_pipeline(
            input_path=args.input,
            output_profiles_path=args.output,
            output_summary_path=args.summary_output,
            output_eval_path=args.eval_output,
            min_k=args.min_k,
            max_k=args.max_k,
            algorithm=args.algorithm,
            eps=args.eps,
            min_samples=args.min_samples,
            generate_plot=not args.no_plot,
        )
    except Exception as e:
        logger.exception("Profiling pipeline failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
