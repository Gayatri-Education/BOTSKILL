# BOTSKILL v3.0 — Complete User Onboarding & Operations Guide

> **Enterprise Local-First Email Co-Pilot & Policy Governance Engine**  
> *Zero Cloud Egress • 100% Offline Local SLM Inference • Windows Outlook COM Integration • Policy-Grounded Draft Staging*

---

## 1. System Overview & The 4 Architectural Pillars

BOTSKILL is an autonomous email co-pilot designed for high-compliance enterprise environments. Unlike cloud-based email bots that transmit proprietary correspondence and confidential internal policies to third-party APIs, BOTSKILL operates **completely on your local Windows workstation**.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        BOTSKILL v3.0 ARCHITECTURE                       │
├──────────────────┬──────────────────┬──────────────────┬───────────────┤
│ 1. LOCAL OUTLOOK │ 2. NATIVE SLM    │ 3. DOCUMENT      │ 4. DECLUTTERED│
│    MAPI/COM      │    INTELLIGENCE  │    INTELLIGENCE  │    WORKSTATION│
├──────────────────┼──────────────────┼──────────────────┼───────────────┤
│ • Direct COM/MAPI│ • Offline CPU SLM│ • PDF, DOCX, TXT │ • Clean HUD   │
│   integration    │   Qwen2.5-0.5B   │   & CSV parser   │   ergonomics  │
│ • Multi-account  │ • Zero cloud     │ • Typed rules &  │ • Review queue│
│   discovery      │   egress bound   │   citations      │   with diffs  │
│ • Non-negotiable │ • Sub-250ms      │ • Deterministic  │ • Emergency   │
│   DRAFT_ONLY mode│   CPU latency    │   policy engine  │   Kill Switch │
└──────────────────┴──────────────────┴──────────────────┴───────────────┘
```

---

## 2. Hardware & System Prerequisites

Before running BOTSKILL, ensure your Windows machine meets the following baseline requirements:

| Component | Minimum Requirement | Recommended |
|---|---|---|
| **Operating System** | Windows 10 (64-bit) or Windows 11 | Windows 11 Pro (64-bit) |
| **Python** | Python 3.12 (64-bit) with `pip` | Python 3.12.10 |
| **RAM** | 4 GB system memory | 8 GB or higher (Local SLM uses ~680 MB RAM) |
| **CPU** | Dual-core x86_64 processor | Quad-core Intel Core i5/i7 or AMD Ryzen |
| **Email Client** | Microsoft Outlook desktop (with at least 1 configured MAPI account) | Outlook 2016 / 2019 / 2021 / Office 365 |
| **Local SLM Model** | `qwen2.5-0.5b-instruct-q4_k_m.gguf` (491 MB) placed in `models/` | Pre-downloaded offline GGUF |

---

## 3. Installation & Download Guide

### Step 1: Clone or Extract the Repository
Open PowerShell and navigate to your desired workspace directory:
```powershell
cd C:\Users\user\Desktop\gayatri
git clone https://github.com/aivara/botskill.git Botskill
cd Botskill
```

### Step 2: Verify Python Environment
Ensure Python 3.12 is in your system PATH:
```powershell
python --version
# Output should be: Python 3.12.x
```

### Step 3: Install Required Dependencies
Run `pip` to install the local production dependencies:
```powershell
pip install -e .
```
Key packages include:
- `llama-cpp-python` (Offline CPU inference engine)
- `pywin32` (Windows COM / Outlook MAPI automation)
- `fastapi` & `uvicorn` (Loopback dashboard API)
- `pydantic` (Typed domain models and schema verification)
- `playwright` (Automated browser testing and demo recording)
- `pytest` (Verification suite)

### Step 4: Verify Local Model Placement
Verify that the quantized GGUF model exists at `models/qwen2.5-0.5b-instruct-q4_k_m.gguf`:
```powershell
Test-Path models\qwen2.5-0.5b-instruct-q4_k_m.gguf
# Should return: True (491 MB)
```
*(If missing, copy the pre-downloaded GGUF from `C:\Users\user\Desktop\gayatri\gayatriailocal\models` into `models/`)*.

---

## 4. How to Launch BOTSKILL

BOTSKILL provides three convenient launch options:

### Option A: The One-Click Windows Launcher (Recommended)
Double-click `run_botskill.bat` in the repository root, or execute via PowerShell:
```powershell
.\run_botskill.bat
```
**What happens behind the scenes:**
1. Validates Python 3.12 and required dependencies.
2. Automatically bootstraps directories: `data/`, `logs/`, `models/`, `snapshots/`.
3. Runs the SQLite startup crash recovery sequence (`PRAGMA integrity_check`, `PRAGMA wal_checkpoint(TRUNCATE)`).
4. Launches the FastAPI workstation server bound strictly to loopback (`127.0.0.1:8765`).
5. Opens the interactive web dashboard in your default browser.

### Option B: The Unified CLI (`botskill`)
BOTSKILL includes a full-featured command-line interface:
```powershell
$env:PYTHONPATH="src"

# Probe connected Outlook accounts
python -m botskill.cli accounts list

# Sync incoming emails from all accounts
python -m botskill.cli accounts sync

# Check local SLM model health and memory profile
python -m botskill.cli ai status

# List pending drafts in the review queue
python -m botskill.cli drafts list

# Safely stage a draft to Outlook's Drafts folder
python -m botskill.cli drafts stage <draft_id>

# Emergency Stop: Immediately lock all operations
python -m botskill.cli autonomy kill
```

---

## 5. Connecting with Microsoft Outlook

BOTSKILL connects natively to the Windows Outlook desktop application using Microsoft's official COM/MAPI client (`win32com.client.Dispatch("Outlook.Application")`).

### Multi-Account Discovery
Upon launch, BOTSKILL automatically enumerates all configured Outlook accounts:
- `hr@aivaratech.online`
- `contactus@aivaratech.online`
- `paul@aivaratech.online`
- `reachus@aivaratech.online`
- `hr@gayatrieducation.info`
- `contactus@gayatrieducation.info`

### The Non-Negotiable Safety Invariant: `DRAFT_ONLY`
> [!IMPORTANT]
> BOTSKILL is hard-locked to **`LEVEL_1_DRAFT_ONLY`** by default.
> The bot **cannot** send emails directly over SMTP/MAPI without human authorization.
> All generated email responses are saved directly into Outlook's **`Drafts`** folder. The human operator reviews the draft, ensures complete accuracy, and clicks "Send" inside Outlook.

---

## 6. How to "Train" and Ground the Bot on Policies

BOTSKILL does not require expensive fine-tuning or model retraining. Instead, it uses **Document Intelligence & Dynamic Policy Grounding**. You provide your company's real documentation, and BOTSKILL parses them into auditable, deterministic policy rules.

### Supported Document Formats
- Text files (`.txt`, `.md`)
- Word documents (`.docx`)
- PDF documents (`.pdf`)
- Tabular data / spreadsheets (`.csv`, `.xlsx`)

### The 4-Step Policy Ingestion Lifecycle:
1. **Upload Document:** In the dashboard's **Knowledge & Policies** section, drag and drop your document (e.g., `Internship_Policy_2026.txt`).
2. **Safe Parsing & Classification:** The engine parses the document, calculates a cryptographic SHA-256 integrity hash, and assigns a category (e.g. `mandatory_policy`, `guardrail`, `sop`, `pricing`).
3. **Candidate Rule Extraction:** Rules are extracted with exact line/quote provenance locators:
   - *Example Rule:* *"Intern stipends are strictly fixed at INR 15,000/month. Any offer above 15,000 INR is strictly prohibited without Director approval."*
4. **Human-in-the-Loop Approval:** Extracted rules start in a disabled state (`is_active=False`). An authorized operator reviews the citation and clicks **Approve & Activate**. Only then does the rule become active.

---

## 7. Generating Grounded Drafts with Citations

When an incoming email arrives in Outlook:
1. **Quote History Stripping:** BOTSKILL strips previous reply chains to keep the AI prompt clean and prevent prompt injection.
2. **Offline Local Inference:** The local SLM (`Qwen2.5-0.5B-Instruct`) reads the customer/candidate message and synthesizes a professional response using approved facts.
3. **Deterministic Policy Evaluation:** Before any draft is accepted, the deterministic policy engine verifies the text against all active rules:
   - **Case A (Unauthorized Request):** If a candidate asks *"Can I get INR 25,000 stipend?"* and the draft attempts to promise it, the engine flags `PolicyDecision.BLOCK` because the stipend exceeds the INR 15,000 threshold.
   - **Case B (Compliant Response):** The draft states *"Our internships offer a fixed stipend of INR 15,000 as per company policy"*. The engine marks `PolicyDecision.PASS` and attaches a traceable citation linking to the specific policy document and section.

---

## 8. Reviewing & Staging Drafts in Outlook

1. Open the **Draft Review Queue** in the BOTSKILL dashboard (`http://127.0.0.1:8765`).
2. Click on any pending draft to view its **Master-Detail Review Card**:
   - Recipient and Subject line.
   - Proposed reply body.
   - Grounding citations (with document title, section, and exact source quote).
   - Local AI latency and model provenance.
3. **In-Place Editing:** You can directly modify any word in the draft text.
4. **1-Click Staging:** Click **Stage in Outlook Drafts**.
5. Switch to your Microsoft Outlook desktop client:
   - Open the **Drafts** folder of the target account (e.g., `hr@aivaratech.online`).
   - The drafted email is waiting there, formatted and ready for dispatch.

---

## 9. Emergency Stop & Autonomy Controls

In the top navigation HUD of the dashboard, you have an **Emergency Kill Switch**:
- **Activate Kill Switch:** Immediately halts all background mailbox polling and draft staging. All mutating API endpoints respond with `HTTP 423 Locked`.
- **Resume Operations:** Click "Resume" to restore normal operational state after inspecting system logs.

---

## 10. Verification & Regression Testing

BOTSKILL includes a comprehensive test suite covering 100% of the codebase across unit, integration, and end-to-end acceptance tests.

Run the test suite anytime:
```powershell
python -m pytest -v
```
**Expected Outcome:**
`69 passed, 0 failed in ~10s` (100% Green).

---

## 11. Controlled Learning & System Upgrading

As your company policies, pricing, or hiring criteria change:
1. **Never edit source code:** Source code files are protected by an automated anti-tamper guard (`verify_no_self_modification`).
2. **Upload new policy documents:** Simply upload the revised policy file (e.g., `Internship_Policy_2027.txt`) through the dashboard.
3. **Approve the updated rules:** Approve the new rule and deactivate the superseded rule. All future draft evaluations immediately reflect the new policy.
4. **PII-Safe Audit Export:** BOTSKILL includes an automated PII Sanitizer that scrubs all candidate emails, phone numbers, and credentials before generating audit exports.
