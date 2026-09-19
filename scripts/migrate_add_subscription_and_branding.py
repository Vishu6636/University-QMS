#!/usr/bin/env python
# scripts/migrate_add_subscription_and_branding.py
"""
Additive migration: Adds logo_url, subscription_status, subscription_plan,
trial_ends_at, subscription_expires_at, razorpay_customer_id, and
razorpay_subscription_id to the universities table.

Supports both SQLite and PostgreSQL. Idempotent and safe to run multiple times.
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from sqlalchemy import inspect, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from models.base import engine, SessionLocal
from models.university import University

COLUMNS_TO_ADD = [
    ("logo_url", "VARCHAR(500)"),
    ("subscription_status", "VARCHAR(50) DEFAULT 'trial'"),
    ("subscription_plan", "VARCHAR(100) DEFAULT '14-Day Free Trial'"),
    ("trial_ends_at", "TIMESTAMP"),
    ("subscription_expires_at", "TIMESTAMP"),
    ("razorpay_customer_id", "VARCHAR(100)"),
    ("razorpay_subscription_id", "VARCHAR(100)"),
]


def run_migration() -> None:
    print(f"Connecting to database: {engine.url}")
    inspector = inspect(engine)
    existing_cols = {col["name"] for col in inspector.get_columns("universities")}

    with engine.begin() as conn:
        for col_name, col_type in COLUMNS_TO_ADD:
            if col_name not in existing_cols:
                print(f"[+] Adding column: {col_name} ({col_type})")
                conn.execute(text(f"ALTER TABLE universities ADD COLUMN {col_name} {col_type}"))
            else:
                print(f"[-] Column already exists: {col_name}")

    # Backfill existing records with a default 14-day trial if unset
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        trial_end = now + timedelta(days=14)
        unis = db.query(University).all()
        for u in unis:
            updated = False
            if not u.subscription_status:
                u.subscription_status = "trial"
                updated = True
            if not u.subscription_plan:
                u.subscription_plan = "14-Day Free Trial"
                updated = True
            if not u.trial_ends_at:
                u.trial_ends_at = trial_end
                updated = True
            if not u.subscription_expires_at:
                u.subscription_expires_at = trial_end
                updated = True
            if updated:
                print(f"[~] Initialised 14-day trial for: {u.name}")
        db.commit()
    finally:
        db.close()
    print("[SUCCESS] Migration completed successfully.")


if __name__ == "__main__":
    run_migration()
