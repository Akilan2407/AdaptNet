"""CLI Inference Entrypoint for Congestion Prediction.

Allows predicting future congestion scores from:
1. Command line telemetry arguments (--throughput, --rtt, etc.)
2. A single sample record from an existing dataset (--sample 0)
3. A telemetry CSV file (--input-file data/features/network_features.csv)
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from ml.congestion.config import (
    DEFAULT_METADATA_FILE,
    DEFAULT_MODEL_FILE,
    DEFAULT_SCALER_FILE,
    DEFAULT_TEST_PATH,
)
from ml.congestion.congestion_predictor import CongestionPredictor

logging.basicConfig(level=logging.WARNING, format="%(message)s")


def main() -> None:
    """Parse arguments and execute inference."""
    parser = argparse.ArgumentParser(
        description="Phase 10: Run Congestion Forecast Inference."
    )
    parser.add_argument(
        "--input-file",
        type=Path,
        help="Path to CSV containing telemetry observations",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Sample index from test dataset (e.g. 0)",
    )
    parser.add_argument(
        "--throughput",
        type=float,
        default=None,
        help="Current throughput in Mbps",
    )
    parser.add_argument(
        "--rtt",
        type=float,
        default=None,
        help="Current RTT in ms",
    )
    parser.add_argument(
        "--packet-loss",
        type=float,
        default=None,
        help="Current packet loss percentage",
    )
    parser.add_argument(
        "--connections",
        type=int,
        default=None,
        help="Current active connections count",
    )
    parser.add_argument(
        "--cluster-id",
        type=int,
        default=None,
        help="Device behavioral cluster ID",
    )
    parser.add_argument(
        "--model-file",
        type=Path,
        default=DEFAULT_MODEL_FILE,
        help="Path to trained .keras model",
    )
    parser.add_argument(
        "--scaler-file",
        type=Path,
        default=DEFAULT_SCALER_FILE,
        help="Path to fitted .pkl scaler",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted report",
    )

    args = parser.parse_args()

    predictor = CongestionPredictor(
        model_path=args.model_file,
        scaler_path=args.scaler_file,
        metadata_path=DEFAULT_METADATA_FILE,
    )

    input_data = {}

    if args.input_file:
        if not args.input_file.exists():
            print(f"Error: Input file '{args.input_file}' not found.")
            sys.exit(1)
        df = pd.read_csv(args.input_file)
        if len(df) == 0:
            print("Error: Input file is empty.")
            sys.exit(1)
        result = predictor.predict_batch(df)
        if args.json:
            print(result.to_json(orient="records", indent=2))
        else:
            print("\nBatch Predictions (first 5):")
            cols_to_show = [
                c for c in ["device_id", "throughput_mbps", "rtt_ms", "packet_loss_percent",
                            "predicted_congestion_score", "predicted_congestion_class"]
                if c in result.columns
            ]
            print(result[cols_to_show].head().to_string(index=False))
        return

    elif args.sample is not None:
        if not DEFAULT_TEST_PATH.exists():
            print(f"Error: Test dataset not found at '{DEFAULT_TEST_PATH}'.")
            sys.exit(1)
        test_df = pd.read_csv(DEFAULT_TEST_PATH)
        idx = max(0, min(args.sample, len(test_df) - 1))
        sample_row = test_df.iloc[idx].to_dict()
        input_data = sample_row
        print(f"Using test sample #{idx} (Device: {sample_row.get('device_id', 'unknown')}):")

    else:
        # Construct observation from explicit CLI flags or defaults
        input_data = {
            "throughput_mbps": args.throughput if args.throughput is not None else 10.0,
            "rtt_ms": args.rtt if args.rtt is not None else 2.5,
            "packet_loss_percent": args.packet_loss if args.packet_loss is not None else 0.0,
            "active_connections": args.connections if args.connections is not None else 5,
            "cluster_id": args.cluster_id if args.cluster_id is not None else 0,
            "throughput_std": 0.5,
            "rtt_std": 0.2,
            "packet_loss_std": 0.0,
            "total_flow_count": 10,
            "tcp_flow_ratio": 0.9,
            "udp_flow_ratio": 0.1,
        }

    prediction = predictor.predict_congestion(input_data)

    if args.json:
        print(json.dumps(prediction, indent=2))
    else:
        print("\n" + "=" * 55)
        print("          CONGESTION FORECAST INFERENCE")
        print("=" * 55)
        print(f" Predicted Congestion Score: {prediction['future_congestion_score']:.4f}")
        print(f" Predicted Congestion Class: {prediction['future_congestion_class']}")
        print(f" Model Decision Confidence:  {prediction['confidence'] * 100:.1f}%")
        print(f" Input Sequence Shape:       ({prediction['input_timesteps']} steps, {prediction['features_per_step']} features)")
        print(f" Prediction Timestamp:       {prediction['prediction_timestamp']}")
        print("=" * 55 + "\n")


if __name__ == "__main__":
    main()
