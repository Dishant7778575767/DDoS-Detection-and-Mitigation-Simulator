#!/usr/bin/env python3
"""Train Random Forest classifier on prepared dataset using training.yaml configuration."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

# Add backend to path for shared feature definitions
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.features.definitions import FEATURE_NAMES, FEATURE_SCHEMA_VERSION


def load_config(config_path: Path) -> dict:
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Random Forest classifier")
    parser.add_argument("--config", type=Path, default=Path("ml/configs/training.yaml"))
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    paths_cfg = config.get("paths", {})
    rf_cfg = config.get("hyperparameters", {}).get("random_forest", {})

    data_dir = args.data_dir or Path(paths_cfg.get("data_dir", "data/processed"))
    output_dir = args.output_dir or Path(paths_cfg.get("rf_model_dir", "models/rf-1.0.0"))
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading training data from {data_dir}...")
    train_df = pd.read_csv(data_dir / "train.csv")
    val_df = pd.read_csv(data_dir / "val.csv")

    # Clean column names
    train_df.columns = [c.strip() for c in train_df.columns]
    val_df.columns = [c.strip() for c in val_df.columns]

    # Verify features match schema v1.0.0
    missing = [f for f in FEATURE_NAMES if f not in train_df.columns]
    if missing:
        raise ValueError(f"Training data missing required features: {missing}")

    X_train = train_df[FEATURE_NAMES]
    y_train = train_df["label"]
    X_val = val_df[FEATURE_NAMES]
    y_val = val_df["label"]

    print(f"Training Random Forest (samples: {len(X_train)}, features: {len(FEATURE_NAMES)})...")
    rf = RandomForestClassifier(
        n_estimators=rf_cfg.get("n_estimators", 100),
        max_depth=rf_cfg.get("max_depth", 15),
        min_samples_split=rf_cfg.get("min_samples_split", 5),
        class_weight=rf_cfg.get("class_weight", "balanced"),
        random_state=rf_cfg.get("random_state", 42),
        n_jobs=rf_cfg.get("n_jobs", 1),
    )

    t0 = time.time()
    rf.fit(X_train, y_train)
    train_time = time.time() - t0
    print(f"Model fitted in {train_time:.2f} seconds.")

    # Validation evaluation
    val_preds = rf.predict(X_val)
    cm = confusion_matrix(y_val, val_preds)
    tn, fp, fn, tp = cm.ravel()
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0

    # Latency measurement over 500 validation observations
    sample_obs = X_val.iloc[:500]
    latencies = []
    for i in range(len(sample_obs)):
        row = sample_obs.iloc[[i]]
        t_start = time.perf_counter()
        rf.predict(row)
        latencies.append((time.perf_counter() - t_start) * 1000)
    p95_latency = float(np.percentile(latencies, 95))

    metrics = {
        "model_name": "RandomForestClassifier",
        "schema_version": FEATURE_SCHEMA_VERSION,
        "accuracy": float(accuracy_score(y_val, val_preds)),
        "precision": float(precision_score(y_val, val_preds, zero_division=0)),
        "recall": float(recall_score(y_val, val_preds, zero_division=0)),
        "f1": float(f1_score(y_val, val_preds, zero_division=0)),
        "false_positive_rate": fpr,
        "p95_latency_ms": p95_latency,
        "confusion_matrix": cm.tolist(),
        "training_time_seconds": float(train_time),
    }

    # Save artifacts
    model_path = output_dir / "model.joblib"
    joblib.dump(rf, model_path)

    metrics_path = output_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    feature_schema = {
        "schema_version": FEATURE_SCHEMA_VERSION,
        "feature_count": len(FEATURE_NAMES),
        "features": list(FEATURE_NAMES),
        "target": "binary_classification",
        "positive_label": 1,
        "negative_label": 0,
        "score_meaning": "Random Forest probability; not a calibrated guarantee for production use.",
    }
    (output_dir / "feature_schema.json").write_text(json.dumps(feature_schema, indent=2), encoding="utf-8")

    print(f"Saved Random Forest artifacts to {output_dir}")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
