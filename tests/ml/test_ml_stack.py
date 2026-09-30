"""
Verification test for ML environment (scikit-learn, TensorFlow GRU, SHAP).
"""
import os
os.environ["MPLBACKEND"] = "Agg"
import numpy as np
import pytest


def test_sklearn_clustering():
    from sklearn.cluster import KMeans, DBSCAN

    X = np.array([[1.0, 2.0], [1.2, 1.8], [8.0, 8.0], [8.5, 8.2]], dtype=np.float32)
    kmeans = KMeans(n_clusters=2, random_state=42, n_init=5).fit(X)
    assert len(kmeans.labels_) == 4
    dbscan = DBSCAN(eps=1.0, min_samples=2).fit(X)
    assert len(dbscan.labels_) == 4


def test_tensorflow_gru_instantiation():
    import tensorflow as tf
    from tensorflow.keras import layers, models

    # Verify GRU model building for network congestion prediction
    model = models.Sequential([
        layers.Input(shape=(10, 5)), # 10 time steps, 5 telemetry features
        layers.GRU(16, return_sequences=False),
        layers.Dense(1, activation="sigmoid")
    ])
    model.compile(optimizer="adam", loss="binary_crossentropy")
    dummy_input = np.random.rand(2, 10, 5).astype(np.float32)
    prediction = model(dummy_input)
    assert prediction.shape == (2, 1)


def test_shap_import():
    import importlib.util

    spec = importlib.util.find_spec("shap")
    assert spec is not None, "shap package must be installed in virtual environment"


