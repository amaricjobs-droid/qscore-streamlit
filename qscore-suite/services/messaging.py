# qscore-suite/services/messaging.py
from __future__ import annotations
import os
from typing import Optional, Tuple

def _get(key: str) -> Optional[str]:
    # Streamlit secrets map to env in Cloud; locally you can set env or secrets.toml via st.secrets
    return os.environ.get(key)

def send_sms(to_number: str, body: str) -> Tuple[bool, Optional[str], Optional[str]]:
    sid = _get("TWILIO_ACCOUNT_SID")
    tok = _get("TWILIO_AUTH_TOKEN")
    frm = _get("TWILIO_FROM")
    if not (sid and tok and frm):
        # Fallback demo mode
        return True, "demo-sms-id", None
    try:
        from twilio.rest import Client
        client = Client(sid, tok)
        msg = client.messages.create(to=to_number, from_=frm, body=body)
        return True, msg.sid, None
    except Exception as e:
        return False, None, str(e)

def send_email(to_email: str, subject: str, body: str) -> Tuple[bool, Optional[str], Optional[str]]:
    key = _get("SENDGRID_API_KEY")
    sender = _get("SENDGRID_FROM") or "noreply@nexa.example"
    if not key:
        return True, "demo-email-id", None
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        message = Mail(from_email=sender, to_emails=to_email, subject=subject, plain_text_content=body)
        sg = SendGridAPIClient(key)
        resp = sg.send(message)
        return True, str(resp.headers.get("X-Message-Id", "")), None
    except Exception as e:
        return False, None, str(e)
