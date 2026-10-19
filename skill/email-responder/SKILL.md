---
name: autonomous-email-responder
description: Equips any AI agent or automation process to inspect local Outlook mailboxes, enforce document policies, review AI-drafted replies, and safely stage them in Outlook Drafts folder with zero cloud egress.
version: 3.0.0
---

# Autonomous Email Responder Skill (BOTSKILL v3.0)

This skill enables autonomous agents and automation processes to manage enterprise business communications locally on Windows using native Microsoft Outlook COM/MAPI and on-device Generative Intelligence (`Qwen2.5-0.5B-Instruct` GGUF).

---

## 1. Core Operating Principles & Invariants

> [!IMPORTANT]
> **Safety Invariant — DRAFT_ONLY by Default:**
> All generated email responses MUST strictly be staged inside the local Microsoft Outlook `Drafts` folder.
> The system NEVER transmits live emails directly unless explicitly authorized by a human supervisor.

- **Zero Cloud Egress:** All generative completions run 100% locally on CPU via `llama-cpp-python` using quantized GGUF weights.
- **Grounding & Provenance:** Every claim regarding compensation, stipend, remote work, or SLAs must cite a verified company policy locator (document, page, and exact quote).

---

## 2. Command Reference for Autonomous Agents

Agents interact with the BOTSKILL runtime via the `botskill` CLI or loopback HTTP REST API (`127.0.0.1:8765`).

### A. Discovery & Account Inventory
```bash
# Discover local Outlook accounts and test COM connectivity
botskill accounts list
```
**Expected Output:** Reports detected accounts (e.g. `hr@aivaratech.online`), connector health, and active autonomy mode (`LEVEL_1_DRAFT_ONLY`).

### B. Inbound Mailbox Sync & Policy Checking
```bash
# Poll active mailboxes for new inbound inquiries
botskill accounts sync
```
Discovered messages are deduplicated using SHA-256 idempotency keys, evaluated against active policy guardrails, and queued for review.

### C. Review Queue Inspection
```bash
# Inspect pending drafts with provenance citations
botskill drafts list
```
Each pending draft displays:
- Proposed response subject and body.
- Grounding citations (Rule ID, source document, exact quote).
- Policy compliance decision (`PASS`, `NEEDS_HUMAN_REVIEW`, or `BLOCK`).

### D. Safe Outlook Draft Staging
```bash
# Stage a verified draft directly into Outlook's Drafts folder
botskill drafts stage <draft_id>
```
**Safety Verification:** This creates a mail item in Outlook's local `Drafts` folder via MAPI COM dispatch without invoking `.Send()`.

### E. Policy Management & Human Approval
```bash
# List all active and candidate policy rules
botskill policy list

# Approve and activate a candidate rule extracted from uploaded documents
botskill policy approve <rule_id>
```

### F. Local AI Engine Telemetry
```bash
# Verify local SLM engine health and RAM footprint
botskill ai status
```

### G. Emergency Interventions
```bash
# Immediately halt all background sync, drafting, and staging
botskill autonomy kill
```

---

## 3. Autonomous Execution Workflow for Agents

When requested to handle customer or applicant correspondence:

1. **Inventory:** Run `botskill accounts list` to verify connected mailboxes.
2. **Scan:** Run `botskill accounts sync` to ingest fresh inquiries safely.
3. **Audit:** Run `botskill drafts list` to inspect generated responses and verify policy citations.
4. **Stage:** For approved items, run `botskill drafts stage <draft_id>` to place them in Outlook Drafts for human review.
5. **Report:** Report the staged draft IDs and cited policy rules back to the user.
