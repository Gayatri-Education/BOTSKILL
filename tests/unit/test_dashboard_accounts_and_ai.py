"""Unit tests for Phase 8 — Dashboard Accounts & AI Engine Management."""

import pytest
from fastapi.testclient import TestClient

from botskill.ai_providers.gateway import AIGateway
from botskill.ai_providers.local_llama import LocalLlamaRuntime
from botskill.ai_providers.router import ModelRouter
from botskill.ai_providers.schema import RoutingProfile
from botskill.app.auth import SessionManager
from botskill.app.server import create_app
from botskill.core.models import AutonomyLevel, EmailMessage, MessageState
from botskill.mail_providers.fake_provider import FakeEmailProvider
from botskill.storage.database import DatabaseManager


@pytest.fixture
def test_setup():
    session_mgr = SessionManager()
    db_mgr = DatabaseManager(":memory:")
    fake_mail = FakeEmailProvider(autonomy_level=AutonomyLevel.DRAFT_ONLY)
    # Configure mock accounts
    fake_mail.test_connection = lambda: {
        "status": "READY",
        "connector": "Fake Windows COM MAPI",
        "accounts": ["hr@aivaratech.online", "contactus@aivaratech.online"],
        "autonomy_level": AutonomyLevel.DRAFT_ONLY.value,
    }

    router = ModelRouter(default_profile=RoutingProfile.LOCAL_ONLY)
    local_slm = LocalLlamaRuntime()
    router.register_adapter("local_slm", local_slm, is_cloud=False)
    gateway = AIGateway(router)

    app = create_app(
        db_manager=db_mgr,
        session_manager=session_mgr,
        mail_provider=fake_mail,
        router=router,
        ai_gateway=gateway,
    )
    client = TestClient(app)
    return client, session_mgr, fake_mail, db_mgr, router


def test_accounts_listing(test_setup):
    client, session_mgr, fake_mail, _, _ = test_setup

    response = client.get("/api/accounts")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["default_autonomy"] == "LEVEL_1_DRAFT_ONLY"
    assert data["live_send_permitted"] is False
    assert any(acc["account_id"] == "hr@aivaratech.online" for acc in data["accounts"])


def test_account_probe(test_setup):
    client, session_mgr, _, _, _ = test_setup

    # POST mutating request requires CSRF
    res_no_csrf = client.post("/api/accounts/hr@aivaratech.online/probe")
    assert res_no_csrf.status_code == 403

    res_probe = client.post(
        "/api/accounts/hr@aivaratech.online/probe",
        headers={"X-CSRF-Token": session_mgr.csrf_token},
    )
    assert res_probe.status_code == 200
    probe_data = res_probe.json()
    assert probe_data["account_id"] == "hr@aivaratech.online"
    assert probe_data["status"] == "READY"
    assert probe_data["folder_access"] == "INBOX_DRAFTS_OK"


def test_account_sync_with_db_persistence(test_setup):
    client, session_mgr, fake_mail, db_mgr, _ = test_setup

    # Seed fake incoming message
    msg = EmailMessage(
        message_id="msg_sync_001",
        provider_id="fake",
        thread_id="th_001",
        account_id="hr@aivaratech.online",
        sender="intern@example.com",
        recipients=["hr@aivaratech.online"],
        subject="Internship Application",
        body_text="Hi, I am applying for the remote python role.",
        received_at="2026-10-20T00:00:00Z",
        state=MessageState.DISCOVERED,
        idempotency_key="key_sync_001",
    )
    fake_mail.inbox.append(msg)

    sync_res = client.post(
        "/api/accounts/sync",
        headers={"X-CSRF-Token": session_mgr.csrf_token},
    )
    assert sync_res.status_code == 200
    sync_data = sync_res.json()
    assert sync_data["messages_discovered"] >= 1
    assert sync_data["draft_only_enforced"] is True

    # Verify message was saved to database
    repo = db_mgr.get_repository()
    saved = repo.get_message("msg_sync_001")
    assert saved is not None
    assert saved.sender == "intern@example.com"


def test_ai_status_and_profile_management(test_setup):
    client, session_mgr, _, _, router = test_setup

    # 1. Inspect status
    status_res = client.get("/api/ai/status")
    assert status_res.status_code == 200
    st_data = status_res.json()
    assert st_data["active_model"] == "Qwen2.5-0.5B-Instruct"
    assert st_data["quantization"] == "Q4_K_M"
    assert st_data["estimated_ram_mb"] == 680
    assert st_data["zero_cloud_egress"] is True

    # 2. Update profile without CSRF -> 403
    fail_res = client.post("/api/ai/profile", json={"profile": "LOCAL_FIRST"})
    assert fail_res.status_code == 403

    # 3. Update profile with CSRF -> 200
    ok_res = client.post(
        "/api/ai/profile",
        json={"profile": "LOCAL_FIRST"},
        headers={"X-CSRF-Token": session_mgr.csrf_token},
    )
    assert ok_res.status_code == 200
    assert ok_res.json()["profile"] == "LOCAL_FIRST"
    assert router.profile == RoutingProfile.LOCAL_FIRST

    # 4. Invalid profile -> 400
    bad_res = client.post(
        "/api/ai/profile",
        json={"profile": "INVALID_PROFILE"},
        headers={"X-CSRF-Token": session_mgr.csrf_token},
    )
    assert bad_res.status_code == 400


def test_ai_test_inference(test_setup):
    client, session_mgr, _, _, _ = test_setup

    # Test local inference execution endpoint
    inf_res = client.post(
        "/api/ai/test-inference",
        json={
            "prompt": "Test candidate message: Is this remote?",
            "max_tokens": 50,
        },
        headers={"X-CSRF-Token": session_mgr.csrf_token},
    )
    assert inf_res.status_code == 200
    inf_data = inf_res.json()
    assert inf_data["is_success"] is True
    assert inf_data["latency_ms"] > 0
    assert len(inf_data["output_text"]) > 0
    assert inf_data["zero_cloud_egress"] is True
