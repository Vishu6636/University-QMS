# Ticket Priority Prediction — Evaluation Report

> **Model**: XGBoost with TF-IDF + rule-based sentiment score + department OHE  
> **Dataset**: `data/queries_labeled.csv` — 400 queries, 3 priority classes  
> **Split**: 80/20 stratified by priority  
> **Imbalance handling**: `compute_sample_weight('balanced')` on train set

---

## Overall Performance

| Metric | Score |
|--------|-------|
| Accuracy | **0.9625** |
| Macro-F1 | **0.9705** |

## Priority Class Distribution (full dataset)

| Priority | Count | % |
|----------|-------|---|
| high     | 167   | 41.8 % |
| medium   | 174   | 43.5 % |
| low      |  59   | 14.8 % |

## Per-University Macro-F1

| University ID | Name | Macro-F1 |
|---|---|---|
| 1 | Greenfield Institute of Technology | 0.9823 |
| 2 | Lakeview University | 0.9556 |

---

## Per-Class F1

```
              precision    recall  f1-score   support

        high       0.97      0.94      0.95        33
         low       1.00      1.00      1.00        12
      medium       0.94      0.97      0.96        35

    accuracy                           0.96        80
   macro avg       0.97      0.97      0.97        80
weighted avg       0.96      0.96      0.96        80

```

## Confusion Matrix

> Rows = actual, Columns = predicted

| | **high** | **low** | **medium** |
|---|---|---|---|
| **high** | 31 | 0 | 2 |
| **low** | 0 | 12 | 0 |
| **medium** | 1 | 0 | 34 |

---

## Feature Engineering

| Feature Group | Details |
|---|---|
| TF-IDF | uni/bigrams, max 5 000 features, sublinear TF |
| Sentiment score | Rule-based urgency lexicon (~30 words), score ∈ [-1, 1] |
| Text length | Normalised word count (÷50, capped at 1) |
| Department | One-hot encoded (14 departments across both universities) |

> *Synthetic data — results are for prototype evaluation only.*