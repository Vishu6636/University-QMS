# UQMS Operations & Deployment Cheat Sheet

This guide contains every shortcut command, script, and template created for your white-label branding, automated onboarding, and SaaS billing system.

---

## 1. Quick Terminal Commands

### A. Push Updates from Local Laptop to GitHub
Run this in PowerShell on your local machine:
```powershell
git add .
git commit -m "Add white-label branding, SaaS billing tab, automated onboarding, and Groq model updates"
git push origin main
```

### B. Pull and Update on AWS Server (Live)
Run this inside your SSH terminal on AWS:
```bash
cd University-QMS
git pull origin main

# If running via Docker:
docker compose down && docker compose up -d --build

# Or if running Streamlit directly / systemctl:
sudo systemctl restart uqms
```

---

## 2. Onboard Any College in 10 Seconds (Automated)

Run this whenever you want to prepare a custom AI portal for a new college:
```bash
python scripts/quick_onboard_college.py --name "College Name" --website "collegedomain.edu.in" --email "director@collegedomain.edu.in"
```

**Example (CIPET Lucknow):**
```bash
python scripts/quick_onboard_college.py --name "CIPET Lucknow" --website "cipet.gov.in" --email "director@cipet.gov.in"
```

**What it automatically produces:**
- **Live Student Test Link:** `https://uqms-portal.duckdns.org?uni=cipet-lucknow`
- **College Admin Email:** `director@cipet.gov.in`
- **Generated Password:** (Printed to your screen)
- **Official Logo:** Auto-scraped and saved to the database.
- **Trial Period:** 14 days active immediately.

---

## 3. High-Converting WhatsApp Hook Template

Copy and paste this message directly to the college Director or Admissions Head:

```text
Respected Director Sir, to save your time, I have already pre-configured {{ College Name }}'s 24/7 AI Admission & Student Helpdesk with your official prospectus.

Test it on your phone right now:
👉 https://uqms-portal.duckdns.org?uni={{ college-slug }}
(Try asking it: "What is the B.Tech fee structure and refund policy?")

Your 14-day test portal is active. You can log into your administrative management portal at https://uqms-portal.duckdns.org with:
Username: {{ admin_email }}
Password: {{ admin_password }}

Can I assist you with any questions while you test?
```

---

## 4. Run the FastAPI Webhook Receiver (Optional for UPI AutoPay)

To receive automated recurring payment events from Razorpay in the background:
```bash
python services/webhook_server.py --port 8000
```
Interactive Swagger API documentation is available at:
`http://localhost:8000/docs`

---

## 5. What Manual Steps Are Left For You?

### Step 1: Push code to AWS (5 minutes)
Run Section 1A on your laptop and Section 1B on AWS so your live AWS instance shows the new **"Billing & Plan"** tab and the white-label branding.

### Step 2: Upload College Prospectus PDF (1 minute per college)
1. Go to `https://uqms-portal.duckdns.org`.
2. Log in using the admin account created in Section 2.
3. Click **"Document Upload"** in the sidebar.
4. Drag and drop the college's admission brochure/fee PDF.
*(ChromaDB indexes it in ~30 seconds)*.

### Step 3: Configure Razorpay Keys (When ready for real money)
When you are ready to collect real payments:
1. Log into your free [Razorpay Dashboard](https://dashboard.razorpay.com).
2. Generate your **API Key ID** and **Key Secret**.
3. Add them to your `.env` file on AWS:
   ```env
   RAZORPAY_KEY_ID=your_razorpay_key_id
   RAZORPAY_KEY_SECRET=your_razorpay_key_secret
   RAZORPAY_WEBHOOK_SECRET=your_razorpay_webhook_secret
   ```
*(Until then, the system runs safely in simulation mode with zero errors)*.
