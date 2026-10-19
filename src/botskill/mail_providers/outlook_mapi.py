"""BOTSKILL — Windows Outlook COM / MAPI Email Connector.

Provides direct local integration with Microsoft Outlook Desktop using pywin32.
Enforces safe draft staging and progressive autonomy.
"""

from __future__ import annotations

import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from botskill.core.interfaces import EmailProvider
from botskill.core.models import (
    AutonomyLevel,
    DraftReply,
    EmailMessage,
    MessageState,
    generate_idempotency_key,
)

logger = logging.getLogger("botskill.mail_providers.outlook_mapi")


class OutlookMAPIAdapter:
    """Native Windows Outlook COM MAPI Adapter."""

    def __init__(self, autonomy_level: AutonomyLevel = AutonomyLevel.DRAFT_ONLY):
        self.autonomy_level = autonomy_level
        self._outlook = None
        self._namespace = None

    def _ensure_connected(self) -> Any:
        """Lazy-initialize Windows COM Outlook session."""
        if sys.platform != "win32":
            raise RuntimeError("OutlookMAPIAdapter is supported only on Windows OS.")

        if self._outlook is None:
            import win32com.client
            self._outlook = win32com.client.Dispatch("Outlook.Application")
            self._namespace = self._outlook.GetNamespace("MAPI")
        return self._namespace

    def test_connection(self) -> Dict[str, Any]:
        """Probe local Outlook MAPI connectivity and list available accounts."""
        try:
            ns = self._ensure_connected()
            accounts = []
            if hasattr(ns, "Accounts"):
                for acc in ns.Accounts:
                    accounts.append(str(acc.DisplayName))
            return {
                "status": "READY",
                "connector": "Windows COM MAPI",
                "accounts_count": len(accounts),
                "accounts": accounts,
                "autonomy_level": self.autonomy_level.value,
            }
        except Exception as ex:
            logger.error("Outlook MAPI connection probe failed: %s", ex)
            return {
                "status": "UNAVAILABLE",
                "connector": "Windows COM MAPI",
                "error": str(ex),
                "autonomy_level": self.autonomy_level.value,
            }

    def _get_folder_for_account(self, ns, account_id: str, target_name: str):
        """Locates the store-specific folder for an account or falls back to default MAPI folder."""
        target_name_lower = target_name.lower()
        if hasattr(ns, "Folders"):
            for folder in ns.Folders:
                if account_id.lower() in folder.Name.lower():
                    for sub in folder.Folders:
                        if sub.Name.lower() == target_name_lower:
                            return sub
        # Fallback to default
        if target_name_lower == "inbox":
            return ns.GetDefaultFolder(6)
        elif target_name_lower == "drafts":
            return ns.GetDefaultFolder(16)
        return None

    def list_new_messages(self, account_id: str, limit: int = 20) -> List[EmailMessage]:
        """Retrieve recent unread messages from Outlook Inbox for the given account."""
        ns = self._ensure_connected()
        messages = []

        try:
            inbox = self._get_folder_for_account(ns, account_id, "inbox")
            if not inbox:
                return []
            items = inbox.Items
            items.Sort("[ReceivedTime]", True)

            count = 0
            for item in items:
                if count >= limit:
                    break
                try:
                    # Filter by unread or account if desired
                    sender_email = getattr(item, "SenderEmailAddress", "") or ""
                    subject = getattr(item, "Subject", "") or "(No Subject)"
                    body = getattr(item, "Body", "") or ""
                    html_body = getattr(item, "HTMLBody", None)
                    entry_id = getattr(item, "EntryID", "") or f"local_{count}"
                    rec_time = getattr(item, "ReceivedTime", None)

                    received_iso = (
                        rec_time.isoformat()
                        if hasattr(rec_time, "isoformat")
                        else datetime.now(timezone.utc).isoformat()
                    )

                    idempotency_key = generate_idempotency_key(
                        account_id=account_id,
                        provider_message_id=str(entry_id),
                        thread_id=subject.strip().lower(),
                    )

                    clean_body = self.clean_inbound_text(body)

                    msg = EmailMessage(
                        message_id=f"mapi_{entry_id[:16]}",
                        provider_id="outlook_mapi",
                        thread_id=subject.strip().lower(),
                        account_id=account_id,
                        sender=sender_email,
                        recipients=[account_id],
                        subject=subject,
                        body_text=clean_body,
                        body_html=html_body,
                        received_at=received_iso,
                        state=MessageState.DISCOVERED,
                        idempotency_key=idempotency_key,
                    )
                    messages.append(msg)
                    count += 1
                except Exception as item_err:
                    logger.warning("Failed to parse Outlook item: %s", item_err)
                    continue

        except Exception as ex:
            logger.error("Error reading Outlook inbox: %s", ex)

        return messages

    def create_draft(self, draft: DraftReply) -> bool:
        """Stage proposed response safely in Microsoft Outlook's local Drafts folder.

        DOES NOT SEND EMAIL. This fulfills the DRAFT_ONLY safety posture.
        """
        try:
            ns = self._ensure_connected()
            drafts_folder = self._get_folder_for_account(ns, draft.account_id, "drafts")
            if not drafts_folder:
                drafts_folder = ns.GetDefaultFolder(16)
            mail_item = drafts_folder.Items.Add(0)  # 0 = olMailItem

            mail_item.Subject = draft.subject
            mail_item.Body = draft.body_text
            if draft.body_html:
                mail_item.HTMLBody = draft.body_html

            # Resolve account to use for sending when approved
            if hasattr(ns, "Accounts"):
                for acc in ns.Accounts:
                    if str(acc.DisplayName).lower() == draft.account_id.lower():
                        mail_item.SendUsingAccount = acc
                        break

            # Save explicitly into Drafts folder without sending
            mail_item.Save()
            logger.info("Successfully staged draft #%s to Outlook Drafts folder", draft.draft_id)
            return True
        except Exception as ex:
            logger.error("Failed to stage draft in Outlook: %s", ex)
            return False

    def send_reply(self, draft: DraftReply, idempotency_key: str) -> bool:
        """Attempt to send email.

        STRICT SAFETY ENFORCEMENT: Rejects any send call if mode is DRAFT_ONLY.
        """
        if self.autonomy_level == AutonomyLevel.DRAFT_ONLY:
            raise PermissionError(
                "Live transmission blocked: System is configured in LEVEL_1_DRAFT_ONLY mode."
            )

        if not draft.is_approved:
            raise PermissionError(
                "Live transmission blocked: Draft has not received human supervisor approval."
            )

        # Transmission path when supervisor explicitly enables live send
        ns = self._ensure_connected()
        drafts_folder = ns.GetDefaultFolder(16)
        mail_item = drafts_folder.Items.Add(0)
        mail_item.Subject = draft.subject
        mail_item.Body = draft.body_text
        if draft.body_html:
            mail_item.HTMLBody = draft.body_html

        if hasattr(ns, "Accounts"):
            for acc in ns.Accounts:
                if str(acc.DisplayName).lower() == draft.account_id.lower():
                    mail_item.SendUsingAccount = acc
                    break

        mail_item.Send()
        logger.info("Live reply sent for draft #%s with key %s", draft.draft_id, idempotency_key)
        return True

    @staticmethod
    def clean_inbound_text(text: str) -> str:
        """Strip quoted thread history, forward headers, and signatures."""
        if not text:
            return ""

        # Normalize line endings
        text = text.replace("\r\n", "\n")

        # Strip standard quoted thread markers
        patterns = [
            r"-+Original Message-+.*",
            r"From:.*?\nSent:.*?\nTo:.*",
            r"On .* wrote:.*",
            r"_{10,}.*",
        ]
        for pattern in patterns:
            text = re.split(pattern, text, flags=re.DOTALL | re.IGNORECASE)[0]

        return text.strip()
