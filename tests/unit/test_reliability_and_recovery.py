"""Unit tests for Phase 13 — Reliability, Crash Recovery, and Resilience."""

import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
import pytest

from botskill.core.models import EmailMessage, MessageState
from botskill.resilience.recovery import CrashRecoveryManager
from botskill.resilience.reaper import StaleLeaseReaper
from botskill.storage.database import DatabaseManager


def test_stale_lease_reclamation():
    db_mgr = DatabaseManager(":memory:")
    repo = db_mgr.get_repository()

    now = datetime.now(timezone.utc).isoformat()

    # 1. Message with expired lease (abandoned by crashed worker)
    msg_expired = EmailMessage(
        message_id="msg_dead_worker",
        provider_id="fake",
        thread_id="th_1",
        account_id="hr@aivaratech.online",
        sender="intern@example.com",
        recipients=["hr@aivaratech.online"],
        subject="Internship Application",
        body_text="Applying for remote role",
        received_at=now,
        state=MessageState.CLAIMED,
        idempotency_key="key_dead_01",
    )
    repo.insert_message(msg_expired)

    # Force expired lease in database
    with db_mgr.transaction() as cur:
        cur.execute(
            "UPDATE messages SET lease_owner = ?, lease_expires_at = ?, state = 'CLAIMED' WHERE message_id = ?;",
            ("dead_worker_pid_8888", str(time.time() - 60.0), "msg_dead_worker"),
        )

    # 2. Message with active valid lease
    msg_active = EmailMessage(
        message_id="msg_active_worker",
        provider_id="fake",
        thread_id="th_2",
        account_id="hr@aivaratech.online",
        sender="student@example.com",
        recipients=["hr@aivaratech.online"],
        subject="Student inquiry",
        body_text="Inquiry regarding remote work",
        received_at=now,
        state=MessageState.CLAIMED,
        idempotency_key="key_active_01",
    )
    repo.insert_message(msg_active)

    with db_mgr.transaction() as cur:
        cur.execute(
            "UPDATE messages SET lease_owner = ?, lease_expires_at = ?, state = 'CLAIMED' WHERE message_id = ?;",
            ("active_worker_pid_1234", str(time.time() + 120.0), "msg_active_worker"),
        )

    # 3. Run Reaper
    reaper = StaleLeaseReaper(db_mgr)
    reaped = reaper.reap_stale_leases()

    assert "msg_dead_worker" in reaped
    assert "msg_active_worker" not in reaped

    # 4. Verify states in DB
    dead_in_db = repo.get_message("msg_dead_worker")
    assert dead_in_db.state == MessageState.DISCOVERED

    active_in_db = repo.get_message("msg_active_worker")
    assert active_in_db.state == MessageState.CLAIMED


def test_startup_recovery_manager_workflow():
    db_mgr = DatabaseManager(":memory:")
    recovery_mgr = CrashRecoveryManager(db_mgr)

    summary = recovery_mgr.run_startup_recovery()

    assert summary["status"] == "RECOVERED"
    assert summary["integrity_ok"] is True
    assert summary["wal_checkpoint_ok"] is True


def test_atomic_online_backup(tmp_path: Path):
    db_file = tmp_path / "primary.db"
    backup_file = tmp_path / "snapshots" / "backup_20261020.db"

    db_mgr = DatabaseManager(str(db_file))
    repo = db_mgr.get_repository()

    # Seed data
    msg = EmailMessage(
        message_id="msg_backup_test",
        provider_id="fake",
        thread_id="th_backup",
        account_id="contactus@aivaratech.online",
        sender="client@corp.com",
        recipients=["contactus@aivaratech.online"],
        subject="SLA question",
        body_text="What is your customer support SLA?",
        received_at=datetime.now(timezone.utc).isoformat(),
        state=MessageState.DISCOVERED,
        idempotency_key="key_backup_001",
    )
    repo.insert_message(msg)

    # Perform online non-blocking backup
    recovery_mgr = CrashRecoveryManager(db_mgr)
    result_path = recovery_mgr.create_backup(str(backup_file))
    assert Path(result_path).exists()

    # Verify backup database contains the data
    backup_mgr = DatabaseManager(result_path)
    backup_repo = backup_mgr.get_repository()
    restored_msg = backup_repo.get_message("msg_backup_test")
    assert restored_msg is not None
    assert restored_msg.sender == "client@corp.com"


def test_crash_simulation_transaction_rollback():
    db_mgr = DatabaseManager(":memory:")
    repo = db_mgr.get_repository()

    now = datetime.now(timezone.utc).isoformat()
    msg = EmailMessage(
        message_id="msg_crash_candidate",
        provider_id="fake",
        thread_id="th_crash",
        account_id="hr@aivaratech.online",
        sender="crashed@example.com",
        recipients=["hr@aivaratech.online"],
        subject="Crash Test",
        body_text="This will simulate worker failure mid-transaction",
        received_at=now,
        state=MessageState.DISCOVERED,
        idempotency_key="key_crash_01",
    )

    # Simulate catastrophic crash mid-transaction before commit
    with pytest.raises(RuntimeError, match="SIMULATED_POWER_FAILURE"):
        with db_mgr.transaction() as cur:
            cur.execute(
                """
                INSERT INTO messages (
                    message_id, provider_id, thread_id, account_id, sender, recipients,
                    subject, body_text, body_html, received_at, state, idempotency_key,
                    is_read, inbound_intent, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    "msg_crash_candidate", "fake", "th_crash", "hr@aivaratech.online",
                    "crashed@example.com", "[]", "Crash Test", "Uncommitted text",
                    None, now, MessageState.DISCOVERED.value, "key_crash_01",
                    0, None, now,
                ),
            )
            # Power failure occurs before commit
            raise RuntimeError("SIMULATED_POWER_FAILURE")

    # Invariant: Uncommitted item must NOT exist in storage
    aborted_msg = repo.get_message("msg_crash_candidate")
    assert aborted_msg is None
