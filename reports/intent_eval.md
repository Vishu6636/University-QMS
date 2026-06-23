# Intent Classifier Evaluation Report

> **Dataset**: `data/queries_labeled.csv` — 400 synthetic student queries, 12 intent classes, 2 universities.  
> **Split**: 80 % train / 20 % test, stratified by intent.

---

## Overall Performance

| Metric | TF-IDF + LR (baseline) | DistilBERT (fine-tuned) |
|--------|------------------------|-------------------------|
| Accuracy | **0.9375** | **0.8875** |
| Macro-F1 | **0.9349** | **0.8158** |

## Per-University Macro-F1

Checks whether the model generalises across university phrasing styles rather than overfitting to one tenant's vocabulary.

| University ID | University Name | TF-IDF + LR | DistilBERT |
|---------------|-----------------|-------------|------------|
| 1 | Greenfield Institute of Technology | 0.9075 | 0.7861 |
| 2 | Lakeview University | 0.9464 | 0.8355 |

## Winner

**TF-IDF + LR** (higher macro-F1) — saved to `models/intent/`  
Loaded automatically by `services/intent_classifier.py`.

---

## Confusion Matrix — TF-IDF + LR

| Intent | admission query | attendance policy | course registratio | document request | exam schedule | fee payment | grievance | hostel booking | library access | placement info | revaluation reques | scholarship inquir |
|--------|------|------|------|------|------|------|------|------|------|------|------|------|
| `admission query` | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| `attendance policy` | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `course registratio` | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `document request` | 0 | 0 | 0 | 4 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| `exam schedule` | 0 | 0 | 0 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| `fee payment` | 0 | 0 | 0 | 0 | 0 | 10 | 0 | 0 | 0 | 0 | 1 | 0 |
| `grievance` | 0 | 0 | 0 | 0 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 0 |
| `hostel booking` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 7 | 0 | 0 | 0 | 0 |
| `library access` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| `placement info` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 6 | 0 | 0 |
| `revaluation reques` | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 6 | 0 |
| `scholarship inquir` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 9 |

## Confusion Matrix — DistilBERT

| Intent | admission query | attendance policy | course registratio | document request | exam schedule | fee payment | grievance | hostel booking | library access | placement info | revaluation reques | scholarship inquir |
|--------|------|------|------|------|------|------|------|------|------|------|------|------|
| `admission query` | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `attendance policy` | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `course registratio` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3 |
| `document request` | 0 | 0 | 0 | 2 | 0 | 0 | 1 | 2 | 0 | 0 | 0 | 0 |
| `exam schedule` | 0 | 0 | 0 | 0 | 7 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| `fee payment` | 0 | 0 | 0 | 0 | 0 | 11 | 0 | 0 | 0 | 0 | 0 | 0 |
| `grievance` | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 2 | 0 | 0 | 0 | 0 |
| `hostel booking` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 7 | 0 | 0 | 0 | 0 |
| `library access` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| `placement info` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 6 | 0 | 0 |
| `revaluation reques` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 7 | 0 |
| `scholarship inquir` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 9 |

---

## Per-Class F1 — TF-IDF + LR

```
                     precision    recall  f1-score   support

    admission_query       1.00      0.75      0.86         4
  attendance_policy       0.89      1.00      0.94         8
course_registration       1.00      1.00      1.00         3
   document_request       1.00      0.80      0.89         5
      exam_schedule       1.00      0.88      0.93         8
        fee_payment       1.00      0.91      0.95        11
          grievance       0.86      1.00      0.92         6
     hostel_booking       1.00      1.00      1.00         7
     library_access       1.00      1.00      1.00         6
     placement_info       0.86      1.00      0.92         6
revaluation_request       0.75      0.86      0.80         7
scholarship_inquiry       1.00      1.00      1.00         9

           accuracy                           0.94        80
          macro avg       0.95      0.93      0.93        80
       weighted avg       0.95      0.94      0.94        80

```

---

> *This is synthetic data generated for prototype evaluation. Results should not be interpreted as real-world benchmarks.*