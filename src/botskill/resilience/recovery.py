"""BOTSKILL — Crash Recovery, WAL Checkpointing, and Automated Backup Manager."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

from botskill.resilience.reaper import StaleLeaseReaper
from botskill.storage.database import DatabaseManager

logger = logging.getLogger("botskill.resilience.recovery")


class CrashRecoveryManager:
    """Oversees startup recovery, database integrity checks, WAL checkpointing, and safe snapshots."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.reaper = StaleLeaseReaper(db_manager)

    def check_integrity(self) -> bool:
        """Executes SQLite internal integrity check."""
        with self.db.transaction() as cur:
            cur.execute("PRAGMA integrity_check;")
            row = cur.fetchone()
            if row and row[0] == "ok":
                return True
            logger.error("Database integrity check failed: %s", row)
            return False

    def checkpoint_wal(self) -> bool:
        """Forces WAL journal checkpoint and truncates the WAL file to guarantee data durability."""
        if self.db.db_path == ":memory:":
            return True

        with self.db.transaction() as cur:
            cur.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            logger.info("WAL checkpoint successfully truncated.")
            return True

    def create_backup(self, backup_filepath: str) -> str:
        """Creates a non-blocking online atomic SQLite backup."""
        dest_path = Path(backup_filepath).resolve()
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        source_conn = self.db.get_connection()
        dest_conn = sqlite3.connect(str(dest_path))

        try:
            with dest_conn:
                source_conn.backup(dest_conn, pages=100)
            logger.info("Database snapshot successfully written to '%s'", dest_path)
            return str(dest_path)
        finally:
            dest_conn.close()

    def run_startup_recovery(self) -> Dict[str, Any]:
        """Performs full recovery sequence on process boot."""
        integrity_ok = self.check_integrity()
        reaped = self.reaper.reap_stale_leases()
        checkpoint_ok = self.checkpoint_wal()

        return {
            "status": "RECOVERED" if integrity_ok else "CORRUPTED",
            "integrity_ok": integrity_ok,
            "reaped_leases_count": len(reaped),
            "reaped_message_ids": reaped,
            "wal_checkpoint_ok": checkpoint_ok,
        }
