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


from unittest.mock import patch, MagicMock
from groq import RateLimitError
import httpx


def test_groq_failure_logging():
    """
    Regression test: mock a Groq API failure and assert that the real exception type
    and details are logged server-side via log_event rather than swallowed silently.
    """
    print(f"\n{'='*65}")
    print("  REGRESSION TEST — Groq API failure logging")
    print(f"{'='*65}")

    mock_req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    mock_resp = httpx.Response(429, request=mock_req, json={"error": {"message": "Rate limit reached"}})
    mock_err = RateLimitError("Rate limit reached", response=mock_resp, body={"error": {"message": "Rate limit reached"}})

    with patch("services.rag_chat._get_client") as mock_get_client, \
         patch("services.rag_chat.log_event") as mock_log_event:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = mock_err
        mock_get_client.return_value = mock_client

        res = answer_query(1, "What is the scholarship application deadline?")

        # 1. Assert user-facing response returned
        ans = res["answer"]
        print(f"  User answer returned: {ans}")

        # 2. Assert log_event was called with full exception details
        logged_events = []
        for call in mock_log_event.call_args_list:
            event_name = call.args[0] if call.args else call.kwargs.get("event_name")
            kwargs = call.kwargs.copy()
            kwargs["event"] = event_name
            logged_events.append(kwargs)

        failure_event = next((e for e in logged_events if e.get("event") == "groq_api_failure"), None)

        assert failure_event is not None, f"groq_api_failure event was not logged! Calls: {mock_log_event.call_args_list}"
        assert failure_event.get("error_type") == "RateLimitError", (
            f"Expected error_type 'RateLimitError', got '{failure_event.get('error_type')}'"
        )
        assert "Rate limit reached" in failure_event.get("error", ""), (
            f"Expected error message in log event, got: {failure_event.get('error')}"
        )
        print("  [PASS] Groq API failure correctly logged real exception type and error details.")
    return True


def run():
    all_pass = True

    # Run regression test first
    if not test_groq_failure_logging():
        all_pass = False

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
            ans_clean = ans.replace("\u202f", " ").replace("\xa0", " ").replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
            ok = (phrase in ans_clean) or (phrase == "5-day" and ("5 days" in ans_clean or "5-day" in ans_clean)) or (phrase == "3-day" and ("3 days" in ans_clean or "3-day" in ans_clean))
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
        gf_ans_clean = gf_ans.replace("\u202f", " ").replace("\xa0", " ")
        if lv_phrase in gf_ans_clean and lv_phrase != gf_phrase:
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

