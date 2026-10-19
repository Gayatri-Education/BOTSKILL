# BOTSKILL v3.0 Phase Map & Execution Matrix

This document maps all original development contract phases (Phase 0–16), the Document Intelligence subphases (DOC-1 to DOC-6 / 6A–6E), and the V3 local runtime requirements into an executable, verifiable sequence.

Every phase adheres to:
$$\text{Phase Plan} \longrightarrow \text{Code / Implement} \longrightarrow \text{Run Tests} \longrightarrow \text{Debug} \longrightarrow \text{Test Green} \longrightarrow \text{Commit \& Next}$$

---

## 1. Unified Phase Mapping Table

| Phase ID | Name & Scope | Key Components | Dependencies | Acceptance Gate |
|---|---|---|---|---|
| **Phase 0** | **Baseline Audit & Environment Mapping** | Environment verification, Git init, baseline audit, Gayatri pattern analysis | None | Baseline audit approved; zero behavior change; tests run clean |
| **Phase 1** | **Core Domain, Persistence & Contracts** | Typed Pydantic domain models, SQLite migrations, message idempotency ledger | Phase 0 | No-send by default invariant proven; atomic state transitions pass unit tests |
| **Phase 2** | **Email Connectors & Message Lifecycle** | Windows Outlook COM (MAPI), IMAP/SMTP, Graph adapters, safe draft staging | Phase 1 | Outlook discovery passes; test mode proves no emails transmitted; mock contract tests pass |
| **Phase 3** | **AI Gateway & Provider Router** | Provider-neutral adapter protocol, router profiles (`LOCAL_ONLY`, `LOCAL_FIRST`), circuit breakers | Phase 1 | Failure classification tested; privacy-preserving routing passes |
| **Phase 4** | **Native Local SLM Runtime** | `llama-cpp-python` wrapper, `models/manifest.json`, local Qwen2.5-0.5B GGUF import | Phase 3 | Real offline CPU inference benchmark passes (<1.5s latency, ~680MB RAM) |
| **Phase 5** | **Reliable Routing & Failover Verification** | Multi-adapter failover chain, circuit breakers, per-request telemetry | Phase 4 | Finite fallback chain verified; simulated outage triggers graceful local SLM fallback |
| **Phase 6A** | **Doc Intake & Safe Parsers** | PDF (`pypdf`/`fitz`), DOCX (`docx`), TXT/Markdown, CSV parsers with size/hash bounds | Phase 1 | Malformed/oversized files quarantined; zero executable macro execution |
| **Phase 6B** | **Document Classification & Metadata** | Document taxonomy (Policy, Guardrail, SOP, FAQ), effective dates, scope | Phase 6A | Unknown metadata flagged for review; historical emails never promoted to policy |
| **Phase 6C** | **Rule Extraction & Conflict Resolution** | Structured rule schema (`HR-001`), deterministic precedence, conflict detection | Phase 6B | Conflicting rules block auto-send; human approval required for activation |
| **Phase 6D** | **Grounded Drafting & Provenance** | Policy retrieval, response plan, draft generation with source citations | Phase 6C, Phase 4 | Every policy claim links to verified document source span; no fabricated numbers |
| **Phase 6E** | **Policy Lifecycle & Invalidation** | Atomic policy updates, re-indexing, invalidating pending drafts on change | Phase 6D | Outdated drafts flagged; rollback restores prior valid rule set |
| **Phase 7** | **Local Dashboard Foundation** | FastAPI server on `127.0.0.1:8765`, session auth, CSRF headers, base UI layout | Phase 1 | Loopback-only binding verified; authenticated endpoints reject CSRF |
| **Phase 8** | **Dashboard: Accounts & AI Management** | Outlook account management UI, local SLM telemetry, routing configuration | Phase 7, Phase 2, Phase 4 | UI reflects real Outlook MAPI accounts; local model test prompt works |
| **Phase 9** | **Dashboard: Knowledge & Policy Matrix** | Document upload, text preview, rule review & approval screen | Phase 8, Phase 6 | Uploaded document preview renders; human rule approval transition verified |
| **Phase 10** | **Draft Queue & Autonomy Controls** | Review queue, in-place edit, 1-click Outlook draft staging, Emergency Stop | Phase 9 | Draft staged in Outlook without transmitting; Kill Switch halts all processing |
| **Phase 11** | **Controlled Learning & Governance** | Private scenario proposals, synthetic test generation, opt-in sanitized export | Phase 10 | Exports reject PII/secrets; self-modification of executable code blocked |
| **Phase 12** | **Security Hardening & Adversarial Tests** | Prompt injection defenses, credential redaction, path traversal checks | Phase 10 | Adversarial corpus passes; zero egress verified under local-only mode |
| **Phase 13** | **Reliability, Recovery & Resilience** | Power-loss crash recovery, stale lease reaper, database backups | Phase 10 | Crash simulation recovers without message duplication or silent drops |
| **Phase 14** | **Packaging & Windows Launcher** | `run_botskill.bat`, local directory initialization, migration check | Phase 13 | Fresh machine install launches cleanly without external tools |
| **Phase 15** | **Agent Skill & CLI Parity** | `botskill` CLI commands, portable `skill/email-responder/SKILL.md` | Phase 14 | CLI commands execute all dashboard actions; skill works without Gemini home |
| **Phase 16** | **E2E Acceptance & Release Sign-Off** | Full regression test suite, clean run, release verification | Phase 15 | All release gates pass; final sign-off confirmation recorded |

---

## 2. Execution Discipline & Gates

1. **Strict Linearity:** Do not begin Phase $N+1$ until Phase $N$ acceptance criteria pass and test results are recorded.
2. **Subdivision of Large Phases:** Subphases like Phase 6 (6A–6E) and Phase 4 (4A–4E) are executed sequentially with individual test/debug steps.
3. **Draft-Only Safety:** Outbound network transmission is locked in `DRAFT_ONLY` mode throughout all phases.
