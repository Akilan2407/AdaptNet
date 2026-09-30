"""TensorFlow / Keras GRU Architecture for Congestion Forecasting.

Implements a recurrent network designed for sequence processing of network telemetry
and predicting future network congestion scores in [0.0, 1.0].
"""

import logging
from typing import Any, Dict, Optional, Tuple

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, regularizers

from ml.congestion.config import (
    DEFAULT_TIMESTEPS,
    DENSE_UNITS,
    DROPOUT_RATE,
    GRU_UNITS,
    LEARNING_RATE,
)

logger = logging.getLogger("ml.congestion.model")


def build_gru_model(
    input_shape: Tuple[int, int] = (DEFAULT_TIMESTEPS, 11),
    gru_units: int = GRU_UNITS,
    dense_units: int = DENSE_UNITS,
    dropout_rate: float = DROPOUT_RATE,
    name: str = "gru_congestion_predictor",
) -> keras.Model:
    """Construct GRU recurrent neural network for continuous congestion prediction.

    Architecture:
      Input: (timesteps, features)
        ↓
      GRU (units=gru_units, return_sequences=False, l2=1e-4)
        ↓
      BatchNormalization
        ↓
      Dropout (rate=dropout_rate)
        ↓
      Dense (units=dense_units, activation='relu', l2=1e-4)
        ↓
      Dropout (rate=dropout_rate)
        ↓
      Dense (units=1, activation='sigmoid', name='future_congestion_score')

    Args:
        input_shape: Tuple of (timesteps, features_per_step).
        gru_units: Number of recurrent GRU units.
        dense_units: Number of neurons in the intermediate dense projection layer.
        dropout_rate: Dropout fraction for regularization.
        name: Name for the Keras model.

    Returns:
        Uncompiled Keras Model instance.
    """
    inputs = keras.Input(shape=input_shape, name="telemetry_sequence_input")

    # Recurrent representation learning
    x = layers.GRU(
        units=gru_units,
        return_sequences=False,
        kernel_regularizer=regularizers.l2(1e-4),
        recurrent_regularizer=regularizers.l2(1e-4),
        name="gru_recurrent",
    )(inputs)

    # Normalization and regularization
    x = layers.BatchNormalization(name="batch_norm")(x)
    x = layers.Dropout(rate=dropout_rate, name="dropout_1")(x)

    # Dense non-linear projection
    x = layers.Dense(
        units=dense_units,
        activation="relu",
        kernel_regularizer=regularizers.l2(1e-4),
        name="dense_features",
    )(x)
    x = layers.Dropout(rate=dropout_rate, name="dropout_2")(x)

    # Target output bounded in [0.0, 1.0] via sigmoid activation
    outputs = layers.Dense(
        units=1,
        activation="sigmoid",
        name="future_congestion_score",
    )(x)

    model = keras.Model(inputs=inputs, outputs=outputs, name=name)
    logger.info(
        "Built GRU model '%s' with input_shape=%s, gru_units=%d, dense_units=%d",
        name,
        input_shape,
        gru_units,
        dense_units,
    )
    return model


def compile_gru_model(
    model: keras.Model,
    learning_rate: float = LEARNING_RATE,
) -> keras.Model:
    """Compile GRU model with Adam optimizer, MSE loss, and MAE/MSE metrics.

    Args:
        model: Uncompiled Keras Model.
        learning_rate: Initial learning rate for Adam optimizer.

    Returns:
        Compiled Keras Model instance.
    """
    optimizer = keras.optimizers.Adam(learning_rate=learning_rate, clipnorm=1.0)
    loss = "mean_squared_error"
    metrics = ["mae", "mse"]

    model.compile(
        optimizer=optimizer,
        loss=loss,
        metrics=metrics,
    )

    logger.info(
        "Compiled model with Adam(lr=%s, clipnorm=1.0), loss=%s, metrics=%s",
        learning_rate,
        loss,
        metrics,
    )
    return model


def get_model_summary(model: keras.Model) -> Dict[str, Any]:
    """Extract serializable structural summary of the model.

    Args:
        model: Keras Model instance.

    Returns:
        Dictionary summarizing layer configurations and parameter counts.
    """
    total_params = int(model.count_params())
    trainable_params = int(sum(keras.ops.prod(w.shape) for w in model.trainable_weights))
    non_trainable_params = int(total_params - trainable_params)

    layers_summary = []
    for layer in model.layers:
        layers_summary.append({
            "name": layer.name,
            "class": layer.__class__.__name__,
            "output_shape": str(getattr(layer, "output_shape", "unknown")),
        })

    return {
        "model_name": model.name,
        "total_parameters": total_params,
        "trainable_parameters": trainable_params,
        "non_trainable_parameters": non_trainable_params,
        "layers": layers_summary,
    }
