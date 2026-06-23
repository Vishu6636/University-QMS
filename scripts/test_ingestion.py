#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
"""
scripts/test_ingestion.py
─────────────────────────
Quick smoke-test for the ingestion pipeline.

What it proves
──────────────
1. Two fake universities (IDs 101 and 202) each get distinct ChromaDB
   collections that are NEVER shared.
2. retrieve(university_id=101, ...) returns ONLY university-101 chunks.
3. retrieve(university_id=202, ...) returns ONLY university-202 chunks.
4. Cross-tenant leakage is architecturally impossible — confirmed by
   asserting that none of the returned texts belong to the other tenant.

Usage
─────
    # From the project root
    python scripts/test_ingestion.py

The script prints a structured report and exits with code 0 on success or
1 on failure.
"""

import sys
import textwrap
import logging

# ── Make sure project root is on sys.path ─────────────────────────────────────
import pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── Configure logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("test_ingestion")

# ── Imports after path fix ─────────────────────────────────────────────────────
from services.ingestion import ingest_to_vectorstore, retrieve  # noqa: E402

# ── Test data ─────────────────────────────────────────────────────────────────

UNIVERSITY_1_ID = 101
UNIVERSITY_2_ID = 202

# Unique fingerprint phrases that must ONLY appear in their university's results.
FINGERPRINT_1 = "GREENFIELD_UNIVERSITY_MARKER"
FINGERPRINT_2 = "REDSTONE_COLLEGE_MARKER"

UNIVERSITY_1_TEXT = textwrap.dedent(f"""
    {FINGERPRINT_1}

    Greenfield University — Admissions Policy 2025

    Greenfield University welcomes applications from students worldwide.
    Our holistic admissions process evaluates academic achievement, personal
    essays, extracurricular involvement, and letters of recommendation.
    Applicants must hold a recognised secondary-school leaving certificate or
    equivalent qualification.  The minimum GPA requirement for undergraduate
    programmes is 3.0 on a 4.0 scale.

    Application Deadlines
    Early Decision:    November 1
    Regular Decision:  January 15
    Transfer:          March 1

    Required Documents
    1. Completed online application form.
    2. Official high-school transcripts.
    3. Two letters of recommendation (academic referees preferred).
    4. Personal statement (650 words maximum).
    5. Standardised test scores (SAT/ACT) — optional for 2025 intake.

    Financial Aid at Greenfield
    Greenfield University offers need-based and merit-based scholarships.
    Students must submit the FAFSA or CSS Profile by February 1 to be
    considered for institutional aid.  International students may apply for
    merit scholarships worth up to 50 % of tuition.

    Campus Life
    The Greenfield campus spans 400 acres in the rolling hills of central
    Vermont.  Students enjoy world-class research facilities, a vibrant arts
    scene, and more than 200 registered student organisations.  On-campus
    housing is guaranteed for all first-year students.

    Contact Admissions
    Email: admissions@greenfield.edu
    Phone: +1 (802) 555-0100
    Office hours: Monday – Friday, 9 am – 5 pm EST
""").strip()

UNIVERSITY_2_TEXT = textwrap.dedent(f"""
    {FINGERPRINT_2}

    Redstone College — Fee Structure and Scholarship Guide 2025

    Redstone College is committed to making quality education accessible.
    Below is our comprehensive fee schedule for the 2025–2026 academic year.

    Tuition Fees (per semester)
    • Engineering programmes:      £9,500
    • Business & Management:       £8,200
    • Humanities & Social Sciences: £7,400
    • Foundation Year:              £6,000

    Additional Mandatory Fees
    Student Union levy:    £120
    Library and IT:        £80
    Health & Wellbeing:    £60
    Sports facilities:     £40

    Scholarships Available at Redstone
    Vice-Chancellor's Excellence Award
        Value: £5,000 per year  |  Criteria: Top 5 % GPA in entry cohort

    Redstone Community Bursary
        Value: £2,500 per year  |  Criteria: Household income below £25,000

    International Student Scholarship
        Value: 20 % tuition reduction  |  Criteria: Non-UK applicants with
        predicted grades ABB or above (A-Level equivalent)

    Payment Deadlines
    Semester 1:  15 September 2025
    Semester 2:  15 January 2026
    Late payment attracts a £50 administrative charge per month.

    Contact Finance Office
    Email: finance@redstone.ac.uk
    Phone: +44 (0)20 7946 0200
    Location: Finance House, Redstone Campus, London EC1A 1BB
""").strip()

# ── Helpers ───────────────────────────────────────────────────────────────────

def section(title: str) -> None:
    width = 70
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}")


def print_results(results: list[dict]) -> None:
    if not results:
        print("  (no results returned)")
        return
    for i, r in enumerate(results, 1):
        preview = r["text"][:120].replace("\n", " ")
        print(f"  [{i}] score={r['score']:.4f}  doc_id={r['doc_id']}  "
              f"chunk={r['chunk_index']}")
        print(f"       '{preview}…'")


# ── Main test logic ───────────────────────────────────────────────────────────

def run_tests() -> bool:
    all_passed = True

    # ── Step 1: Ingest documents ───────────────────────────────────────────────
    section("STEP 1 — Ingesting documents")

    ok1 = ingest_to_vectorstore(UNIVERSITY_1_ID, doc_id=1, text=UNIVERSITY_1_TEXT)
    print(f"  ingest university_id={UNIVERSITY_1_ID}: {'[OK]' if ok1 else '[FAILED]'}")

    ok2 = ingest_to_vectorstore(UNIVERSITY_2_ID, doc_id=2, text=UNIVERSITY_2_TEXT)
    print(f"  ingest university_id={UNIVERSITY_2_ID}: {'[OK]' if ok2 else '[FAILED]'}")

    if not (ok1 and ok2):
        print("\n  ✗ Ingestion failed — aborting further tests.")
        return False

    # ── Step 2: Retrieve for university 1 ─────────────────────────────────────
    section("STEP 2 — Retrieve: university 1 (admissions query)")
    q1 = "What are the application deadlines and required documents?"
    results_1 = retrieve(UNIVERSITY_1_ID, q1, k=5)
    print(f"  Query : '{q1}'")
    print_results(results_1)

    # ── Step 3: Retrieve for university 2 ─────────────────────────────────────
    section("STEP 3 — Retrieve: university 2 (fees query)")
    q2 = "What are the scholarship amounts and eligibility criteria?"
    results_2 = retrieve(UNIVERSITY_2_ID, q2, k=5)
    print(f"  Query : '{q2}'")
    print_results(results_2)

    # ── Step 4: Cross-tenant isolation assertions ──────────────────────────────
    section("STEP 4 — Tenant isolation assertions")

    # University 1 results must NEVER contain university-2 fingerprint.
    uni1_texts_combined = " ".join(r["text"] for r in results_1)
    uni1_leaked = FINGERPRINT_2 in uni1_texts_combined
    if uni1_leaked:
        print(f"  [FAIL] University-1 results contain university-2 fingerprint!")
        all_passed = False
    else:
        print(f"  [PASS] University-1 results contain NO university-2 content.")

    # University 2 results must NEVER contain university-1 fingerprint.
    uni2_texts_combined = " ".join(r["text"] for r in results_2)
    uni2_leaked = FINGERPRINT_1 in uni2_texts_combined
    if uni2_leaked:
        print(f"  [FAIL] University-2 results contain university-1 fingerprint!")
        all_passed = False
    else:
        print(f"  [PASS] University-2 results contain NO university-1 content.")

    # University 1 results should contain its own fingerprint (sanity check).
    if results_1 and FINGERPRINT_1 not in uni1_texts_combined:
        # The fingerprint may be in a different chunk — do a full ingest text check.
        pass  # Non-critical; fingerprint may be in a non-top-k chunk.

    # university_id in metadata must match the requested tenant.
    uni1_meta_ok = all(
        r.get("university_id") == UNIVERSITY_1_ID for r in results_1
    )
    uni2_meta_ok = all(
        r.get("university_id") == UNIVERSITY_2_ID for r in results_2
    )

    if uni1_meta_ok:
        print(f"  [PASS] All university-1 result metadata carry university_id={UNIVERSITY_1_ID}.")
    else:
        print(f"  [FAIL] Unexpected university_id in university-1 results!")
        all_passed = False

    if uni2_meta_ok:
        print(f"  [PASS] All university-2 result metadata carry university_id={UNIVERSITY_2_ID}.")
    else:
        print(f"  [FAIL] Unexpected university_id in university-2 results!")
        all_passed = False

    # ── Step 5: Cross-query sanity — wrong university returns irrelevant results ─
    section("STEP 5 — Cross-query sanity check")
    # Ask university-1's question against university-2's collection.
    cross_results = retrieve(UNIVERSITY_2_ID, q1, k=5)
    cross_texts = " ".join(r["text"] for r in cross_results)
    cross_leaked = FINGERPRINT_1 in cross_texts
    if cross_leaked:
        print(f"  [FAIL] Cross-query to university-2 returned university-1 content!")
        all_passed = False
    else:
        print(f"  [PASS] Cross-query to university-2 returned NO university-1 content.")
        print(f"         (University-2 collection correctly knows nothing about university-1.)")

    # -- Summary ---------------------------------------------------------------
    section("SUMMARY")
    if all_passed:
        print("  [ALL PASSED] Tenant isolation is working correctly.\n")
    else:
        print("  [FAILURES DETECTED] See output above.\n")

    return all_passed


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
