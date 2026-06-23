#!/usr/bin/env python
"""
scripts/test_rag_chat.py
Run 5 queries against Greenfield (university_id=1) and 5 against Lakeview
(university_id=2) from the synthetic dataset to verify RAG answers differ
correctly where policies differ.

Usage (from project root):
    python scripts/test_rag_chat.py
"""
import sys
import os
import pathlib
import io

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Project root on path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from services.rag_chat import answer_query

# Policy-sensitive queries that should produce DIFFERENT answers per university
# (scholarship deadline, revaluation fee, attendance %, late fee grace, hostel curfew)
QUERIES = [
    "What is the scholarship application deadline?",
    "What is the fee for exam revaluation?",
    "What is the minimum attendance required to sit in exams?",
    "How many grace days do I get after the fee due date before a fine?",
    "What time does the hostel gate close on weekdays?",
]

UNIVERSITIES = {
    1: "Greenfield Institute of Technology",
    2: "Lakeview University",
}

# Expected key phrases that MUST appear in the right university's answer
# (used for a simple pass/fail check)
EXPECTED = {
    1: ["March 15", "500", "75%", "5-day", "10:00"],
    2: ["April 30", "750", "80%", "3-day", "9:30"],
}


def run():
    all_pass = True
    results_by_uni = {}

    for uid, uname in UNIVERSITIES.items():
        print(f"\n{'='*65}")
        print(f"  University {uid}: {uname}")
        print(f"{'='*65}")
        answers = []
        for i, q in enumerate(QUERIES, 1):
            print(f"\n  Q{i}: {q}")
            result = answer_query(uid, q)
            ans = result["answer"]
            print(f"  A : {ans[:300]}")
            print(f"      [chunks={result['chunks_used']} escalate={result['escalate']}]")
            answers.append(ans)
        results_by_uni[uid] = answers

    # Verification
    print(f"\n{'='*65}")
    print("  VERIFICATION — policy-specific phrase checks")
    print(f"{'='*65}")

    for uid in [1, 2]:
        for i, (ans, phrase) in enumerate(zip(results_by_uni[uid], EXPECTED[uid])):
            ok = (phrase in ans) or (phrase == "5-day" and "5 days" in ans) or (phrase == "3-day" and "3 days" in ans)
            status = "[PASS]" if ok else "[FAIL]"
            print(f"  {status} Uni-{uid} Q{i+1}: expected '{phrase}' in answer")
            if not ok:
                all_pass = False

    # Cross-check: Greenfield's answer must NOT contain Lakeview phrases
    print(f"\n  Cross-contamination check:")
    lv_phrases = EXPECTED[2]
    gf_phrases = EXPECTED[1]
    for i, (gf_ans, lv_phrase, gf_phrase) in enumerate(
        zip(results_by_uni[1], lv_phrases, gf_phrases)
    ):
        if lv_phrase in gf_ans and lv_phrase != gf_phrase:
            print(f"  [FAIL] Uni-1 Q{i+1} contains Lakeview phrase '{lv_phrase}'")
            all_pass = False
        else:
            print(f"  [PASS] Uni-1 Q{i+1} does not contain Lakeview phrase '{lv_phrase}'")

    print(f"\n{'='*65}")
    if all_pass:
        print("  ALL CHECKS PASSED")
    else:
        print("  SOME CHECKS FAILED — see above")
    print(f"{'='*65}\n")
    return all_pass


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
