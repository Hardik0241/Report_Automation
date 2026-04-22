"""
gmail_reader.py — Fetch unread emails (body + image attachments) from Gmail.
Uses OAuth2 with token.pickle for authentication.

Each returned email dict now includes:
  "received_at"  → datetime object of when the email was received
  "received_ms"  → raw internalDate in milliseconds (for Sales date logic)
"""

import base64
import hashlib
import logging
import os
import pickle
from datetime import datetime
from typing import Dict, List, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from config import (
    GMAIL_QUERY,
    GMAIL_SCOPES,
    GMAIL_USER_ID,
    MAX_EMAILS_PER_RUN,
)
from error_handler import AttachmentError, EmailFetchError, with_retry

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
ATTACHMENTS_DIR  = "attachments"

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]

import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build

def _get_service(self):
    creds_dict = st.secrets["GOOGLE_CREDENTIALS"]

    creds = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/gmail.readonly"]
    )

    service = build("gmail", "v1", credentials=creds)
    return service

self.gmail = GmailReader()
emails = self.gmail.fetch_emails()

class GmailReader:
    def __init__(self):
        os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
        self._service = None

    # ──────────────────────────────────────────
    # Auth
    # ──────────────────────────────────────────

    def _get_service(self):
        if self._service:
            return self._service
        try:
            creds = None
            if os.path.exists("token.pickle"):
                with open("token.pickle", "rb") as f:
                    creds = pickle.load(f)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        "client_secret.json", GMAIL_SCOPES
                    )
                    try:
                        creds = flow.run_local_server(port=0)
                    except Exception as exc:
                        logger.warning(f"Local server auth failed ({exc}); using console.")
                        creds = flow.run_console()

                with open("token.pickle", "wb") as f:
                    pickle.dump(creds, f)

            self._service = build("gmail", "v1", credentials=creds)
            logger.info("Gmail service initialised.")
        except Exception as exc:
            raise EmailFetchError(
                f"Cannot create Gmail service: {exc}",
                "auth_error",
                {"error": str(exc)},
            ) from exc
        return self._service

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    @with_retry()
    def fetch_emails(self) -> List[Dict]:
        """
        Fetch unread emails.
        Returns list of dicts with keys:
          id, subject, from, body, attachments, hash,
          received_at (datetime), received_ms (int)
        """
        svc = self._get_service()
        try:
            result = svc.users().messages().list(
                userId=GMAIL_USER_ID,
                q=GMAIL_QUERY,
                maxResults=MAX_EMAILS_PER_RUN,
            ).execute()
        except HttpError as exc:
            raise EmailFetchError(
                "Gmail list() failed",
                "api_error",
                {"status": exc.resp.status, "reason": exc.reason},
            ) from exc

        messages = result.get("messages", [])
        logger.info(f"Found {len(messages)} unread email(s).")

        emails = []
        for msg_stub in messages:
            email_obj = self._process_message(svc, msg_stub["id"])
            if email_obj:
                emails.append(email_obj)
        return emails

    # ──────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────

    def _process_message(self, svc, msg_id: str) -> Optional[Dict]:
        try:
            msg = svc.users().messages().get(
                userId=GMAIL_USER_ID, id=msg_id, format="full"
            ).execute()
        except HttpError as exc:
            logger.error(f"Could not fetch message {msg_id}: {exc}")
            return None

        # ── Headers ──
        subject    = ""
        from_email = ""
        for h in msg["payload"].get("headers", []):
            name_lower = h["name"].lower()
            if name_lower == "subject":
                subject = h["value"]
            elif name_lower == "from":
                from_email = h["value"]

        # ── Received timestamp ──
        # internalDate is milliseconds since Unix epoch
        received_ms = int(msg.get("internalDate", 0))
        received_at = datetime.fromtimestamp(received_ms / 1000) if received_ms else datetime.now()

        # ── Body + attachments ──
        body_parts: List[str] = []
        att_paths:  List[str] = []
        self._walk_parts(svc, msg_id, msg["payload"], body_ref=body_parts, att_ref=att_paths)
        body = "\n".join(body_parts)

        # ── Mark as read ──
        try:
            svc.users().messages().modify(
                userId=GMAIL_USER_ID,
                id=msg_id,
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()
        except Exception as exc:
            logger.warning(f"Could not mark {msg_id} as read: {exc}")

        return {
            "id":          msg_id,
            "subject":     subject,
            "from":        from_email,
            "body":        body,
            "attachments": att_paths,
            "hash":        self._email_hash(msg_id, subject),
            "received_at": received_at,
            "received_ms": received_ms,
        }

    def _walk_parts(self, svc, msg_id: str, part: Dict,
                    body_ref: List[str], att_ref: List[str]):
        mime = part.get("mimeType", "")

        if mime == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                text = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                body_ref.append(text)

        elif part.get("filename") and part.get("body", {}).get("attachmentId"):
            ext = os.path.splitext(part["filename"])[1].lower()
            if ext in IMAGE_EXTENSIONS:
                path = self._download_attachment(svc, msg_id, part)
                if path:
                    att_ref.append(path)

        for sub in part.get("parts", []):
            self._walk_parts(svc, msg_id, sub, body_ref, att_ref)

    def _download_attachment(self, svc, msg_id: str, part: Dict) -> Optional[str]:
        filename = part["filename"]
        att_id   = part["body"]["attachmentId"]
        try:
            att       = svc.users().messages().attachments().get(
                userId=GMAIL_USER_ID, messageId=msg_id, id=att_id
            ).execute()
            raw       = base64.urlsafe_b64decode(att["data"])
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            safe_name = f"{timestamp}_{filename}"
            path      = os.path.join(ATTACHMENTS_DIR, safe_name)
            with open(path, "wb") as fh:
                fh.write(raw)
            logger.info(f"Attachment saved: {safe_name}")
            return path
        except Exception as exc:
            logger.error(f"Attachment download failed for {filename}: {exc}")
            return None

    @staticmethod
    def _email_hash(msg_id: str, subject: str) -> str:
        return hashlib.md5(f"{msg_id}|{subject}".encode()).hexdigest()
