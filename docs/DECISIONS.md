# BOTSKILL Architecture Decision Records (ADRs)

---

## ADR-001: Local-First Inference with llama-cpp-python and GGUF
- **Date:** October 20, 2026
- **Status:** Approved
- **Context:** The system must generate intelligent, grounded draft replies without sending company or customer data to third-party cloud AI APIs unless explicitly authorized. The system must also run without requiring external servers like Ollama.
- **Decision:** Adopt `llama-cpp-python` (v0.3.35) as the default native execution engine, bundled with `Qwen2.5-0.5B-Instruct` in `Q4_K_M` GGUF format (~491 MB).
- **Consequences:**
  - Zero cloud egress by default.
  - Low hardware requirement: ~680 MB peak RAM on CPU.
  - Sub-500ms latency on local CPU inference.

---

## ADR-002: Dual Integration Mode: Standalone App + Portable Agent Skill
- **Date:** October 20, 2026
- **Status:** Approved
- **Context:** BOTSKILL needs to be usable by non-technical managers via a local browser control center and also callable by autonomous AI agents.
- **Decision:** Build a single core runtime exposed through a local FastAPI loopback server (`127.0.0.1:8765`), a documented CLI (`botskill`), and an Agent Skill (`skill/email-responder/SKILL.md`) that wraps CLI commands.
- **Consequences:**
  - One source of truth for business logic and policy enforcement.
  - No duplicated business logic between the dashboard and skill scripts.

---

## ADR-003: Native Windows Outlook COM / MAPI Integration
- **Date:** October 20, 2026
- **Status:** Approved
- **Context:** The user already operates Microsoft Outlook locally with 6 active business accounts (`hr@aivaratech.online`, etc.). Asking for passwords or setting up OAuth apps in cloud consoles adds friction and security risks.
- **Decision:** Interface directly with local Outlook desktop using `win32com.client.Dispatch("Outlook.Application")` via MAPI.
- **Consequences:**
  - Discovers existing accounts automatically with zero password storage.
  - Staging creates real Outlook drafts directly in the user's `Drafts` folder.
  - IMAP/SMTP and Graph connectors remain available as pluggable adapters for Linux or cloud deployments.

---

## ADR-004: Bespoke Industrial UI/UX Fusion (Claude Cowork + Perplexity + Antigravity)
- **Date:** October 20, 2026
- **Status:** Approved
- **Context:** Generic developer themes cause visual fatigue and cognitive clutter. The user required a calm, focused, uncluttered experience where all operations are at the fingertips.
- **Decision:** Synthesize the uncluttered clarity of Perplexity, the warm coworker ergonomics of Claude Cowork, and the surgical HUD precision of Antigravity into a single bespoke palette (Graphite Obsidian `#0f1115`, Velvet Card `#181d26`, Arctic Mint `#14b8a6`, Warm Amber `#f59e0b`).
- **Consequences:**
  - Eliminates theme fragmentation.
  - Provides a master-detail review queue with 1-click Outlook staging.
