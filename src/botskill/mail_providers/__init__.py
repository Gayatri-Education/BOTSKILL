"""BOTSKILL Mail Providers Package."""

from botskill.mail_providers.fake_provider import FakeEmailProvider
from botskill.mail_providers.outlook_mapi import OutlookMAPIAdapter

__all__ = ["FakeEmailProvider", "OutlookMAPIAdapter"]
