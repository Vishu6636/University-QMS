# services/webhook_server.py
"""
services/webhook_server.py — FastAPI Webhook & Verification Server for Razorpay.

Built for high reliability, automatic error recovery, and systemd/Uvicorn hosting:
- Built-in payload validation prevents malformed requests from crashing the process.
- Header-based signature extraction with cryptographic HMAC-SHA256 verification.
- Handles asynchronous background events:
    - 'payment_link.paid' (manual renewal)
    - 'subscription.charged' (UPI AutoPay recurring debit)
    - 'subscription.activated'
- Centralized payment verification endpoint for client redirects.

Production Deployment (AWS EC2):
--------------------------------
1. Systemd Service (/etc/systemd/system/uqms-webhook.service):
    [Unit]
    Description=UQMS Razorpay Webhook Service
    After=network.target

    [Service]
    User=ubuntu
    WorkingDirectory=/home/ubuntu/University-QMS
    ExecStart=/home/ubuntu/University-QMS/.venv/bin/uvicorn services.webhook_server:app --host 127.0.0.1 --port 8000 --workers 2
    Restart=always
    RestartSec=5

    [Install]
    WantedBy=multi-user.target

2. Nginx Reverse Proxy (/etc/nginx/sites-available/default):
    location /api/webhook/razorpay {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

Usage (Local / Testing):
    python services/webhook_server.py --port 8000
    or
    uvicorn services.webhook_server:app --port 8000 --reload
"""

import os
import sys
import json
import logging
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from models.base import SessionLocal
from models.university import University
from services.billing import (
    verify_webhook_signature,
    extend_subscription,
    get_subscription_summary,
    coerce_notes_dict,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [FastAPI Webhook] %(message)s",
)
logger = logging.getLogger("RazorpayWebhook")

app = FastAPI(
    title="UQMS Razorpay Webhook API",
    description="Dedicated micro-service for Razorpay asynchronous webhooks and payment verification.",
    version="1.0.0",
)

# Enable CORS for cross-origin callbacks if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    """Database session dependency for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
@app.get("/")
def health_check():
    """Service health check endpoint."""
    return {
        "status": "online",
        "service": "UQMS Razorpay Webhook API",
        "engine": "FastAPI + Uvicorn",
    }


@app.post("/api/webhook/razorpay")
async def handle_razorpay_webhook(request: Request, db=Depends(get_db)):
    """
    Handle incoming Razorpay webhooks with signature verification.
    Processes:
      - payment_link.paid / payment.captured
      - subscription.charged / subscription.activated
    """
    # 1. Extract raw body bytes (required for signature verification)
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    if not signature:
        logger.warning("Rejected webhook: Missing X-Razorpay-Signature header")
        raise HTTPException(status_code=400, detail="Missing X-Razorpay-Signature header")

    # 2. Cryptographically verify signature
    if not verify_webhook_signature(raw_body, signature):
        logger.warning("Rejected webhook: Invalid HMAC-SHA256 signature")
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    # 3. Parse JSON payload
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        logger.error("Failed to parse JSON body: %s", str(e))
        raise HTTPException(status_code=400, detail="Malformed JSON body")

    event = payload.get("event")
    logger.info("Received valid Razorpay event: %s", event)

    try:
        # Event Type A: Payment Link Paid (Manual Renewal)
        if event in ("payment_link.paid", "payment.captured"):
            payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
            notes = coerce_notes_dict(payment_entity.get("notes"))
            uni_id_str = notes.get("university_id")
            uni_slug = notes.get("university_slug")
            payment_id = payment_entity.get("id")

            uni = None
            if uni_id_str and str(uni_id_str).isdigit():
                uni = db.query(University).filter(University.id == int(uni_id_str)).first()
            elif uni_slug:
                uni = db.query(University).filter(University.slug == uni_slug).first()

            if uni:
                extend_subscription(
                    db=db,
                    university_id=uni.id,
                    days=30,
                    plan_name="Starter Plan",
                    payment_id=payment_id,
                )
                logger.info("Extended subscription (+30 days) for %s (payment_id=%s)", uni.name, payment_id)
                return {"status": "success", "event": event, "university": uni.name, "action": "extended"}
            else:
                logger.warning("No university found matching notes: id=%s slug=%s", uni_id_str, uni_slug)

        # Event Type B: Subscription Charged (Recurring UPI AutoPay Renewal)
        elif event in ("subscription.charged", "subscription.activated"):
            sub_entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
            sub_id = sub_entity.get("id")
            notes = coerce_notes_dict(sub_entity.get("notes"))
            uni_id_str = notes.get("university_id")

            uni = None
            if uni_id_str and str(uni_id_str).isdigit():
                uni = db.query(University).filter(University.id == int(uni_id_str)).first()
            elif sub_id:
                uni = db.query(University).filter(University.razorpay_subscription_id == sub_id).first()

            if uni:
                extend_subscription(
                    db=db,
                    university_id=uni.id,
                    days=30,
                    plan_name="Starter Plan (Auto-Pay)",
                    subscription_id=sub_id,
                )
                logger.info("Processed recurring AutoPay renewal (+30 days) for %s (sub_id=%s)", uni.name, sub_id)
                return {"status": "success", "event": event, "university": uni.name, "action": "auto_renewed"}
            else:
                logger.warning("No university found matching subscription notes: sub_id=%s", sub_id)

    except Exception as e:
        logger.error("Error applying subscription extension: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error applying renewal")

    return {"status": "acknowledged", "event": event}


@app.get("/api/verify-payment")
def verify_payment_endpoint(
    payment_id: str = Query(..., description="Razorpay payment ID"),
    uni_slug: str = Query(..., description="University tenant slug"),
    db=Depends(get_db),
):
    """
    Centralized payment verification endpoint for client redirects.
    Can be called by Streamlit or external redirect pages to confirm payment status.
    """
    uni = db.query(University).filter(University.slug == uni_slug).first()
    if not uni:
        raise HTTPException(status_code=404, detail="University not found")

    extended_uni = extend_subscription(
        db=db,
        university_id=uni.id,
        days=30,
        plan_name="Starter Plan",
        payment_id=payment_id,
    )

    if not extended_uni:
        raise HTTPException(status_code=500, detail="Failed to extend subscription")

    summary = get_subscription_summary(extended_uni)
    return {
        "status": "success",
        "university": extended_uni.name,
        "subscription_status": extended_uni.subscription_status,
        "expires_at": summary["expires_at_formatted"],
        "days_left": summary["days_left"],
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Start UQMS Razorpay Webhook Server")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--host", default="0.0.0.0", help="Host IP to bind to (default: 0.0.0.0)")
    args = parser.parse_args()

    uvicorn.run(
        "services.webhook_server:app",
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
