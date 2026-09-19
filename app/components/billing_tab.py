# app/components/billing_tab.py
"""
app/components/billing_tab.py — Modular SaaS Billing Tab (Linear / Notion aesthetic).

Design principles:
- Calm, neutral, professional typography and cards.
- No nagging popups or flashing alerts.
- Subtle amber indicator only when <= 3 days remain.
- Single unified status card with Plan details, Renewal date, and action buttons.
- Supports both Manual Renewal (Razorpay Payment Link) and Recurring UPI AutoPay.
"""

import streamlit as st
from sqlalchemy.orm import Session
from models.university import University
from models.user import User
from services.billing import (
    get_subscription_summary,
    create_payment_link,
    create_autopay_subscription,
    extend_subscription,
)


def _is_external_checkout_url(url) -> bool:
    return isinstance(url, str) and url.startswith(("https://", "http://"))


def render_billing_tab(db: Session, university: University, user: User) -> None:
    """Render the calm SaaS billing settings tab."""
    # ── Check for payment return query params (Synchronous confirmation) ──────
    payment_id = st.query_params.get("razorpay_payment_id") or st.query_params.get("payment_id")
    if payment_id and not st.session_state.get("payment_processed"):
        extended_uni = extend_subscription(
            db=db,
            university_id=university.id,
            days=30,
            plan_name="Starter Plan",
            payment_id=payment_id,
        )
        if extended_uni:
            st.session_state["payment_processed"] = True
            st.toast("Payment confirmed. Subscription renewed.", icon="✓")
            # Clear query params quietly
            if "razorpay_payment_id" in st.query_params:
                del st.query_params["razorpay_payment_id"]
            if "payment_id" in st.query_params:
                del st.query_params["payment_id"]
            st.rerun()

    # Fetch calm display summary
    info = get_subscription_summary(university)

    st.markdown("<h3>Billing & Subscription</h3>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#71717A; font-size:14px; margin-bottom: 1.75rem;'>"
        "Manage your institution's subscription plan, automated payments, and invoices."
        "</p>",
        unsafe_allow_html=True,
    )

    # ── Current Plan Card (Linear / Notion style) ──────────────────────────────
    card_border = "#E4E4E7"
    if info["urgency"] == "amber":
        card_border = "#FDE68A"

    st.markdown(
        f"""
        <div style="border: 1px solid {card_border}; border-radius: 10px; background: #FFFFFF; padding: 24px; margin-bottom: 24px; box-shadow: 0 1px 2px rgba(0,0,0,0.03);">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px;">
                <div>
                    <span style="font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #A1A1AA;">Current Plan</span>
                    <h2 style="margin: 4px 0 0 0; font-size: 22px; font-weight: 600; color: #18181B;">{info['plan_name']}</h2>
                </div>
                <span style="display: inline-block; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: 500; {info['badge_style']}">
                    {info['status_label']}
                </span>
            </div>
            <div style="border-top: 1px solid #F4F4F5; padding-top: 16px; display: flex; flex-wrap: wrap; gap: 32px;">
                <div>
                    <p style="margin: 0; font-size: 12px; color: #71717A;">Billing Cycle</p>
                    <p style="margin: 2px 0 0 0; font-size: 14px; font-weight: 500; color: #27272A;">Monthly (₹4,999 / mo)</p>
                </div>
                <div>
                    <p style="margin: 0; font-size: 12px; color: #71717A;">Valid Through</p>
                    <p style="margin: 2px 0 0 0; font-size: 14px; font-weight: 500; color: #27272A;">{info['expires_at_formatted']}</p>
                </div>
                <div>
                    <p style="margin: 0; font-size: 12px; color: #71717A;">Time Remaining</p>
                    <p style="margin: 2px 0 0 0; font-size: 14px; font-weight: 500; color: #27272A;">{info['days_left']} days</p>
                </div>
                <div>
                    <p style="margin: 0; font-size: 12px; color: #71717A;">Auto-Pay</p>
                    <p style="margin: 2px 0 0 0; font-size: 14px; font-weight: 500; color: #27272A;">
                        {'Enabled (UPI Mandate)' if info['has_autopay'] else 'Not enabled'}
                    </p>
                </div>
            </div>
            <p style="margin: 16px 0 0 0; font-size: 13px; color: #71717A;">
                {info['subtext']}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Action Buttons ────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns([1.2, 1.2, 2])

    with col1:
        if st.button("Renew Subscription", key="btn_renew_manual", use_container_width=True):
            with st.spinner("Generating payment link..."):
                res = create_payment_link(university, admin_email=user.email)
                if res.get("success"):
                    pay_url = res.get("payment_url")
                    if _is_external_checkout_url(pay_url):
                        st.session_state["active_pay_url"] = pay_url
                    elif res.get("simulated"):
                        st.info(res.get("message", "Payment simulation mode is active."))
                    else:
                        st.error("Razorpay did not return a checkout URL.")
                else:
                    st.error(res.get("error", "Failed to initiate payment."))

    with col2:
        if st.button("Set up Auto-Pay (UPI)", key="btn_setup_autopay", use_container_width=True):
            with st.spinner("Setting up UPI AutoPay mandate..."):
                res = create_autopay_subscription(university, customer_email=user.email)
                if res.get("success"):
                    sub_url = res.get("subscription_url")
                    if _is_external_checkout_url(sub_url):
                        st.session_state["active_sub_url"] = sub_url
                    elif res.get("simulated"):
                        st.info(res.get("message", "AutoPay simulation mode is active. Configure Razorpay keys to authorize a live UPI mandate."))
                    else:
                        st.error("Razorpay did not return an AutoPay authorization URL.")
                else:
                    st.error(res.get("error", "Failed to set up AutoPay."))

    # Display active payment or mandate link calmly if generated
    if not _is_external_checkout_url(st.session_state.get("active_pay_url")):
        st.session_state.pop("active_pay_url", None)
    if not _is_external_checkout_url(st.session_state.get("active_sub_url")):
        st.session_state.pop("active_sub_url", None)

    if "active_pay_url" in st.session_state:
        st.markdown(
            f"""
            <div style="background: #FAFAFA; border: 1px solid #E4E4E7; border-radius: 8px; padding: 16px; margin-top: 16px;">
                <p style="margin: 0 0 8px 0; font-size: 14px; font-weight: 500; color: #18181B;">Complete Payment</p>
                <p style="margin: 0 0 12px 0; font-size: 13px; color: #71717A;">
                    Click below to open Razorpay checkout (UPI, Cards, NetBanking):
                </p>
                <a href="{st.session_state['active_pay_url']}" target="_blank" style="display: inline-block; background: #18181B; color: #FFFFFF; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 500;">
                    Open Razorpay Payment &rarr;
                </a>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if "active_sub_url" in st.session_state:
        st.markdown(
            f"""
            <div style="background: #FAFAFA; border: 1px solid #E4E4E7; border-radius: 8px; padding: 16px; margin-top: 16px;">
                <p style="margin: 0 0 8px 0; font-size: 14px; font-weight: 500; color: #18181B;">Authorize Recurring Mandate</p>
                <p style="margin: 0 0 12px 0; font-size: 13px; color: #71717A;">
                    Authorize your UPI or card mandate via Razorpay to auto-renew every month:
                </p>
                <a href="{st.session_state['active_sub_url']}" target="_blank" style="display: inline-block; background: #18181B; color: #FFFFFF; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 500;">
                    Authorize UPI AutoPay Mandate &rarr;
                </a>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Feature Inclusions ───────────────────────────────────────────────────
    st.markdown(
        """
        <div style="margin-top: 32px; border-top: 1px solid #F4F4F5; padding-top: 24px;">
            <p style="font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #A1A1AA; margin-bottom: 12px;">Plan Features Included</p>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px;">
                <div style="font-size: 13px; color: #52525B;">✓ 24/7 AI Admission & Student Helpdesk</div>
                <div style="font-size: 13px; color: #52525B;">✓ Unlimited Knowledge Base Document Uploads</div>
                <div style="font-size: 13px; color: #52525B;">✓ White-Labeled Student Portal & Custom Logo</div>
                <div style="font-size: 13px; color: #52525B;">✓ Real-time Admission Lead Capture</div>
                <div style="font-size: 13px; color: #52525B;">✓ Multi-Department Support Ticket Routing</div>
                <div style="font-size: 13px; color: #52525B;">✓ 48-Hour Auto-Pay Retry Grace Period</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
