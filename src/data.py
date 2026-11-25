"""Loading and cleaning helpers for CIC-IDS2017 (MachineLearningCSV version).

Every notebook imports from here so that loading and cleaning happen the
same way everywhere.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = Path(os.environ.get("IDS_RAW_DIR", PROJECT_ROOT / "data" / "raw"))
PROCESSED_DIR = Path(os.environ.get("IDS_PROCESSED_DIR", PROJECT_ROOT / "data" / "processed"))
REPORTS_DIR = Path(os.environ.get("IDS_REPORTS_DIR", PROJECT_ROOT / "reports"))
FIGURES_DIR = REPORTS_DIR / "figures"

LABEL_COL = "Label"

# Friday captures: Bot (morning), PortScan and DDoS (afternoon).
FRIDAY_FILES = {
    "morning_bot": "Friday-WorkingHours-Morning.pcap_ISCX.csv",
    "afternoon_portscan": "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv",
    "afternoon_ddos": "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv",
}


def load_friday(raw_dir: Path | str = RAW_DIR) -> pd.DataFrame:
    """Read the three Friday CSVs into one DataFrame.

    Adds a `source_file` column so we can tell which capture a row came from.
    That column is for analysis only and must be dropped before training.
    """
    raw_dir = Path(raw_dir)
    frames = []
    for tag, name in FRIDAY_FILES.items():
        path = raw_dir / name
        if not path.exists():
            raise FileNotFoundError(
                f"Missing {path}\nPut the Friday CSVs from MachineLearningCSV.zip in {raw_dir}"
            )
        df = pd.read_csv(path, low_memory=False, encoding_errors="replace")
        # The original headers have stray leading spaces, e.g. " Label".
        df.columns = df.columns.str.strip()
        df["source_file"] = tag
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df[LABEL_COL] = df[LABEL_COL].str.strip()
    return df


def feature_columns(df: pd.DataFrame) -> list[str]:
    """All numeric feature columns (everything except label and bookkeeping)."""
    return [c for c in df.columns if c not in (LABEL_COL, "source_file")]


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Apply the standard CIC-IDS2017 fixes and report what was removed.

    1. +/-inf -> NaN, then drop rows with NaN (from Flow Bytes/s, Flow Packets/s).
    2. Drop 'Fwd Header Length.1', an exact copy of 'Fwd Header Length'.
    3. Drop columns that hold a single value in every row (carry no information).
    4. Drop exact duplicate rows.
    5. Store features as float32 to halve memory.
    """
    report = {"rows_before": len(df), "cols_before": df.shape[1]}
    df = df.copy()
    feats = feature_columns(df)

    df[feats] = df[feats].replace([np.inf, -np.inf], np.nan)
    report["rows_with_nan_or_inf"] = int(df[feats].isna().any(axis=1).sum())
    df = df.dropna(subset=feats)

    dropped = []
    if "Fwd Header Length.1" in df.columns:
        df = df.drop(columns="Fwd Header Length.1")
        dropped.append("Fwd Header Length.1")

    feats = feature_columns(df)
    constant = [c for c in feats if df[c].nunique() <= 1]
    df = df.drop(columns=constant)
    dropped += constant
    report["dropped_columns"] = dropped

    before = len(df)
    df = df.drop_duplicates(subset=feature_columns(df) + [LABEL_COL])
    report["duplicate_rows_removed"] = before - len(df)

    feats = feature_columns(df)
    df[feats] = df[feats].astype("float32")
    df = df.reset_index(drop=True)

    report["rows_after"] = len(df)
    report["cols_after"] = df.shape[1]
    return df, report
