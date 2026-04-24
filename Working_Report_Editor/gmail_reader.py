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

logger = logging.getLogger(__name日)

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

    # ... rest of your gmail_reader.py code remains the same ...
