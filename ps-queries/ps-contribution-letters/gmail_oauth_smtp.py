#!/usr/bin/env python3

"""Standalone helpers for sending email via Gmail SMTP using OAuth2 (XOAUTH2).

This module is intentionally independent from ECC / ParishSoft code so it can be
reused by other scripts.

Typical Google Workspace usage is via a Service Account with Domain-Wide
Delegation enabled, impersonating a Workspace user ("subject") and requesting
`https://mail.google.com/` scope.
"""

from __future__ import annotations

import base64
import mimetypes
import os
import smtplib
from contextlib import contextmanager
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Dict, Iterable, Iterator, Optional, Sequence, Tuple


@dataclass(frozen=True)
class GmailServiceAccountAuth:
    """Parameters to obtain an OAuth2 access token for Gmail SMTP."""

    service_account_keyfile: str
    impersonate_user: str
    scopes: Tuple[str, ...] = ("https://mail.google.com/",)


def _require_file(path: str) -> None:
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"File does not exist: {path}")


def get_access_token_via_service_account(auth: GmailServiceAccountAuth) -> str:
    """Return an OAuth2 access token using a service account + domain delegation."""

    _require_file(auth.service_account_keyfile)

    from google.oauth2 import service_account
    from google.auth.transport.requests import Request

    credentials = service_account.Credentials.from_service_account_file(
        auth.service_account_keyfile,
        scopes=list(auth.scopes),
    )

    if auth.impersonate_user:
        credentials = credentials.with_subject(auth.impersonate_user)

    request = Request()
    credentials.refresh(request)

    if not credentials.token:
        raise RuntimeError("Failed to obtain OAuth2 access token")

    return credentials.token


def build_xoauth2_initial_client_response(user_email: str, access_token: str) -> str:
    """Return base64-encoded XOAUTH2 initial response."""

    if not user_email:
        raise ValueError("user_email is required")
    if not access_token:
        raise ValueError("access_token is required")

    auth_string = f"user={user_email}\x01auth=Bearer {access_token}\x01\x01"
    return base64.b64encode(auth_string.encode("utf-8")).decode("ascii")


def smtp_login_xoauth2(smtp: smtplib.SMTP, user_email: str, access_token: str) -> None:
    """Authenticate an already-connected SMTP session using XOAUTH2."""

    b64 = build_xoauth2_initial_client_response(user_email, access_token)
    code, response = smtp.docmd("AUTH", f"XOAUTH2 {b64}")

    # 235 means "Authentication successful".
    if code != 235:
        raise RuntimeError(f"XOAUTH2 authentication failed: {code} {response!r}")


@contextmanager
def open_gmail_smtp_connection_oauth2(
    *,
    smtp_server: str,
    smtp_user: str,
    access_token: str,
    smtp_port: int = 465,
    use_ssl: bool = True,
    use_starttls: bool = False,
    local_hostname: Optional[str] = None,
    debuglevel: int = 0,
    timeout: int = 60,
    log=None,
) -> Iterator[smtplib.SMTP]:
    """Context manager returning an authenticated SMTP object.

    Notes:
    - For Gmail, common endpoints are:
      - `smtp.gmail.com:465` (SSL)
      - `smtp.gmail.com:587` (STARTTLS)
    - `smtp-relay.gmail.com` may not support XOAUTH2; prefer `smtp.gmail.com`.
    """

    if use_ssl and use_starttls:
        raise ValueError("use_ssl and use_starttls are mutually exclusive")

    if log:
        log.debug(f"Connecting to SMTP server {smtp_server}:{smtp_port}...")

    smtp: Optional[smtplib.SMTP] = None
    try:
        if use_ssl:
            smtp = smtplib.SMTP_SSL(
                host=smtp_server,
                port=smtp_port,
                local_hostname=local_hostname,
                timeout=timeout,
            )
        else:
            smtp = smtplib.SMTP(
                host=smtp_server,
                port=smtp_port,
                local_hostname=local_hostname,
                timeout=timeout,
            )

        if debuglevel:
            smtp.set_debuglevel(debuglevel)

        smtp.ehlo()
        if use_starttls:
            smtp.starttls()
            smtp.ehlo()

        smtp_login_xoauth2(smtp, smtp_user, access_token)

        yield smtp
    finally:
        if smtp is not None:
            try:
                smtp.quit()
            except Exception:
                try:
                    smtp.close()
                except Exception:
                    pass


def build_email_message(
    *,
    message_body: str,
    content_type: str,
    smtp_to: str,
    smtp_subject: str,
    smtp_from: str,
    attachments: Optional[Dict[int, Dict[str, str]]] = None,
    log=None,
) -> EmailMessage:
    """Build an EmailMessage with optional attachments.

    `attachments` matches the existing ECC convention:

        {
          1: {"filename": "/path/to/file.pdf", "type": "pdf"},
          2: {"filename": "/path/to/other.png", "type": "png"},
        }

    Only `filename` is required; `type` is used as a hint.
    """

    msg = EmailMessage()
    msg["Subject"] = smtp_subject
    msg["From"] = smtp_from
    msg["To"] = smtp_to

    subtype = "plain"
    if content_type and "/" in content_type:
        subtype = content_type.split("/", 1)[1]

    msg.set_content(message_body, subtype=subtype)

    if attachments:
        for attachment_id in sorted(attachments.keys()):
            attachment = attachments[attachment_id]
            filename = attachment.get("filename")
            if not filename:
                raise ValueError(f"Attachment {attachment_id} is missing filename")

            ctype_hint = attachment.get("type")
            guessed, encoding = mimetypes.guess_type(filename)

            mime_type = guessed
            if not mime_type and ctype_hint:
                # Minimal hint mapping; expand if/when needed.
                if ctype_hint.lower() == "pdf":
                    mime_type = "application/pdf"

            if not mime_type:
                mime_type = "application/octet-stream"

            maintype, sub = mime_type.split("/", 1)

            if log:
                log.debug(f"Attachment is: {filename} ({mime_type})")

            with open(filename, "rb") as fp:
                msg.add_attachment(
                    fp.read(),
                    maintype=maintype,
                    subtype=sub,
                    filename=os.path.basename(filename),
                )

    return msg


def send_email_existing_smtp(
    message_body: str,
    content_type: str,
    smtp_to: str,
    smtp_subject: str,
    smtp_from: str,
    smtp: smtplib.SMTP,
    log,
    attachments: Optional[Dict[int, Dict[str, str]]] = None,
) -> None:
    """Send an email using an existing authenticated SMTP connection."""

    msg = build_email_message(
        message_body=message_body,
        content_type=content_type,
        smtp_to=smtp_to,
        smtp_subject=smtp_subject,
        smtp_from=smtp_from,
        attachments=attachments,
        log=log,
    )

    smtp.send_message(msg)
    if log:
        log.debug(f"Mail sent to {smtp_to}, subject {smtp_subject!r}")
