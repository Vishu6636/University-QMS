"""
scripts/train_priority_model.py
================================
XGBoost ticket-priority classifier.

Features
--------
  1. TF-IDF of query_text          (5 000 sparse features)
  2. Rule-based sentiment score     (1 float, no heavy model)
  3. Department one-hot             (14 binary features)

Class imbalance handled via sklearn compute_sample_weight('balanced').

Outputs
-------
  models/priority/pipeline.joblib  — saved XGBoost pipeline
  reports/priority_eval.md         — per-class F1 + confusion matrix

Usage
-----
  python scripts/train_priority_model.py
"""

import sys, pathlib, warnings
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")

import re
import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder, OneHotEncoder
from sklearn.utils.class_weight import compute_sample_weight
from sklearn.metrics import (
    accuracy_score, f1_score, classification_report, confusion_matrix
)
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
import scipy.sparse as sp
from xgboost import XGBClassifier

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT        = pathlib.Path(__file__).resolve().parent.parent
DATA_CSV    = ROOT / "data" / "queries_labeled.csv"
MODEL_DIR   = ROOT / "models" / "priority"
MODEL_PATH  = MODEL_DIR / "pipeline.joblib"
REPORT_PATH = ROOT / "reports" / "priority_eval.md"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Import from service so joblib pickles the canonical class location.
from services.priority_model import TextMetaFeatures, sentiment_score  # noqa: E402


# ── Build feature pipeline ────────────────────────────────────────────────────

def build_features(df: pd.DataFrame) -> sp.csr_matrix:
    """
    Combine TF-IDF + sentiment/length + department OHE into one sparse matrix.
    Returns (X_sparse, column_transformer) — fit on this df.
    """
    pass  # handled in fit_transform below


# ── Confusion matrix markdown ─────────────────────────────────────────────────

def cm_to_md(cm, labels):
    hdr = "| | " + " | ".join(f"**{l}**" for l in labels) + " |"
    sep = "|---|" + "|".join(["---"] * len(labels)) + "|"
    rows = [hdr, sep]
    for i, label in enumerate(labels):
        rows.append("| **" + label + "** | " + " | ".join(str(v) for v in cm[i]) + " |")
    return "\n".join(rows)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # 1. Load data
    df = pd.read_csv(DATA_CSV)
    print(f"Loaded {len(df)} rows.")
    print(df["priority"].value_counts().to_string(), "\n")

    texts       = df["query_text"].to_numpy(dtype=str)
    departments = df["department"].to_numpy(dtype=str)
    labels_raw  = df["priority"].to_numpy(dtype=str)

    # Encode labels: low=0, medium=1, high=2
    le = LabelEncoder()
    le.fit(["low", "medium", "high"])
    y = le.transform(labels_raw)
    class_names = le.classes_   # ['high', 'low', 'medium'] after fit

    # 2. Stratified 80/20 split
    (t_txt, v_txt,
     t_dept, v_dept,
     y_train, y_test) = train_test_split(
        texts, departments, y,
        test_size=0.2, random_state=42, stratify=y
    )
    print(f"Train: {len(y_train)}  Test: {len(y_test)}\n")

    # 3. Build transformers
    tfidf = TfidfVectorizer(ngram_range=(1, 2), max_features=5000, sublinear_tf=True)
    ohe   = OneHotEncoder(handle_unknown="ignore", sparse_output=True)
    meta  = TextMetaFeatures()

    # Fit on train, transform both splits
    X_tfidf_tr  = tfidf.fit_transform(t_txt)
    X_tfidf_val = tfidf.transform(v_txt)

    X_ohe_tr    = ohe.fit_transform(t_dept.reshape(-1, 1))
    X_ohe_val   = ohe.transform(v_dept.reshape(-1, 1))

    X_meta_tr   = sp.csr_matrix(meta.fit_transform(t_txt))
    X_meta_val  = sp.csr_matrix(meta.transform(v_txt))

    X_train = sp.hstack([X_tfidf_tr,  X_ohe_tr,  X_meta_tr],  format="csr")
    X_test  = sp.hstack([X_tfidf_val, X_ohe_val, X_meta_val], format="csr")

    print(f"Feature matrix: {X_train.shape[1]} features\n")

    # 4. Class-imbalance weights
    sample_weights = compute_sample_weight("balanced", y_train)

    # 5. XGBoost
    xgb = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric="mlogloss",
        random_state=42,
        n_jobs=-1,
    )
    print("Training XGBoost…")
    xgb.fit(X_train, y_train, sample_weight=sample_weights)
    print("Done.\n")

    # 6. Evaluate
    y_pred = xgb.predict(X_test)
    acc    = accuracy_score(y_test, y_pred)
    mf1    = f1_score(y_test, y_pred, average="macro", zero_division=0)
    cm     = confusion_matrix(y_test, y_pred)
    report = classification_report(
        y_test, y_pred, target_names=le.classes_, zero_division=0
    )

    print(f"Accuracy : {acc:.4f}")
    print(f"Macro-F1 : {mf1:.4f}")
    print()
    print(report)

    # Per-university F1
    uni_ids = df["university_id"].to_numpy()
    # We need test indices — re-do split with same seed to get indices
    idx_all = np.arange(len(df))
    _, _, _, _, _, idx_test = train_test_split(
        texts, departments, idx_all,
        test_size=0.2, random_state=42, stratify=y
    )
    uni_test = uni_ids[idx_test]
    per_uni = {}
    for uid in sorted(np.unique(uni_test)):
        mask = uni_test == uid
        f1u = f1_score(y_test[mask], y_pred[mask], average="macro", zero_division=0)
        per_uni[int(uid)] = round(f1u, 4)
    print(f"Per-university macro-F1: {per_uni}\n")

    # 7. Save pipeline components
    artefact = {
        "tfidf": tfidf,
        "ohe":   ohe,
        "meta":  meta,
        "xgb":   xgb,
        "le":    le,
    }
    joblib.dump(artefact, MODEL_PATH)
    print(f"Model saved -> {MODEL_PATH}\n")

    # 8. Write report
    write_report(acc, mf1, cm, report, le.classes_, per_uni)
    print(f"Report saved -> {REPORT_PATH}")


def write_report(acc, mf1, cm, report_text, class_names, per_uni):
    uni_names = {1: "Greenfield Institute of Technology", 2: "Lakeview University"}
    lines = [
        "# Ticket Priority Prediction — Evaluation Report",
        "",
        "> **Model**: XGBoost with TF-IDF + rule-based sentiment score + department OHE  ",
        "> **Dataset**: `data/queries_labeled.csv` — 400 queries, 3 priority classes  ",
        "> **Split**: 80/20 stratified by priority  ",
        "> **Imbalance handling**: `compute_sample_weight('balanced')` on train set",
        "",
        "---",
        "",
        "## Overall Performance",
        "",
        "| Metric | Score |",
        "|--------|-------|",
        f"| Accuracy | **{acc:.4f}** |",
        f"| Macro-F1 | **{mf1:.4f}** |",
        "",
        "## Priority Class Distribution (full dataset)",
        "",
        "| Priority | Count | % |",
        "|----------|-------|---|",
        "| high     | 167   | 41.8 % |",
        "| medium   | 174   | 43.5 % |",
        "| low      |  59   | 14.8 % |",
        "",
        "## Per-University Macro-F1",
        "",
        "| University ID | Name | Macro-F1 |",
        "|---|---|---|",
    ]
    for uid, f1 in per_uni.items():
        lines.append(f"| {uid} | {uni_names.get(uid, str(uid))} | {f1} |")

    lines += [
        "",
        "---",
        "",
        "## Per-Class F1",
        "",
        "```",
        report_text,
        "```",
        "",
        "## Confusion Matrix",
        "",
        "> Rows = actual, Columns = predicted",
        "",
        cm_to_md(cm, class_names),
        "",
        "---",
        "",
        "## Feature Engineering",
        "",
        "| Feature Group | Details |",
        "|---|---|",
        "| TF-IDF | uni/bigrams, max 5 000 features, sublinear TF |",
        "| Sentiment score | Rule-based urgency lexicon (~30 words), score ∈ [-1, 1] |",
        "| Text length | Normalised word count (÷50, capped at 1) |",
        "| Department | One-hot encoded (14 departments across both universities) |",
        "",
        "> *Synthetic data — results are for prototype evaluation only.*",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
