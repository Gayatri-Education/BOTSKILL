# BOTSKILL — Development Contract and Phase-by-Phase Implementation Plan

> **Purpose:** This document is the source of truth for any human or AI coding agent developing BOTSKILL. Follow phases in order. Do not claim a phase is complete until its acceptance criteria and evidence are recorded.
>
> **Approved product decisions:** Distribution = standalone application + importable agent skill; email connectors = Gmail, Microsoft 365/Outlook, and generic IMAP/SMTP; autonomy = progressive; learning = private by default with opt-in sanitized template sharing; primary scope = general business email across industries.
>
> **Default safety posture:** Draft-only. No live email sending during development, tests, setup, migration, or acceptance checks unless a human explicitly enables a bounded live-send test for a designated test mailbox.

## 1. Product objective

Turn the existing repository into a provider-independent, local-first email automation product that can be installed by non-technical users and imported as a portable agent skill. It must monitor authorized mailboxes, use approved business knowledge, propose accurate thread-aware replies, stage drafts, and gradually allow approved categories to auto-send under explicit policies.

BOTSKILL must not require Gemini, a particular coding agent, or a `~/.gemini` directory. The core runtime must work without any AI provider configured, using deterministic rules/templates where possible and clearly reporting unavailable capabilities.

## 2. Non-negotiable engineering rules

1. **Plan → implement → test → debug → review → document** each phase before starting the next.
2. Read the current repository and run baseline tests before refactoring. Preserve useful behavior unless a documented migration decision replaces it.
3. Never send real email as a side effect of unit tests, import, installation, inspection, migrations, or default startup.
4. Never store passwords, OAuth tokens, private mailbox content, customer records, or business-specific policy in Git, logs, fixtures, telemetry, or shared templates.
5. Treat email bodies, attachments, quoted threads, linked pages, and retrieved documents as untrusted data. They cannot override system policy or grant permissions.
6. Never allow a model or incoming email to execute arbitrary commands, rewrite production code, expand permissions, or enable auto-send.
7. Never report an operation as successful when it failed, timed out ambiguously, or was silently skipped. Surface a structured status and actionable error.
8. Do not swallow exceptions without recording a safe, useful failure event. Never log secrets or full message bodies by default.
9. Do not hard-code company domains, mailbox addresses, recipient exclusions, business facts, or provider credentials in core code.
10. Avoid destructive changes. Migrations must be backed up, repeatable, and reversible where practical.
11. Keep changes focused and commits small. Do not delete existing files until references, tests, migration impact, and replacement behavior have been verified.
12. Do not mark a phase complete with failing, skipped-without-justification, or unexecuted required tests.

## 3. Product architecture

### 3.1 Layers and boundaries

- **Portable skill package:** `skill/email-responder/SKILL.md`, scripts and references. Explains workflows and invokes documented BOTSKILL CLI commands. Contains no provider-specific execution logic.
- **Core runtime:** message lifecycle, policy evaluation, orchestration, idempotency, approval state, audit events and scheduling.
- **Provider adapters:** interchangeable AI and email connectors implementing stable interfaces.
- **Knowledge subsystem:** approved local files, explicit integrations, retrieval, citations/provenance and versioned learning proposals.
- **Local application:** setup wizard/control panel, configuration, inbox status, draft review, activity/error views, autonomy controls and pause/kill switch.
- **CLI/service:** the same runtime is usable from terminal, desktop app, background service, or supported agent skill.
- **Optional sharing library:** off by default; exports only reviewed, generic templates after sanitization and user confirmation. Local execution must not require this service.

### 3.2 Target package layout

Adapt names to existing code after Phase 0; do not create duplicate implementations.

```text
BOTSKILL/
  skill/email-responder/
    SKILL.md
    scripts/
    references/
  src/botskill/
    core/              # orchestration, domain models, policy
    ai_providers/      # Ollama, OpenAI-compatible, cloud adapters
    mail_providers/    # Gmail, Microsoft Graph, IMAP/SMTP, optional Outlook COM
    knowledge/         # loaders, retrieval, approved sources
    storage/           # migrations, repositories, message ledger
    approvals/         # draft queue and autonomy gates
    scheduler/         # polling, leases, retry/backoff
    security/          # secret-store interface, redaction, permissions
    observability/     # structured events, health and diagnostics
    app/               # local API/UI entry point
    cli.py
  tests/
    unit/
    integration/
    security/
    fixtures/
  docs/
  DEVELOPMENT.md
  pyproject.toml
  config.example.yaml
  .gitignore
```

### 3.3 Core contracts

Define typed models and interfaces before adding more integrations.

- `AIProvider`: `health_check()`, `capabilities()`, `classify_email()`, `generate_reply()`. Adapter declares support for structured output, tools, streaming, context size and timeout behavior.
- `EmailProvider`: `test_connection()`, `list_new_messages(cursor)`, `get_message(id)`, `create_draft(reply)`, `send_reply(reply, idempotency_key)`, `get_send_status(operation_id)`, `mark_processed(id)`. Provider-specific capabilities must be explicit.
- `KnowledgeSource`: authorized retrieval of approved content with source identifiers, version and provenance.
- `PolicyEngine`: deterministic decision for draft, approval-required, auto-send, reject, or quarantine.
- `StateStore`: durable message ledger, cursor, processing lease, draft, approval, send attempt, audit event and learning proposal.
- `SecretStore`: OS credential vault where available; documented encrypted fallback only if necessary. Secrets never belong in ordinary configuration.
- `Scheduler`: bounded polling, lease-based processing, retry/backoff and graceful shutdown.
- `AuditSink`: structured, redacted, timestamped events with correlation IDs.

### 3.4 Message lifecycle

`DISCOVERED → CLAIMED → PARSED → CLASSIFIED → KNOWLEDGE_RETRIEVED → DRAFTED → POLICY_CHECKED → (PENDING_APPROVAL | APPROVED_TO_SEND | BLOCKED) → SEND_PENDING → SENT_CONFIRMED`

Additional terminal/recovery states must include `FAILED_RETRYABLE`, `FAILED_FINAL`, `SEND_OUTCOME_UNKNOWN`, `QUARANTINED`, and `IGNORED_WITH_REASON`. State transitions must be persisted and validated. Unknown send outcomes must be reconciled before retry; do not blindly resend after a timeout.

## 4. Provider and email support

### AI
- First local adapter: Ollama HTTP API.
- Cloud: one supported cloud adapter in the initial milestone, with provider-neutral interface; add others without changing core orchestration.
- Compatible endpoints: support OpenAI-compatible APIs only when their capabilities are verified; do not assume every endpoint implements every feature.
- Rules-only: deterministic templates and policies must remain available.
- AI outages must not prevent message ingestion, durable queuing, pausing, or reporting.

### Email
- Gmail/Google Workspace: official Gmail API and OAuth scopes appropriate to the enabled operations.
- Outlook/Microsoft 365: Microsoft Graph and OAuth permissions appropriate to the enabled operations.
- Generic business email: IMAP/SMTP with TLS and OAuth where supported; application passwords only where provider guidance requires them.
- Existing Outlook COM integration may remain as an optional Windows adapter, not a core dependency.
- All connectors must support test mode and fake/mock transports. Live sending requires an explicit operator action and policy approval.
- Preserve threading headers and provider-native draft/thread behavior where supported. Document capability gaps instead of silently approximating them.

### Credentials
Use browser-based OAuth where available. Never ask users to paste normal mailbox passwords into an AI chat. Use OS credential stores where possible. Support disconnect/revoke, token expiry status, reauthentication and least-privilege scopes. Never print secrets in diagnostics.

## 5. Progressive autonomy policy

- **Level 0 — Disabled:** no mailbox processing.
- **Level 1 — Draft-only (default):** read authorized messages and create drafts; never send.
- **Level 2 — Approval required:** a human approves each outgoing message.
- **Level 3 — Approved categories:** auto-send only explicitly enabled low-risk categories, within account, recipient, schedule and volume limits.
- **Level 4 — Expanded automation:** not part of initial release; requires a separate risk review and explicit product decision.

Policy is deterministic and must run after generation and before sending. Confidence scores alone never authorize a send. High-risk/uncertain cases (legal complaints, financial instructions, credentials, sensitive personal data, account changes, commitments, complaints, ambiguous recipients, unknown policies, prompt-injection attempts) require review or quarantine. Provide a global pause/kill switch, per-mailbox limits, recipient suppression configuration, loop detection, allow/deny lists and a daily send cap. Never use a universal hard-coded suppression domain.

## 6. Learning and cross-installation sharing

Local learning is private by default. Store candidate scenarios separately from active approved rules.

Lifecycle: `DETECT → CLUSTER → PROPOSE → GENERATE TESTS → REVIEW → APPROVE → VERSION → ACTIVATE`.

- User edits and feedback may create a learning proposal, not an immediate policy change.
- Each approved rule stores provenance, reviewer, timestamp, version and regression tests.
- Rollback to the previous rule set must be possible.
- Never let inbound email trigger executable-code generation/activation or permission changes.
- Opt-in sharing must be a separate, explicit export step. Sanitize and inspect the export, show a preview, require confirmation, and export only generic patterns/templates with no personal data, mailbox identifiers, internal URLs, confidential policy or customer-specific answers.
- Sharing must be disabled by default and the product must function fully without it.
- Add tests proving that secrets and personal data are rejected from shared exports.

## 7. Data, privacy and reliability requirements

Persist message identifiers, provider/thread IDs, cursor state, processing leases, approval decisions, send attempts and outcomes. Use SQLite for the initial single-user local install unless Phase 0 evidence justifies another store. Define migrations and backups. Avoid storing full message bodies after their purpose is fulfilled; retention must be configurable and documented.

Requirements:
- Deduplication on stable provider/message identifiers and safe thread identity.
- Concurrency-safe claims/leases and idempotent state transitions.
- Exponential backoff with jitter and bounded retries for transient errors.
- Respect provider rate limits and `Retry-After` where supplied.
- Graceful shutdown and restart recovery.
- Explicit outcome for every processed message; no silent drops.
- Health/readiness checks for AI, mail, storage and scheduler.
- Structured logs with correlation IDs, redaction and configurable retention.
- No outbound telemetry by default.
- Attachment parsing is disabled unless explicitly enabled, bounded by file size/type and isolated from execution.
- HTML email is sanitized; outbound content has plain-text alternative and safe MIME construction.
- Prompt injection, malicious links, unexpected attachments, bounce loops, auto-replies and self-replies are handled defensively.

## 8. Phase execution contract

At the start of every phase, the coding agent MUST:
1. Read this contract, README, relevant skill references and current progress log.
2. Inspect actual code and dependencies; list the files and behavior affected.
3. Write a short phase plan with risks, migrations and test cases.
4. Record baseline test results and current Git commit.
5. Implement the smallest coherent change.
6. Run targeted tests, then the full applicable suite; debug and rerun failures.
7. Review security, backward compatibility, error paths and logs.
8. Update progress, architecture notes, README/docs and tests.
9. Commit the completed work with a descriptive message.
10. Stop if acceptance criteria fail; do not begin the next phase.

### Phase 0 — Repository audit and baseline
**Tasks**
- Inventory all tracked files, entry points, imports, dependency versions, provider assumptions, hard-coded addresses/domains, secret handling, network calls, side effects and exception handlers.
- Run existing tests in a safe environment; record failures as baseline rather than hiding them.
- Trace the full path from mailbox polling to classification, draft, send, marking replied, daemon scheduling and learning.
- Inspect `email_bot_brain.py`, `outlook_email_service.py`, `email_reply_daemon.py`, `project_inspector.py`, `project_bot_factory.py`, `global_knowledge_sync.py`, `scenario_evolver.py`, `SKILL.md`, existing tests and data files.
- Identify legacy state and migration needs. Never upload private data or run live-send tests.
**Acceptance**
- `docs/BASELINE_AUDIT.md` lists architecture, entry points, risks, hard-coded assumptions, test command/results and a file-by-file migration map.
- All live-send code paths and hidden side effects are documented.
- No production code is deleted or behavior changed in this phase.

### Phase 1 — Safety baseline and test harness
**Tasks**
- Establish isolated test configuration, fake AI provider, fake email provider and deterministic fixtures.
- Add tests for no-send-by-default, secret redaction, suppression configuration, quoted-thread parsing, malformed messages, exceptions and interrupted processing.
- Add lint/type-check/test commands and CI if practical.
- Ensure import, startup, inspection and tests never send messages.
**Acceptance**
- Tests run without real credentials or network access.
- A test can prove that no send method was called.
- Baseline failures are tracked; all new tests pass.

### Phase 2 — Core domain models and provider interfaces
**Tasks**
- Add typed message, thread, account, draft, policy decision, processing state, send attempt, audit event and learning proposal models.
- Implement provider interfaces and capability declarations.
- Move orchestration away from direct Outlook/SMTP and provider-specific code.
- Keep compatibility wrappers for existing entry points where needed.
**Acceptance**
- Core unit tests run with fake adapters and no external provider packages.
- Core imports do not require Gemini or Windows COM.
- Adapter errors are typed and visible; no silent-success fallback exists.

### Phase 3 — Durable storage, migrations and idempotency
**Tasks**
- Add SQLite repositories and versioned migrations for messages, cursors, leases, drafts, approvals, send attempts, audit events and learning proposals.
- Implement duplicate detection, lease expiry/recovery, state-transition validation and backup/restore.
- Model `SEND_OUTCOME_UNKNOWN` and reconciliation before retries.
**Acceptance**
- Restart/replay tests do not create duplicate sends.
- Migrations work on empty and previous-version fixtures, are repeatable where designed, and preserve existing data.
- Concurrent workers cannot claim the same message simultaneously.
- Restore procedure is documented and tested.

### Phase 4 — AI adapters and rules-only operation
**Tasks**
- Implement Ollama adapter, one cloud adapter and deterministic rules/template provider.
- Add timeout, retry, model health and capability checks.
- Normalize outputs and validate structured classification fields.
- Prevent AI provider failures from losing incoming messages.
**Acceptance**
- Contract tests pass against fakes; optional provider integration tests require explicit configuration.
- Missing/unavailable AI results in a queued/degraded status, not an invented reply.
- No provider-specific configuration leaks into core logic.

### Phase 5 — Email connectors and secure account onboarding
**Tasks**
- Implement Gmail API/OAuth, Microsoft Graph/OAuth and generic IMAP/SMTP connectors behind the common interface.
- Preserve threading, drafts, message IDs, pagination/cursors and provider rate limits.
- Implement secure credential storage, connection test, permission summary, disconnect and reauthentication.
- Retain Outlook COM only as an optional adapter if its behavior is covered.
**Acceptance**
- Each connector has fake-based contract tests and documented live sandbox tests.
- Read, draft and send capabilities are declared separately.
- Credentials never appear in logs, configuration examples, test snapshots or error messages.
- Unsupported provider behavior is reported clearly.

### Phase 6 — Knowledge retrieval and business onboarding
**Tasks**
- Create onboarding for business profile, timezone, approved FAQs/documents, categories, sender identity, policies and retention.
- Implement source-aware retrieval and provenance.
- Restrict file scanning and database discovery to user-authorized paths/resources; preview discoveries before use.
- Separate approved facts from inferred content and learned proposals.
**Acceptance**
- Drafts can identify their supporting approved source internally.
- Unknown policy/factual questions are flagged for review, not answered with fabricated business facts.
- Tests prove unauthorized paths/tables are not read.
- No business-specific data is embedded in shared default templates.

### Phase 7 — Policy engine, approval queue and progressive autonomy
**Tasks**
- Implement autonomy levels and category/account/recipient rules.
- Add deterministic pre-send validation, risk gates, recipient verification, loop prevention, quotas and kill switch.
- Implement draft review, approve/reject, edit-before-send and auditable decisions.
- Require explicit operator enablement for any live-send mode.
**Acceptance**
- Draft-only remains the default after install, upgrade and restart.
- High-risk/unknown messages cannot auto-send even with a high model confidence score.
- Kill switch blocks queued and future sends immediately.
- Every allow/block/approval decision has a reason in the audit trail.

### Phase 8 — Scheduler, daemon and operational resilience
**Tasks**
- Add bounded polling, concurrency controls, retry/backoff, rate-limit handling, graceful shutdown and restart recovery.
- Add health status, pending queue, last successful poll, error details and send reconciliation.
- Replace broad catch-and-continue behavior with typed errors and observable outcomes.
**Acceptance**
- Simulated network outages, expired tokens, provider throttling, crashes and restart recover without silent message loss.
- Every discovered message reaches a known state.
- Unknown send outcome is never automatically resent until reconciled or explicitly resolved.

### Phase 9 — Controlled learning and opt-in sharing
**Tasks**
- Refactor scenario evolution into proposal generation, test generation, review, versioning and rollback.
- Add feedback capture with privacy controls.
- Add opt-in export preview, sanitizer, explicit confirmation and generic template import validation.
- Remove mandatory global sync and all assumptions that `~/.gemini` is the global store.
**Acceptance**
- New scenarios cannot activate without approval and passing tests.
- Rollback restores prior behavior.
- Sharing is off by default and can be disabled permanently.
- Automated tests reject secrets, personal data, account IDs, internal URLs and organization-specific policy from exports.
- The product operates with no network access to any sharing service.

### Phase 10 — Standalone app, CLI and portable skill
**Tasks**
- Implement one documented CLI for setup, health, mailbox test, draft sweep, review, service run, pause/resume and diagnostics.
- Build a local control panel for account status, provider/model selection, knowledge sources, draft review, autonomy, logs and kill switch.
- Package the skill using portable Agent Skills conventions; scripts invoke the shared CLI/API.
- Build Windows packaging first and document Linux support. Add macOS support only if validated.
- Provide safe upgrade/uninstall and data-retention behavior.
**Acceptance**
- A clean machine can install and configure without editing Python.
- The standalone app works without an agent host; the skill works without Gemini-specific directories.
- Skill and app use the same runtime and policies.
- Uninstall does not silently delete user data or leave background services running.

### Phase 11 — Security, compatibility and release hardening
**Tasks**
- Run unit, integration, security, migration, recovery and end-to-end tests.
- Audit permissions, OAuth scopes, secret storage, local API binding, CSRF/authentication for the control panel, path traversal, HTML sanitization, prompt injection, dependency vulnerabilities and logs.
- Test Windows and Linux clean installs; verify local model and cloud API configurations.
- Prepare README, quick start, provider guides, privacy statement, threat model, troubleshooting and release notes.
- Generate checksummed release artifacts and sign binaries where feasible.
**Acceptance**
- No open critical/high severity security findings; any accepted medium risk has owner, mitigation and documented rationale.
- All mandatory CI checks pass on supported platforms.
- Installation, upgrade, backup/restore, pause, disconnect and uninstall are tested.
- Release notes state limitations and do not promise guaranteed inbox delivery.

## 9. Mandatory test matrix

Tests must include, at minimum:

- Classification, intent ambiguity, quoted replies, HTML/plain text, Unicode and malformed MIME.
- Duplicate message IDs, repeated polling, concurrent workers, stale leases and restart recovery.
- AI timeout, invalid structured output, unavailable model, rate limit and context overflow.
- OAuth denial, expired/revoked token, IMAP/SMTP authentication failure and permission insufficiency.
- Draft creation failure, provider rejection, timeout before send, timeout after provider acceptance, unknown outcome and reconciliation.
- Prompt injection in email body, quoted thread, attachment and retrieved document.
- Secret redaction, path traversal, unauthorized resource discovery, unsafe HTML and shared-export sanitization.
- High-risk classification, recipient mismatch, self-reply/auto-reply loops, suppression rules, daily cap and kill switch.
- Learning proposal failing tests, approval, versioning, rollback and cross-install isolation.
- Clean install, upgrade, uninstall, backup/restore, CLI usage and skill import.

Use fakes for deterministic CI. Live provider tests must use dedicated test accounts, explicit opt-in, known recipients and a bounded send cap. Never use real customer inboxes in automated tests.

## 10. GitHub progress tracking

Maintain the following in Git:
- `DEVELOPMENT.md`: this contract and phase acceptance criteria.
- `docs/PROGRESS.md`: current phase, status, completed tasks, pending tasks, blockers, test commands/results, latest commit and next action.
- `docs/BASELINE_AUDIT.md`: findings and migration map from Phase 0.
- `docs/DECISIONS.md`: architecture decisions, alternatives, rationale and date.
- `CHANGELOG.md`: user-visible changes and migration notes.

For every phase:
1. Create a branch named `phase-N-short-description` when repository permissions/workflow allow.
2. Open or update a GitHub issue with scope and acceptance checklist.
3. Commit code, tests and documentation together where practical.
4. Update `docs/PROGRESS.md` with evidence and exact test outcomes.
5. Use a pull request for review; do not force-push or rewrite shared history.
6. Mark checkboxes complete only with evidence. Record failed/skipped tests and why.
7. Do not start the next phase until current acceptance criteria pass or a human explicitly approves a documented exception.

Progress status values: `NOT STARTED`, `IN PROGRESS`, `BLOCKED`, `IN REVIEW`, `ACCEPTED`. Do not invent completion percentages; calculate them from checked, evidence-backed tasks.

## 11. Definition of done for any feature

A feature is not done until:
- Requirements and failure modes are documented.
- Permission and data-flow impact is reviewed.
- Tests cover success, failure, retry and unsafe input.
- User-visible errors are actionable and safe.
- Logs are redacted and outcomes are auditable.
- Documentation/config examples are updated.
- Migration/backward compatibility is addressed.
- CI passes and progress tracking is updated.
- No unrelated files or secrets were added.

## 12. Release gates

A release is blocked if any of the following are true:
- Default mode can send an email.
- Any required connector silently reports success on failure.
- Duplicate-send behavior after uncertain network outcomes is unresolved.
- Credentials or private data appear in tracked files, logs, fixtures or shared templates.
- The kill switch, rate limits, approval gates or audit events are missing.
- Critical/high security defects remain open.
- Clean install or upgrade fails on a supported platform.
- Required tests are failing or have no recorded result.
- README claims capabilities that are not implemented and tested.

Release checklist:
- [ ] Phase 0 baseline audit approved.
- [ ] Required unit, integration, security and recovery tests pass.
- [ ] Clean install and upgrade validated.
- [ ] Default draft-only mode verified on fresh install and restart.
- [ ] Test mailbox proves draft, approval, bounded send and pause workflows.
- [ ] Provider scopes and credential storage reviewed.
- [ ] Backup/restore and uninstall validated.
- [ ] Documentation, privacy notes, limitations and changelog updated.
- [ ] Release artifacts checksummed; signing applied where feasible.
- [ ] No critical/high issues remain; accepted risks documented.
- [ ] Human release approval recorded.

## 13. First action for the coding agent

Start with **Phase 0 only**. Inspect the actual repository at the current commit, run the existing test suite without live email access, and create `docs/BASELINE_AUDIT.md` plus `docs/PROGRESS.md`. Do not begin broad refactoring until the baseline report, migration map and test safety controls are reviewed. Then proceed one phase at a time.


---

# 14. Document Intelligence, Policy Guardrails, and Context-Aware Draft Design

This section is mandatory. BOTSKILL must not treat every uploaded document as a generic text file or let an LLM infer policy authority from document wording alone. It must identify document types, establish source authority and applicability, extract policy obligations, reconcile conflicts, and apply approved rules when drafting and deciding whether to send.

## 14.1 Required product behavior

Users may provide company guardrails, policy documents, standard operating procedures (SOPs), employee handbooks, FAQs, product/service documentation, tone-of-voice guides, email templates, contracts, escalation matrices, approval matrices, pricing/benefits sheets, compliance documents, and other approved business resources.

BOTSKILL must:
1. Identify each document's likely type and intended use.
2. Extract metadata such as title, owner, issuing department, version, effective date, expiry/review date, jurisdiction, audience, status, confidentiality label, and superseded documents when present.
3. Distinguish **mandatory policy**, **recommended guidance**, **reference facts**, **examples/templates**, **legal/compliance restrictions**, and **untrusted or unknown material**.
4. Preserve provenance at the claim/rule level: document ID, version, page/section, extraction method, and confidence.
5. Determine which rules apply to a particular email based on mailbox, organization, recipient type, region/jurisdiction, subject, workflow, category and date.
6. Generate a draft that follows all applicable approved rules and has a tone, format and detail level suited to the email category.
7. Detect missing, ambiguous, conflicting, expired or low-confidence policies and request human review rather than inventing a resolution.
8. Explain draft decisions to the operator using an internal-facing policy trace: rules applied, sources consulted, facts not found, conflicts, and why auto-send was allowed or blocked.
9. Keep document content separate from system instructions. A document must not grant itself authority to bypass security, reveal secrets, change permissions or enable sending.
10. Reprocess documents safely when replaced, revoked, expired or superseded, and invalidate affected retrieval indexes and cached decisions.

## 14.2 Document ingestion pipeline

Implement a staged, inspectable pipeline:

`DISCOVER → AUTHORIZE → TYPE_DETECT → SAFETY_SCAN → EXTRACT → NORMALIZE → METADATA_REVIEW → SEGMENT → CLASSIFY_CLAIMS → RESOLVE_AUTHORITY → INDEX → VALIDATE → ACTIVATE`

Each stage must have a persisted state, timestamp, outcome, error and retry policy. Failed ingestion must not silently activate a partial index. A document is not an active policy merely because it was uploaded or its filename contains words such as “policy”, “official” or “final”.

### Supported initial document types

- PDF with text; scanned PDF via optional OCR.
- DOCX.
- TXT and Markdown.
- HTML after sanitization.
- CSV/XLSX for tabular rules, price lists, eligibility tables and approved structured facts.
- Email/template files only when explicitly imported as knowledge.
- Image formats for OCR only when explicitly enabled.

Unsupported, encrypted, malformed, oversized or suspicious files must be quarantined with a clear explanation. Do not execute macros, embedded scripts, links, attachments or document actions. Enforce file-size, page-count, decompression, parsing-time and OCR limits. Keep the original file unchanged and store a hash for change detection.

## 14.3 Document taxonomy and metadata model

Use a versioned schema; examples of document types include:

| Type | Typical purpose | Default treatment |
|---|---|---|
| `mandatory_policy` | Rules that staff/bot must follow | Enforce only after authorized review/activation |
| `guardrail` | Safety, privacy, communication and action limits | Enforce as policy once approved |
| `approval_matrix` | Who may approve what | Deterministic gate; never infer missing approvers |
| `sop` | Process steps and operating procedures | Guide workflow; flag ambiguous steps |
| `compliance_requirement` | Legal/regulatory or contractual obligations | High-risk; require designated owner review |
| `product_or_service_facts` | Verified product details, eligibility, features | Factual source with effective dates |
| `pricing_or_benefits` | Prices, benefits, discounts, stipend/fee data | Require freshness and exact source support |
| `faq` | Approved answers to recurring questions | Preferred response source for matching intent |
| `tone_guide` | Voice, language, style and formatting | Style guidance only; cannot override policy |
| `template_or_example` | Approved structure or sample response | Use as pattern, not as proof that facts are true |
| `reference_material` | Background information | Retrieval source, not automatically authoritative |
| `unknown` | Unclassified or unclear authority | Do not use for autonomous commitments |

Document metadata should include at least:
- Stable document ID and content hash.
- Display name and detected type.
- Issuer/owner and who authorized it.
- Version/revision, effective date, expiry/review date, received date.
- Status: `QUARANTINED`, `NEEDS_REVIEW`, `APPROVED`, `ACTIVE`, `SUPERSEDED`, `EXPIRED`, `REVOKED`, `REJECTED`, `INGESTION_FAILED`.
- Scope: organization, department, product, audience, mailbox, region/jurisdiction and workflow.
- Confidentiality/access level and allowed processing purposes.
- Extraction/OCR method, parser version, detected language and quality metrics.
- Links to superseding/superseded documents and review history.

Do not guess absent dates, issuer, version or legal status. Represent unknown fields as unknown and ask an authorized reviewer.

## 14.4 Authority, conflict resolution, and policy lifecycle

Do not resolve conflicting documents with vector similarity, recency alone, filename, or an LLM's unsupported judgment.

Use an explicit, configurable authority model:
1. Platform security and non-overridable product safety controls.
2. Applicable laws and provider terms, as assessed by the organization's authorized owner; do not present BOTSKILL as a legal decision-maker.
3. Approved organization-wide mandatory policies.
4. Approved department/workflow policies and approval matrices.
5. Approved product/service facts and operational procedures.
6. FAQs and templates.
7. Reference material and examples.
8. Unknown/unreviewed content (never authoritative).

This is a default precedence model, not a substitute for organization-specific governance. If two applicable mandatory policies conflict, or scope/authority cannot be determined, block autonomous sending and route the draft for review. A human with appropriate permission must resolve the conflict and record the rationale.

Policy changes must be versioned and auditable. Require review/approval before activation of mandatory policy or guardrails. Provide dry-run impact analysis showing which categories, rules, drafts and automation paths would change. Expired or superseded sources must no longer authorize new responses; retain historical provenance for past decisions as permitted by retention rules.

## 14.5 Rule extraction schema

Normalize extracted requirements into typed, testable rule objects, for example:

```yaml
rule_id: HR-INTERNSHIP-004
title: Do not promise unapproved stipend amounts
rule_type: prohibited_commitment
severity: high
status: needs_review
applies_to:
  categories: [internship_enquiry, candidate_follow_up]
  recipient_types: [candidate]
condition: "The response states a stipend, compensation, or guaranteed payment"
required_action: "Use only an active approved source; otherwise request human review"
allowed_behavior:
  - "Quote the exact approved range with its source and effective date"
blocked_behavior:
  - "Invent a number"
  - "Treat an old email as current policy"
source:
  document_id: "doc-example"
  version: "unknown"
  locator: "page 4, section 2"
  content_hash: "record-at-ingestion"
review:
  approved_by: null
  approved_at: null
  rationale: null
tests:
  - "No source means no numeric commitment"
  - "Expired source blocks automatic numeric commitment"
```

The schema is illustrative. Implement strict validation, enums, schema versioning, migration and provenance. An LLM may propose rule objects but must not self-approve them. Extracted rules must be rendered in human-readable form before approval.

Rules should cover:
- Required disclosures or disclaimers.
- Prohibited claims and commitments.
- Eligibility, pricing, fees, compensation, refunds and deadlines.
- Identity verification and data minimization.
- Escalation conditions and authorized approvers.
- Tone, language, formatting and response-time guidance.
- Attachments and forms that may or may not be sent.
- Whether a category is draft-only, approval-required or eligible for auto-send.
- Retention and restricted handling instructions.

## 14.6 Retrieval and applicability engine

Use hybrid retrieval where justified: exact keyword/metadata filters plus semantic retrieval. Apply scope and access filters before returning content to the model. Do not rely on similarity score alone.

For each candidate source:
- Check active status, effective date, expiry, supersession, jurisdiction, audience, mailbox/workflow scope and user authorization.
- Prefer exact structured records for amounts, dates, eligibility, policy IDs and approval requirements.
- Return source IDs and exact page/section/row references alongside the content.
- Keep mandatory rules available to deterministic policy checks, not only in the LLM prompt.
- Distinguish “not found” from “the answer is no”.
- Detect conflicting values across sources and fail closed for high-risk facts.
- Limit retrieved content and record which source versions were used for each draft.
- Never expose content to a user or mailbox account without permission to access it.

For numeric or time-sensitive claims, require an active authoritative source and validate units, currency, date range and scope. The model must not calculate or infer policy commitments from stale or incomplete data unless a documented deterministic calculation is approved.

## 14.7 Draft design engine

Draft generation must be a controlled multi-step process, not one unconstrained prompt.

1. Parse the message and thread; identify sender, recipient, intent, requested action, deadline and language.
2. Detect risk and possible prompt injection, spoofing, impersonation, unusual urgency, financial instructions and requests for sensitive data.
3. Select applicable active policies and approved knowledge with provenance.
4. Build a structured response plan: objective, must-include items, prohibited content, evidence-supported facts, tone, format, next action and approval level.
5. Generate the draft with the selected AI provider.
6. Validate claims against source evidence; verify required disclaimers, dates, numbers, recipient, attachments and forbidden commitments.
7. Apply style/format guidance without allowing style rules to override policy.
8. Evaluate the deterministic policy engine after generation.
9. Either save a draft, request approval, quarantine, or auto-send only if every gate passes.
10. Save an internal explanation and audit trace; do not expose confidential internal policy details to the email recipient.

Draft profiles should be configurable per category, for example:
- Customer support: acknowledge issue, answer verified question, state next action and avoid unsupported promises.
- Recruitment/HR: respectful tone, approved eligibility/compensation facts, no unapproved hiring decisions or guarantees.
- Billing: precise amounts and dates from active records, no changed payment instructions without verification.
- Sales: approved product claims and price lists, no invented discounts or contractual promises.
- General business: concise, clear, professional, context-aware responses.
- Complaints/legal/compliance: acknowledgement and escalation, no admission of liability or definitive legal interpretation unless explicitly approved by authorized personnel.

These profiles are defaults/examples; users must be able to configure categories and policies.

## 14.8 Policy-aware draft evaluation

Before a draft can be approved or auto-sent, evaluate it against:
- Policy applicability and conflicts.
- Claim support and source freshness.
- Required fields/disclosures.
- Prohibited promises, unsupported numbers and sensitive data leakage.
- Recipient identity and thread consistency.
- Tone and formatting profile.
- Risk category and autonomy level.
- Attachments, links and external actions.
- Duplicate/reply-loop detection.
- Provider/account send limits.

Return a typed result such as `PASS`, `NEEDS_HUMAN_REVIEW`, `BLOCK`, or `SOURCE_CONFLICT`, plus machine-readable reasons and a human-readable explanation. Do not let an LLM alone return `PASS`; deterministic checks must enforce non-negotiable rules. The evaluation record must include policy version and source versions.

## 14.9 Document governance UI

The local control panel must include a **Knowledge & Policies** area:
- Add files/folders only after explicit path selection and access confirmation.
- Show document type, owner, version, effective/review dates, scope, status and extraction quality.
- Preview extracted text and proposed rules before activation.
- Highlight uncertain metadata, conflicting rules, missing sources and expired documents.
- Allow authorized users to approve, reject, supersede, revoke and roll back.
- Show policy change impact and affected workflows before activation.
- Show source citations and rule explanations for each draft.
- Offer re-index, retry, export and delete operations with confirmation and audit history.
- Provide retention, deletion and backup controls.
- Do not expose hidden/internal guardrails in outgoing email or to unauthorized users.

## 14.10 Document intelligence tests and acceptance gates

Mandatory tests:
- Correct and incorrect document-type classification, ambiguous type and conflicting metadata.
- Text PDF, scanned PDF/OCR, DOCX, Markdown, HTML, CSV/XLSX, malformed, encrypted and oversized files.
- Prompt injection in body text, footnotes, metadata, OCR output, hidden HTML, tables, comments and attachments.
- Effective/expiry dates, superseded versions, revoked policy, scope mismatch and jurisdiction mismatch.
- Conflicting mandatory policies and missing approval matrix.
- Exact extraction and provenance for dates, percentages, money, eligibility and deadlines.
- Retrieval from authorized versus unauthorized folders, documents and departments.
- Draft with supported facts, unsupported facts, stale facts, conflicting facts and no relevant source.
- Required disclaimer omitted, prohibited commitment inserted, tone-guide conflict and policy conflict.
- Re-index after update/delete/revoke, cache invalidation, rollback and historical audit trace.
- Cross-tenant/cross-profile leakage and shared-template sanitizer behavior.

Acceptance gates:
- No unapproved document can become an active mandatory policy.
- No filename or model judgment alone establishes authority.
- Every policy-backed draft has a retrievable internal provenance trace.
- Conflicts, expired sources and missing high-risk facts block auto-send.
- A source update/revocation invalidates future authorization immediately after successful activation, and stale caches are tested.
- Human reviewers can inspect and correct document type, metadata and extracted rules.
- If document extraction fails, BOTSKILL reports it and does not pretend the source was indexed.
- No document content can override platform security or directly execute a tool/command.

---

# 15. Extended phase plan for an industrial-grade local AI coding agent

The agent must integrate this work into the existing phases above, not build a parallel document subsystem. Document intelligence should be delivered as incremental phases with the same plan/code/test/debug/review gate. The following phases are added after Phase 5 and before policy-aware drafting is declared complete. Renumber phases in the progress tracker if desired, but keep stable IDs `DOC-1` through `DOC-6`.

## DOC-1 — Document inventory, taxonomy and threat model
**Plan:** Inspect current document/file ingestion, knowledge sync, prompts, policy references and data stores. Define supported types, trust boundaries, access scope, metadata schema, retention, file limits and threat model.
**Code:** Add schema/models and migration; do not yet activate extracted policy rules.
**Test/debug:** Test schema validation, unknown metadata, malformed inputs and authorization boundaries.
**Acceptance:** Document types and lifecycle are documented; all ingested material starts untrusted/unapproved; no production policy behavior changes without review.

## DOC-2 — Safe parsers and ingestion pipeline
**Plan:** Select maintained parsers for PDF, DOCX, text/Markdown, HTML, CSV/XLSX and optional OCR. Record licensing and security implications.
**Code:** Implement isolated parsing, file limits, MIME/type checks, content hashes, malware-scan hook where available, parser timeouts, normalization, extraction quality and explicit failure states.
**Test/debug:** Malformed, encrypted, oversized, decompression-bomb-like and adversarial files; Unicode; scanned PDFs; HTML sanitization; parser crash recovery.
**Acceptance:** Unsupported/failed content is quarantined; no macro/script/link execution; partial extraction cannot be silently marked complete.

## DOC-3 — Metadata, classification and review workflow
**Plan:** Define classification evaluation set and human correction workflow. Decide which metadata can be inferred and which requires explicit confirmation.
**Code:** Add document type detection, metadata extraction, confidence/quality signals, status lifecycle, reviewer approval and version/supersession links.
**Test/debug:** Confusable documents, misleading filenames, conflicting dates, missing owner, false positives/negatives and reviewer correction.
**Acceptance:** Filename alone never decides type/authority; unknown/low-confidence material stays in `NEEDS_REVIEW`; all changes are auditable.

## DOC-4 — Policy rule extraction and authority resolution
**Plan:** Define rule taxonomy, severity, applicability and conflict behavior with deterministic examples.
**Code:** Generate proposed structured rules with citations; add strict schema validation, authority model, conflict detector, approval and rollback.
**Test/debug:** Conflicting policies, stale policies, wrong jurisdiction, contradictory examples, injection text, missing approval owners and fabricated citations.
**Acceptance:** No LLM self-approval; no unresolved mandatory conflict can authorize a send; each active rule links to a reviewed source span and tests.

## DOC-5 — Retrieval, applicability and policy-aware draft design
**Plan:** Define category profiles, retrieval evaluation set, evidence requirements and draft quality rubric.
**Code:** Add scope-filtered hybrid retrieval, structured fact lookups, response plans, evidence trace, deterministic draft evaluator and source-aware review UI.
**Test/debug:** Unsupported claims, stale pricing, wrong recipient scope, missing disclaimer, conflicting sources, source revocation, prompt injection and different email categories.
**Acceptance:** Every material policy-backed claim is traceable; unsupported high-risk facts require review; style guidance cannot override mandatory rules; no auto-send on conflict.

## DOC-6 — Governance, observability and document lifecycle
**Plan:** Define document owner roles, retention, re-index/rollback, review cadence, impact analysis and audit requirements.
**Code:** Add policy dashboard, expiry/review reminders, impact preview, revocation, cache invalidation, re-index, backup/restore and deletion workflows.
**Test/debug:** Update/delete/revoke policy while drafts are queued; failed re-index; rollback; stale caches; unauthorized reviewer; restore after crash.
**Acceptance:** Revoked/superseded policies no longer authorize future actions; historical decisions remain traceable subject to retention; every lifecycle failure is visible and recoverable.

These DOC phases require the same evidence rules as all other phases. Do not mark the overall product phase accepted until the related document-intelligence acceptance tests pass.


---

# DEVELOPMENT CONTRACT V2 — POLICY AND GUARDRAIL DOCUMENT INTELLIGENCE

> This section is mandatory and extends the original contract. If any older section conflicts with this addendum, use the more restrictive security requirement and the more specific document-policy requirements here. The coding agent must merge these requirements into the relevant implementation phases, not treat this as an optional future enhancement.

## 14. New mandatory capability: policy-aware email drafting

BOTSKILL must not merely search documents and paste matching text into a prompt. It must understand the **type, authority, scope, effective dates, version, status, audience and intended use** of every company document, then apply approved policy rules to the email workflow.

A user may supply:
- Company policies, HR policies, employee handbooks and codes of conduct.
- Email guardrails, tone/style guides, brand voice and approved response templates.
- SOPs, escalation matrices, approval matrices and delegation-of-authority documents.
- Product/service documentation, FAQs, pricing sheets, refund/returns policies and SLAs.
- Legal notices, contracts, DPAs, privacy notices and regulatory guidance.
- Role-specific instructions, departmental procedures, recipient lists and communication boundaries.
- Historical emails as examples, which are **examples only** unless explicitly promoted and approved as policy.
- Scanned PDFs, DOCX, XLSX, PPTX, HTML, TXT, Markdown and other formats only when a safe parser exists for that type.

The user must be able to add, remove, replace, disable, version, approve and inspect sources through the local UI or CLI. Every source must have a visible processing state and any extraction/classification warnings.

### 14.1 Document intelligence pipeline

Implement this explicit pipeline:

`INGESTED → TYPE_DETECTED → TEXT_EXTRACTED → STRUCTURE_PARSED → CLASSIFIED → METADATA_EXTRACTED → POLICY_CANDIDATES → VALIDATED → HUMAN_APPROVED → ACTIVE`

Any step may instead produce `NEEDS_REVIEW`, `REJECTED`, `QUARANTINED`, `EXTRACTION_FAILED` or `SUPERSEDED`. A file must never become an active policy merely because it was uploaded or classified with high model confidence.

For each document, the system must:
1. Compute a cryptographic hash and identify duplicate or near-duplicate content.
2. Detect MIME/type from content as well as extension; reject mismatches and unsafe formats.
3. Enforce file-size, page-count, archive-expansion, processing-time and token limits.
4. Scan using available malware/security tooling when configured; never execute macros, scripts, embedded files, or document actions.
5. Extract text and structural metadata with a parser selected by file type; retain page/slide/sheet/section and table coordinates where feasible.
6. Detect language, document title, organization/department, intended audience, owner, author (if available), version, status, issue/effective/review/expiry dates, jurisdiction (if relevant), confidentiality marking and supersession references.
7. Classify document type and purpose with confidence and evidence. If uncertain, ask the user rather than inventing metadata.
8. Extract candidate rules into a typed schema, preserving exact source spans and provenance.
9. Detect contradictions, ambiguous obligations, missing context, expired policy and duplicate/conflicting versions.
10. Present a review screen with extracted metadata, proposed rules, source quotations, confidence/uncertainty, conflicts and suggested email categories affected.
11. Activate only after explicit approval from an authorized local user.
12. Index only the approved portions for production retrieval; retain rejected candidates separately for audit and troubleshooting.

### 14.2 Document taxonomy

Create a versioned taxonomy. Initial categories should include:

- `POLICY_MANDATORY`: approved company rules with explicit authority.
- `GUARDRAIL`: response restrictions, prohibited claims, approval conditions, tone boundaries and safety constraints.
- `SOP`: step-by-step process; may define workflow but cannot override higher-authority policies.
- `APPROVAL_MATRIX`: who may approve what, thresholds and delegation rules.
- `STYLE_GUIDE`: tone, formatting, language, signature, reading level and brand voice.
- `APPROVED_TEMPLATE`: approved text or structural template with conditions for use.
- `PRODUCT_FACTS`: verified product/service facts, feature lists, availability and technical details.
- `PRICING_OR_COMMERCIAL_TERMS`: price, discount, refund, payment and commitment limits; effective dates are essential.
- `FAQ_OR_KNOWLEDGE`: explanatory content; not automatically authoritative for policy.
- `CONTRACT_OR_LEGAL_SOURCE`: legal/contractual obligations requiring cautious extraction and potentially human/legal review.
- `REGULATORY_REFERENCE`: external regulation or guidance; jurisdiction and currentness must be recorded, and the tool must not claim legal interpretation is definitive.
- `HISTORICAL_EMAIL_EXAMPLE`: precedent/example only; never policy by itself.
- `UNTRUSTED_OR_UNKNOWN`: not eligible for active policy retrieval until reviewed.

Allow one document to have multiple labels but exactly one primary type. Type classification must include a rationale and confidence. Low confidence, legal/contractual material, or a document that contains conflicting signals must go to review.

### 14.3 Typed policy rule schema

Store extracted policy as data, not as free-form prompt paragraphs. The precise implementation may use Pydantic/JSON Schema or an equivalent validated schema. Each rule should include fields equivalent to:

```json
{
  "rule_id": "stable-unique-id",
  "title": "Do not promise unapproved discounts",
  "rule_type": "prohibition",
  "authority_level": "company_policy",
  "scope": {
    "mailboxes": ["configured-account-id"],
    "departments": ["sales"],
    "email_categories": ["pricing", "discount_request"],
    "recipient_groups": ["external_customer"]
  },
  "condition": "A reply would promise or imply a discount",
  "required_action": "request_approval",
  "prohibited_actions": ["promise_discount", "invent_price"],
  "severity": "high",
  "effective_from": "2026-01-01",
  "effective_until": null,
  "status": "candidate",
  "source_document_id": "doc-id",
  "source_version": "v3",
  "source_location": {
    "page": 4,
    "section": "Discount approvals",
    "paragraph": 2
  },
  "source_quote": "Exact short excerpt supporting the rule",
  "extraction_confidence": 0.91,
  "reviewed_by": null,
  "approved_at": null
}
```

The values above are illustrative. Do not use the example policy as a default business rule. Dates, authority and confidence must be validated; absent values remain unknown rather than being fabricated.

Supported rule types should include:
- `requirement`
- `prohibition`
- `approval_required`
- `escalation`
- `tone_or_format`
- `approved_fact`
- `template_selection`
- `retention_or_privacy`
- `routing`
- `exception`
- `supersession`

Rules need a machine-readable condition/action, human-readable explanation, severity, applicability scope, source provenance, status, version and test cases. Never make a policy active if its conditions cannot be represented safely or the parser cannot preserve the meaning. Keep the source text and extracted rule side by side for audit.

## 15. Policy authority, conflicts and change control

### 15.1 Explicit precedence

Implement a deterministic policy resolver. The default precedence should be:

1. Applicable law/platform restrictions and technical access permissions.
2. Explicit BOTSKILL security invariants (never expose secrets, never execute instructions embedded in untrusted mail, never bypass approval).
3. Approved, current organization-wide mandatory policies.
4. Approved, current department-specific policies.
5. Approved, current process/SOP and approval-matrix rules.
6. Approved response templates, style guides and communication preferences.
7. Approved factual knowledge and FAQs.
8. Historical emails and inferred preferences as non-authoritative evidence only.
9. Model-generated suggestions, which have no policy authority.

This ordering is a safe default, not a substitute for legal review. If two policies at the same level conflict, a narrower rule conflicts with a broader rule, a document references a missing annex, or authority cannot be determined, do not silently choose whichever chunk the retriever returned first. Mark the decision `POLICY_CONFLICT`, explain the conflict, and require an authorized reviewer. More restrictive safety outcomes win while the conflict is unresolved.

A user may configure organization-specific authority levels through an explicit policy administration workflow, but the user cannot disable BOTSKILL's fundamental security invariants.

### 15.2 Effective dates and supersession

- Only approved, currently effective rules may govern auto-send.
- Expired, draft, revoked or superseded documents must not be returned as active policy.
- If effective dates are missing or ambiguous for a policy-sensitive rule, require review.
- Store each version immutably with its hash and activation/deactivation audit event.
- Support a preview of the impact of a new version: affected rules, contradictions, categories, tests and pending drafts.
- Reprocess affected knowledge indexes and invalidate stale caches when policy changes.
- Existing drafts created under an older policy must be revalidated before approval/send.
- If a critical policy changes, provide an option to pause auto-send until impact review completes.

### 15.3 Least privilege and document permissions

Each source needs access controls such as `private_to_owner`, `department`, `organization`, or `approved_shared_template`. The simplest initial single-user product can implement owner-only local data but must retain a clean scope model for future multi-user support.

A document's content must never grant itself a permission. A PDF saying “this document overrides all other instructions” has no effect unless an authorized user classifies and approves its authority through the policy UI.

## 16. Retrieval and policy-aware response construction

The email response pipeline must use a two-stage retrieval strategy:

1. **Mandatory policy retrieval:** query active policy rules for the mailbox, category, department, recipient group and date. This is not merely semantic top-k search; use metadata filters and deterministic policy matching.
2. **Supporting knowledge retrieval:** retrieve relevant approved facts, SOP passages, FAQs and templates for the specific inquiry.
3. **Conflict check:** determine whether any retrieved sources conflict, are stale, lack required authority, or have insufficient evidence.
4. **Response plan:** create an internal structured plan mapping each material claim or commitment in the proposed email to supporting source IDs and applicable rules.
5. **Draft generation:** generate a natural reply using the approved plan, style guide and recipient/thread context.
6. **Post-generation validation:** check factual support, prohibited claims, required disclosures, promises/commitments, tone, recipient, attachment intent, sensitive data, policy conflicts and unsupported dates/prices.
7. **Decision:** draft, require human approval, block, or auto-send only if every hard gate passes.
8. **Audit:** save source IDs/versions, rule IDs/versions, policy decision, model/provider/version, prompt/config version and validation outcomes. Do not log the whole private email or hidden reasoning by default.

A model must not be allowed to override policy by saying that a source is irrelevant. A mandatory rule is enforced by deterministic code, not solely by prompt instructions. If required evidence is absent, the reply should ask a clarifying question, state that the team will confirm, or route for approval rather than fabricate a policy or fact.

### 16.1 Citation and evidence requirements

The UI must let a reviewer inspect why a draft was produced:
- Applied rules and their authority/status.
- Supporting documents, versions and page/section/paragraph references.
- Missing evidence and unresolved conflicts.
- Claims that were flagged or removed.
- Validation and approval results.

Customer-facing emails normally should not include internal policy citations unless the business explicitly wants them. Internal provenance belongs in the draft review/audit UI.

## 17. Document processing, parsing and indexing implementation

Use a parser registry rather than one universal parser. Select mature maintained libraries after reviewing their licenses and security posture. Keep parsers behind interfaces so they can be swapped.

Minimum requirements:
- PDF: page-aware text extraction; OCR only as an optional fallback for scans; flag low-quality OCR.
- DOCX: headings, paragraphs, tables, comments/headers where relevant; ignore embedded active content.
- XLSX: sheet names, table regions, formulas vs cached values, units, effective dates and hidden sheets; do not silently treat arbitrary spreadsheet cells as approved facts.
- PPTX: slide titles, text and notes if enabled, with slide provenance.
- HTML/email: sanitized text extraction; remove scripts and unsafe active content.
- TXT/Markdown/CSV: encoding detection, size limits and structure preservation.
- Unsupported or encrypted files: clear `UNSUPPORTED`/`ENCRYPTED_NEEDS_USER_ACTION` status; never attempt password cracking.
- ZIP/archive input: disabled by default; if enabled, defend against zip bombs, path traversal and excessive nested files.
- OCR output must be labeled as extracted/OCR-derived and lower-confidence until reviewed.

Index chunks with stable IDs, document ID/version, type, authority, status, scope, effective dates, page/section, hash and confidentiality label. Policy filters must apply before semantic ranking. A vector database is not mandatory for v1: start with SQLite/FTS or a lightweight local index if it meets quality/scale needs. Add embeddings/vector retrieval behind an interface only after evaluation shows benefit. The system must work offline with a supported local model or rules-only mode, subject to configured parser availability.

Re-indexing must be deterministic and incremental. On file replacement/deletion, mark the prior version inactive, remove its chunks from active retrieval, invalidate caches and preserve a minimal audit record. A failed index update must not leave a partially active policy.

## 18. Additional phase plan: document intelligence and policy engine

The original phases must be updated as follows. These are mandatory subphases; they can be separate numbered phases in the progress tracker if the agent finds that clearer.

### Phase 6A — Document intake and parser safety
**Plan**
- Inventory accepted file types, parser dependencies, licenses, known CVEs and data-flow risks.
- Design size/time/page/token limits, MIME validation, quarantine, extraction states and safe storage.
**Code**
- Implement upload/import interface, content hashing, parser registry, text/structure extraction, source-location metadata, size limits and explicit processing states.
- Keep original files and extracted text in separate controlled locations; no executable content is run.
**Test**
- PDF/DOCX/XLSX/PPTX/HTML/TXT/Markdown/CSV fixtures, malformed files, mismatched extensions, encrypted files, huge files, scanned PDFs, embedded objects and malicious archives.
**Debug**
- Fix extraction loss, encoding problems, parser crashes, memory exhaustion and false success statuses.
**Acceptance**
- Each file has a traceable processing result and source metadata.
- Failed extraction cannot produce an active policy.
- Parser errors are actionable and do not expose document contents in logs.

### Phase 6B — Document classification and metadata extraction
**Plan**
- Define taxonomy, confidence thresholds, required metadata by document type and human-review UX.
**Code**
- Implement classification for primary type, secondary labels, language, title, owner, department, audience, version, status, effective/review/expiry dates, jurisdiction, confidentiality and supersession references.
- Separate model suggestions from verified metadata; never guess missing dates or authority.
**Test**
- Ambiguous documents, mixed policy/SOP documents, historical examples, contradictory title/body, missing dates, multiple languages and adversarial prompt-injection text.
**Debug**
- Improve low-confidence routing and ensure a classification cannot activate rules.
**Acceptance**
- Low-confidence or high-impact/legal documents require review.
- The user can correct labels and metadata; changes are audited.
- Historical emails are not elevated to policy automatically.

### Phase 6C — Policy rule extraction, approval and conflict resolution
**Plan**
- Finalize typed schema, authority model, rule validation and conflict UX before enabling retrieval.
**Code**
- Extract candidate requirements/prohibitions/approvals/escalations/style rules/facts/templates into structured records with exact provenance.
- Build policy versioning, effective dates, supersession, same-level conflict detection and approval workflows.
- Add deterministic policy resolver.
**Test**
- Negation, exceptions, tables, footnotes, conflicting versions, expired policies, missing annexes, ambiguous authority and rules that are impossible to enforce.
**Debug**
- Verify that “must not” is never inverted to “must”; test exceptions and precedence explicitly.
**Acceptance**
- No rule becomes active without explicit approval.
- All active rules have source provenance and valid scope/status.
- Conflicts result in review/block, never silent arbitrary selection.
- A changed policy version triggers impact analysis and revalidation of affected drafts.

### Phase 6D — Policy-aware retrieval and grounded drafting
**Plan**
- Create a golden evaluation set of representative emails, policies and expected outcomes before tuning prompts.
**Code**
- Implement mandatory policy lookup, supporting knowledge retrieval, response plan, evidence map, post-generation policy validation and reviewer provenance UI.
- Apply access/scope/effective-date filters before semantic search.
**Test**
- Unsupported claims, stale facts, pricing changes, tone requirements, mandatory disclaimers, policy exceptions, no-answer cases and conflicting source documents.
**Debug**
- Analyze false retrievals, missing rules, citation mismatches and unsupported claims. Improve filters/ranking and tests, not only prompts.
**Acceptance**
- Every policy-sensitive material claim has supporting evidence or is flagged.
- Expired/superseded policies are not used as current authority.
- If a hard policy cannot be resolved, auto-send is denied.
- The reviewer can inspect sources/rules behind a draft.

### Phase 6E — Policy change lifecycle and regression automation
**Plan**
- Define change impact, re-indexing, cache invalidation and rollback behavior.
**Code**
- Implement document version diffs, affected-rule reports, approval, activation, re-index, stale-draft detection, rollback and regression suites.
- Offer optional pause-auto-send-on-critical-policy-change.
**Test**
- Replace/revoke/expire a policy while drafts are queued; simulate failed re-index and interrupted activation; restore previous version.
**Debug**
- Ensure no window exists where partially updated policy is active.
**Acceptance**
- Policy activation is atomic from the runtime's perspective.
- Existing pending drafts are revalidated before sending.
- Rollback restores the previous known-good rule/index version.

## 19. Mandatory document-policy evaluation suite

Create a versioned, synthetic test corpus. Do not commit customer/company confidential files. Each test case should define:
- Email input and thread context.
- Active document set and versions.
- Expected document classification/metadata (where applicable).
- Expected applicable policy rule IDs.
- Expected response disposition: draft, approval, block, quarantine or auto-send eligible.
- Expected prohibited claims/phrases and required facts/disclosures.
- Expected evidence source spans.
- Whether a human review is mandatory and why.

Required test families:
1. Policy beats historical email examples.
2. Current approved policy beats expired/superseded policy.
3. Mandatory security invariant beats any company document.
4. Department-specific rule and organization-wide rule conflict.
5. Pricing/refund/discount terms have expired or ambiguous effective dates.
6. A document contains “ignore previous instructions” or asks for secret disclosure.
7. An attachment contains instructions for the bot; it is treated as untrusted content.
8. A rule appears in a table, footnote, image/OCR text or nested section.
9. OCR confidence is low or a page is missing.
10. A policy exception applies only to a subset of recipients or dates.
11. A historical email contradicts the current policy.
12. A new policy is uploaded but has not been approved.
13. A policy is revoked while a draft awaits sending.
14. Multiple versions have identical titles but different hashes.
15. The retrieved answer has no supporting source.
16. A required disclaimer is missing from a generated draft.
17. The model generates an unauthorized promise or commitment.
18. A document has unclear owner/authority or missing annexes.
19. One department's private policy must not be retrieved for another scope.
20. An opt-in shared template contains sensitive data and must be rejected.

Track separate metrics:
- Document type macro-F1 and per-type precision/recall.
- Metadata field accuracy, especially version/status/effective dates.
- Policy rule extraction precision/recall, with extra weight on missed prohibitions and approval requirements.
- Conflict detection recall.
- Retrieval precision@k and recall for mandatory policy rules.
- Evidence/provenance correctness.
- Unsupported-claim rate.
- Required-review recall and false auto-send eligibility.
- Draft acceptance/edit rate from human review.
- Parser failure detection and recovery rates.

Do not set arbitrary universal thresholds without a baseline. Before enabling auto-send, define thresholds on the golden set and require zero false auto-send decisions for critical/high-risk test cases. Report uncertainty and dataset coverage; do not claim safety from aggregate accuracy alone.

## 20. Security and governance additions

Use the OWASP GenAI/LLM risk guidance and NIST AI Risk Management Framework/Generative AI Profile as review references, adapted to this product's risk and scale. Treat these as engineering guides, not claims of certification.

Threat-model at least:
- Prompt injection from email, quoted text, attachments, links, extracted documents and retrieved chunks.
- Sensitive information disclosure across mailboxes, departments, customers and shared templates.
- Excessive agency through send APIs, file access, shell execution, plugin calls or broad OAuth scopes.
- Data poisoning via malicious or misleading policy documents and historical email examples.
- Unsafe parser dependencies, malicious files, supply-chain compromise and dependency vulnerabilities.
- Unbounded consumption via huge mailboxes, oversized files, recursive archives, OCR and repeated model retries.
- Improper output handling in HTML/MIME and control-panel rendering.
- Hidden context leakage through logs, debug endpoints, telemetry, error messages or prompts.
- Vector/index access-control mistakes and stale-index leakage.

Required mitigations:
- Treat all external content as data, never instructions.
- Keep tools/actions allowlisted and parameter-validated; no arbitrary shell/code execution from mail or documents.
- Enforce least privilege in OAuth, local filesystem access and connector capabilities.
- Use isolated parser workers with resource/time limits for risky file processing where practical.
- Validate model output with typed schemas and deterministic policy checks.
- Redact secrets and minimize retained personal data.
- Pin and audit dependencies; run automated vulnerability and secret scans in CI.
- Authenticate the local control panel/API; bind to loopback by default, protect state-changing requests, and never expose it publicly without an explicit secure deployment design.
- Keep outbound telemetry disabled by default and disclose any optional diagnostics.
- Document incident response, credential revocation and safe pause procedures.

## 21. Expanded progress tracking

Update `docs/PROGRESS.md` with one row per phase and subphase:

| Phase | Status | Plan reviewed | Code complete | Tests passed | Debug/review done | Evidence/commit | Blockers |
|---|---|---|---|---|---|---|---|
| 0 | NOT STARTED | no | no | no | no | — | — |
| 6A | NOT STARTED | no | no | no | no | — | — |
| 6B | NOT STARTED | no | no | no | no | — | — |
| 6C | NOT STARTED | no | no | no | no | — | — |
| 6D | NOT STARTED | no | no | no | no | — | — |
| 6E | NOT STARTED | no | no | no | no | — | — |

The agent must add all original phases to the table, not only these examples. A phase may be marked `ACCEPTED` only if the plan was reviewed, code is complete, mandatory tests passed, failures were debugged, security review was completed, documentation was updated and a commit/test log is linked.

## 22. Required documentation outputs

In addition to existing outputs, maintain:
- `docs/DOCUMENT_INTELLIGENCE.md` — supported file types, parser limits, taxonomy and failure states.
- `docs/POLICY_SCHEMA.md` — rule schema, authority, scope, versioning and examples.
- `docs/POLICY_CONFLICTS.md` — precedence, conflict resolution and escalation behavior.
- `docs/THREAT_MODEL.md` — assets, trust boundaries, attack paths, mitigations and residual risks.
- `docs/EVALUATION.md` — golden corpus methodology, metrics, results and known limitations.
- `docs/OPERATIONS.md` — setup, backup/restore, credential revocation, kill switch, recovery and troubleshooting.
- `tests/fixtures/document_policy/` — synthetic documents only, with expected classifications and rules.
- `tests/evals/` — synthetic email/document cases and expected policy decisions.

## 23. Updated first action

Start with Phase 0. Audit the current repository and safely establish the baseline. Include document parsing, current policy/guardrail handling, existing knowledge sync, prompt construction, hard-coded rules and all send paths in the audit. Then propose a migration map and a phase plan covering the original phases plus 6A–6E. Do not start building document ingestion or autonomous sending until the test harness, typed policy model, approval boundaries and safety gates have been designed and reviewed.

---

# BOTSKILL V3 — Local LLM Platform, Provider Failover, and User Dashboard

> **V3 supersedes any conflicting prior instruction in this file.** It extends the approved email, policy-document, security, and phase-gated development contract with a first-class local inference runtime modeled on the verified public architecture in `Gayatri-Education/Gayatri`. It does not imply Gayatri code should be copied blindly: use its architectural pattern and inspect licensing/dependencies before reuse.

## 24. V3 product definition and decisions

BOTSKILL is one product distributed in two forms: (1) a standalone local-first application with a user-facing dashboard, runtime and service/CLI, and (2) an importable agent skill that invokes the same installed core through documented CLI/API commands. The skill is a portable entry point, not a second implementation of business logic.

The product MUST include:

- A native local inference path based on **`llama-cpp-python` + GGUF**, shipped and operated by BOTSKILL without requiring Ollama. This is the preferred bundled inference engine and the final generative fallback when every configured provider is unavailable, assuming the model is installed and the host has sufficient resources.
- Pluggable cloud AI APIs, local Ollama, and other explicitly supported OpenAI-compatible endpoints. Providers are optional integrations rather than hard dependencies.
- A resilient provider router with health checks, timeouts, bounded retries, circuit breakers, clear provenance, and configurable policy that does not bypass security or document-grounding gates during failover.
- A local dashboard for setup and daily operations: mailboxes/accounts, provider/model settings, local model lifecycle, business documents and policies, integrations/resources, draft review, autonomy and approvals, activity/audit, diagnostics, data privacy, backup/restore, and stop/pause controls.
- A policy-aware document intelligence pipeline that approves source material before it may govern replies. Uploading a file never grants it policy authority by itself.
- Offline-capable core workflows. When all generative inference options are unavailable, deterministic templates/rules must remain usable; if a task needs generation and the bundled local model is unavailable or incapable, the system returns a structured degraded/unavailable status rather than fabricating a reply or silently pretending a mock response is real.

**Terminology:** “Default fallback” means the packaged/local GGUF runtime is the last available *real generative model* tried in the configured failover chain, not that it can guarantee good generation on every machine or that it overrides explicit privacy rules. Provider ordering is configurable. The default policy should prefer a user-selected cloud/remote provider if configured and healthy, then configured local Ollama/OpenAI-compatible providers, and finally BOTSKILL's native llama.cpp runtime. A local-first profile reverses the order and must not transmit email/document content to remote services unless the user explicitly permits it.

## 25. Reference implementation findings and reuse boundary

The current public `Gayatri-Education/Gayatri` README and AI source show a useful reference pattern:

- A unified AI gateway coordinates provider-neutral requests, routing, adapter dispatch, failover, policy and telemetry (`central_platform/ai/gateway.py`).
- A typed `ModelRouter` separates task/capability selection and routing strategies (`central_platform/ai/model_router.py`).
- Provider adapters include a local GGUF path and multiple cloud providers (`central_platform/ai/adapters.py`).
- A model manifest describes the local artifact, quantization, context, format, capabilities, language support, and resource profile (`model_manifest.json`).
- `install_llama.py` handles installation of `llama-cpp-python`; the README documents a local GGUF model such as Qwen2.5-0.5B-Instruct Q4_K_M.

Reference links for developers:
- https://github.com/Gayatri-Education/Gayatri
- https://github.com/Gayatri-Education/Gayatri/blob/main/central_platform/ai/gateway.py
- https://github.com/Gayatri-Education/Gayatri/blob/main/central_platform/ai/model_router.py
- https://github.com/Gayatri-Education/Gayatri/blob/main/central_platform/ai/adapters.py
- https://github.com/Gayatri-Education/Gayatri/blob/main/model_manifest.json
- https://github.com/Gayatri-Education/Gayatri/blob/main/install_llama.py

**Do not assume every behavior of the upstream repository is production-validated just because the README describes it.** Inspect concrete implementation, licensing, current versions, model licenses, platform wheel availability, hardware, and tests. In particular, test real inference; do not use simulated consensus output, mock adapters, or fabricated health checks as evidence of model readiness. BOTSKILL's own tests and acceptance gates remain authoritative.

## 26. V3 target architecture

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ User surfaces                                                           │
│ Local Dashboard (browser UI) │ CLI │ Agent Skill │ Optional desktop shell│
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ authenticated loopback API / core calls
┌───────────────────────────────▼─────────────────────────────────────────┐
│ BOTSKILL application services                                           │
│ Accounts & Mail │ Draft/Approval Workflow │ Policy & Docs │ Scheduler    │
│ Audit/Observability │ Autonomy Controls │ Resource Readiness │ Backup     │
└────────────────┬───────────────────────────────┬────────────────────────┘
                 │                               │
┌────────────────▼────────────────┐  ┌───────────▼────────────────────────┐
│ AI Gateway / Model Router       │  │ Knowledge & Policy Engine          │
│ task classification             │  │ secure parsers / document registry │
│ capability-aware selection      │  │ versioned approved rule store       │
│ timeouts/circuit-breakers       │  │ hybrid search / access boundaries    │
│ per-provider telemetry          │  │ provenance / conflict validation      │
└───────────────┬─────────────────┘  └─────────────────────────────────────┘
                │
      Configurable provider chain (each adapter implements one contract)
                │
   ┌────────────┼─────────────────┬───────────────────┐
   ▼            ▼                 ▼                   ▼
 Cloud APIs   Ollama/local API   OpenAI-compatible   Native local GGUF
 (optional)   (optional)         endpoint (optional) llama-cpp-python
                                                       final real-model fallback
                │
                ▼
   Local durable storage: SQLite + migrations, encrypted secrets,
   document originals/indexes, drafts, idempotency ledger and audit log
```

All user-facing surfaces call the same runtime and repositories. Do not implement separate routing, policy precedence, send permissions, or message processing inside the dashboard or skill scripts. API handlers validate authorization and input, then call a service layer; the service layer enforces business invariants even when called from CLI or agent skill.

## 27. Local model runtime contract

### 27.1 Required engine

Use `llama-cpp-python` as the initial native inference backend for GGUF. It must be wrapped behind a BOTSKILL-owned `LocalModelRuntime` protocol so a future native llama.cpp server or alternate backend can be substituted without changing the email core. BOTSKILL must work without Ollama installed.

Minimum interfaces:

- `discover_models()` — find only model files explicitly installed/registered in BOTSKILL-managed directories and return manifest-backed metadata.
- `validate_manifest()` — validate schema, format, file existence, checksum when provided, supported architecture/runtime constraints, and license metadata.
- `install_model()` / `remove_model()` — only with explicit user action; show size, source, license, checksum, target path and estimated storage before download. Never run downloaded code.
- `health_check()` — perform a bounded runtime check, distinguishing `READY`, `NOT_INSTALLED`, `INVALID_ARTIFACT`, `DEPENDENCY_MISSING`, `INSUFFICIENT_RESOURCES`, `BUSY`, `TIMEOUT`, and `FAILED`.
- `generate()` — accept a typed task request, bounded input, timeout, context/token limits, and cancellation; return text plus model/runtime metadata and measured latency. Treat empty output, malformed structured output, exceptions, truncation, and timeout as failure, not success.
- `unload()` / `shutdown()` — explicitly release loaded model resources and gracefully stop inference without corrupting pending mail jobs.
- `runtime_info()` — report runtime version, model ID/path alias (never leak sensitive paths), context limit, quantization, device mode, memory observations where supported, and last health result.

Use streaming only if the UI and service support reliable cancellation and backpressure; streaming must not bypass final validation. The model process/worker must be supervised, time-limited, and cancellable. Avoid unbounded concurrency: a small CPU model may need a single inference worker and queue.

### 27.2 Model manifest

Maintain a validated `models/manifest.json` or equivalent database-backed manifest with at least:

```json
{
  "schema_version": 1,
  "model_id": "local-default-instruct",
  "display_name": "BOTSKILL Local Fallback",
  "provider": "llama_cpp",
  "format": "gguf",
  "artifact_path": "models/local-default.gguf",
  "download_source": null,
  "sha256": null,
  "quantization": null,
  "parameter_count": null,
  "context_length": 4096,
  "chat_template": null,
  "capabilities": ["text-generation", "instruction-following"],
  "license_id": "REQUIRED_BEFORE_DISTRIBUTION",
  "license_url": null,
  "estimated_ram_mb": null,
  "enabled": true
}
```

This is a schema example, not a claim that a named model has been selected. Phase 0 must benchmark candidate instruct models on the minimum target hardware and choose a default using measured quality, memory, latency, license, distribution rights and download reliability. Avoid hard-coding a model name based only on the Gayatri chemistry-tutor manifest; BOTSKILL needs general-business-email instruction following. Allow user-provided local GGUF model files when their license is compatible, the manifest validates, and resource checks pass.

Do not silently download a very large model. The setup/dashboard must communicate model size, required disk, memory, expected CPU/GPU support, license, and whether generation is available before starting. Prefer verified releases and checksums. Support a no-model installation in which non-generative features still run.

### 27.3 Resource-aware inference

- Detect practical resources without collecting unrelated host data; permit manual overrides for constrained or virtualized environments.
- Configure context length, generation tokens, CPU threads and GPU/offload options only when the installed build supports them.
- Never assume a model will fit solely from parameter count. Record measured peak memory and latency in local diagnostics.
- Enforce queue limits, per-request token limits, timeouts, cancellation and overload responses. A slow local inference request must not stall inbox synchronization, draft review, or the dashboard.
- Avoid loading duplicate model copies across workers. Decide process model during Phase 0 and verify memory use under concurrency.
- CPU-only mode is a required baseline. GPU acceleration is optional and must degrade gracefully to CPU or report clearly that the selected configuration is unsupported.
- The dashboard can set a preferred model, but cannot bypass manifest validation, provider health or configured privacy controls.

## 28. AI provider abstraction and failover

### 28.1 Provider protocol and adapters

Create a provider-neutral adapter protocol with:

- `provider_id`, provider kind, supported tasks/capabilities and privacy characteristics.
- `validate_config()` and secret-reference validation.
- `health_check(timeout)` with structured status and no sensitive prompt content.
- `generate(request)` and, where supported, `classify_email(request)` / structured JSON capability.
- normalized success/failure response, provider/model identity, latency, token counts when available, estimated cost when supported, retryability, and a safe sanitized error.
- optional cancellation and streaming contracts.

Initial adapters: native `llama-cpp-python` GGUF, Ollama API, cloud providers selected by the user (initially OpenAI, Anthropic, Gemini and/or OpenAI-compatible services after Phase 0 verifies scope), and generic OpenAI-compatible URL. Do not require all providers or all SDKs at installation. Keep optional dependencies extras-based and test unsupported-platform installation.

### 28.2 Routing profiles and default order

Implement at least these profiles:

- `CLOUD_PREFERRED`: selected healthy remote provider(s) → configured Ollama/compatible local endpoint(s) → native GGUF model.
- `LOCAL_FIRST`: native or configured local models first → remote providers only if explicit cloud fallback permission is enabled → no egress if permission is disabled.
- `LOCAL_ONLY`: local provider adapters only; the router must never attempt network generation endpoints.
- `CUSTOM`: user-specified ordered list, validated against currently configured provider IDs.

**V3 default final fallback:** native BOTSKILL `llama-cpp-python` runtime with an approved local GGUF model. Ollama is not the final fallback because it may be missing or its service may be down; BOTSKILL should manage its own native runtime.

For each request: validate task and privacy policy → build bounded context → obtain routing plan → attempt eligible providers sequentially or under carefully bounded hedging if later justified → classify errors → retry only retryable errors under strict budgets → open circuit after repeated failures → proceed to next allowed provider → record provenance → validate output → return. The chain must be finite, deduplicated and traceable. No unbounded retries and no retry storm.

Fallback must not silently change privacy tier. If a message or document is labelled local-only, a failed local provider can trigger another permitted local backend or a deterministic safe fallback, but cannot trigger a cloud API. Provider credentials being configured is not permission to send private content externally.

### 28.3 What counts as provider failure

Handle at least: missing key/configuration, invalid key, permission/plan error, rate limit, quota/budget reached, network unreachable, DNS/TLS failure, connect/read timeout, unavailable service, HTTP 5xx, unsupported model, invalid request/context too large, malformed response, empty response, refused or blocked response, invalid structured output, local runtime not installed, model load error, insufficient memory, cancellation, and output-validation failure.

Map each error to safe categories: `CONFIGURATION`, `AUTHENTICATION`, `RATE_LIMIT`, `QUOTA`, `NETWORK`, `TIMEOUT`, `PROVIDER_UNAVAILABLE`, `UNSUPPORTED_CAPABILITY`, `RESOURCE_EXHAUSTED`, `INVALID_RESPONSE`, `POLICY_BLOCKED`, `CANCELLED`, `UNKNOWN`. Retry/fallback policy must be explicit and tested per category. Do not log raw provider response bodies or secrets.

A technically successful provider response is not necessarily a valid reply. Continue to validation when appropriate; policy violations, missing source evidence or unsafe content must block output delivery, not automatically be waved through because another provider generated it.

### 28.4 Observability and controls

The dashboard must show configured, disabled, healthy, degraded, unavailable and error states distinctly; last successful check; last attempt; bounded sanitized failure reason; circuit-breaker status; active model/provider; latency; request and fallback counts; cost/token information when available; and recent failover events. Let users test a provider with a clearly marked synthetic health request, never an actual customer email by default. Never show actual API keys again after saving them.

## 29. Local dashboard — required user-facing control centre

### 29.1 Runtime and access model

Build a local web dashboard served by the BOTSKILL application (choose a stack after Phase 0 architecture review; reuse the current Python core if practical). Default bind must be loopback (`127.0.0.1`), not `0.0.0.0`. Require authenticated sessions even on loopback for sensitive operations, CSRF protection where cookie-based, secure headers, restrictive CORS, and bounded upload endpoints. Provide a clear warning and a separate documented hardening workflow if remote/LAN access is ever enabled. Never expose the unauthenticated admin dashboard to the internet.

Local dashboard startup must not initiate email sends, start live auto-send, share learning data, activate uploaded policies, download large models, or begin a wide filesystem scan. The setup wizard requests explicit choices and reports exactly what it will do.

### 29.2 Navigation and views

Required views and acceptance criteria:

1. **Overview** — overall runtime status; mailbox connectivity; provider/model availability; pending drafts/approvals; documents waiting for review; recent failures; last scheduler cycle; current autonomy mode; global Pause/Stop indicator. Every status links to a useful diagnosis and cannot show green when a required check did not run.
2. **Setup & resource readiness** — guided first-run setup, platform/dependency checks, storage/model path, database health/migrations, background scheduler, secret store availability, required permissions, and actionable missing-resource report. Setup is resumable and idempotent.
3. **Email accounts** — add/edit/disable/test mailbox; provider selection Gmail, Microsoft 365/Outlook, generic IMAP/SMTP and optional Windows Outlook COM; OAuth where supported; read/write/send permission scopes; folders/labels and sync window; signature/sender identity; allowed domains/recipients; send caps and exclusions. Credentials stored through a secret-store abstraction, never displayed after saving, and safe to rotate/revoke. Tests are non-destructive and cannot send a live message without a separate explicit send-test confirmation.
4. **AI providers & models** — add/edit/test/enable/disable a provider; securely enter credential references; configure base URL and model IDs; view capabilities/latency/status; set routing profile/order; toggle cloud egress; set budget/timeouts/retry limits; view failover trace. Secrets never render into UI or logs.
5. **Local model manager** — list installed models and manifest validation; show disk footprint, license/source/checksum, expected and observed resource profile, current status, selected fallback and runtime version; import local GGUF; download only after user confirmation; cancel download; validate checksum; test inference with a synthetic prompt; load/unload/recover; remove an artifact only after explicit confirmation and checking if a running profile references it. The UI must identify when there is no working local model fallback.
6. **Business documents & knowledge** — upload/select files, drag-and-drop optional; display progress and per-file parser/classifier status; preview extracted text safely; detect document type; show source, version, metadata, effective dates, scope, confidence, classification, errors, and extracted evidence; reprocess, supersede, archive or delete with confirmation; search documents; compare versions; view which policy/rules cite each file; download/export source only with permission. Quarantine documents until validated.
7. **Policies, approvals & guardrails** — inspect extracted rules, source quotations/locations, proposed authority/scope, conflicts and uncertain fields; approve/reject/edit with audit record; manage policy hierarchy; effective dates and supersession; auto-send risk classes; domain/category allowlist; blocked recipients/topics; mandatory escalation conditions. A policy edit revalidates impacted drafts and may pause auto-send. No model, file or incoming email can approve its own rules.
8. **Knowledge sources & integrations** — configure permitted folders, shared drives, project-specific read-only data sources or future connectors; show access boundaries, include/exclude patterns, sync method and last scan; user must explicitly authorize each root/connector. Do not auto-discover all disk content or enumerate unrelated credentials. Filesystem discovery starts with configured project roots only.
9. **Draft inbox & review queue** — show sender, subject, matched thread, proposed reply, citations/source rules, provider/model provenance, confidence/validation warnings, approvals, attachment intention, and send state. Support edit, approve, reject, regenerate, save as draft, defer and audit. Never allow a draft to be sent twice; show idempotency state. The send button must clearly name sender and recipients and require appropriate confirmation.
10. **Autonomy & scheduling** — `DRAFT_ONLY` default; supervised approval; category-bounded auto-send only after enabled by a privileged user; mailboxes and categories explicitly scoped; rate limits, max per hour/day, send window, allowed recipient scope, exclusions and expiry/review date. Visible kill switch stops new processing and outbound sends; pending tasks drain or remain safely queued. Restart must preserve safe state and never restore auto-send after a crash without re-reading persisted explicit configuration and checking all gates.
11. **Learning & templates** — reviewed generic scenario proposals and regression cases; per-item approval; local private history by default; opt-in sanitized sharing off by default. Show exactly what would leave the machine before export, allow preview/redaction/rejection, and prevent sharing raw email, names, contact info, tokens, policy text or business confidential facts. Never automatically modify executable code/prompts/tests based on incoming emails without review.
12. **Activity, audit & failures** — searchable metadata-only event feed, processing status, provider attempts/fallback chain, policy decision, document version, approvals, send/draft idempotency, retries, diagnosis and safe redacted error. Full email bodies are excluded by default; controlled access for troubleshooting must be permission-gated and time-limited. Export redacted diagnostics only after preview/confirmation.
13. **Privacy, security & retention** — current data storage paths, external egress permission/profile, retention periods, delete/export requests, backups, encryption and secret-store status, sanitized sharing preference, audit log retention and access roles. Provide deletion with references/index cleanup and documented limits for immutable audit records.
14. **Backup, restore & upgrades** — create consistent backup of database/config/non-secret metadata/document registry and optionally encrypted user data according to user choice; exclude secrets unless separately protected through the chosen secret store. Test restore in an isolated temporary location. Show schema version and migration/rollback status. A restore cannot enable auto-send or cloud egress without confirmation.
15. **Health & diagnostics** — check database, scheduler, mail read access, draft-write access, provider connectivity, local model inference, filesystem quotas, parser tools, pending jobs and clock/timezone. Synthetic tests only unless user explicitly selects a designated test resource. Status must include not-tested and stale results, not just pass/fail.
16. **User/access management** — initial local admin, session expiry, re-authentication for high-risk actions, role separation where multi-user is supported, recovery flow and audit logging. For single-user deployments, still protect secrets and high-impact actions against CSRF/local browser misuse.

### 29.3 UI/UX and usability requirements

- Professional responsive layout, keyboard navigation, visible focus, labelled controls, useful empty states, accessible contrast, readable error messages and confirmation for destructive/high-risk operations.
- Use plain language, not provider stack traces. Diagnostics may expose a safe technical detail after user requests it.
- Every asynchronous operation shows queued/running/succeeded/failed/cancelled, progress when measurable, retry where safe and trace/correlation ID. A spinner is not proof of completion.
- Forms validate server-side and client-side. API remains authoritative.
- Preserve form state during temporary errors and avoid double-submission.
- Polling or event stream disconnects must not falsely show green/stale data as current; display last refresh time and stale status.
- Core review, config, policy approval and pause/resume controls remain usable when the AI provider fails.

## 30. Dashboard API, persistence and security boundary

Phase 0 should fit the schema to current code; implement versioned migrations, typed schemas and service boundaries for at least these resources:

- `app_users`, `sessions`, `roles` / local ACL
- `mail_accounts`, `mail_account_permissions`, `provider_credentials_refs`
- `ai_providers`, `ai_models`, `model_manifests`, `routing_profiles`, `provider_health_events`
- `documents`, `document_versions`, `document_processing_jobs`, `document_chunks`, `policy_candidates`, `approved_policies`, `policy_conflicts`
- `knowledge_sources`, `source_sync_runs`
- `email_threads`, `email_messages_metadata`, `drafts`, `draft_revisions`, `approval_events`, `send_ledger`, `suppression_entries`
- `jobs`, `job_attempts`, `audit_events`, `health_checks`, `learning_proposals`, `sharing_events`, `backups`

Do not duplicate every raw email body in application tables. Store originals only when needed and permitted; otherwise use provider IDs and minimal metadata. Mailbox-specific records, documents, retrieval chunks, policies and drafts must be access-scoped. Add foreign keys, uniqueness constraints, transactional state changes and migrations with backup/rollback instructions.

All API routes must validate typed input and authorization at service and persistence boundaries. Never trust a hidden UI control to enforce permission. Implement CSRF controls for cookie sessions, safe file handling, request-size limits, upload extension/content inspection, path traversal prevention, authentication throttling, secure cookie attributes, restrictive CORS and security headers. Do not put API tokens in query strings or localStorage. Use OS credential store where practical and a well-reviewed encrypted fallback only when an appropriate key lifecycle exists; do not invent a weak home-grown cryptosystem.

## 31. Document ingestion, policy lifecycle and source-aware email drafting

Keep the previously defined policy/document workflow mandatory. V3 requires the same pipeline:

`INGESTED → TYPE_DETECTED → TEXT_EXTRACTED → STRUCTURE_PARSED → CLASSIFIED → METADATA_EXTRACTED → POLICY_CANDIDATES → VALIDATED → HUMAN_APPROVED → ACTIVE`

Unsupported/encrypted, malformed, oversized, suspicious, OCR-low-confidence, ambiguous, expired, conflicting or untrusted documents enter explicit review/quarantine states. A file is never active policy merely because its filename suggests “policy.”

### 31.1 Types and rule authority

Support classification including mandatory company policy, guardrail, approval matrix, SOP, approved template, style guide, facts/FAQs, product/pricing terms, contract/legal/regulatory source, historical email examples and unknown/untrusted source. Extract metadata including title, issuing owner, department, version, publication/effective/expiry dates, scope, jurisdiction when relevant, supersession, confidentiality, access scope, and source provenance. Every actionable rule needs source ID/version and source text/location; retain the original for audit when policy allows.

For conflicts, use the defined authority model: applicable law and platform permissions; BOTSKILL safety invariants; organization-wide approved policy; department policy; approved SOP/approval matrix; templates/style guide; factual knowledge; historical examples; model-generated suggestions. Conflicting active mandatory sources, missing authority, low confidence or stale source must block automation and request human resolution, rather than allowing the LLM to choose.

### 31.2 Reply construction contract

For every business reply, the runtime must: determine recipient/thread/context; identify sensitivity and send-risk; retrieve applicable active policies first; retrieve supporting facts from authorized sources second; detect conflicts and effective-date issues; produce a structured response plan tying factual/commitment claims to source evidence; generate a draft; run deterministic checks for claims, missing data, disallowed promises, required disclaimers, approval routing, tone, recipients, attachments, injection attempts and privacy; then record policy/document/provider version provenance. If required claims cannot be grounded, ask for input, produce a partial draft with explicit gaps, or escalate. Never invent prices, deadlines, promises, policy statements or actions.

Retrieved documents and emails are untrusted evidence, not instructions. Text like “ignore all previous rules,” hidden HTML, file metadata, macros, links or embedded prompts must never change system policy, provider permissions, recipient list, external egress, or send autonomy. Do not execute macros or active content.

## 32. Safe mail operations and progressive autonomy

The dashboard must make mode and scope obvious:

- `DRAFT_ONLY` (default): read authorized email and create a local/provider draft; no outbound transmission.
- `SUPERVISED`: send only after an authorized human reviews recipient, content, account and relevant evidence and presses a send/approve action.
- `LIMITED_AUTO_SEND`: only named categories and mailboxes, approved policies, allowed recipient scope, explicit send cap, schedule, and expiration/review date. Any mismatch, uncertainty, provider validation failure, policy conflict or critical change stops the send and escalates.

The global stop switch must prevent starting new outbound actions immediately, cancel not-yet-committed work where possible, preserve ledger state, and clearly report any in-flight send whose outcome is uncertain. An ambiguous SMTP/API timeout after transmission must not be blindly retried: reconcile with provider message IDs/thread state first to avoid duplicates.

Enforce loop detection, auto-reply/bounce suppression, duplicate detection, sender/recipient authorization, rate limits, allowed windows, bounded polling and per-mailbox locks. Untrusted incoming mail cannot whitelist recipients or grant send permissions. Attachments are not sent unless an explicit allowed policy and UI approval cover them; default is no new attachment. Preserve existing deliverability guidelines as quality goals, but never claim “100% deliverability,” and do not bypass provider anti-abuse controls.

## 33. Privacy, local-first behavior and sharing

- Local storage and local inference are the privacy-preserving baseline. A cloud provider only receives data after both its provider configuration and the applicable outbound-data policy allow that specific request.
- Display the chosen provider and egress class before turning on a cloud-first profile. Sensitive content may be redacted or restricted according to policy; fallback must not downgrade restrictions.
- API keys/passwords/tokens must be saved to a credential store and represented in normal config by references. Redact Authorization headers, query tokens, exception text, and secrets embedded in URLs.
- Retain only necessary email content. Define configurable retention and delete behavior for downloaded message copies, indexes, generated drafts and event logs.
- Model downloads, documents and archives are untrusted inputs: verify size, expected content, archive member paths and checksum; prevent path traversal, zip bombs and disk exhaustion. Limit uploads and unpacking resources.
- Opt-in sanitized sharing remains disabled by default. Share only specifically reviewed generic patterns/templates, never raw messages, documents, active policy text, PII, identifiers, secrets or company-specific facts. Sanitization must be tested against synthetic adversarial cases and include a user preview.

## 34. Updated phases and order of implementation

The prior phases in this document remain in force. Phase 0 is mandatory first. Preserve original phase numbering when mapping to the repository, and integrate the following V3 work as explicit subphases. If the original phase numbering conflicts, document the mapping in `docs/PHASE_MAP.md` rather than silently renumbering or skipping work.

### Phase 0 — Baseline audit and migration map (blocking)
Inspect all current source, script, tests and workflows in BOTSKILL plus reference Gayatri files. Run the current test suite; record exact command, exit code, skips and environment. Map email send paths, current mail credentials and provider support, rule/knowledge paths, current self-evolution and global sync, platform dependencies, UI/launcher behavior, state files and test side effects. Audit current claims against implementation (including any claimed reliability/deliverability). Identify duplication, dead ends and hidden failures. Produce baseline findings, proposed architecture, data migration plan, threat model and tests-before-refactor plan. No major refactor until reviewed.

### Phase 1 — Core domain, persistence and contracts
Implement state models, database migrations/repositories, message idempotency, structured errors, audit event interface, provider protocols, secret-store boundary and service layer. Preserve draft-only behavior and add tests for no-send by default.

### Phase 2 — Email connectors and normalized message lifecycle
Implement/test Gmail, Microsoft Graph/Microsoft 365, IMAP/SMTP and Windows Outlook COM as supported OS permits. Add permissions/scope checks, paginated retrieval, thread parsing, draft write, safe outbound send, retry classifications, rate limits, duplicate/loop/suppression protection, mailbox isolation and resumable sync. Verify each send route under tests and mock servers; live test only on designated test mailbox with confirmation.

### Phase 3 — AI gateway, typed adapters and model router
Define provider-neutral contract, task/capability schema, routing profiles, model registry, health checks, retries, circuit breakers, telemetry and strict privacy-aware fallback. Add deterministic failure classification and no-mock-in-production invariants. Test missing key, auth error, rate limit, network failure, timeout, empty/malformed output and cancellation.

### Phase 4 — Native local inference runtime
**4A.** Audit target OS/Python versions and llama-cpp-python wheel/build matrix. Add optional dependency and installer path that does not break basic installation where the package is unsupported.

**4B.** Implement manifest schema/validation, local model discovery/import, checksums, license notices, download consent, storage limits and secure artifact placement.

**4C.** Implement supervised local inference lifecycle, bounded concurrency, cancellation, memory/context limits, CPU-only baseline, optional GPU configuration, real synthetic inference and truthful health/readiness status.

**4D.** Integrate as final real-model fallback by default. Test all-cloud-down, Ollama-down, no API keys, local model missing, invalid checksum, model load OOM, timeout, empty response and successful real local inference. If local inference is not available, return degraded capability and deterministic-template alternatives; never present mock output as real AI.

**4E.** Benchmark at least two suitable small instruct GGUF candidates across target hardware: representative classification/drafting tasks, policy-grounded tasks, multilingual needs if in scope, latency, peak RAM, install burden, output quality, context, license and artifact origin. Select a default only after evaluation results are recorded. Keep user-supplied manifests supported.

### Phase 5 — Reliable routing and failover verification
Test each routing profile with fake providers and a real local integration test. Verify finite chain/no duplicates, correct retry class, circuit breaker half-open behavior, provider recovery, cancellation and concurrency limits. Assert local-only requests cause zero network generation calls. Ensure failover never changes data-sharing permission. Produce visible per-request trace in dashboard.

### Phase 6 — Document intelligence and policy-aware replies (mandatory subphases)
Retain subphases **6A–6E** from this document: safe parsers and intake; type/metadata classification; policy extraction/approval/conflict resolution; evidence-grounded drafting/validation; policy lifecycle/impact analysis and revalidation. Dashboard operations are required for upload, preview, review, approve, supersede, search and audit; CLI-only handling is not sufficient.

### Phase 7 — Local dashboard foundation
Implement local web-server lifecycle, authentication, API contracts, UI navigation, overview, setup/readiness, error states, session/security controls and accessible component system. Every operation uses core services; API tests must enforce same invariants as UI.

### Phase 8 — Dashboard: accounts, providers, models and integrations
Implement all sections in Section 29, with secret-store references, safe test actions, local model manager, configuration validation, provider chain preview and explicit egress permission. Test persistence across restart and configuration rollback.

### Phase 9 — Dashboard: documents, policy approval and knowledge
Implement upload queue, extraction progress, classification preview, source-linked rule review, policy conflict resolution, document versions, active/inactive state, source sync and impact preview. Every policy transition creates audit event; pending drafts are revalidated when an active policy changes.

### Phase 10 — Draft queue and autonomy controls
Implement draft review, edit/revise, source citations, model/provider provenance, preview, idempotent send ledger, approval evidence, per-category auto-send configuration, scheduler, kill switch and uncertain-send reconciliation. Auto-send remains disabled by default.

### Phase 11 — Self-evolution, feedback and sharing governance
Treat new scenarios and patterns as proposals. Generate synthetic regression tests, run them against a test suite, show diffs/impact and require review before activation. Keep local/private data private; sharing remains opt-in, reviewed, sanitized and previewed. No automatic source-code edits in production.

### Phase 12 — Security hardening and adversarial testing
Threat-model prompt injection, indirect injection in documents, data leakage, unsafe tool use, overbroad local filesystem scanning, credential theft, dashboard CSRF/session abuse, insecure loopback assumptions, SSRF via configurable provider URL, parser attacks, document poisoning, policy conflict exploits, OAuth scope abuse, mail loop/duplicate sending, resource exhaustion, malicious model artifact, and sanitized-share bypass. Add tests for access isolation and no unauthorized network egress.

### Phase 13 — Reliability, performance and recovery
Test prolonged polling, worker restart, provider flap, database lock/corruption recovery, model unload/reload, disk full, interrupted download, interrupted document extraction, expired token, revoked authorization, user pause and restart. Measure resource usage and queue latency under realistic workload. Backups and restore validated in an isolated location.

### Phase 14 — Packaging and installation
Deliver Windows setup/launcher first if consistent with current users, plus documented portable Python/local deployment; plan macOS/Linux support where dependencies permit. Installer should create safe directories, initialize DB, optionally install local inference and model only with consent, create shortcuts, perform migrations with backup, and provide clean uninstall/export. Never bundle secrets or an unlicensed model. Avoid silently requiring compilers on user machines; prefer verified compatible wheels or actionable fallback instructions.

### Phase 15 — Agent skill and CLI parity
Refactor skill instructions to use stable BOTSKILL CLI operations. Every instruction must map to a tested command/API; no direct editing of databases, credential files or arbitrary project resources. Verify that skill-installed workflows reuse the same policy gates, routing and send ledger as dashboard use. Skill works without Gemini/Antigravity or their home folders.

### Phase 16 — End-to-end acceptance and release
Run complete tests from clean install; install with no internet/provider/model; install with native GGUF only; install with Ollama only; cloud preferred with local fallback; local-first with cloud egress disabled; invalid credential; policy upload/review; conflicting policies; draft-only email flow; explicit supervised send test; stop/resume; backup/restore; upgrade/rollback; untrusted message/document prompt injection; multi-account isolation. Publish limitations, supported OS/Python/provider matrices, threat model, model-license notices, troubleshooting and release evidence. No “production-ready” label until mandatory acceptance gates pass.

## 35. Mandatory V3 evaluation and release gates

In addition to the prior metrics and security checks, maintain reproducible test corpora that include synthetic emails, document types, policy conflicts, model prompt cases and provider faults. At minimum measure:

- Provider health-check truthfulness, routing correctness, fallback activation/reason, retry budget, request latency percentiles, local model cold-start/warm-start latency, peak RAM/disk and queue overload correctness.
- Local-model benchmark results for intent classification, extraction, concise professional drafting, policy-grounded content, refusals/uncertain cases and prompt injection resistance. Models must be evaluated with the same system instructions and representative context sizes as production.
- Grounded-claim accuracy, unsupported commitments/rates/prices, source citation correctness, policy conflict detection, false auto-send eligibility, sensitive-data disclosure and retrieval authorization failures.
- Dashboard API authorization, CSRF, upload handling, secret redaction, stale-status detection, duplicate submits, canceled jobs, persistence after restart and keyboard accessibility basics.
- Email deliverability tests via controlled seed/test mailboxes, MIME correctness, duplicate-send incidents, suppression/loop behavior, bounce handling and provider throttling. Do not claim absolute inbox deliverability.

**Release blockers:** any unauthorized send; any cloud egress for local-only data; any bypass of required policy approval; a critical false-negative for a send restriction; cross-account data access; secret leakage; false success for model/mail/document failure; untrusted input changing system policy or permissions; unbounded retries; a duplicate send caused by failure handling; unlicensed/unverified model artifact distribution; or a dashboard high-impact action without server-side authorization. Critical/high-risk cases must default to no-send and human review.

## 36. Updated source-of-truth documents and progress tracker

Maintain existing documents required in earlier sections and add:

- `docs/V3_ARCHITECTURE.md` — component diagram, trust boundaries and service ownership.
- `docs/LOCAL_MODEL_RUNTIME.md` — llama-cpp runtime lifecycle, install paths, manifest, limits and troubleshooting.
- `docs/AI_PROVIDER_ROUTING.md` — adapter protocol, profiles, failure categories, fallback and privacy invariants.
- `docs/DASHBOARD_SPEC.md` — navigation, screens, API contract, auth, UX acceptance criteria and screenshots where helpful.
- `docs/DATA_RETENTION_AND_EGRESS.md` — data classes, storage paths, retention and external provider permissions.
- `docs/PHASE_MAP.md` — mapping from current implementation and older phase numbers to V3 phases, migration dependencies and blockers.
- `docs/PROGRESS.md` — one row per original phase and every V3 subphase, status, plan review, implementation, test results, debugging/review, commit SHA, evidence and blockers.
- `docs/MODEL_EVALUATION.md` — candidate versions, license/source/checksum, benchmarks, hardware, failure cases and selected default rationale.
- `docs/OPERATIONS.md` — setup, account/provider configuration, model selection, backups, restore, kill switch, credential revocation and incident response.

Every phase follows **inspect → plan → implement → test → debug → independent review → document → commit**. Keep original numbered phase scope; mark status as `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `FAILED`, or `ACCEPTED`. `ACCEPTED` requires test evidence, review, docs, security gate and commit reference. Do not mark a phase complete because code exists or because a mock test passed.

## 37. Immediate instructions to the coding agent

1. Audit BOTSKILL in its current state first. Do not replace files wholesale or assume the repository is empty. Current README claims must be verified against code and test output.
2. Inspect the actual Gayatri implementations listed in Section 25, particularly adapter/runtime behavior, router, manifest, model install and config patterns; document what is reusable conceptually and what should not be copied.
3. Produce `docs/PHASE_MAP.md`, `docs/V3_ARCHITECTURE.md`, a current-state and risk report, a model/runtime feasibility table, and an executable acceptance-test plan before undertaking major changes.
4. Preserve existing good email behavior only where tests establish it; fix unsupported guarantees and dead ends. Use a dedicated local model runtime with `llama-cpp-python` and a valid GGUF manifest, not an assumption that Ollama will exist.
5. Make the dashboard the human operations surface for adding files, policies, accounts, providers, models and integration resources. The core must remain CLI/skill-callable and headless-capable.
6. Finish one phase at a time. Update `docs/PROGRESS.md` and repository progress after each accepted phase. Never hide red tests, convert real tests into mocks merely to get green, or skip failing acceptance criteria without an explicit documented blocker.
7. Keep all runtime data, mailbox content, credentials, downloaded models, vector/index files, DBs and logs out of Git by default. Commit only source, safe examples, documentation and synthetic fixtures.
8. Do not turn on auto-send, remote document sharing, cloud egress or opt-in learning sharing as a side effect of setup, installation, model download, restoration, or migration. Require deliberate user action and audit it.

**Definition of V3 complete:** a user can install BOTSKILL, open an authenticated local dashboard, configure one or more mail accounts and optional AI providers, add and approve business policy documents, select/verify a local GGUF fallback, route requests through a tested finite failover chain, review evidence-grounded drafts, and enable only tightly scoped sending after explicit authorization—while being able to run the core locally without Ollama or cloud credentials and receive truthful, auditable failures whenever a required capability is not available.
