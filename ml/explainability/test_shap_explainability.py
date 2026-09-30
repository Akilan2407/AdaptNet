"""Comprehensive Unit Test Suite for Phase 16: SHAP Explainability Module.

Tests 15 critical requirements:
1. Phase 10 GRU model loading
2. Phase 10 StandardScaler loading and reuse
3. Feature mapping alignment (11 recurrent input features)
4. Prediction consistency validation
5. SHAP value generation for valid sequences
6. SHAP output dimension and structure
7. Time-series temporal aggregation modes (mean_absolute, mean, sum, last_timestep)
8. Signed contribution and direction semantics
9. Additivity verification
10. Incomplete trace graceful handling (STATUS_SKIPPED)
11. Feature ranking determinism
12. Target leakage prevention
13. Reproducibility across repeated explanations
14. CSV and JSONL export integrity
15. End-to-end integration and Phase 17 contract generation
"""

import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.explainability.config import (
    ADDITIVITY_TOLERANCE,
    AGG_LAST_TIMESTEP,
    AGG_MEAN,
    AGG_MEAN_ABSOLUTE,
    AGG_SUM,
    CONSISTENCY_TOLERANCE,
    DIRECTION_DECREASED,
    DIRECTION_INCREASED,
    DIRECTION_NEUTRAL,
    FEATURES_PER_STEP,
    RECURRENT_FEATURE_NAMES,
    SCALER_FEATURE_COLUMNS,
    STATUS_SKIPPED,
    STATUS_SUCCESS,
    TIMESTEPS,
)
from ml.explainability.explanation_validator import ExplanationValidator
from ml.explainability.feature_mapper import FeatureMapper
from ml.explainability.global_explanation import GlobalExplainer
from ml.explainability.local_explanation import LocalExplainer
from ml.explainability.model_loader import ModelLoader
from ml.explainability.shap_explainer import SHAPExplainerWrapper
from ml.explainability.trace_explainer import TraceExplainerPipeline


@pytest.fixture(scope="module")
def model_loader():
    return ModelLoader()


@pytest.fixture(scope="module")
def shap_explainer(model_loader):
    return SHAPExplainerWrapper(model_loader=model_loader)


# 1. Model loading
def test_model_loading(model_loader):
    assert model_loader.model is not None
    assert model_loader.model.name == "gru_congestion_predictor"
    assert model_loader.model.input_shape == (None, TIMESTEPS, FEATURES_PER_STEP)


# 2. Scaler loading and reuse
def test_scaler_loading(model_loader):
    assert model_loader.scaler is not None
    assert hasattr(model_loader.scaler, "transform")
    assert len(model_loader.feature_columns) == len(SCALER_FEATURE_COLUMNS)


# 3. Feature mapping alignment
def test_feature_mapping_alignment():
    mapper = FeatureMapper()
    assert len(mapper.feature_names) == FEATURES_PER_STEP
    assert mapper.get_feature_name(0) == "cluster_id"
    assert mapper.get_feature_name(1) == "throughput_mbps"
    assert mapper.get_feature_name(2) == "rtt_ms"
    assert mapper.get_feature_name(3) == "packet_loss_percent"
    assert mapper.get_feature_name(4) == "active_connections"
    assert mapper.get_feature_index("total_flow_count") == 8


# 4. Prediction consistency validation
def test_prediction_consistency(model_loader):
    # Test valid sequence from test_dataset
    bg = model_loader.prepare_background_dataset(sample_size=1)
    pred_arr = model_loader.model.predict(bg, verbose=0).flatten()
    pred_score = float(pred_arr[0])

    assert 0.0 <= pred_score <= 1.0
    errs = ExplanationValidator.validate_explanation(
        {
            "feature_contributions": [{"feature_name": f} for f in RECURRENT_FEATURE_NAMES],
            "predicted_congestion_score": pred_score,
            "base_value": 0.35,
            "shap_sum": pred_score - 0.35,
        },
        expected_score=pred_score,
    )
    assert len(errs) == 0


# 5. SHAP value generation for valid sequences
def test_shap_generation(shap_explainer):
    sample = np.zeros((1, TIMESTEPS, FEATURES_PER_STEP), dtype=np.float32)
    res = shap_explainer.explain_sample(sample)

    assert "predicted_congestion_score" in res
    assert "base_value" in res
    assert "feature_contributions" in res
    assert len(res["feature_contributions"]) == FEATURES_PER_STEP
    assert res["explainer_type"] in ("GradientExplainer", "KernelExplainer")


# 6. SHAP output dimensions and structure
def test_shap_output_structure(shap_explainer):
    sample = np.zeros((1, TIMESTEPS, FEATURES_PER_STEP), dtype=np.float32)
    res = shap_explainer.explain_sample(sample)

    contribs = res["feature_contributions"]
    for item in contribs:
        assert "feature_name" in item
        assert "shap_value" in item
        assert "absolute_shap_value" in item
        assert "direction" in item
        assert "feature_rank" in item
        assert item["direction"] in (DIRECTION_INCREASED, DIRECTION_DECREASED, DIRECTION_NEUTRAL)


# 7. Temporal aggregation modes
def test_temporal_aggregation_modes():
    # Synthetic SHAP tensor: 2 timesteps, 11 features
    tensor = np.array([
        [-0.10, 0.20] + [0.0] * 9,  # Timestep 0
        [0.30, -0.40] + [0.0] * 9,  # Timestep 1
    ], dtype=np.float32)

    # Mean absolute: (| -0.10 | + | 0.30 |)/2 = 0.20
    s_abs, mag = FeatureMapper.aggregate_temporal_shap(tensor, mode=AGG_MEAN_ABSOLUTE)
    assert mag[0] == pytest.approx(0.20, abs=1e-5)
    assert s_abs[0] == pytest.approx(0.10, abs=1e-5)  # (-0.10 + 0.30)/2 = 0.10

    # Mean signed
    s_mean, _ = FeatureMapper.aggregate_temporal_shap(tensor, mode=AGG_MEAN)
    assert s_mean[0] == pytest.approx(0.10, abs=1e-5)

    # Sum: -0.10 + 0.30 = 0.20
    s_sum, mag_sum = FeatureMapper.aggregate_temporal_shap(tensor, mode=AGG_SUM)
    assert s_sum[0] == pytest.approx(0.20, abs=1e-5)
    assert mag_sum[0] == pytest.approx(0.40, abs=1e-5)

    # Last timestep: 0.30
    s_last, _ = FeatureMapper.aggregate_temporal_shap(tensor, mode=AGG_LAST_TIMESTEP)
    assert s_last[0] == pytest.approx(0.30, abs=1e-5)


# 8. Signed contribution and direction semantics
def test_direction_determination():
    assert FeatureMapper.determine_direction(0.15) == DIRECTION_INCREASED
    assert FeatureMapper.determine_direction(-0.08) == DIRECTION_DECREASED
    assert FeatureMapper.determine_direction(0.0) == DIRECTION_NEUTRAL


# 9. Additivity verification in validator
def test_additivity_validation():
    # Valid additivity
    valid_res = {
        "feature_contributions": [{"feature_name": f} for f in RECURRENT_FEATURE_NAMES],
        "predicted_congestion_score": 0.80,
        "base_value": 0.40,
        "shap_sum": 0.40,
        "explainer_type": "KernelExplainer",
    }
    assert len(ExplanationValidator.validate_explanation(valid_res)) == 0

    # Additivity violation
    invalid_res = {
        "feature_contributions": [{"feature_name": f} for f in RECURRENT_FEATURE_NAMES],
        "predicted_congestion_score": 0.80,
        "base_value": 0.40,
        "shap_sum": 0.05,  # 0.45 vs 0.80 -> diff 0.35 > 0.25 tolerance
        "explainer_type": "KernelExplainer",
    }
    errs = ExplanationValidator.validate_explanation(invalid_res)
    assert any("Additivity violation" in e for e in errs)


# 10. Incomplete trace handling
def test_incomplete_trace_handling(shap_explainer):
    local_explainer = LocalExplainer(shap_explainer=shap_explainer)
    incomplete_trace = {
        "trace_id": "TRC-000001",
        "predicted_congestion_score": None,  # Missing prediction
        "trace_completeness": "PARTIAL",
    }
    res = local_explainer.explain_trace(incomplete_trace)
    assert res["explanation_status"] == STATUS_SKIPPED
    assert "Incomplete trace" in res["explanation_error"]
    assert len(res["features"]) == 0


# 11. Feature ranking determinism
def test_feature_ranking_determinism(shap_explainer):
    sample = np.zeros((1, TIMESTEPS, FEATURES_PER_STEP), dtype=np.float32)
    res = shap_explainer.explain_sample(sample)
    contribs = res["feature_contributions"]

    # Invariants: ranks 1 to 11, strictly descending magnitudes
    ranks = [c["feature_rank"] for c in contribs]
    assert ranks == list(range(1, FEATURES_PER_STEP + 1))
    for i in range(len(contribs) - 1):
        assert contribs[i]["absolute_shap_value"] >= contribs[i + 1]["absolute_shap_value"]


# 12. Target leakage prevention
def test_target_leakage_prevention():
    safe_keys = ["throughput_mbps", "rtt_ms", "packet_loss_percent", "active_connections"]
    assert len(ExplanationValidator.validate_no_target_leakage(safe_keys)) == 0

    leaked_keys = ["throughput_mbps", "future_congestion_score", "future_congestion_class"]
    errs = ExplanationValidator.validate_no_target_leakage(leaked_keys)
    assert len(errs) == 2
    assert any("future_congestion_score" in e for e in errs)


# 13. Reproducibility across repeated explanations
def test_reproducibility(shap_explainer):
    sample = np.zeros((1, TIMESTEPS, FEATURES_PER_STEP), dtype=np.float32)
    res1 = shap_explainer.explain_sample(sample)
    res2 = shap_explainer.explain_sample(sample)

    assert res1["predicted_congestion_score"] == pytest.approx(res2["predicted_congestion_score"], abs=1e-4)
    for c1, c2 in zip(res1["feature_contributions"], res2["feature_contributions"]):
        assert c1["feature_name"] == c2["feature_name"]
        assert c1["shap_value"] == pytest.approx(c2["shap_value"], abs=0.01)


# 14. CSV and JSONL export integrity
def test_export_integrity(tmp_path, shap_explainer):
    local_explainer = LocalExplainer(
        shap_explainer=shap_explainer,
        output_csv=tmp_path / "local.csv",
        output_jsonl=tmp_path / "local.jsonl",
    )
    csv_df, jsonl_recs = local_explainer.explain_all_traces()

    assert (tmp_path / "local.csv").exists()
    assert (tmp_path / "local.jsonl").exists()
    assert len(jsonl_recs) == 53
    # Check JSONL parsing
    with open(tmp_path / "local.jsonl") as f:
        first_line = json.loads(f.readline())
        assert "trace_id" in first_line
        assert "explanation_status" in first_line


# 15. End-to-end integration and Phase 17 contract generation
def test_end_to_end_phase17_contract():
    pipeline = TraceExplainerPipeline()
    summary = pipeline.run_full_pipeline(max_plots=5)

    assert summary["number_of_samples"] == 53
    assert summary["number_of_successful_explanations"] >= 5
    assert summary["number_of_failed_explanations"] == 0
    assert summary["feature_count"] == 11
    assert summary["additivity_validation"]["passed"]
    assert summary["prediction_consistency_validation"]["passed"]

    # Verify Phase 17 structured contract
    contract_path = pipeline.output_dir / "explanation_records.jsonl"
    assert contract_path.exists()
    with open(contract_path) as f:
        records = [json.loads(line) for line in f]
    assert len(records) == 53

    complete_records = [r for r in records if r["explanation_status"] == STATUS_SUCCESS]
    assert len(complete_records) >= 5
    for cr in complete_records:
        assert "trace_id" in cr
        assert "prediction" in cr
        assert "top_contributors" in cr
        assert "policy" in cr
        assert "network_control" in cr
