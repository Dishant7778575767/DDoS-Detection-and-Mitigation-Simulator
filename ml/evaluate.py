#!/usr/bin/env python3
"""Evaluate candidate models on held-out test split and report comparison metrics."""

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
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
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


def evaluate_model(
    model,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    is_iforest: bool = False,
    threshold: float = 0.0,
) -> dict:
    t0 = time.time()
    if is_iforest:
        scores = model.decision_function(X_test)
        preds = (scores < threshold).astype(int)
        # Use negative score as proxy ranking score for ROC-AUC
        auc = float(roc_auc_score(y_test, -scores)) if len(np.unique(y_test)) > 1 else np.nan
    else:
        preds = model.predict(X_test)
        probs = model.predict_proba(X_test)[:, 1] if hasattr(model, "predict_proba") else None
        auc = float(roc_auc_score(y_test, probs)) if probs is not None and len(np.unique(y_test)) > 1 else np.nan

    eval_time = time.time() - t0
    cm = confusion_matrix(y_test, preds)
    tn, fp, fn, tp = cm.ravel()
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0

    # Benchmark p95 latency over 500 individual observations
    sample_obs = X_test.iloc[:500]
    latencies = []
    for i in range(len(sample_obs)):
        row = sample_obs.iloc[[i]]
        t_start = time.perf_counter()
        if is_iforest:
            model.decision_function(row)
        else:
            model.predict(row)
        latencies.append((time.perf_counter() - t_start) * 1000)
    p95_latency = float(np.percentile(latencies, 95))

    return {
        "accuracy": float(accuracy_score(y_test, preds)),
        "precision": float(precision_score(y_test, preds, zero_division=0)),
        "recall": float(recall_score(y_test, preds, zero_division=0)),
        "f1": float(f1_score(y_test, preds, zero_division=0)),
        "false_positive_rate": fpr,
        "roc_auc": auc,
        "p95_latency_ms": p95_latency,
        "confusion_matrix": {
            "true_negatives": int(tn),
            "false_positives": int(fp),
            "false_negatives": int(fn),
            "true_positives": int(tp),
        },
        "evaluation_time_seconds": float(eval_time),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate candidate models on held-out test data")
    parser.add_argument("--config", type=Path, default=Path("ml/configs/training.yaml"))
    parser.add_argument("--data-dir", type=Path, default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    paths_cfg = config.get("paths", {})
    data_dir = args.data_dir or Path(paths_cfg.get("data_dir", "data/processed"))

    test_path = data_dir / "test.csv"
    if not test_path.exists():
        raise FileNotFoundError(f"Held-out test set not found at {test_path}")

    print(f"Loading held-out test set from {test_path}...")
    test_df = pd.read_csv(test_path)
    test_df.columns = [c.strip() for c in test_df.columns]

    X_test = test_df[FEATURE_NAMES]
    y_test = test_df["label"]

    results = {
        "schema_version": FEATURE_SCHEMA_VERSION,
        "test_rows": len(test_df),
        "candidates": {},
    }

    # 1. Evaluate Random Forest
    rf_dir = Path(paths_cfg.get("rf_model_dir", "models/rf-1.0.0"))
    if (rf_dir / "model.joblib").exists():
        print("Evaluating Random Forest candidate...")
        rf_model = joblib.load(rf_dir / "model.joblib")
        results["candidates"]["RandomForest"] = evaluate_model(rf_model, X_test, y_test, is_iforest=False)

    # 2. Evaluate Isolation Forest
    if_dir = Path(paths_cfg.get("iforest_model_dir", "models/iforest-1.0.0"))
    if (if_dir / "model.joblib").exists():
        print("Evaluating Isolation Forest candidate...")
        if_model = joblib.load(if_dir / "model.joblib")
        thresh = 0.0
        if (if_dir / "metrics.json").exists():
            if_meta = json.loads((if_dir / "metrics.json").read_text(encoding="utf-8"))
            thresh = if_meta.get("calibrated_threshold", 0.0)
        results["candidates"]["IsolationForest"] = evaluate_model(
            if_model, X_test, y_test, is_iforest=True, threshold=thresh
        )

    print("\n================ Held-out Test Results ================")
    print(json.dumps(results, indent=2))

    # Save test results
    output_path = data_dir / "test_evaluation_results.json"
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved test evaluation to {output_path}")


if __name__ == "__main__":
    main()
