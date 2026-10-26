#!/usr/bin/env python3
"""Prepare the CIC-DDoS2019 CSV corpus for model training and evaluation.

This Phase 2 baseline keeps the workflow reproducible and memory-safe for local
runs by defaulting to a bounded sample, while preserving the same chunked logic
required for larger datasets.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

EXCLUDED_COLUMNS = {
    "unnamed",
    "unnamed_0",
    "unnamed_0_0",
    "flow_id",
    "source_ip",
    "destination_ip",
    "source_port",
    "destination_port",
    "protocol",
    "timestamp",
    "label",
    "simillarhttp",
    "inbound",
}


def normalize_column_name(value: str) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def parse_label(value) -> int:
    if pd.isna(value):
        return 0
    label = str(value).strip().lower()
    if label in {"benign", "normal", "0", "0.0"} or "benign" in label:
        return 0
    return 1


def discover_csv_files(root: Path) -> list[Path]:
    files = sorted(root.rglob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found under {root}")
    return files


def infer_feature_columns(sample: pd.DataFrame) -> list[str]:
    columns: list[str] = []
    for name in sample.columns:
        key = normalize_column_name(name)
        if key in EXCLUDED_COLUMNS or key.startswith("unnamed"):
            continue
        try:
            pd.to_numeric(sample[name], errors="raise")
        except (TypeError, ValueError):
            continue
        columns.append(str(name))
    if not columns:
        raise ValueError("No numeric feature columns were found in the dataset sample.")
    return columns


def process_csv(
    data_file: Path,
    feature_columns: list[str],
    output_path: Path,
    limit: int | None = None,
    chunksize: int = 250_000,
) -> int:
    header_written = output_path.exists()
    total_rows = 0

    for chunk in pd.read_csv(data_file, chunksize=chunksize, low_memory=False):
        chunk = chunk.copy()
        chunk.columns = [str(c).strip() for c in chunk.columns]
        if "Label" not in chunk.columns:
            raise ValueError(f"Missing Label column in {data_file}")

        chunk["label"] = chunk["Label"].map(parse_label)
        selected = []
        for col in feature_columns:
            if col not in chunk.columns:
                continue
            chunk[col] = pd.to_numeric(chunk[col], errors="coerce")
            selected.append(col)

        cleaned = chunk[selected + ["label"]].copy()
        cleaned = cleaned.replace([np.inf, -np.inf], np.nan)
        cleaned = cleaned.dropna().copy()
        if cleaned.empty:
            continue

        if limit is not None and total_rows + len(cleaned) > limit:
            remaining = max(limit - total_rows, 0)
            if remaining <= 0:
                break
            cleaned = cleaned.iloc[:remaining]

        cleaned.to_csv(output_path, mode="a", header=not header_written, index=False)
        header_written = True
        total_rows += len(cleaned)

        if limit is not None and total_rows >= limit:
            break

    return total_rows


def split_dataset(
    processed_csv: Path, output_dir: Path, seed: int = 42, test_size: float = 0.20
):
    output_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(processed_csv)
    df = df.replace([np.inf, -np.inf], np.nan).dropna().copy()
    X = df.drop(columns=["label"])
    X = X.loc[:, ~X.columns.astype(str).str.lower().str.contains("unnamed", na=False)]
    y = df["label"]

    from sklearn.model_selection import train_test_split

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=seed,
        stratify=y,
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_train,
        y_train,
        test_size=0.25,
        random_state=seed,
        stratify=y_train,
    )

    train_df = X_train.copy()
    train_df["label"] = y_train.values
    val_df = X_val.copy()
    val_df["label"] = y_val.values
    test_df = X_test.copy()
    test_df["label"] = y_test.values

    train_df.to_csv(output_dir / "train.csv", index=False)
    val_df.to_csv(output_dir / "val.csv", index=False)
    test_df.to_csv(output_dir / "test.csv", index=False)

    metadata = {
        "schema_version": "1.0.0",
        "target": "binary_classification",
        "positive_label": 1,
        "negative_label": 0,
        "feature_columns": list(X.columns),
        "train_rows": len(train_df),
        "val_rows": len(val_df),
        "test_rows": len(test_df),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare CIC-DDoS2019 data")
    parser.add_argument("--data-root", type=Path, default=Path("data/raw/CIC-DDoS2019"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument(
        "--limit",
        type=int,
        default=200_000,
        help="Rows to process per run; 0 means full processing.",
    )
    parser.add_argument("--chunksize", type=int, default=250_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    csv_files = discover_csv_files(args.data_root)
    sample = pd.read_csv(csv_files[0], nrows=5_000, low_memory=False)
    feature_columns = infer_feature_columns(sample)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    combined_path = args.output_dir / "combined.csv"
    if combined_path.exists():
        combined_path.unlink()

    total_rows = 0
    for path in csv_files:
        rows = process_csv(
            path,
            feature_columns,
            combined_path,
            limit=None if args.limit == 0 else args.limit - total_rows,
            chunksize=args.chunksize,
        )
        total_rows += rows
        if args.limit and total_rows >= args.limit:
            break

    if not combined_path.exists() or combined_path.stat().st_size == 0:
        raise FileNotFoundError(
            "No data rows were prepared. Check the dataset files or the --limit argument."
        )

    split_dataset(combined_path, args.output_dir, seed=args.seed)
    print(f"Prepared {total_rows} rows using features: {len(feature_columns)}")


if __name__ == "__main__":
    main()
