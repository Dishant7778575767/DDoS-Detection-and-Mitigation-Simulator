#!/usr/bin/env python3
"""Train Isolation Forest anomaly detector on benign baseline and tune threshold on validation data."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

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
    parser = argparse.ArgumentParser(description="Train Isolation Forest anomaly detector")
    parser.add_argument("--config", type=Path, default=Path("ml/configs/training.yaml"))
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    paths_cfg = config.get("paths", {})
    if_cfg = config.get("hyperparameters", {}).get("isolation_forest", {})

    data_dir = args.data_dir or Path(paths_cfg.get("data_dir", "data/processed"))
    output_dir = args.output_dir or Path(paths_cfg.get("iforest_model_dir", "models/iforest-1.0.0"))
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading data from {data_dir}...")
    train_df = pd.read_csv(data_dir / "train.csv")
    val_df = pd.read_csv(data_dir / "val.csv")

    train_df.columns = [c.strip() for c in train_df.columns]
    val_df.columns = [c.strip() for c in val_df.columns]

    X_train = train_df[FEATURE_NAMES]
    y_train = train_df["label"]
    X_val = val_df[FEATURE_NAMES]
    y_val = val_df["label"]

    # In accordance with PRD, fit unsupervised Isolation Forest on benign baseline flows
    X_train_benign = X_train[y_train == 0]
    fit_data = X_train_benign if len(X_train_benign) >= 100 else X_train
    print(f"Fitting Isolation Forest on {len(fit_data)} flows...")

    iforest = IsolationForest(
        n_estimators=if_cfg.get("n_estimators", 100),
        max_samples=min(if_cfg.get("max_samples", 256), len(fit_data)),
        contamination=if_cfg.get("contamination", 0.05),
        random_state=if_cfg.get("random_state", 42),
        n_jobs=if_cfg.get("n_jobs", 1),
    )

    t0 = time.time()
    iforest.fit(fit_data)
    train_time = time.time() - t0
    print(f"Isolation Forest fitted in {train_time:.2f} seconds.")

    # Validation scores: lower score = more anomalous
    val_scores = iforest.decision_function(X_val)

    # Calibrate threshold on validation set to find best F1
    candidate_thresholds = np.percentile(val_scores, np.linspace(0.5, 99.5, 200))
    best_thresh = 0.0
    best_f1 = -1.0

    for th in candidate_thresholds:
        preds = (val_scores < th).astype(int)
        f1 = f1_score(y_val, preds, zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_thresh = th

    print(f"Calibrated validation decision threshold: {best_thresh:.4f} (Validation F1: {best_f1:.4f})")

    val_preds = (val_scores < best_thresh).astype(int)
    cm = confusion_matrix(y_val, val_preds)
    tn, fp, fn, tp = cm.ravel()
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0

    # Latency measurement over 500 validation observations
    sample_obs = X_val.iloc[:500]
    latencies = []
    for i in range(len(sample_obs)):
        row = sample_obs.iloc[[i]]
        t_start = time.perf_counter()
        iforest.decision_function(row)
        latencies.append((time.perf_counter() - t_start) * 1000)
    p95_latency = float(np.percentile(latencies, 95))

    metrics = {
        "model_name": "IsolationForest",
        "schema_version": FEATURE_SCHEMA_VERSION,
        "calibrated_threshold": float(best_thresh),
        "accuracy": float(accuracy_score(y_val, val_preds)),
        "precision": float(precision_score(y_val, val_preds, zero_division=0)),
        "recall": float(recall_score(y_val, val_preds, zero_division=0)),
        "f1": float(f1_score(y_val, val_preds, zero_division=0)),
        "false_positive_rate": fpr,
        "p95_latency_ms": p95_latency,
        "confusion_matrix": cm.tolist(),
        "training_time_seconds": float(train_time),
        "score_convention": "Isolation Forest decision_function: scores < calibrated_threshold represent anomalies (label=1). Negative/lower scores denote higher anomaly intensity.",
    }

    # Save artifacts
    joblib.dump(iforest, output_dir / "model.joblib")
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    feature_schema = {
        "schema_version": FEATURE_SCHEMA_VERSION,
        "feature_count": len(FEATURE_NAMES),
        "features": list(FEATURE_NAMES),
        "target": "anomaly_detection",
        "calibrated_threshold": float(best_thresh),
        "score_meaning": "Anomaly decision score; not a calibrated probability.",
    }
    (output_dir / "feature_schema.json").write_text(json.dumps(feature_schema, indent=2), encoding="utf-8")

    print(f"Saved Isolation Forest artifacts to {output_dir}")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
