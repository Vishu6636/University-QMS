"""
scripts/ingest_faqs.py
Reads the synthetic FAQ CSVs and ingests them into ChromaDB
using services/ingestion.py so the RAG pipeline has data.

University IDs:
  1 = Greenfield Institute of Technology  -> data/greenfield_faqs.csv
  2 = Lakeview University                 -> data/lakeview_faqs.csv

Usage (from project root):
    python scripts/ingest_faqs.py
"""
import sys, pathlib, csv
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from services.ingestion import ingest_to_vectorstore

FILES = [
    (1, "Greenfield Institute of Technology", pathlib.Path("data/greenfield_faqs.csv")),
    (2, "Lakeview University",                pathlib.Path("data/lakeview_faqs.csv")),
]

for uid, uname, fpath in FILES:
    print(f"\nIngesting {fpath.name} -> university_id={uid} ({uname})")
    with open(fpath, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for i, row in enumerate(rows):
        # Combine Q+A as a single chunk so both are searchable
        text = f"Q: {row['question']}\nA: {row['answer']}"
        ok = ingest_to_vectorstore(uid, doc_id=uid * 1000 + i, text=text)
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {row['category']:15s} | {row['question'][:60]}")

print("\nIngestion complete.")
