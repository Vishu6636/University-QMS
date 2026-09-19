#!/usr/bin/env python
# scripts/quick_onboard_college.py
"""
Quick Onboarding CLI Tool.

Usage:
    python scripts/quick_onboard_college.py --name "CIPET Lucknow" --website "cipet.gov.in" --email "director@cipet.gov.in"
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from models.base import SessionLocal
from services.onboarding import create_tenant_with_trial


def main():
    parser = argparse.ArgumentParser(description="Quick Onboard a College into UQMS")
    parser.add_argument("--name", required=True, help="Full College / University Name")
    parser.add_argument("--website", required=True, help="Official Website URL (e.g. cipet.gov.in)")
    parser.add_argument("--email", required=True, help="Admin / Director Email")
    parser.add_argument("--admin-name", default=None, help="Director / Admin Name")
    parser.add_argument("--trial-days", type=int, default=14, help="Trial duration in days")

    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = create_tenant_with_trial(
            db=db,
            name=args.name,
            website=args.website,
            admin_email=args.email,
            admin_name=args.admin_name,
            trial_days=args.trial_days,
        )

        print("\n" + "=" * 60)
        print("          TENANT ONBOARDED SUCCESSFULLY")
        print("=" * 60)
        print(f"College Name     : {result['name']}")
        print(f"Tenant Slug      : {result['slug']}")
        print(f"Auto-Fetched Logo: {result['logo_url']}")
        print(f"Trial Expiry     : {result['trial_ends_at']} (14 Days)")
        print("-" * 60)
        print(f"Admin Email      : {result['admin_email']}")
        if result['temp_password']:
            print(f"Admin Password   : {result['temp_password']}")
        else:
            print(f"Admin Password   : (Existing user account used)")
        print("-" * 60)
        print(f"Live Student Link: {result['public_test_url']}")
        print(f"Admin Login Link : {result['admin_login_url']}")
        print("=" * 60 + "\n")

    finally:
        db.close()


if __name__ == "__main__":
    main()
