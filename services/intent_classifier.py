# services/intent_classifier.py
"""
Intent classifier service.
Winner: tfidf_lr

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
    if _meta is not None and (_model is not None or _tokenizer is not None):
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
        raise ValueError(f"Unknown winner: {winner}")


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
    label_map = _meta["label_map"]   # {str(int): intent_str}

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
        print(f"  {predict_intent(s):<30} | {s}")
