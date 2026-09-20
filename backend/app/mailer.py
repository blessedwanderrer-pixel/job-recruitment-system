from __future__ import annotations

from typing import Any

import httpx

from .config import settings
from .errors import AppError


class Mailer:
    def __init__(self, store, webhook_url: str | None = None):
        self.store = store
        self.webhook_url = webhook_url if webhook_url is not None else settings.n8n_webhook_url
        self.sent: list[dict[str, Any]] = []

    def send(
        self,
        email_type: str,
        recipient: dict[str, Any],
        application_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> bool:
        recorded = self.store.record_email(email_type, recipient["id"], application_id)
        if not recorded:
            return False
        payload = {
            "type": email_type,
            "to": recipient["email"],
            "candidate_name": recipient.get("full_name"),
            "application_id": application_id,
            **(extra or {}),
        }
        self.sent.append(payload)
        if self.webhook_url:
            try:
                response = httpx.post(self.webhook_url, json=payload, timeout=20.0)
                if response.status_code >= 400:
                    raise AppError("Email could not be sent. Try again.", 502)
            except AppError:
                if hasattr(self.store, "delete_email_record"):
                    self.store.delete_email_record(email_type, recipient["id"], application_id)
                self.sent.pop()
                raise
            except Exception:
                if hasattr(self.store, "delete_email_record"):
                    self.store.delete_email_record(email_type, recipient["id"], application_id)
                self.sent.pop()
                raise AppError("Email could not be sent. Try again.", 502)
        return True
