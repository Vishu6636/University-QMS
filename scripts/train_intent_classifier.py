"""
scripts/train_intent_classifier.py
===================================
Trains and compares two intent classifiers on data/queries_labeled.csv:
  1. Baseline  : TF-IDF + Logistic Regression  (scikit-learn)
  2. Fine-tuned: DistilBERT                     (HuggingFace transformers)

Outputs
-------
  models/intent/tfidf_lr/pipeline.joblib       — saved baseline
  models/intent/distilbert/                    — saved DistilBERT model+tokenizer
  models/intent/best_model.json                — which model won + label map
  reports/intent_eval.md                       — comparison table (markdown)

Usage
-----
  python scripts/train_intent_classifier.py
  python scripts/train_intent_classifier.py --skip-distilbert   # baseline only
"""

import sys, pathlib, json, argparse, time, warnings
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    accuracy_score, f1_score, classification_report, confusion_matrix
)
import joblib

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT        = pathlib.Path(__file__).resolve().parent.parent
DATA_CSV    = ROOT / "data" / "queries_labeled.csv"
MODEL_DIR   = ROOT / "models" / "intent"
TFIDF_DIR   = MODEL_DIR / "tfidf_lr"
BERT_DIR    = MODEL_DIR / "distilbert"
BEST_JSON   = MODEL_DIR / "best_model.json"
REPORT_PATH = ROOT / "reports" / "intent_eval.md"

MODEL_DIR.mkdir(parents=True, exist_ok=True)
TFIDF_DIR.mkdir(parents=True, exist_ok=True)
BERT_DIR.mkdir(parents=True, exist_ok=True)
(ROOT / "reports").mkdir(exist_ok=True)

# ── Load data ─────────────────────────────────────────────────────────────────

def load_data():
    df = pd.read_csv(DATA_CSV)
    print(f"Loaded {len(df)} rows. Intent distribution:")
    print(df["intent"].value_counts().to_string())
    print()
    return df

# ── Evaluation helpers ────────────────────────────────────────────────────────

def eval_metrics(y_true, y_pred, label_names):
    acc = accuracy_score(y_true, y_pred)
    mf1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    cm  = confusion_matrix(y_true, y_pred)
    return acc, mf1, cm

def per_university_f1(df_test, y_pred, label_enc):
    """Return {university_id: macro_f1} for each university in test set."""
    result = {}
    for uid in sorted(df_test["university_id"].unique()):
        mask = df_test["university_id"] == uid
        yt = df_test.loc[mask, "intent_enc"].values
        yp = y_pred[mask]
        f1 = f1_score(yt, yp, average="macro", zero_division=0)
        result[uid] = round(f1, 4)
    return result

# ── 1. Baseline: TF-IDF + Logistic Regression ────────────────────────────────

def train_baseline(X_train, y_train):
    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=20_000,
            sublinear_tf=True,
        )),
        ("clf", LogisticRegression(
            max_iter=1000,
            C=5.0,
            solver="lbfgs",
        )),
    ])
    t0 = time.time()
    pipe.fit(X_train, y_train)
    elapsed = time.time() - t0
    print(f"  Baseline trained in {elapsed:.1f}s")
    return pipe

# ── 2. Fine-tuned DistilBERT ──────────────────────────────────────────────────

def train_distilbert(X_train, y_train, X_test, y_test, num_labels, epochs=5):
    try:
        import torch
        from transformers import (
            DistilBertTokenizerFast,
            DistilBertForSequenceClassification,
            Trainer, TrainingArguments,
        )
        from torch.utils.data import Dataset as TorchDataset
    except ImportError as e:
        print(f"  [SKIP] DistilBERT unavailable: {e}")
        return None, None

    MODEL_NAME = "distilbert-base-uncased"
    tokenizer  = DistilBertTokenizerFast.from_pretrained(MODEL_NAME)

    class IntentDataset(TorchDataset):
        def __init__(self, texts, labels):
            enc = tokenizer(
                list(texts), truncation=True, padding=True, max_length=64
            )
            self.input_ids      = enc["input_ids"]
            self.attention_mask = enc["attention_mask"]
            self.labels         = list(labels)
        def __len__(self):  return len(self.labels)
        def __getitem__(self, i):
            return {
                "input_ids":      torch.tensor(self.input_ids[i]),
                "attention_mask": torch.tensor(self.attention_mask[i]),
                "labels":         torch.tensor(self.labels[i]),
            }

    train_ds = IntentDataset(X_train, y_train)
    test_ds  = IntentDataset(X_test,  y_test)

    model = DistilBertForSequenceClassification.from_pretrained(
        MODEL_NAME, num_labels=num_labels
    )

    args = TrainingArguments(
        output_dir=str(BERT_DIR / "checkpoints"),
        num_train_epochs=epochs,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=32,
        learning_rate=3e-5,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="no",
        load_best_model_at_end=False,
        logging_steps=20,
        report_to="none",
        seed=42,
    )

    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        preds = np.argmax(logits, axis=-1)
        return {
            "accuracy": accuracy_score(labels, preds),
            "macro_f1": f1_score(labels, preds, average="macro", zero_division=0),
        }

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=test_ds,
        compute_metrics=compute_metrics,
    )

    print(f"  Training DistilBERT for {epochs} epochs…")
    t0 = time.time()
    trainer.train()
    elapsed = time.time() - t0
    print(f"  DistilBERT trained in {elapsed:.1f}s")

    # Predictions on test set
    preds_out = trainer.predict(test_ds)
    y_pred = np.argmax(preds_out.predictions, axis=-1)

    # Save model + tokenizer
    model.save_pretrained(str(BERT_DIR))
    tokenizer.save_pretrained(str(BERT_DIR))
    print(f"  DistilBERT saved -> {BERT_DIR}")

    return trainer, y_pred

# ── Confusion matrix as markdown ──────────────────────────────────────────────

def cm_to_markdown(cm, labels):
    header = "| Intent | " + " | ".join(labels) + " |"
    sep    = "|--------|" + "|".join(["------"] * len(labels)) + "|"
    rows   = [header, sep]
    for i, row in enumerate(cm):
        rows.append("| `" + labels[i] + "` | " + " | ".join(str(v) for v in row) + " |")
    return "\n".join(rows)

# ── Main ──────────────────────────────────────────────────────────────────────

def main(skip_distilbert=False):
    df = load_data()

    # Encode intents
    intents      = sorted(df["intent"].unique())
    intent2id    = {v: i for i, v in enumerate(intents)}
    id2intent    = {i: v for v, i in intent2id.items()}
    df["intent_enc"] = df["intent"].map(intent2id)

    X = df["query_text"].to_numpy(dtype=str)
    y = df["intent_enc"].to_numpy(dtype=int)

    # Stratified 80/20 split
    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        X, y, np.arange(len(df)),
        test_size=0.2, random_state=42, stratify=y
    )
    df_test = df.iloc[idx_test].copy().reset_index(drop=True)
    # Align df_test index with test arrays
    df_test["intent_enc"] = y_test

    print(f"Train size: {len(X_train)}  |  Test size: {len(X_test)}\n")

    results = {}

    # ── Baseline ──────────────────────────────────────────────────────────────
    print("=" * 60)
    print("1. TF-IDF + Logistic Regression (baseline)")
    print("=" * 60)
    baseline = train_baseline(X_train, y_train)
    y_pred_lr = baseline.predict(X_test)
    acc_lr, mf1_lr, cm_lr = eval_metrics(y_test, y_pred_lr, intents)
    puf1_lr = per_university_f1(df_test, y_pred_lr, intent2id)
    print(f"  Accuracy : {acc_lr:.4f}")
    print(f"  Macro-F1 : {mf1_lr:.4f}")
    print(f"  Per-uni F1: {puf1_lr}")
    print()
    print(classification_report(y_test, y_pred_lr, target_names=intents, zero_division=0))

    joblib.dump(baseline, TFIDF_DIR / "pipeline.joblib")
    print(f"  Baseline saved -> {TFIDF_DIR / 'pipeline.joblib'}\n")

    results["tfidf_lr"] = {
        "accuracy": round(acc_lr, 4),
        "macro_f1": round(mf1_lr, 4),
        "per_uni_f1": puf1_lr,
        "cm": cm_lr,
        "y_pred": y_pred_lr,
    }

    # ── DistilBERT ────────────────────────────────────────────────────────────
    bert_trained = False
    if not skip_distilbert:
        print("=" * 60)
        print("2. Fine-tuned DistilBERT")
        print("=" * 60)
        trainer, y_pred_bert = train_distilbert(
            X_train, y_train, X_test, y_test,
            num_labels=len(intents), epochs=5,
        )
        if y_pred_bert is not None:
            acc_b, mf1_b, cm_b = eval_metrics(y_test, y_pred_bert, intents)
            puf1_b = per_university_f1(df_test, y_pred_bert, intent2id)
            print(f"  Accuracy : {acc_b:.4f}")
            print(f"  Macro-F1 : {mf1_b:.4f}")
            print(f"  Per-uni F1: {puf1_b}")
            print()
            print(classification_report(y_test, y_pred_bert, target_names=intents, zero_division=0))
            results["distilbert"] = {
                "accuracy": round(acc_b, 4),
                "macro_f1": round(mf1_b, 4),
                "per_uni_f1": puf1_b,
                "cm": cm_b,
                "y_pred": y_pred_bert,
            }
            bert_trained = True
        else:
            print("  DistilBERT skipped.\n")

    # ── Pick winner ───────────────────────────────────────────────────────────
    if bert_trained and results["distilbert"]["macro_f1"] >= results["tfidf_lr"]["macro_f1"]:
        winner = "distilbert"
    else:
        winner = "tfidf_lr"

    best_meta = {
        "winner": winner,
        "label_map": id2intent,
        "intents": intents,
    }
    with open(BEST_JSON, "w") as f:
        json.dump(best_meta, f, indent=2)
    print(f"\n*** Best model: {winner} ***\n")

    # ── Write intent_classifier.py ────────────────────────────────────────────
    write_classifier_service(winner, intents)

    # ── Write report ──────────────────────────────────────────────────────────
    write_report(results, intents, y_test, bert_trained)

    print(f"Report saved -> {REPORT_PATH}")


def write_classifier_service(winner, intents):
    src = ROOT / "services" / "intent_classifier.py"
    code = f'''# services/intent_classifier.py
"""
Intent classifier service.
Winner: {winner}

predict_intent(query_text) -> str
  Returns the predicted intent label for a student query.
"""

import json, pathlib

ROOT      = pathlib.Path(__file__).resolve().parent.parent
BEST_JSON = ROOT / "models" / "intent" / "best_model.json"

_model     = None
_tokenizer = None
_meta      = None


def _load():
    global _model, _tokenizer, _meta
    if _meta is not None:
        return  # already loaded

    with open(BEST_JSON) as f:
        _meta = json.load(f)

    winner = _meta["winner"]

    if winner == "tfidf_lr":
        import joblib
        _model = joblib.load(ROOT / "models" / "intent" / "tfidf_lr" / "pipeline.joblib")

    elif winner == "distilbert":
        from transformers import (
            DistilBertTokenizerFast,
            DistilBertForSequenceClassification,
        )
        import torch
        bert_dir  = str(ROOT / "models" / "intent" / "distilbert")
        _tokenizer = DistilBertTokenizerFast.from_pretrained(bert_dir)
        _model     = DistilBertForSequenceClassification.from_pretrained(bert_dir)
        _model.eval()

    else:
        raise ValueError(f"Unknown winner: {{winner}}")


def predict_intent(query_text: str) -> str:
    """
    Predict the intent category of a student query.

    Args:
        query_text: Raw student query string.

    Returns:
        Intent label string, e.g. "scholarship_inquiry".
    """
    _load()
    winner = _meta["winner"]
    label_map = _meta["label_map"]   # {{str(int): intent_str}}

    if winner == "tfidf_lr":
        pred_id = int(_model.predict([query_text])[0])
        return label_map[str(pred_id)]

    else:  # distilbert
        import torch
        enc = _tokenizer(
            query_text, return_tensors="pt",
            truncation=True, padding=True, max_length=64,
        )
        with torch.no_grad():
            logits = _model(**enc).logits
        pred_id = int(logits.argmax(dim=-1).item())
        return label_map[str(pred_id)]


if __name__ == "__main__":
    # Quick smoke test
    samples = [
        "when is the scholarship deadline",
        "hostel curfew time kya hai",
        "how to apply for revaluation",
        "what is the late fee penalty",
        "campus placement registration",
    ]
    for s in samples:
        print(f"  {{predict_intent(s):<30}} | {{s}}")
'''
    src.write_text(code, encoding="utf-8")
    print(f"  Written -> {src}")


def write_report(results, intents, y_test, bert_trained):
    lr  = results["tfidf_lr"]
    has_bert = bert_trained and "distilbert" in results
    bt  = results.get("distilbert", {})

    # Short intent labels for confusion matrix
    short = [i.replace("_", " ")[:18] for i in intents]

    lines = [
        "# Intent Classifier Evaluation Report",
        "",
        "> **Dataset**: `data/queries_labeled.csv` — 400 synthetic student queries, "
        "12 intent classes, 2 universities.  ",
        "> **Split**: 80 % train / 20 % test, stratified by intent.",
        "",
        "---",
        "",
        "## Overall Performance",
        "",
        "| Metric | TF-IDF + LR (baseline) | DistilBERT (fine-tuned) |",
        "|--------|------------------------|-------------------------|",
        f"| Accuracy | **{lr['accuracy']:.4f}** | {'**' + str(bt.get('accuracy','—')) + '**' if has_bert else '—'} |",
        f"| Macro-F1 | **{lr['macro_f1']:.4f}** | {'**' + str(bt.get('macro_f1','—')) + '**' if has_bert else '—'} |",
        "",
    ]

    # Per-university F1
    lines += [
        "## Per-University Macro-F1",
        "",
        "Checks whether the model generalises across university phrasing styles "
        "rather than overfitting to one tenant's vocabulary.",
        "",
        "| University ID | University Name | TF-IDF + LR | DistilBERT |",
        "|---------------|-----------------|-------------|------------|",
    ]
    uni_names = {1: "Greenfield Institute of Technology", 2: "Lakeview University"}
    for uid, uname in uni_names.items():
        lr_f1  = lr["per_uni_f1"].get(uid, "—")
        bt_f1  = bt.get("per_uni_f1", {}).get(uid, "—") if has_bert else "—"
        lines.append(f"| {uid} | {uname} | {lr_f1} | {bt_f1} |")

    lines += [""]

    # Winner
    if has_bert:
        winner_name = "DistilBERT" if bt["macro_f1"] >= lr["macro_f1"] else "TF-IDF + LR"
        lines += [
            "## Winner",
            "",
            f"**{winner_name}** (higher macro-F1) — saved to `models/intent/`  ",
            f"Loaded automatically by `services/intent_classifier.py`.",
            "",
        ]

    # Confusion matrix — baseline
    lines += [
        "---",
        "",
        "## Confusion Matrix — TF-IDF + LR",
        "",
        cm_to_markdown(lr["cm"], short),
        "",
    ]

    if has_bert:
        lines += [
            "## Confusion Matrix — DistilBERT",
            "",
            cm_to_markdown(bt["cm"], short),
            "",
        ]

    # Per-class report
    from sklearn.metrics import classification_report as cr
    report_text = cr(y_test, lr["y_pred"], target_names=intents, zero_division=0)
    lines += [
        "---",
        "",
        "## Per-Class F1 — TF-IDF + LR",
        "",
        "```",
        report_text,
        "```",
        "",
        "---",
        "",
        "> *This is synthetic data generated for prototype evaluation. "
        "Results should not be interpreted as real-world benchmarks.*",
    ]

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-distilbert", action="store_true",
        help="Only train the TF-IDF + LR baseline (much faster)."
    )
    args = parser.parse_args()
    main(skip_distilbert=args.skip_distilbert)
