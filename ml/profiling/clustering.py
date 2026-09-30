"""Clustering Engine for Phase 8: User Behavior Profiling.

Implements:
- K-Means as the primary clustering algorithm
- Adaptive K-range evaluation (inertia and silhouette score)
- Small dataset resilience (detects sample size limitations without crashing)
- Best K selection based on empirical evaluation
- Cluster assignment mapping
- Optional comparative DBSCAN clustering
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import silhouette_score

from ml.profiling.config import (
    DBSCAN_DEFAULT_EPS,
    DBSCAN_DEFAULT_MIN_SAMPLES,
    DEFAULT_MAX_K,
    DEFAULT_MIN_K,
    KMEANS_N_INIT,
    RANDOM_STATE,
)

logger = logging.getLogger("ml.profiling.clustering")


def evaluate_kmeans_range(
    X: np.ndarray,
    min_k: int = DEFAULT_MIN_K,
    max_k: int = DEFAULT_MAX_K,
    random_state: int = RANDOM_STATE,
) -> pd.DataFrame:
    """Evaluate K-Means across a candidate range of K values.

    Calculates inertia (within-cluster sum of squares) and silhouette score.
    Safely adapts to small LAN sample sizes (N < max_k) without crashing.

    Args:
        X: Scaled feature matrix (N x M)
        min_k: Minimum clusters to test (must be >= 2)
        max_k: Maximum clusters to test
        random_state: Random state for deterministic reproduction

    Returns:
        DataFrame with columns: ['k', 'inertia', 'silhouette_score']
    """
    n_samples = X.shape[0]

    # Small dataset detection & boundary adjustment
    # In K-Means, we require 1 < K < n_samples for meaningful silhouette score
    if n_samples < 2:
        logger.warning(
            "Dataset has %d device(s). Clustering requires at least 2 devices.",
            n_samples,
        )
        return pd.DataFrame([{"k": 1, "inertia": 0.0, "silhouette_score": np.nan}])

    n_distinct = len(np.unique(X, axis=0))
    effective_min_k = max(2, min_k)
    effective_max_k = min(max_k, n_samples - 1, n_distinct)

    if effective_max_k < effective_min_k:
        logger.warning(
            "Sample size (%d devices, %d distinct feature points) is too small to evaluate range [%d, %d]. "
            "Restricting evaluation to k=%d.",
            n_samples,
            n_distinct,
            min_k,
            max_k,
            effective_min_k,
        )
        k_values = [effective_min_k] if effective_min_k <= n_distinct and effective_min_k < n_samples else [min(n_distinct, n_samples)]
    else:
        k_values = list(range(effective_min_k, effective_max_k + 1))

    results: List[Dict[str, Any]] = []

    for k in k_values:
        if k >= n_samples:
            logger.info("Skipping k=%d as k must be strictly less than n_samples (%d)", k, n_samples)
            continue

        kmeans = KMeans(
            n_clusters=k,
            random_state=random_state,
            n_init=KMEANS_N_INIT,
        )
        labels = kmeans.fit_predict(X)
        inertia = float(kmeans.inertia_)

        # Silhouette score requires 2 <= number of unique labels <= n_samples - 1
        n_unique_labels = len(np.unique(labels))
        if 1 < n_unique_labels < n_samples:
            try:
                score = float(silhouette_score(X, labels, random_state=random_state))
            except Exception as e:
                logger.warning("Could not calculate silhouette score for k=%d: %s", k, e)
                score = np.nan
        else:
            score = np.nan

        results.append({
            "k": int(k),
            "inertia": round(inertia, 4),
            "silhouette_score": round(score, 4) if not np.isnan(score) else np.nan,
        })

    eval_df = pd.DataFrame(results)
    logger.info("K-Means evaluation completed across %d tested K values", len(eval_df))
    return eval_df


def select_best_k(evaluation_df: pd.DataFrame, fallback_k: int = DEFAULT_MIN_K) -> int:
    """Select the best K value from the evaluation results.

    Selection Rule:
    1. Filter for rows where silhouette_score is not NaN.
    2. Choose K with the highest silhouette score.
    3. If silhouette scores are unavailable or tied, select the lowest K with acceptable inertia.
    4. If no valid evaluations exist, return fallback_k.

    Args:
        evaluation_df: DataFrame containing ['k', 'inertia', 'silhouette_score']
        fallback_k: Default fallback cluster count

    Returns:
        Selected optimal K as an integer.
    """
    if evaluation_df.empty:
        logger.warning("Empty evaluation DataFrame. Returning fallback k=%d", fallback_k)
        return fallback_k

    valid_silhouette = evaluation_df.dropna(subset=["silhouette_score"])

    if not valid_silhouette.empty:
        # Sort by silhouette_score descending, then inertia ascending
        best_row = valid_silhouette.sort_values(
            by=["silhouette_score", "inertia"],
            ascending=[False, True],
        ).iloc[0]
        chosen_k = int(best_row["k"])
        logger.info(
            "Selected k=%d based on highest silhouette score (%.4f, inertia=%.4f)",
            chosen_k,
            best_row["silhouette_score"],
            best_row["inertia"],
        )
        return chosen_k

    # If silhouette score is NaN (e.g. extremely small dataset), select min K
    chosen_k = int(evaluation_df.iloc[0]["k"])
    logger.info("Silhouette scores unavailable. Selected first evaluated k=%d", chosen_k)
    return chosen_k


def train_kmeans(
    X: np.ndarray,
    n_clusters: int,
    random_state: int = RANDOM_STATE,
) -> Tuple[KMeans, np.ndarray]:
    """Train the final K-Means model and generate cluster assignments.

    Args:
        X: Scaled feature matrix
        n_clusters: Number of clusters to partition
        random_state: Fixed seed for reproducibility

    Returns:
        Tuple of (fitted_kmeans_model, cluster_labels_array)
    """
    n_samples = X.shape[0]
    n_distinct = len(np.unique(X, axis=0))
    max_allowable = min(n_samples, n_distinct)
    if n_clusters > max_allowable:
        logger.warning(
            "Requested n_clusters=%d exceeds distinct samples (%d). Reducing n_clusters to %d.",
            n_clusters,
            max_allowable,
            max_allowable,
        )
        n_clusters = max_allowable

    kmeans = KMeans(
        n_clusters=n_clusters,
        random_state=random_state,
        n_init=KMEANS_N_INIT,
    )
    labels = kmeans.fit_predict(X)

    logger.info(
        "Trained KMeans(k=%d) with inertia %.4f across %d devices",
        n_clusters,
        kmeans.inertia_,
        n_samples,
    )
    return kmeans, labels


def run_dbscan_comparison(
    X: np.ndarray,
    eps: float = DBSCAN_DEFAULT_EPS,
    min_samples: int = DBSCAN_DEFAULT_MIN_SAMPLES,
) -> Dict[str, Any]:
    """Run optional DBSCAN clustering comparison on the same scaled feature matrix.

    DBSCAN is evaluated strictly as an exploratory baseline comparison;
    it does NOT replace K-Means as the primary pipeline algorithm.

    Args:
        X: Scaled feature matrix
        eps: Maximum distance between two samples for neighborhood consideration
        min_samples: Minimum samples in a neighborhood for core point classification

    Returns:
        Dictionary summarizing DBSCAN clusters, noise points, and assignments.
    """
    n_samples = X.shape[0]
    if n_samples < min_samples:
        logger.warning(
            "DBSCAN: n_samples (%d) is less than min_samples (%d). Skipping DBSCAN.",
            n_samples,
            min_samples,
        )
        return {
            "algorithm": "DBSCAN",
            "status": "skipped",
            "reason": f"Insufficient samples ({n_samples} < min_samples {min_samples})",
            "n_clusters": 0,
            "n_noise": 0,
            "labels": [],
        }

    dbscan = DBSCAN(eps=eps, min_samples=min_samples)
    labels = dbscan.fit_predict(X)

    unique_labels = set(labels)
    n_clusters = len(unique_labels - {-1})
    n_noise = int(np.sum(labels == -1))

    logger.info(
        "DBSCAN Comparison: eps=%.2f, min_samples=%d -> %d clusters, %d noise points",
        eps,
        min_samples,
        n_clusters,
        n_noise,
    )

    return {
        "algorithm": "DBSCAN",
        "status": "completed",
        "eps": eps,
        "min_samples": min_samples,
        "n_clusters": n_clusters,
        "n_noise": n_noise,
        "labels": labels.tolist(),
        "model": dbscan,
    }
