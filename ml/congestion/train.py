"""Model Training Pipeline for Congestion Forecasting.

Orchestrates:
- Loading Phase 9 datasets and preparing sequence tensors
- Constructing and compiling the GRU neural network
- Training with EarlyStopping and adaptive batch sizing
- Overfitting detection and diagnostics
- Serializing model (.keras), scaler (.pkl), metadata (.json), and loss curve (.png)
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import joblib
import numpy as np
import tensorflow as tf
from tensorflow import keras

from ml.congestion.config import (
    BATCH_SIZE,
    DEFAULT_METADATA_FILE,
    DEFAULT_MODEL_FILE,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SCALER_FILE,
    DEFAULT_TIMESTEPS,
    DEFAULT_TRAINING_LOSS_PLOT,
    DENSE_UNITS,
    DROPOUT_RATE,
    EARLY_STOPPING_PATIENCE,
    EPOCHS,
    GRU_UNITS,
    LEARNING_RATE,
    RANDOM_SEED,
)
from ml.congestion.model import build_gru_model, compile_gru_model, get_model_summary
from ml.congestion.preprocessing import prepare_training_tensors
from ml.congestion.visualization import plot_training_loss

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ml.congestion.train")


def train_congestion_model(
    data_dir: Path = DEFAULT_OUTPUT_DIR,
    epochs: int = EPOCHS,
    batch_size: int = BATCH_SIZE,
    learning_rate: float = LEARNING_RATE,
    patience: int = EARLY_STOPPING_PATIENCE,
    gru_units: int = GRU_UNITS,
    dense_units: int = DENSE_UNITS,
    dropout_rate: float = DROPOUT_RATE,
    timesteps: int = DEFAULT_TIMESTEPS,
    random_seed: int = RANDOM_SEED,
    model_output: Path = DEFAULT_MODEL_FILE,
    scaler_output: Path = DEFAULT_SCALER_FILE,
    metadata_output: Path = DEFAULT_METADATA_FILE,
    plot_output: Path = DEFAULT_TRAINING_LOSS_PLOT,
) -> Dict[str, Any]:
    """Train GRU model on Phase 9 time-series datasets.

    Args:
        data_dir: Directory containing train_dataset.csv, validation_dataset.csv, test_dataset.csv.
        epochs: Maximum training epochs.
        batch_size: Target mini-batch size (automatically bounded by dataset size).
        learning_rate: Initial Adam learning rate.
        patience: Early stopping patience.
        gru_units: Number of recurrent GRU units.
        dense_units: Intermediate projection units.
        dropout_rate: Regularization dropout rate.
        timesteps: Sequence steps.
        random_seed: Reproducibility seed.
        model_output: Destination path for .keras model.
        scaler_output: Destination path for .pkl scaler.
        metadata_output: Destination path for metadata .json.
        plot_output: Destination path for training loss .png.

    Returns:
        Dictionary containing training metadata, final metrics, and artifact paths.
    """
    # 1. Reproducibility
    np.random.seed(random_seed)
    tf.random.set_seed(random_seed)

    # 2. Data Preparation
    logger.info("Loading Phase 9 datasets from %s...", data_dir)
    data = prepare_training_tensors(data_dir=data_dir, timesteps=timesteps)

    X_train = data["X_train"]
    y_train = data["y_train_score"]
    X_val = data["X_val"]
    y_val = data["y_val_score"]
    scaler = data["scaler"]
    feature_cols = data["feature_cols"]
    input_shape = data["input_shape"]

    logger.info(
        "Loaded training data: X_train shape=%s, y_train samples=%d",
        X_train.shape,
        len(y_train),
    )

    # 3. Model Construction & Compilation
    model = build_gru_model(
        input_shape=input_shape,
        gru_units=gru_units,
        dense_units=dense_units,
        dropout_rate=dropout_rate,
    )
    compile_gru_model(model, learning_rate=learning_rate)

    # 4. Adaptive Batch Size & Callbacks
    # Ensure batch size is never larger than available training samples
    effective_batch_size = max(1, min(batch_size, len(X_train)))
    logger.info("Configured effective batch size: %d", effective_batch_size)

    callbacks = []
    val_data = None
    monitor_metric = "loss"

    if X_val is not None and len(X_val) > 0:
        val_data = (X_val, y_val)
        monitor_metric = "val_loss"
        logger.info("Validation set available (%d samples); monitoring %s", len(X_val), monitor_metric)

    early_stopping = keras.callbacks.EarlyStopping(
        monitor=monitor_metric,
        patience=patience,
        restore_best_weights=True,
        mode="min",
        verbose=1,
    )
    callbacks.append(early_stopping)

    # 5. Fit Model
    logger.info("Starting model training for up to %d epochs...", epochs)
    history = model.fit(
        X_train,
        y_train,
        validation_data=val_data,
        epochs=epochs,
        batch_size=effective_batch_size,
        callbacks=callbacks,
        verbose=1,
    )

    epochs_trained = len(history.history["loss"])
    final_train_loss = float(history.history["loss"][-1])
    final_train_mae = float(history.history.get("mae", [0.0])[-1])

    final_val_loss = None
    final_val_mae = None
    if "val_loss" in history.history and history.history["val_loss"]:
        final_val_loss = float(history.history["val_loss"][-1])
        final_val_mae = float(history.history.get("val_mae", [0.0])[-1])

    # 6. Overfitting Assessment
    overfitting_status = "NORMAL"
    overfitting_notes = "Training converged normally."

    if final_val_loss is not None:
        loss_ratio = final_val_loss / max(final_train_loss, 1e-6)
        if loss_ratio > 2.0:
            overfitting_status = "WARNING_HIGH_VAL_LOSS"
            overfitting_notes = (
                f"Validation loss ({final_val_loss:.4f}) is more than 2x training loss "
                f"({final_train_loss:.4f}). Characteristic of small LAN dataset sample size."
            )
        elif loss_ratio > 1.4:
            overfitting_status = "MODERATE_DIVERGENCE"
            overfitting_notes = f"Validation loss ({final_val_loss:.4f}) moderately higher than train loss."

    logger.info("Training complete in %d epochs. Overfitting status: %s", epochs_trained, overfitting_status)

    # 7. Serialize Artifacts
    model_output.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(model_output))
    logger.info("Saved trained Keras model to %s", model_output)

    scaler_output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(scaler, str(scaler_output))
    logger.info("Saved fitted StandardScaler to %s", scaler_output)

    # Save diagnostic loss plot
    plot_training_loss(history.history, plot_output)

    # Metadata record
    summary_dict = get_model_summary(model)
    metadata = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": 10,
        "model_architecture": "GRU",
        "model_name": model.name,
        "input_shape": list(input_shape),
        "timesteps": timesteps,
        "features_per_step": input_shape[1],
        "feature_columns": feature_cols,
        "hyperparameters": {
            "gru_units": gru_units,
            "dense_units": dense_units,
            "dropout_rate": dropout_rate,
            "learning_rate": learning_rate,
            "max_epochs": epochs,
            "epochs_trained": epochs_trained,
            "effective_batch_size": effective_batch_size,
            "early_stopping_patience": patience,
            "random_seed": random_seed,
        },
        "dataset_sample_counts": {
            "train": len(X_train),
            "validation": len(X_val) if X_val is not None else 0,
            "test": len(data["X_test"]) if data["X_test"] is not None else 0,
        },
        "training_results": {
            "final_train_loss_mse": round(final_train_loss, 6),
            "final_train_mae": round(final_train_mae, 6),
            "final_val_loss_mse": round(final_val_loss, 6) if final_val_loss is not None else None,
            "final_val_mae": round(final_val_mae, 6) if final_val_mae is not None else None,
            "best_epoch": int(np.argmin(history.history[monitor_metric])) + 1,
        },
        "overfitting_assessment": {
            "status": overfitting_status,
            "notes": overfitting_notes,
        },
        "artifacts": {
            "model_file": str(model_output),
            "scaler_file": str(scaler_output),
            "loss_plot": str(plot_output),
        },
        "parameter_counts": {
            "total": summary_dict["total_parameters"],
            "trainable": summary_dict["trainable_parameters"],
            "non_trainable": summary_dict["non_trainable_parameters"],
        },
    }

    metadata_output.parent.mkdir(parents=True, exist_ok=True)
    with open(metadata_output, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info("Saved model metadata to %s", metadata_output)

    # 8. Print Formatted Training Summary
    print("\n" + "=" * 65)
    print("           PHASE 10: MODEL TRAINING SUMMARY")
    print("=" * 65)
    print(f" Architecture:           GRU Time-Series Predictor")
    print(f" Input Tensor Shape:     (samples, {input_shape[0]}, {input_shape[1]})")
    print(f" Train Samples:          {len(X_train)}")
    print(f" Validation Samples:     {len(X_val) if X_val is not None else 0}")
    print(f" Epochs Trained:         {epochs_trained} / {epochs}")
    print(f" Final Train Loss (MSE): {final_train_loss:.6f}")
    print(f" Final Train MAE:        {final_train_mae:.6f}")
    if final_val_loss is not None:
        print(f" Final Val Loss (MSE):   {final_val_loss:.6f}")
        print(f" Final Val MAE:          {final_val_mae:.6f}")
    print(f" Overfitting Check:      {overfitting_status}")
    print(f" Model Saved To:         {model_output}")
    print(f" Scaler Saved To:        {scaler_output}")
    print(f" Loss Curve Saved To:    {plot_output}")
    print("=" * 65 + "\n")

    return metadata


def parse_args() -> argparse.Namespace:
    """Parse command line arguments for training."""
    parser = argparse.ArgumentParser(
        description="Phase 10: Train GRU Congestion Prediction Model."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory containing Phase 9 datasets (default: data/congestion)",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=EPOCHS,
        help=f"Number of training epochs (default: {EPOCHS})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"Mini-batch size (default: {BATCH_SIZE})",
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=LEARNING_RATE,
        help=f"Learning rate for Adam optimizer (default: {LEARNING_RATE})",
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=EARLY_STOPPING_PATIENCE,
        help=f"Early stopping patience (default: {EARLY_STOPPING_PATIENCE})",
    )
    parser.add_argument(
        "--gru-units",
        type=int,
        default=GRU_UNITS,
        help=f"Number of GRU units (default: {GRU_UNITS})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=RANDOM_SEED,
        help=f"Random seed (default: {RANDOM_SEED})",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    train_congestion_model(
        data_dir=args.data_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        patience=args.patience,
        gru_units=args.gru_units,
        random_seed=args.seed,
    )
