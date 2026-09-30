"""Evaluation, Artifact Persistence, and PCA Visualization for Phase 8 Profiling.

Handles:
- Exporting clustering evaluation metrics (inertia and silhouette score) to CSV
- Saving trained KMeans model, StandardScaler, and feature list
- Generating 2D PCA scatter plot visualization of device clusters

CRITICAL DESIGN RULE:
PCA dimensionality reduction is used EXCLUSIVELY for 2D visualization.
It is never used to transform the feature space fed to K-Means.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

# Use Agg backend for headless rendering
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

logger = logging.getLogger("ml.profiling.evaluation")


def save_evaluation_results(
    eval_df: pd.DataFrame,
    output_path: Union[str, Path],
) -> Path:
    """Save K-Means evaluation table (k, inertia, silhouette_score) to CSV.

    Args:
        eval_df: Evaluation DataFrame
        output_path: Target CSV file path

    Returns:
        Path to written CSV
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Format NaN as N/A in the output CSV if desired, or standard empty
    export_df = eval_df.copy()
    export_df.to_csv(path, index=False)
    logger.info("Saved clustering evaluation table to %s", path)
    return path


def save_model_artifacts(
    model: Any,
    scaler: Any,
    feature_list: List[str],
    model_path: Union[str, Path],
    scaler_path: Union[str, Path],
    features_json_path: Union[str, Path],
) -> Dict[str, Path]:
    """Persist the trained clustering model, fitted scaler, and feature metadata.

    Args:
        model: Trained KMeans model object
        scaler: Fitted StandardScaler object
        feature_list: List of feature names used during training
        model_path: Destination for clustering_model.pkl
        scaler_path: Destination for scaler.pkl
        features_json_path: Destination for clustering_features.json

    Returns:
        Dictionary of saved file paths.
    """
    m_path = Path(model_path)
    s_path = Path(scaler_path)
    f_path = Path(features_json_path)

    m_path.parent.mkdir(parents=True, exist_ok=True)
    s_path.parent.mkdir(parents=True, exist_ok=True)
    f_path.parent.mkdir(parents=True, exist_ok=True)

    # Save model and scaler via joblib
    joblib.dump(model, m_path)
    joblib.dump(scaler, s_path)

    # Save features metadata via json
    metadata = {
        "num_features": len(feature_list),
        "features": feature_list,
        "algorithm": model.__class__.__name__,
        "n_clusters": getattr(model, "n_clusters", None),
        "random_state": getattr(model, "random_state", None),
    }
    with open(f_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info("Successfully persisted model artifacts to %s, %s, %s", m_path, s_path, f_path)
    return {
        "model": m_path,
        "scaler": s_path,
        "features": f_path,
    }


def plot_cluster_visualization(
    X_scaled: np.ndarray,
    cluster_labels: np.ndarray,
    device_ids: List[str],
    output_path: Union[str, Path],
    title_suffix: str = "K-Means Clustering",
) -> Optional[Path]:
    """Generate and save a 2D PCA cluster visualization plot.

    Note: PCA is applied ONLY for 2D visualization of the multi-dimensional
    scaled feature space. Axes represent orthogonal variance components, not
    direct physical network metrics.

    Args:
        X_scaled: Scaled feature matrix (N x M)
        cluster_labels: Cluster assignment per sample
        device_ids: Device identifier labels (e.g. h1, h2, ...)
        output_path: Path to save PNG figure
        title_suffix: Suffix for the plot title

    Returns:
        Path to generated PNG plot, or None if skipped due to sample size.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    n_samples, n_features = X_scaled.shape

    if n_samples < 2 or n_features < 2:
        logger.warning(
            "Insufficient samples (%d) or features (%d) for 2D PCA visualization. Skipping plot.",
            n_samples,
            n_features,
        )
        return None

    # Compute 2-component PCA projection
    n_components = min(2, n_samples, n_features)
    pca = PCA(n_components=n_components, random_state=42)
    X_pca = pca.fit_transform(X_scaled)

    if n_components == 1:
        # Pad with zeros for 1D case
        X_pca = np.column_stack([X_pca, np.zeros(n_samples)])
        var_explained = [pca.explained_variance_ratio_[0], 0.0]
    else:
        var_explained = pca.explained_variance_ratio_

    # Create figure with high quality
    plt.figure(figsize=(9, 6), dpi=150)
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    unique_clusters = np.unique(cluster_labels)
    # Distinct color palette
    colors = plt.get_cmap("tab10")

    for idx, cid in enumerate(unique_clusters):
        mask = cluster_labels == cid
        label_text = f"Cluster {cid}" if cid != -1 else "Noise (DBSCAN -1)"
        plt.scatter(
            X_pca[mask, 0],
            X_pca[mask, 1],
            s=120,
            color=colors(idx),
            label=label_text,
            edgecolors="black",
            linewidth=1.2,
            alpha=0.85,
            zorder=3,
        )

    # Annotate device IDs next to each data point
    for i, dev in enumerate(device_ids):
        plt.annotate(
            dev,
            (X_pca[i, 0], X_pca[i, 1]),
            textcoords="offset points",
            xytext=(7, 7),
            ha="left",
            fontsize=10,
            fontweight="bold",
            color="#222222",
            zorder=4,
        )

    plt.xlabel(f"PCA Component 1 ({var_explained[0]*100:.1f}% Variance)", fontsize=11, fontweight="semibold")
    plt.ylabel(f"PCA Component 2 ({var_explained[1]*100:.1f}% Variance)", fontsize=11, fontweight="semibold")
    plt.title(
        f"Device Behavior Profiles - {title_suffix}\n(2D PCA Projection for Visualization Only)",
        fontsize=12,
        fontweight="bold",
        pad=12,
    )
    plt.legend(frameon=True, loc="best", fontsize=10)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()

    plt.savefig(path, format="png", dpi=150)
    plt.close()

    logger.info("Saved PCA cluster visualization to %s", path)
    return path
