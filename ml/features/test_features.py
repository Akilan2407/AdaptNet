"""Unit tests for Phase 7 Feature Extraction Module.

Uses deterministic synthetic test datasets to verify each extraction step:
- CSV loading and schema validation
- Flow, time, aggregation, and mix features
- RTT missing value preservation
- Quality checks and CLI compatibility
"""

import io
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from ml.features.config import REQUIRED_COLUMNS
from ml.features.feature_extractor import (
    extract_all_features,
    extract_device_aggregations,
    extract_flow_features,
    extract_rolling_features,
    extract_time_features,
    extract_traffic_mix_features,
    validate_features,
)
from ml.features.preprocessing import (
    clean_network_data,
    load_network_data,
    prepare_scaled_features,
)


class TestFeatureExtraction(unittest.TestCase):
    """Deterministic test suite for feature extraction."""

    def setUp(self):
        """Create deterministic in-memory test data."""
        self.sample_csv_content = (
            "timestamp,device_id,src_ip,dst_ip,src_port,dst_port,protocol,throughput,rtt,packet_loss,active_connections\n"
            "2026-09-12 08:30:00,h1,192.168.1.10,192.168.1.11,5001,5201,TCP,15.5,1.25,0.0,3\n"
            "2026-09-12 08:31:00,h1,192.168.1.10,192.168.1.12,5002,5201,UDP,25.0,N/A,0.5,1\n"
            "2026-09-12 14:15:00,h2,192.168.1.11,192.168.1.13,5003,5201,TCP,8.0,3.50,1.0,2\n"
            "2026-09-12 21:45:00,h2,192.168.1.11,192.168.1.14,5004,5201,TCP,12.0,2.50,0.0,4\n"
        )
        self.temp_csv = tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".csv")
        self.temp_csv.write(self.sample_csv_content)
        self.temp_csv.flush()
        self.temp_csv.close()

    def tearDown(self):
        """Clean up temporary test file."""
        Path(self.temp_csv.name).unlink(missing_ok=True)

    def test_csv_loading_and_record_count(self):
        """Test 1: CSV loading and correct row count."""
        df = load_network_data(self.temp_csv.name)
        self.assertEqual(len(df), 4)
        for col in REQUIRED_COLUMNS:
            self.assertIn(col, df.columns)

    def test_missing_column_detection(self):
        """Test 2: Ensure error is raised if a required column is missing."""
        bad_csv = tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".csv")
        bad_csv.write("timestamp,device_id,throughput\n2026-09-12 08:00:00,h1,10.0\n")
        bad_csv.flush()
        bad_csv.close()

        with self.assertRaises(ValueError) as ctx:
            load_network_data(bad_csv.name)
        self.assertIn("missing", str(ctx.exception).lower())
        Path(bad_csv.name).unlink(missing_ok=True)

    def test_timestamp_parsing_and_time_features(self):
        """Test 3: Verify timestamp parsing and derived diurnal time features."""
        df = load_network_data(self.temp_csv.name)
        df_time = extract_time_features(df)

        self.assertEqual(df_time.iloc[0]["hour"], 8)
        self.assertEqual(df_time.iloc[0]["minute"], 30)
        self.assertEqual(df_time.iloc[0]["time_of_day"], "morning")  # 08:30 -> morning
        self.assertEqual(df_time.iloc[2]["time_of_day"], "afternoon")  # 14:15 -> afternoon
        self.assertEqual(df_time.iloc[3]["time_of_day"], "evening")  # 21:45 -> evening
        self.assertEqual(df_time.iloc[0]["day_of_week"], 5)  # 2026-09-12 is Saturday
        self.assertEqual(df_time.iloc[0]["is_weekend"], 1)

    def test_numeric_conversion_and_rtt_nan_preservation(self):
        """Test 4: Verify numeric type conversions and NaN preservation for UDP RTT."""
        df = load_network_data(self.temp_csv.name)
        # Record 1 (UDP) has RTT = N/A
        self.assertTrue(np.isnan(df.iloc[1]["rtt"]))
        self.assertEqual(df.iloc[0]["rtt"], 1.25)
        self.assertEqual(df.iloc[0]["throughput"], 15.5)

    def test_protocol_numeric_encoding(self):
        """Test 5: Verify TCP = 1 and UDP = 0 encoding."""
        df = load_network_data(self.temp_csv.name)
        df_flow = extract_flow_features(df)

        self.assertEqual(df_flow.iloc[0]["protocol_numeric"], 1)  # TCP
        self.assertEqual(df_flow.iloc[1]["protocol_numeric"], 0)  # UDP

    def test_flow_id_generation(self):
        """Test 6: Verify deterministic flow_id generation."""
        df = load_network_data(self.temp_csv.name)
        df_flow = extract_flow_features(df)

        expected_flow_0 = "h1_192.168.1.10:5001->192.168.1.11:5201_TCP"
        self.assertEqual(df_flow.iloc[0]["flow_id"], expected_flow_0)

    def test_device_aggregation_and_traffic_mix(self):
        """Test 7: Verify device-level aggregations and TCP/UDP flow ratios."""
        df = load_network_data(self.temp_csv.name)
        df_flow = extract_flow_features(df)
        df_time = extract_time_features(df_flow)
        df_agg = extract_device_aggregations(df_time)
        df_mix = extract_traffic_mix_features(df_agg)

        # For device h1: 2 records (1 TCP @ 15.5 Mbps, 1 UDP @ 25.0 Mbps)
        h1_records = df_mix[df_mix["device_id"] == "h1"]
        self.assertEqual(len(h1_records), 2)
        self.assertAlmostEqual(h1_records.iloc[0]["mean_throughput_mbps"], 20.25)
        self.assertEqual(h1_records.iloc[0]["max_throughput_mbps"], 25.0)
        self.assertEqual(h1_records.iloc[0]["min_throughput_mbps"], 15.5)
        self.assertEqual(h1_records.iloc[0]["total_flow_count"], 2)
        self.assertEqual(h1_records.iloc[0]["tcp_flow_count"], 1)
        self.assertEqual(h1_records.iloc[0]["udp_flow_count"], 1)
        self.assertAlmostEqual(h1_records.iloc[0]["tcp_flow_ratio"], 0.5)
        self.assertAlmostEqual(h1_records.iloc[0]["udp_flow_ratio"], 0.5)

        # For device h2: 2 records (2 TCP: 8.0 and 12.0 Mbps)
        h2_records = df_mix[df_mix["device_id"] == "h2"]
        self.assertAlmostEqual(h2_records.iloc[0]["mean_throughput_mbps"], 10.0)
        self.assertAlmostEqual(h2_records.iloc[0]["tcp_flow_ratio"], 1.0)
        self.assertAlmostEqual(h2_records.iloc[0]["udp_flow_ratio"], 0.0)

    def test_rolling_features(self):
        """Test 8: Verify rolling time-window features."""
        df = load_network_data(self.temp_csv.name)
        df_all = extract_all_features(df, window_seconds=300)

        self.assertIn("rolling_mean_throughput_5m", df_all.columns)
        self.assertIn("rolling_mean_rtt_5m", df_all.columns)
        self.assertIn("rolling_mean_packet_loss_5m", df_all.columns)

        # h1 record 0 (08:30) has throughput 15.5
        h1_0 = df_all.iloc[0]
        self.assertEqual(h1_0["rolling_mean_throughput_5m"], 15.5)

        # h1 record 1 (08:31, within 300s window) has rolling mean (15.5 + 25.0) / 2 = 20.25
        h1_1 = df_all.iloc[1]
        self.assertAlmostEqual(h1_1["rolling_mean_throughput_5m"], 20.25)

    def test_feature_quality_validation(self):
        """Test 9: Quality validation catches bad records."""
        df = load_network_data(self.temp_csv.name)
        df_all = extract_all_features(df)
        is_valid, issues = validate_features(df_all)
        self.assertTrue(is_valid)
        self.assertEqual(len(issues), 0)

        # Introduce intentional bad record
        bad_df = df_all.copy()
        bad_df.loc[0, "throughput_mbps"] = -5.0
        is_valid_bad, issues_bad = validate_features(bad_df)
        self.assertFalse(is_valid_bad)
        self.assertTrue(any("negative throughput" in iss for iss in issues_bad))

    def test_scaled_features_utility(self):
        """Test 10: Verify prepare_scaled_features creates normalized columns without mutating originals."""
        df = load_network_data(self.temp_csv.name)
        df_all = extract_all_features(df)
        scaled_df = prepare_scaled_features(
            df_all, feature_cols=["throughput_mbps", "active_connections"], scaler_type="standard"
        )
        self.assertIn("throughput_mbps_scaled", scaled_df.columns)
        self.assertIn("active_connections_scaled", scaled_df.columns)
        # Original column unmodified
        self.assertEqual(df_all["throughput_mbps"].iloc[0], 15.5)


if __name__ == "__main__":
    unittest.main()
