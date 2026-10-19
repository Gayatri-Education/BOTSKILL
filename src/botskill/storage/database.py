"""BOTSKILL — Durable SQLite Storage Manager & Repositories."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from botskill.core.models import (
    AuditEvent,
    DraftReply,
    EmailMessage,
    MessageState,
    PolicyCitation,
    PolicyDecision,
    PolicyRule,
    RuleType,
    SeverityLevel,
)

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    sender TEXT NOT NULL,
    recipients TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_text TEXT NOT NULL,
    body_html TEXT,
    received_at TEXT NOT NULL,
    state TEXT NOT NULL,
    idempotency_key TEXT UNIQUE NOT NULL,
    is_read INTEGER DEFAULT 0,
    inbound_intent TEXT,
    lease_owner TEXT,
    lease_expires_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drafts (
    draft_id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES messages(message_id),
    thread_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_text TEXT NOT NULL,
    body_html TEXT,
    policy_decision TEXT NOT NULL,
    decision_reason TEXT,
    citations_json TEXT,
    model_provenance TEXT NOT NULL,
    latency_ms REAL DEFAULT 0.0,
    staged_to_provider INTEGER DEFAULT 0,
    is_approved INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS policy_rules (
    rule_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    condition TEXT NOT NULL,
    required_action TEXT,
    prohibited_actions_json TEXT,
    source_document_id TEXT NOT NULL,
    source_location TEXT NOT NULL,
    source_quote TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS send_ledger (
    entry_id TEXT PRIMARY KEY,
    idempotency_key TEXT UNIQUE NOT NULL,
    message_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    account_id TEXT,
    message_id TEXT,
    severity TEXT NOT NULL,
    details_json TEXT NOT NULL
);
"""


class DatabaseManager:
    """Manages SQLite connections, WAL mode pragmas, and transactional safety."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._mem_conn: Optional[sqlite3.Connection] = None
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        else:
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
            self._mem_conn.execute("PRAGMA foreign_keys = ON;")
        self._initialize_schema()

    def get_connection(self) -> sqlite3.Connection:
        if self._mem_conn is not None:
            return self._mem_conn
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        with self._lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            try:
                yield cursor
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                if self._mem_conn is None:
                    conn.close()

    def _initialize_schema(self) -> None:
        with self.transaction() as cur:
            cur.executescript(SCHEMA_SQL)
            cur.execute("SELECT version FROM schema_version WHERE version = ?;", (SCHEMA_VERSION,))
            row = cur.fetchone()
            if not row:
                cur.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?);",
                    (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat())
                )

    def get_repository(self) -> "StorageRepository":
        return StorageRepository(self)



class StorageRepository:
    """High-level repository for messages, drafts, policy rules, and audit events."""

    def __init__(self, db_mgr: DatabaseManager):
        self.db = db_mgr

    # --- Message Operations ---

    def insert_message(self, msg: EmailMessage) -> bool:
        """Insert new message. Returns False if duplicate idempotency_key exists."""
        query = """
        INSERT OR IGNORE INTO messages (
            message_id, provider_id, thread_id, account_id, sender, recipients,
            subject, body_text, body_html, received_at, state, idempotency_key,
            is_read, inbound_intent, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.db.transaction() as cur:
            cur.execute(query, (
                msg.message_id, msg.provider_id, msg.thread_id, msg.account_id,
                msg.sender, json.dumps(msg.recipients), msg.subject, msg.body_text,
                msg.body_html, msg.received_at, msg.state.value, msg.idempotency_key,
                1 if msg.is_read else 0, msg.inbound_intent,
                datetime.now(timezone.utc).isoformat()
            ))
            return cur.rowcount > 0

    save_message = insert_message

    def get_message(self, message_id: str) -> Optional[EmailMessage]:
        query = "SELECT * FROM messages WHERE message_id = ?;"
        with self.db.transaction() as cur:
            cur.execute(query, (message_id,))
            row = cur.fetchone()
            if not row:
                return None
            return EmailMessage(
                message_id=row["message_id"],
                provider_id=row["provider_id"],
                thread_id=row["thread_id"],
                account_id=row["account_id"],
                sender=row["sender"],
                recipients=json.loads(row["recipients"]),
                subject=row["subject"],
                body_text=row["body_text"],
                body_html=row["body_html"],
                received_at=row["received_at"],
                state=MessageState(row["state"]),
                idempotency_key=row["idempotency_key"],
                is_read=bool(row["is_read"]),
                inbound_intent=row["inbound_intent"],
            )

    def update_message_state(self, message_id: str, new_state: MessageState) -> None:
        query = "UPDATE messages SET state = ? WHERE message_id = ?;"
        with self.db.transaction() as cur:
            cur.execute(query, (new_state.value, message_id))

    def claim_message_lease(self, message_id: str, lease_owner: str, ttl_seconds: int = 60) -> bool:
        """Atomic lease claiming to prevent concurrent processing. Allows lease renewal by the same owner."""
        now = datetime.now(timezone.utc).timestamp()
        expires = now + ttl_seconds
        query = """
        UPDATE messages
        SET lease_owner = ?, lease_expires_at = ?
        WHERE message_id = ? AND (lease_owner IS NULL OR lease_owner = ? OR CAST(lease_expires_at AS REAL) < ?);
        """
        with self.db.transaction() as cur:
            cur.execute(query, (lease_owner, str(expires), message_id, lease_owner, now))
            return cur.rowcount > 0

    # --- Draft Operations ---

    def save_draft(self, draft: DraftReply) -> None:
        query = """
        INSERT OR REPLACE INTO drafts (
            draft_id, message_id, thread_id, account_id, subject, body_text,
            body_html, policy_decision, decision_reason, citations_json,
            model_provenance, latency_ms, staged_to_provider, is_approved, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        citations_data = [c.model_dump() for c in draft.citations]
        with self.db.transaction() as cur:
            cur.execute(query, (
                draft.draft_id, draft.message_id, draft.thread_id, draft.account_id,
                draft.subject, draft.body_text, draft.body_html,
                draft.policy_decision.value, draft.decision_reason,
                json.dumps(citations_data), draft.model_provenance,
                draft.latency_ms, 1 if draft.staged_to_provider else 0,
                1 if draft.is_approved else 0, draft.created_at
            ))

    def get_draft(self, draft_id: str) -> Optional[DraftReply]:
        query = "SELECT * FROM drafts WHERE draft_id = ?;"
        with self.db.transaction() as cur:
            cur.execute(query, (draft_id,))
            row = cur.fetchone()
            if not row:
                return None
            citations = [
                PolicyCitation(**c) for c in json.loads(row["citations_json"] or "[]")
            ]
            return DraftReply(
                draft_id=row["draft_id"],
                message_id=row["message_id"],
                thread_id=row["thread_id"],
                account_id=row["account_id"],
                subject=row["subject"],
                body_text=row["body_text"],
                body_html=row["body_html"],
                citations=citations,
                policy_decision=PolicyDecision(row["policy_decision"]),
                decision_reason=row["decision_reason"],
                model_provenance=row["model_provenance"],
                latency_ms=row["latency_ms"],
                staged_to_provider=bool(row["staged_to_provider"]),
                is_approved=bool(row["is_approved"]),
                created_at=row["created_at"],
            )

    # --- Policy Rule Operations ---

    def insert_rule(self, rule: PolicyRule) -> None:
        query = """
        INSERT OR REPLACE INTO policy_rules (
            rule_id, title, rule_type, severity, condition, required_action,
            prohibited_actions_json, source_document_id, source_location,
            source_quote, is_active, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.db.transaction() as cur:
            cur.execute(query, (
                rule.rule_id, rule.title, rule.rule_type.value, rule.severity.value,
                rule.condition, rule.required_action,
                json.dumps(rule.prohibited_actions), rule.source_document_id,
                rule.source_location, rule.source_quote,
                1 if rule.is_active else 0, rule.created_at
            ))

    def list_active_rules(self) -> List[PolicyRule]:
        query = "SELECT * FROM policy_rules WHERE is_active = 1;"
        rules = []
        with self.db.transaction() as cur:
            cur.execute(query)
            for row in cur.fetchall():
                rules.append(PolicyRule(
                    rule_id=row["rule_id"],
                    title=row["title"],
                    rule_type=RuleType(row["rule_type"]),
                    severity=SeverityLevel(row["severity"]),
                    condition=row["condition"],
                    required_action=row["required_action"],
                    prohibited_actions=json.loads(row["prohibited_actions_json"] or "[]"),
                    source_document_id=row["source_document_id"],
                    source_location=row["source_location"],
                    source_quote=row["source_quote"],
                    is_active=bool(row["is_active"]),
                    created_at=row["created_at"]
                ))
        return rules

    # --- Audit Operations ---

    def log_audit(self, event: AuditEvent) -> None:
        query = """
        INSERT INTO audit_events (
            event_id, timestamp, event_type, account_id, message_id, severity, details_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        with self.db.transaction() as cur:
            cur.execute(query, (
                event.event_id, event.timestamp, event.event_type,
                event.account_id, event.message_id, event.severity.value,
                json.dumps(event.details)
            ))
