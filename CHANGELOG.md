# Changelog

All notable changes to the BOTSKILL project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [3.0.0] - 2026-10-20

### Added
- **Core Domain & Storage Engine (Phase 1):** Typed Pydantic domain models (`EmailMessage`, `DraftReply`, `PolicyRule`, `AuditEvent`), SQLite with WAL mode, foreign keys, and atomic lease locking (`claim_message_lease`).
- **Windows Outlook MAPI Connector (Phase 2):** Integration with Microsoft Outlook via `win32com.client`, quote stripping, multi-account polling across 6 corporate mailboxes, and non-negotiable `DRAFT_ONLY` transmission barrier.
- **AI Gateway & Circuit Breakers (Phase 3):** Three-tier routing architecture (`LOCAL_ONLY`, `LOCAL_FIRST`, `CLOUD_FIRST`), sliding-window failure tracking, half-open recovery, and sensitive credential scrubbers.
- **Native Local SLM Runtime (Phase 4):** Offline local CPU inference runtime powered by `llama-cpp-python` and ChatML prompt templating with `Qwen2.5-0.5B-Instruct` Q4_K_M GGUF.
- **Failover Routing Verification (Phase 5):** Verified automatic fallbacks during simulated cloud outages with zero privacy boundary leaks in `LOCAL_ONLY` mode.
- **Document Intelligence & Policy Matrix (Phases 6A–6E):** Safe parsers for PDF, DOCX, TXT, and CSV formats, confidence-scored classifiers, candidate rule extraction, human approval workflows, and deterministic policy enforcement with exact provenance citations.
- **Local Dashboard & Security Auth (Phase 7):** Industrial-grade, decluttered web workstation interface combining Claude Cowork review ergonomics, Perplexity clarity, and Antigravity HUD diagnostics. Enforced loopback binding (`127.0.0.1`), session management, and cryptographic CSRF tokens.
- **Dashboard Accounts & AI Management (Phase 8):** Real-time mailbox polling endpoints, live Outlook connection probing, AI profile toggling, and live latency benchmarks.
- **Knowledge & Policy Matrix UI (Phase 9):** Drag-and-drop document upload (25 MB bounded), SHA-256 integrity hashing, candidate rule extraction, and human-in-the-loop rule approval/deactivation.
- **Draft Review Queue & Autonomy Controls (Phase 10):** Master-detail draft review queue, in-place draft edits, 1-click safe staging to Outlook's `Drafts` folder, and Emergency Stop Kill Switch.
- **Controlled Learning & Governance (Phase 11):** Autonomous interaction capture, multi-pattern `PIISanitizer` (redacting emails, phones, API keys, bearer tokens, credit cards), and code anti-tamper self-modification guards.
- **Security Hardening & Adversarial Evals (Phase 12):** Defensive prompt injection guards, strict path traversal guards, and zero cloud egress network boundaries.
- **Reliability & Crash Recovery (Phase 13):** Stale lease reapers, crash recovery managers executing SQLite integrity checks, WAL truncation checkpoints, and non-blocking online backups (`conn.backup()`).
- **Packaging & Windows Launcher (Phase 14):** Automated environment bootstrapping, CLI entrypoints, and double-clickable `run_botskill.bat` launcher.
- **Agent Skill & CLI Parity (Phase 15):** Unified `botskill` CLI suite with global argument normalization, and portable `autonomous-email-responder` agent skill (`skill/email-responder/SKILL.md`).
- **End-to-End Acceptance (Phase 16):** Full lifecycle acceptance test suite validating 100% test pass rate across 69 tests.

---

## [0.1.0-phase0] - 2026-10-20

### Added
- **Phase 0 Baseline Audit:** Established `docs/BASELINE_AUDIT.md` verifying Python 3.12, `llama_cpp`, `win32com.client`, and local system readiness.
- **Local Outlook Discovery:** Verified non-destructive MAPI read probe discovering 6 active business accounts (`hr@aivaratech.online`, etc.).
- **Local SLM Identification:** Located `qwen2.5-0.5b-instruct-q4_k_m.gguf` (491 MB) for offline local execution.
- **Bespoke Workstation UI/UX:** Created `docs/ui_ux_design_plan.md` and interactive prototype `dashboard_cowork.html` fusing Perplexity clarity, Claude Cowork ergonomics, and Antigravity HUD precision.
- **Architecture & Planning:** Published `docs/PHASE_MAP.md`, `docs/V3_ARCHITECTURE.md`, `docs/PROGRESS.md`, and `docs/DECISIONS.md`.
- **Repository Setup:** Initialized Git version control with production-grade `.gitignore`.
