"""
scripts/generate_dataset.py
Generate synthetic FAQs and labeled student queries for two fake universities.
Run from project root: python scripts/generate_dataset.py
"""

import csv
import random
import pathlib
import textwrap

random.seed(42)
DATA_DIR = pathlib.Path("data")
DATA_DIR.mkdir(exist_ok=True)

# ── University definitions ────────────────────────────────────────────────────

UNIVERSITIES = {
    1: {
        "name": "Greenfield Institute of Technology",
        "short": "greenfield",
        "departments": [
            "Computer Science & Engineering",
            "Mechanical Engineering",
            "Electronics & Communication",
            "Civil Engineering",
            "Business Technology Management",
            "Mathematics & Physics",
            "Examination Cell",
            "Finance & Accounts",
            "Hostel Administration",
            "Student Affairs",
            "Library",
            "Career Services",
        ],
        "scholarship_deadline": "March 15",
        "late_fee_grace": "5 days",
        "hostel_checkin": "10:00 PM",
        "revaluation_fee": "₹500 per subject",
        "min_attendance": "75%",
        "exam_fee_last_date": "15th of the exam month",
        "scholarship_amount": "up to ₹80,000 per year",
    },
    2: {
        "name": "Lakeview University",
        "short": "lakeview",
        "departments": [
            "Information Technology",
            "Aerospace Engineering",
            "Electrical Engineering",
            "Architecture & Planning",
            "Liberal Arts & Sciences",
            "Statistics & Data Science",
            "Academic Registry",
            "Bursary Office",
            "Residential Services",
            "Student Welfare",
            "Digital Library",
            "Placement Cell",
        ],
        "scholarship_deadline": "April 30",
        "late_fee_grace": "3 days",
        "hostel_checkin": "9:30 PM",
        "revaluation_fee": "₹750 per subject",
        "min_attendance": "80%",
        "exam_fee_last_date": "10th of the exam month",
        "scholarship_amount": "up to ₹1,00,000 per year",
    },
}

# ── FAQ templates (filled per university) ─────────────────────────────────────

def make_faqs(u):
    d = u["departments"]
    return [
        # Scholarships
        {
            "category": "scholarship",
            "question": f"What is the last date to apply for scholarships at {u['name']}?",
            "answer": f"The scholarship application deadline at {u['name']} is {u['scholarship_deadline']} every academic year. Late applications are not accepted. Visit the Finance/Bursary office for the application form.",
        },
        {
            "category": "scholarship",
            "question": "How much scholarship amount can I receive?",
            "answer": f"Merit-based scholarships at {u['name']} cover {u['scholarship_amount']}. Need-based grants are assessed separately based on family income. Contact {d[7]} for details.",
        },
        {
            "category": "scholarship",
            "question": "What documents are required for the scholarship application?",
            "answer": f"You need: (1) Income certificate, (2) Previous semester marksheet, (3) Bank passbook copy, (4) Aadhaar/ID proof, (5) Bonafide certificate. Submit to {d[7]}.",
        },
        # Attendance
        {
            "category": "attendance",
            "question": "What is the minimum attendance required to appear in exams?",
            "answer": f"Students must maintain a minimum of {u['min_attendance']} attendance in each subject to be eligible for end-semester examinations at {u['name']}.",
        },
        {
            "category": "attendance",
            "question": "Can I get attendance exemption for medical reasons?",
            "answer": f"Yes. Submit a medical certificate from a registered physician to {d[9]} within 7 days of rejoining. Maximum 10% attendance relaxation is granted upon approval.",
        },
        {
            "category": "attendance",
            "question": "Where can I check my attendance percentage?",
            "answer": f"Log in to the {u['name']} student portal at portal.{u['short']}.edu.in and navigate to 'My Attendance'. For discrepancies, contact your department coordinator in {d[0]}.",
        },
        # Exams
        {
            "category": "exams",
            "question": "What is the fee for exam revaluation?",
            "answer": f"The revaluation fee at {u['name']} is {u['revaluation_fee']}. Apply within 15 days of result declaration via the {d[6]} portal.",
        },
        {
            "category": "exams",
            "question": "By when must I pay the examination fee?",
            "answer": f"Examination fees must be paid by the {u['exam_fee_last_date']}. Payments after this date attract a late fine of ₹200. Contact {d[6]} for payment modes.",
        },
        {
            "category": "exams",
            "question": "What happens if I fail in a subject?",
            "answer": f"Failed students can appear in supplementary exams held within 60 days of the main result. Register through {d[6]}. A maximum of two backlogs are permitted in the same semester.",
        },
        {
            "category": "exams",
            "question": "How do I get my grade sheet or transcript?",
            "answer": f"Official transcripts can be requested from {d[6]} by submitting a written application with a fee of ₹250 per copy. Processing takes 5–7 working days.",
        },
        # Hostel / Residential
        {
            "category": "hostel",
            "question": "What is the hostel curfew time?",
            "answer": f"The hostel gate closes at {u['hostel_checkin']} on weekdays and 11:00 PM on weekends. Late entry must be pre-approved by the {d[8]} warden.",
        },
        {
            "category": "hostel",
            "question": "How do I apply for hostel accommodation?",
            "answer": f"Hostel allotment forms are available at {d[8]} and on the student portal. Allotment is based on merit and distance from campus. Apply before June 30 for the upcoming academic year.",
        },
        {
            "category": "hostel",
            "question": "Is Wi-Fi available in the hostel?",
            "answer": f"Yes. {u['name']} provides 24×7 Wi-Fi in all hostel blocks with a 50 Mbps shared connection. Credentials are issued with your hostel allotment letter.",
        },
        # Fees
        {
            "category": "fees",
            "question": "What is the late fee penalty for paying tuition after the due date?",
            "answer": f"{u['name']} allows a grace period of {u['late_fee_grace']} after the due date without penalty. After that, a fine of ₹100 per day is levied. Pay at {d[7]}.",
        },
        {
            "category": "fees",
            "question": "Can I pay tuition fees in instalments?",
            "answer": f"Yes. {u['name']} offers a two-instalment plan: 60% due at the start of the semester and 40% by the midpoint. Submit an instalment request to {d[7]} before the fee due date.",
        },
        {
            "category": "fees",
            "question": "How do I get a fee receipt or payment acknowledgment?",
            "answer": f"Receipts are auto-generated on the student portal after online payment. For cash payments, collect the stamped receipt from {d[7]}. Duplicate receipts cost ₹50.",
        },
        # Library
        {
            "category": "library",
            "question": "How many books can I borrow from the library?",
            "answer": f"Undergraduate students may borrow up to 4 books for 14 days. Postgraduate students may borrow 6 books for 21 days. Late returns attract ₹5 per day fine. Contact {d[10]}.",
        },
        {
            "category": "library",
            "question": "Does the library provide access to online journals?",
            "answer": f"Yes. {u['name']}'s {d[10]} provides access to JSTOR, IEEE Xplore, Elsevier ScienceDirect, and Springer via the student portal. Use your university credentials to log in.",
        },
        # Placement / Career
        {
            "category": "placement",
            "question": "When does the campus placement season begin?",
            "answer": f"The placement season at {u['name']} begins in October for final-year students. Pre-placement talks start in September. Register with {d[11]} before August 31.",
        },
        {
            "category": "placement",
            "question": "What is the eligibility criteria for sitting in placement drives?",
            "answer": f"Students must have a minimum CGPA of 6.0, no active backlogs, and {u['min_attendance']} attendance. Register on the {d[11]} portal at least 2 weeks before a drive.",
        },
    ]


GREENFIELD_FAQS = make_faqs(UNIVERSITIES[1])
LAKEVIEW_FAQS = make_faqs(UNIVERSITIES[2])

# ── Query templates ───────────────────────────────────────────────────────────

INTENT_DEPT_MAP = {
    "scholarship_inquiry":  {"gf": "Finance & Accounts",          "lv": "Bursary Office"},
    "fee_payment":          {"gf": "Finance & Accounts",          "lv": "Bursary Office"},
    "exam_schedule":        {"gf": "Examination Cell",            "lv": "Academic Registry"},
    "hostel_booking":       {"gf": "Hostel Administration",       "lv": "Residential Services"},
    "attendance_policy":    {"gf": "Student Affairs",             "lv": "Student Welfare"},
    "course_registration":  {"gf": "Computer Science & Engineering", "lv": "Information Technology"},
    "library_access":       {"gf": "Library",                     "lv": "Digital Library"},
    "placement_info":       {"gf": "Career Services",             "lv": "Placement Cell"},
    "grievance":            {"gf": "Student Affairs",             "lv": "Student Welfare"},
    "document_request":     {"gf": "Examination Cell",            "lv": "Academic Registry"},
    "admission_query":      {"gf": "Student Affairs",             "lv": "Student Welfare"},
    "revaluation_request":  {"gf": "Examination Cell",            "lv": "Academic Registry"},
}

PRIORITY_MAP = {
    "scholarship_inquiry": "high",
    "fee_payment": "high",
    "exam_schedule": "medium",
    "hostel_booking": "medium",
    "attendance_policy": "medium",
    "course_registration": "medium",
    "library_access": "low",
    "placement_info": "low",
    "grievance": "high",
    "document_request": "medium",
    "admission_query": "medium",
    "revaluation_request": "high",
}

# Variations: list of (template_fn, intent)
def q_templates(u_key, u):
    """Return list of (query_text, intent) for a given university config."""
    sd = u["scholarship_deadline"]
    la = u["min_attendance"]
    rv = u["revaluation_fee"]
    lf = u["late_fee_grace"]
    ci = u["hostel_checkin"]
    sa = u["scholarship_amount"]

    templates = []

    # scholarship_inquiry (25 variants)
    scholarship_variants = [
        f"when is the last date to apply for scholarship at {u['name']}?",
        f"what is the scholarship deadline this year",
        f"can you tell me the scolarship deadline plz",
        f"i want to know about scholarship last date",
        f"scholarship application kab band hoti hai",
        f"Is the scholarship deadline still {sd}?",
        f"Did the scholarship deadline get extended?",
        f"How much scholarship can I get from {u['name']}?",
        f"what is the max scholarship amount available",
        f"scholarship kitni milegi mujhe",
        f"What documents do I need for scholarship?",
        f"docs required for scholarship application pls tell",
        f"need docs list for scholrship form filling",
        f"Can I apply for scholarship after {sd}?",
        f"missed scholarship deadline is there any extension",
        f"scholarship nahi mili abhi tak kya karun",
        f"who processes scholarship applications",
        f"which office handles scholarship at {u['name']}",
        f"is merit scholarship different from need-based grant",
        f"What's the income limit for scholarship eligibility?",
        f"Need help with scholarship form",
        f"scholarship form kahan se milegi",
        f"My scholarship got rejected, what to do?",
        f"scholarship rejected reason kya hoga",
        f"can I renew my scholarship next year",
    ]
    templates += [(v, "scholarship_inquiry") for v in scholarship_variants]

    # fee_payment (25 variants)
    fee_variants = [
        f"when is the tuition fee due this semester",
        f"fee jama karne ki last date kya hai",
        f"is there a late fee penalty after due date",
        f"how many days grace period for fee payment",
        f"late fee kitni lagti hai",
        f"can fees be paid in installments",
        f"i want to pay fee in two parts is it possible",
        f"instalment option hai kya fees ke liye",
        f"how to get fee receipt online",
        f"fee receipt nahi mili portal pe",
        f"duplicate fee receipt kaise milegi",
        f"accepted payment modes for fee",
        f"can i pay fees by UPI or credit card",
        f"online payment kaise karte hain fees ka",
        f"fee not reflecting in portal after payment",
        f"paid fees but portal still shows due",
        f"hostel fee alag se bharna hoga kya",
        f"Is mess fee included in hostel charges?",
        f"annual fee structure kya hai",
        f"total fees for one year",
        f"fee waiver possible for economically weak students",
        f"my family can't afford fees right now",
        f"partial fee payment allowed?",
        f"when exactly does late fee start after {lf} grace",
        f"How much is the late fine per day?",
    ]
    templates += [(v, "fee_payment") for v in fee_variants]

    # exam_schedule (20 variants)
    exam_variants = [
        f"when are the end semester exams",
        f"exam schedule kab aayega",
        f"date sheet kab release hoti hai",
        f"how do i know my exam timetable",
        f"where can I find the exam schedule",
        f"exam fee last date kya hai",
        f"what is the exam fee payment deadline",
        f"how to pay exam fee online",
        f"what happens if i miss the exam fee deadline",
        f"can I appear in exam without paying fee",
        f"re-exam schedule kab hoga",
        f"supplementary exam dates",
        f"back paper exam kab hoga",
        f"how to apply for supplementary exam",
        f"exam hall ticket kaise download karein",
        f"admit card download karna hai",
        f"where to get hall ticket",
        f"exam centre kahan hoga",
        f"what items can i bring to examination hall",
        f"is calculator allowed in maths exam",
    ]
    templates += [(v, "exam_schedule") for v in exam_variants]

    # hostel_booking (20 variants)
    hostel_variants = [
        f"how do I apply for hostel",
        f"hostel allotment kaise hoti hai",
        f"hostel application form kahan milega",
        f"is hostel available for first year students",
        f"what is the hostel fee",
        f"hostel mein wifi hai kya",
        f"what time does hostel gate close",
        f"hostel curfew time kya hai",
        f"late entry hostel mein possible hai kya",
        f"kya hostel mein guests aa sakte hain",
        f"visitor policy in hostel",
        f"hostel room change request karna hai",
        f"can I change my hostel room",
        f"mess food quality complaint kaise dun",
        f"hostel warden se complaint kaise karein",
        f"is AC available in hostel rooms",
        f"hostel mein laundry facility hai kya",
        f"how many students per hostel room",
        f"single room available in hostel",
        f"hostel check-in time kya hai arriving at {ci}",
    ]
    templates += [(v, "hostel_booking") for v in hostel_variants]

    # attendance_policy (20 variants)
    att_variants = [
        f"what is minimum attendance required",
        f"kitni attendance required hoti hai exams ke liye",
        f"i have {la} attendance is that enough",
        f"attendance kam hai kya karun",
        f"medical leave pe attendance relax hogi kya",
        f"how to apply for attendance exemption",
        f"medical certificate kahan submit karein",
        f"attendance portal pe nahi dikh rahi",
        f"attendance mismatch in portal how to correct",
        f"proxy attendance allowed hai kya",
        f"what is detain policy for low attendance",
        f"agar attendance {la} se kam ho toh kya hoga",
        f"can I check my attendance subject wise",
        f"subject wise attendance kaise dekhein",
        f"attendance shortage letter kaise milega",
        f"condonation of shortage of attendance process",
        f"how many leaves can I take in a semester",
        f"sports event pe gaya tha attendance count hogi",
        f"if I attend college event will it count as attendance",
        f"attendance update hone mein kitna time lagta hai",
    ]
    templates += [(v, "attendance_policy") for v in att_variants]

    # placement_info (18 variants)
    place_variants = [
        f"when does placement season start at {u['name']}",
        f"placement ke liye register kaise karein",
        f"eligibility criteria for campus placements",
        f"minimum CGPA for placement",
        f"which companies come for placement",
        f"highest package offered last year",
        f"placement cell contact number",
        f"internship opportunities through placement cell",
        f"off-campus placement support milti hai kya",
        f"resume building workshop kab hoga",
        f"mock interview sessions available",
        f"placement registration last date",
        f"can third year students sit in placements",
        f"backlog hai toh placement mil sakti hai",
        f"dress code for placement drive",
        f"which department handles placements",
        f"previous year placement statistics kahan dekhein",
        f"how many students got placed last year",
    ]
    templates += [(v, "placement_info") for v in place_variants]

    # revaluation_request (18 variants)
    reval_variants = [
        f"how to apply for revaluation",
        f"revaluation fee kya hai",
        f"revaluation ke liye apply karne ki last date",
        f"result ke baad revaluation kab hoti hai",
        f"revaluation application kahan jama karein",
        f"can I apply for photocopy of answer sheet",
        f"answer sheet photocopy process",
        f"revaluation se marks badh sakte hain kya",
        f"can revaluation reduce my marks",
        f"result change hone mein kitna time lagta hai after revaluation",
        f"grace marks policy kya hai",
        f"how many grace marks allowed",
        f"what if revaluation result is same",
        f"revaluation rejected what to do",
        f"challenge valuation possible hai kya",
        f"I disagree with my result what can I do",
        f"marks totalling error lag raha hai",
        f"wrong marks added in result sheet",
    ]
    templates += [(v, "revaluation_request") for v in reval_variants]

    # library_access (15 variants)
    lib_variants = [
        f"how many books can I borrow from library",
        f"library mein kitni books mil sakti hain",
        f"return date extend ho sakti hai kya",
        f"late return fine kya hai library mein",
        f"library timing kya hai",
        f"is library open on weekends",
        f"online journals access kaise karein",
        f"IEEE access student portal pe hai kya",
        f"library membership renewal process",
        f"no dues certificate library se chahiye",
        f"book reservation possible hai kya",
        f"can I reserve a book that is currently issued",
        f"reference section mein books issue hoti hain kya",
        f"library card kho gayi kya karein",
        f"digital library access from home",
    ]
    templates += [(v, "library_access") for v in lib_variants]

    # grievance (15 variants)
    griev_variants = [
        f"I want to file a complaint against a faculty member",
        f"complaint kaise darj karein",
        f"ragging complaint kahan karein",
        f"who handles student grievances",
        f"how to escalate an unresolved complaint",
        f"meri problem ka koi solution nahi de raha",
        f"fees wrongly deducted complaint",
        f"hostel warden ne galat fine laga di",
        f"faculty giving partiality in marks",
        f"discrimination complaint kaise karein",
        f"sexual harassment complaint process",
        f"ICC committee contact",
        f"anonymous complaint dene ka option hai kya",
        f"grievance portal link kya hai",
        f"how long does grievance resolution take",
    ]
    templates += [(v, "grievance") for v in griev_variants]

    # document_request (14 variants)
    doc_variants = [
        f"bonafide certificate kaise milegi",
        f"how to get bonafide certificate",
        f"migration certificate process",
        f"character certificate ke liye apply karna hai",
        f"transcript request kaise karein",
        f"official transcript for abroad application",
        f"duplicate marksheet kaise milegi",
        f"TC transfer certificate apply karna hai",
        f"medium of instruction certificate chahiye",
        f"gap year certificate process",
        f"NOC for internship kahan se milegi",
        f"document verification for job",
        f"how many days for document processing",
        f"urgent bonafide possible hai kya",
    ]
    templates += [(v, "document_request") for v in doc_variants]

    # course_registration (10 variants)
    course_variants = [
        f"how to register for elective subjects",
        f"elective selection deadline kya hai",
        f"course add drop last date",
        f"can I change my elective after registration",
        f"open elective list kahan milegi",
        f"minimum credit requirement per semester",
        f"how many credits can I register for",
        f"audit course kaise register karein",
        f"can I take courses from another department",
        f"course registration portal link",
    ]
    templates += [(v, "course_registration") for v in course_variants]

    # admission_query (10 variants)
    adm_variants = [
        f"admission process for postgraduate programs",
        f"PG admission eligibility criteria",
        f"lateral entry admission kaise hoti hai",
        f"entrance exam required for admission",
        f"direct admission available kya hai",
        f"admission counselling dates",
        f"foreign national admission process",
        f"NRI quota admission details",
        f"management quota seats available",
        f"admission form fill karne ki last date",
    ]
    templates += [(v, "admission_query") for v in adm_variants]

    return templates


# ── Generate query rows ────────────────────────────────────────────────────────

def build_query_rows():
    rows = []
    for uid, u in UNIVERSITIES.items():
        key = "gf" if uid == 1 else "lv"
        templates = q_templates(key, u)

        # We need exactly 200 per university; sample with replacement if needed
        pool = templates * 4  # expand pool
        selected = random.sample(pool, 200)

        for (qtext, intent) in selected:
            dept = INTENT_DEPT_MAP[intent][key]
            priority = PRIORITY_MAP[intent]
            rows.append({
                "university_id": uid,
                "university_name": u["name"],
                "query_text": qtext,
                "intent": intent,
                "department": dept,
                "priority": priority,
            })

    random.shuffle(rows)
    return rows


# ── Write files ────────────────────────────────────────────────────────────────

def write_faq_csv(path, faqs):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["category", "question", "answer"])
        writer.writeheader()
        writer.writerows(faqs)
    print(f"  Wrote {len(faqs)} FAQ rows -> {path}")


def write_queries_csv(path, rows):
    fields = ["university_id", "university_name", "query_text", "intent", "department", "priority"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Wrote {len(rows)} query rows -> {path}")


def write_notes(path):
    notes = textwrap.dedent("""\
    # Dataset Notes — Synthetic Data for University Query System

    ## Overview
    This dataset was **synthetically generated** for prototype evaluation and
    multi-tenancy testing of the University Query Management System.
    It does NOT represent real institutions, students, or policies.

    ## Universities
    | ID | Name | Scholarship Deadline | Min Attendance | Revaluation Fee |
    |----|------|----------------------|----------------|-----------------|
    | 1  | Greenfield Institute of Technology | March 15 | 75% | ₹500/subject |
    | 2  | Lakeview University                | April 30 | 80% | ₹750/subject |

    Key policy differences are intentional — they validate that the retrieval
    pipeline returns university-specific answers and does not cross-contaminate
    tenants.

    ## Files
    | File | Description | Rows |
    |------|-------------|------|
    | `greenfield_faqs.csv` | 20 Q&A pairs for Greenfield Institute of Technology | 20 |
    | `lakeview_faqs.csv`   | 20 Q&A pairs for Lakeview University | 20 |
    | `queries_labeled.csv` | 400 synthetic student queries (200 per university) | 400 |

    ## FAQ Schema
    ```
    category   — topic area (scholarship / attendance / exams / hostel / fees / library / placement)
    question   — student-facing question text
    answer     — official university answer text
    ```

    ## Query Schema
    ```
    university_id   — 1 = Greenfield, 2 = Lakeview
    university_name — full university name
    query_text      — raw student query (mixed formal/informal/Hindi-English/typos)
    intent          — one of: scholarship_inquiry, fee_payment, exam_schedule,
                      hostel_booking, attendance_policy, course_registration,
                      library_access, placement_info, grievance, document_request,
                      admission_query, revaluation_request
    department      — target department that should handle the query
    priority        — low / medium / high
    ```

    ## Generation Process
    - FAQs were hand-authored with distinct per-university details
      (deadlines, amounts, grace periods, curfew times) to stress-test
      tenant isolation in the vector store.
    - Queries were generated from 200+ phrase templates covering 12 intent
      categories, then sampled to 200 per university using `random.seed(42)`
      for reproducibility.
    - Phrasing intentionally varies: formal English, informal English,
      Hinglish (Hindi-English code-switching), and common typos.
    - Priority is rule-based on intent (grievance/fee/scholarship = high;
      library/placement = low; others = medium).

    ## Usage
    - **FAQ CSVs** → ingest into ChromaDB via `services/ingestion.py`
    - **queries_labeled.csv** → use as evaluation set for intent classifier
      or retrieval benchmarks
    - **Tenant isolation test** → run `scripts/test_ingestion.py`

    > ⚠️ **This is entirely synthetic data created for testing purposes only.**
    > No real student, faculty, or institutional data is present.
    """)
    path.write_text(notes, encoding="utf-8")
    print(f"  Wrote dataset notes -> {path}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\nGenerating synthetic dataset...")

    write_faq_csv(DATA_DIR / "greenfield_faqs.csv", make_faqs(UNIVERSITIES[1]))
    write_faq_csv(DATA_DIR / "lakeview_faqs.csv",   make_faqs(UNIVERSITIES[2]))

    rows = build_query_rows()
    write_queries_csv(DATA_DIR / "queries_labeled.csv", rows)

    write_notes(DATA_DIR / "DATASET_NOTES.md")

    # Quick stats
    from collections import Counter
    uid_counts = Counter(r["university_id"] for r in rows)
    intent_counts = Counter(r["intent"] for r in rows)
    print(f"\nQuery distribution by university: {dict(uid_counts)}")
    print("Intent distribution:")
    for intent, count in sorted(intent_counts.items()):
        print(f"  {intent:<25} {count}")
    print("\nDone. All files saved to /data/")
