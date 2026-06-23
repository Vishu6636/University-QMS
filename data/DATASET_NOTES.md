# Dataset Notes — Synthetic Data for University Query System

## Overview
This dataset was **synthetically generated** for prototype evaluation and
multi-tenancy testing of the University Query Management System.
It does NOT represent real institutions, students, or policies.

## Universities
| ID | Name | Scholarship Deadline | Min Attendance | Revaluation Fee |
|----|------|----------------------|----------------|-----------------|
| 1  | Greenfield Institute of Technology | March 15 | 75% | ₹500/subject |
| 2  | Lakeview University                | April 30 | 80% | ₹750/subject |

Key policy differences are intentional — they validate that the retrieval
pipeline returns university-specific answers and does not cross-contaminate
tenants.

## Files
| File | Description | Rows |
|------|-------------|------|
| `greenfield_faqs.csv` | 20 Q&A pairs for Greenfield Institute of Technology | 20 |
| `lakeview_faqs.csv`   | 20 Q&A pairs for Lakeview University | 20 |
| `queries_labeled.csv` | 400 synthetic student queries (200 per university) | 400 |

## FAQ Schema
```
category   — topic area (scholarship / attendance / exams / hostel / fees / library / placement)
question   — student-facing question text
answer     — official university answer text
```

## Query Schema
```
university_id   — 1 = Greenfield, 2 = Lakeview
university_name — full university name
query_text      — raw student query (mixed formal/informal/Hindi-English/typos)
intent          — one of: scholarship_inquiry, fee_payment, exam_schedule,
                  hostel_booking, attendance_policy, course_registration,
                  library_access, placement_info, grievance, document_request,
                  admission_query, revaluation_request
department      — target department that should handle the query
priority        — low / medium / high
```

## Generation Process
- FAQs were hand-authored with distinct per-university details
  (deadlines, amounts, grace periods, curfew times) to stress-test
  tenant isolation in the vector store.
- Queries were generated from 200+ phrase templates covering 12 intent
  categories, then sampled to 200 per university using `random.seed(42)`
  for reproducibility.
- Phrasing intentionally varies: formal English, informal English,
  Hinglish (Hindi-English code-switching), and common typos.
- Priority is rule-based on intent (grievance/fee/scholarship = high;
  library/placement = low; others = medium).

## Usage
- **FAQ CSVs** → ingest into ChromaDB via `services/ingestion.py`
- **queries_labeled.csv** → use as evaluation set for intent classifier
  or retrieval benchmarks
- **Tenant isolation test** → run `scripts/test_ingestion.py`

> ⚠️ **This is entirely synthetic data created for testing purposes only.**
> No real student, faculty, or institutional data is present.
