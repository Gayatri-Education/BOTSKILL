"""BOTSKILL — Distributed Lease Reaper for Abandoned & Crashed Worker Recovery."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import List, Optional

from botskill.core.models import AuditEvent, MessageState, SeverityLevel
from botskill.storage.database import DatabaseManager

logger = logging.getLogger("botskill.resilience.reaper")


class StaleLeaseReaper:
    """Scans and reclaims abandoned message leases left behind by crashed workers or power loss."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def reap_stale_leases(self) -> List[str]:
        """Finds all expired leases, resets them to DISCOVERED state, and releases ownership."""
        now = time.time()
        reaped_ids: List[str] = []

        query_find = """
        SELECT message_id, lease_owner, lease_expires_at, state
        FROM messages
        WHERE lease_owner IS NOT NULL
          AND CAST(lease_expires_at AS REAL) < ?
          AND state IN ('CLAIMED', 'PARSED', 'CLASSIFIED');
        """

        query_reset = """
        UPDATE messages
        SET lease_owner = NULL,
            lease_expires_at = NULL,
            state = ?
        WHERE message_id = ?;
        """

        with self.db.transaction() as cur:
            cur.execute(query_find, (now,))
            rows = cur.fetchall()

            for row in rows:
                msg_id = row["message_id"]
                dead_owner = row["lease_owner"]
                cur.execute(query_reset, (MessageState.DISCOVERED.value, msg_id))
                reaped_ids.append(msg_id)
                logger.warning("Reaped stale lease for message '%s' abandoned by '%s'", msg_id, dead_owner)

        if reaped_ids:
            repo = self.db.get_repository()
            audit = AuditEvent(
                event_id=f"audit_reap_{int(time.time() * 1000)}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                event_type="STALE_LEASES_REAPED",
                severity=SeverityLevel.MEDIUM,
                details={
                    "reaped_count": len(reaped_ids),
                    "message_ids": reaped_ids,
                    "restored_state": MessageState.DISCOVERED.value,
                },
            )
            repo.log_audit(audit)

        return reaped_ids
