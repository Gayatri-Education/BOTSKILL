"""Unit tests for Phase 14 — Packaging, Windows Launcher, and Environment Bootstrap."""

from pathlib import Path
import pytest

from botskill.main import bootstrap_environment, main


def test_bootstrap_environment_creates_directories_and_db(tmp_path: Path):
    env = bootstrap_environment(base_dir=tmp_path)

    assert (tmp_path / "data").is_dir()
    assert (tmp_path / "logs").is_dir()
    assert (tmp_path / "models").is_dir()
    assert (tmp_path / "snapshots").is_dir()
    assert (tmp_path / "data" / "botskill.db").exists()

    assert env["db_manager"] is not None
    assert env["recovery_report"]["status"] == "RECOVERED"
    assert env["recovery_report"]["integrity_ok"] is True


def test_windows_launcher_bat_structure():
    root_dir = Path(__file__).resolve().parent.parent.parent
    bat_file = root_dir / "run_botskill.bat"

    assert bat_file.exists(), "run_botskill.bat must exist in project root"
    content = bat_file.read_text(encoding="utf-8")

    assert "python -m botskill.main" in content
    assert "PYTHONPATH=" in content
    assert "127.0.0.1:8765" in content


def test_main_cli_loopback_restriction():
    # Attempting to start server on non-loopback IP must exit with code 1
    code = main(["--host", "0.0.0.0", "--no-browser"])
    assert code == 1

    code2 = main(["--host", "192.168.1.1", "--no-browser"])
    assert code2 == 1
