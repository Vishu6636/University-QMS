#!/usr/bin/env python
"""
scripts/test_tenant_isolation.py
Verifies tenant isolation at the vector database layer.

It embeds distinct documents for two different mock universities,
queries each namespace, and asserts that no cross-tenant leakage occurs.

Usage:
    python scripts/test_tenant_isolation.py
"""

import sys
import os
import pathlib
import io

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add project root to path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from services.ingestion import ingest_to_vectorstore, retrieve, _get_chroma_client

# Use distinct mock university IDs to prevent interference with existing seed data
UNI_A_ID = 99991
UNI_B_ID = 99992

DOC_A_CONTENT = (
    "Alpha University is a world-class institution dedicated to quantum computing, "
    "theoretical physics, and advanced photonics research. The primary laboratory is located "
    "in the science block room 402."
)

DOC_B_CONTENT = (
    "Beta University is a leading research center for marine biology, ocean currents, "
    "and deep-sea coral reef ecosystems. Students regularly conduct field studies off the coast."
)


def run_test():
    print("=" * 70)
    print("     RUNNING TENANT ISOLATION VECTOR SEARCH TEST")
    print("=" * 70)

    client = _get_chroma_client()

    # Clean up any leftover test collections before starting
    for uid in [UNI_A_ID, UNI_B_ID]:
        coll_name = f"university_{uid}"
        try:
            client.delete_collection(coll_name)
            print(f"Cleaned up existing collection: {coll_name}")
        except Exception:
            pass

    # 1. Ingest document for University A
    print(f"\nIngesting document for University A (ID: {UNI_A_ID})...")
    ok_a = ingest_to_vectorstore(UNI_A_ID, doc_id=101, text=DOC_A_CONTENT)
    if not ok_a:
        print("[FAIL] Ingesting document for University A failed.")
        return False
    print("[SUCCESS] Ingested document for University A.")

    # 2. Ingest document for University B
    print(f"Ingesting document for University B (ID: {UNI_B_ID})...")
    ok_b = ingest_to_vectorstore(UNI_B_ID, doc_id=102, text=DOC_B_CONTENT)
    if not ok_b:
        print("[FAIL] Ingesting document for University B failed.")
        return False
    print("[SUCCESS] Ingested document for University B.")

    # 3. Query University A's collection
    print(f"\nQuerying University A (ID: {UNI_A_ID}) for 'quantum computing'...")
    results_a = retrieve(UNI_A_ID, "quantum computing", k=5)
    print(f"Results returned: {len(results_a)}")
    
    # Assertions for University A
    leak_found_in_a = False
    for res in results_a:
        print(f"  - Chunk [Score: {res['score']}]: {res['text']}")
        if "marine biology" in res['text'] or "Beta University" in res['text']:
            leak_found_in_a = True

    if len(results_a) == 0:
        print("[FAIL] No results returned for University A.")
        return False

    if leak_found_in_a:
        print("[FAIL] Leakage detected! University B's content appeared in University A's results.")
        return False
    else:
        print("[PASS] University A results are properly isolated.")

    # 4. Query University B's collection
    print(f"\nQuerying University B (ID: {UNI_B_ID}) for 'marine biology'...")
    results_b = retrieve(UNI_B_ID, "marine biology", k=5)
    print(f"Results returned: {len(results_b)}")

    # Assertions for University B
    leak_found_in_b = False
    for res in results_b:
        print(f"  - Chunk [Score: {res['score']}]: {res['text']}")
        if "quantum computing" in res['text'] or "Alpha University" in res['text']:
            leak_found_in_b = True

    if len(results_b) == 0:
        print("[FAIL] No results returned for University B.")
        return False

    if leak_found_in_b:
        print("[FAIL] Leakage detected! University A's content appeared in University B's results.")
        return False
    else:
        print("[PASS] University B results are properly isolated.")

    # 5. Cross-tenant retrieval query check
    # Query University A's collection for University B's topic.
    # Because collections are isolated, it should return nothing or irrelevant content, but NOT University B's document.
    print(f"\nCross-querying: Querying University A (ID: {UNI_A_ID}) for 'marine biology'...")
    cross_results = retrieve(UNI_A_ID, "marine biology", k=5)
    print(f"Results returned: {len(cross_results)}")
    
    cross_leak = False
    for res in cross_results:
        print(f"  - Chunk [Score: {res['score']}]: {res['text']}")
        if "marine biology" in res['text'] or "Beta University" in res['text']:
            cross_leak = True

    if cross_leak:
        print("[FAIL] Leakage detected! A search in University A returned University B's document.")
        return False
    else:
        print("[PASS] Cross-tenant query does not leak Beta University's documents.")

    # Cleanup collections
    print("\nCleaning up collections...")
    for uid in [UNI_A_ID, UNI_B_ID]:
        coll_name = f"university_{uid}"
        try:
            client.delete_collection(coll_name)
            print(f"Deleted test collection: {coll_name}")
        except Exception as e:
            print(f"Error deleting collection {coll_name}: {e}")

    print("\n" + "=" * 70)
    print("     ALL TENANT ISOLATION TESTS PASSED SUCCESSFULLY")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
