# services/priority_model.py
"""
Ticket priority predictor.

predict_priority(query_text, department) -> str
  Returns "low", "medium", or "high".
"""

import sys, re
import numpy as np
import pathlib
import joblib
from sklearn.base import BaseEstimator, TransformerMixin

ROOT = pathlib.Path(__file__).resolve().parent.parent
# Ensure project root is on sys.path so joblib can resolve this module.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODEL_PATH = ROOT / "models" / "priority" / "pipeline.joblib"

# ── Sentiment lexicon (must live here so joblib can unpickle TextMetaFeatures) ─
URGENT_WORDS = {
    "urgent", "immediately", "asap", "critical", "emergency", "serious",
    "escalate", "problem", "error", "wrong", "rejected", "failed", "fail",
    "missing", "lost", "stolen", "harassment", "complaint", "issue",
    "incorrect", "mistake", "unfair", "discrimination", "ragging",
    "not working", "broken", "deadline", "overdue", "fine", "penalty",
}
CALM_WORDS = {
    "thank", "thanks", "please", "query", "info", "information",
    "know", "check", "view", "see", "access", "when", "how", "what",
    "library", "book", "borrow", "journal",
}

def sentiment_score(text: str) -> float:
    tokens = set(re.findall(r"\b\w+\b", text.lower()))
    score  = sum(1.0 for w in URGENT_WORDS if w in tokens)
    score -= sum(0.5 for w in CALM_WORDS  if w in tokens)
    return float(np.clip(score / max(len(tokens), 1) * 10, -1.0, 1.0))


class TextMetaFeatures(BaseEstimator, TransformerMixin):
    """[sentiment_score, text_length_norm] extractor — must be in this module."""
    def fit(self, X, y=None): return self
    def transform(self, X):
        texts = X if isinstance(X, (list, np.ndarray)) else list(X)
        return np.array([
            [sentiment_score(t), min(len(t.split()) / 50.0, 1.0)]
            for t in texts
        ])


_artefact = None


def _load():
    global _artefact
    if _artefact is None:
        _artefact = joblib.load(MODEL_PATH)


def predict_priority(query_text: str, department: str) -> str:
    """
    Predict ticket priority.

    Args:
        query_text:  Raw student query string.
        department:  Target department (must match training labels, but
                     unknown values are handled gracefully via OHE).

    Returns:
        "low", "medium", or "high".
    """
    import numpy as np
    import scipy.sparse as sp

    _load()
    tfidf = _artefact["tfidf"]
    ohe   = _artefact["ohe"]
    meta  = _artefact["meta"]
    xgb   = _artefact["xgb"]
    le    = _artefact["le"]

    X_tfidf = tfidf.transform([query_text])
    X_ohe   = ohe.transform(np.array([[department]]))
    X_meta  = sp.csr_matrix(meta.transform([query_text]))

    X = sp.hstack([X_tfidf, X_ohe, X_meta], format="csr")
    pred_id = xgb.predict(X)[0]
    return le.inverse_transform([pred_id])[0]


if __name__ == "__main__":
    # Quick smoke test
    samples = [
        ("I have a ragging complaint, need urgent help!", "Student Affairs"),
        ("when is the library open on weekends", "Library"),
        ("how to pay fees online", "Finance & Accounts"),
        ("scholarship deadline nahi pata", "Finance & Accounts"),
        ("my answer sheet has wrong marks totalled", "Examination Cell"),
    ]
    for text, dept in samples:
        p = predict_priority(text, dept)
        print(f"  {p:<8} | [{dept}] {text[:60]}")
