"""BOTSKILL — Standalone Windows Application Entrypoint & Server Bootstrapper."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Dict, Optional

import uvicorn

from botskill.ai_providers.gateway import AIGateway
from botskill.ai_providers.local_llama import LocalLlamaRuntime
from botskill.ai_providers.router import ModelRouter
from botskill.ai_providers.schema import RoutingProfile
from botskill.app.auth import SessionManager
from botskill.app.server import create_app
from botskill.core.models import AutonomyLevel
from botskill.mail_providers.fake_provider import FakeEmailProvider
from botskill.mail_providers.outlook_mapi import OutlookMAPIAdapter
from botskill.resilience.recovery import CrashRecoveryManager
from botskill.storage.database import DatabaseManager

logger = logging.getLogger("botskill.main")


def bootstrap_environment(base_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Ensures local state directories, SQLite database, and models are properly provisioned."""
    if base_dir is None:
        base_dir = Path(__file__).resolve().parent.parent.parent

    data_dir = base_dir / "data"
    logs_dir = base_dir / "logs"
    models_dir = base_dir / "models"
    snapshots_dir = base_dir / "snapshots"

    for d in (data_dir, logs_dir, models_dir, snapshots_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Setup file logging
    log_file = logs_dir / "botskill.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(log_file), encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    model_path = models_dir / "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    model_present = model_path.exists()

    db_path = str(data_dir / "botskill.db")
    db_mgr = DatabaseManager(db_path)

    # Execute recovery sequence (integrity, stale leases, WAL checkpoint)
    recovery_mgr = CrashRecoveryManager(db_mgr)
    recovery_report = recovery_mgr.run_startup_recovery()
    logger.info("Startup recovery completed: %s", recovery_report)

    return {
        "base_dir": base_dir,
        "data_dir": data_dir,
        "logs_dir": logs_dir,
        "models_dir": models_dir,
        "model_present": model_present,
        "db_manager": db_mgr,
        "recovery_report": recovery_report,
    }


def open_browser_delayed(url: str, delay_seconds: float = 1.0) -> None:
    def _open():
        time.sleep(delay_seconds)
        webbrowser.open(url)
    threading.Thread(target=_open, daemon=True).start()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="BOTSKILL Autonomous Local Email Workstation",
        prog="botskill",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Loopback host to bind (must be 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on (default: 8765)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch web browser")
    parser.add_argument("--mock-mail", action="store_true", help="Use in-memory fake email provider for testing")
    parser.add_argument("--profile", default="LOCAL_ONLY", help="Routing profile (LOCAL_ONLY, LOCAL_FIRST)")

    args = parser.parse_args(argv)

    if args.host not in {"127.0.0.1", "localhost"}:
        sys.stderr.write("Security Error: BOTSKILL server must bind strictly to a loopback address.\n")
        return 1

    env = bootstrap_environment()
    db_mgr = env["db_manager"]

    # Choose mail provider
    if args.mock_mail or sys.platform != "win32":
        mail_provider = FakeEmailProvider(autonomy_level=AutonomyLevel.DRAFT_ONLY)
    else:
        mail_provider = OutlookMAPIAdapter(autonomy_level=AutonomyLevel.DRAFT_ONLY)

    # Initialize AI router & Local SLM
    router = ModelRouter(default_profile=RoutingProfile(args.profile.upper()))
    local_slm = LocalLlamaRuntime()
    router.register_adapter("local_slm", local_slm, is_cloud=False)
    gateway = AIGateway(router)

    session_mgr = SessionManager(token_file=env["data_dir"] / ".session_token")

    app = create_app(
        db_manager=db_mgr,
        session_manager=session_mgr,
        mail_provider=mail_provider,
        router=router,
        ai_gateway=gateway,
        host=args.host,
        port=args.port,
    )

    url = f"http://{args.host}:{args.port}"
    logger.info("=" * 60)
    logger.info("BOTSKILL Autonomous Local Email Workstation v3.0")
    logger.info("Serving securely on: %s", url)
    logger.info("Local SLM Runtime: Qwen2.5-0.5B-Instruct (CPU)")
    logger.info("Safety Invariant: LEVEL_1_DRAFT_ONLY (No live outbound email)")
    logger.info("=" * 60)

    if not args.no_browser:
        open_browser_delayed(url)

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
