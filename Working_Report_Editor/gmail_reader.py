"""
gmail_reader.py — Fetch unread emails (body + image attachments) from Gmail.
"""

import base64
import hashlib
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import (
    GMAIL_QUERY,
    GMAIL_USER_ID,
    MAX_EMAILS_PER_RUN,
    GMAIL_SCOPES,
)
from error_handler import AttachmentError, EmailFetchError, with_retry

# ✅ FIXED: Changed __name日 to __name__
logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
ATTACHMENTS_DIR = "attachments"


class GmailReader:
    def __init__(self):
        os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
        self._service = None
        self._oauth_creds = None

    def _get_oauth_creds(self):
        """Get OAuth credentials for Gmail (works on both Streamlit Cloud and GitHub Actions)"""
        if self._oauth_creds:
            return self._oauth_creds

        try:
            # Try Streamlit secrets first
            import streamlit as st
            oauth = st.secrets.get("GOOGLE_OAUTH", {})
            if oauth:
                self._oauth_creds = Credentials(
                    token=None,
                    refresh_token=oauth.get("refresh_token"),
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=oauth.get("client_id"),
                    client_secret=oauth.get("client_secret"),
                    scopes=GMAIL_SCOPES,
                )
                return self._oauth_creds
        except:
            pass

        # Try environment variables (GitHub Actions)
        import os
        refresh_token = os.environ.get("GMAIL_REFRESH_TOKEN", "")
        client_id = os.environ.get("GMAIL_CLIENT_ID", "")
        client_secret = os.environ.get("GMAIL_CLIENT_SECRET", "")

        if refresh_token and client_id and client_secret:
            self._oauth_creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=GMAIL_SCOPES,
            )
            return self._oauth_creds

        raise Exception("No OAuth credentials found in secrets or environment")

    def _get_service(self):
        if self._service:
            return self._service

        creds = self._get_oauth_creds()
        self._service = build("gmail", "v1", credentials=creds)
        logger.info("Gmail service initialised")
        return self._service

    @with_retry()
    def fetch_emails(self) -> List[Dict]:
        svc = self._get_service()

        try:
            result = svc.users().messages().list(
                userId="me",
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

    def _process_message(self, svc, msg_id: str) -> Optional[Dict]:
        try:
            msg = svc.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()
        except HttpError as exc:
            logger.error(f"Could not fetch message {msg_id}: {exc}")
            return None

        subject = ""
        from_email = ""

        for h in msg["payload"].get("headers", []):
            if h["name"].lower() == "subject":
                subject = h["value"]
            elif h["name"].lower() == "from":
                from_email = h["value"]

        received_ms = int(msg.get("internalDate", 0))
        received_at = (
            datetime.fromtimestamp(received_ms / 1000)
            if received_ms else datetime.now()
        )

        body_parts = []
        att_paths = []

        self._walk_parts(
            svc, msg_id, msg["payload"],
            body_ref=body_parts,
            att_ref=att_paths
        )

        body = "\n".join(body_parts)

        return {
            "id": msg_id,
            "subject": subject,
            "from": from_email,
            "body": body,
            "attachments": att_paths,
            "hash": self._email_hash(msg_id, subject),
            "received_at": received_at,
            "received_ms": received_ms,
        }

    def _walk_parts(self, svc, msg_id, part, body_ref, att_ref):
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

    def _download_attachment(self, svc, msg_id, part):
        try:
            att = svc.users().messages().attachments().get(
                userId="me",
                messageId=msg_id,
                id=part["body"]["attachmentId"]
            ).execute()

            raw = base64.urlsafe_b64decode(att["data"])
            filename = part["filename"]

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            safe_name = f"{timestamp}_{filename}"
            path = os.path.join(ATTACHMENTS_DIR, safe_name)

            with open(path, "wb") as fh:
                fh.write(raw)

            return path

        except Exception as exc:
            logger.error(f"Attachment download failed: {exc}")
            return None

    @staticmethod
    def _email_hash(msg_id: str, subject: str) -> str:
        return hashlib.md5(f"{msg_id}|{subject}".encode()).hexdigest()
