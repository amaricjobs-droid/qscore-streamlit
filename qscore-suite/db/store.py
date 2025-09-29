# qscore-suite/db/store.py
from __future__ import annotations
import os, json, datetime as dt
from typing import Optional, Dict, Any
from sqlalchemy import create_engine, text

def _db_url() -> str:
    # Prefer secrets (Streamlit or env), else SQLite file
    url = os.environ.get("DATABASE_URL") or os.getenv("DB_URL") or ""
    if not url:
        # local default
        sqlite_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "nexa.db"))
        return f"sqlite:///{sqlite_path}"
    return url

_engine = create_engine(_db_url(), future=True)

DDL = """
CREATE TABLE IF NOT EXISTS outreach (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  -- use SERIAL/BIGSERIAL on Postgres; SQLite uses INTEGER PK AUTOINCREMENT
  patient_id TEXT,
  measure TEXT,
  clinic TEXT,
  channel TEXT,              -- 'sms' or 'email'
  template TEXT,
  payload_json TEXT,
  status TEXT,               -- 'queued','sent','delivered','failed'
  provider_msg_id TEXT,
  error TEXT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
"""

def ensure_schema():
    with _engine.begin() as conn:
        # SQLite-friendly; on Postgres this is fine too
        if _db_url().startswith("sqlite"):
            conn.exec_driver_sql(DDL)
        else:
            # Postgres flavor
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS outreach (
              id BIGSERIAL PRIMARY KEY,
              patient_id TEXT,
              measure TEXT,
              clinic TEXT,
              channel TEXT,
              template TEXT,
              payload_json TEXT,
              status TEXT,
              provider_msg_id TEXT,
              error TEXT,
              created_at TIMESTAMP,
              updated_at TIMESTAMP
            );
            """))

def log_outreach(rec: Dict[str, Any]) -> None:
    now = dt.datetime.utcnow()
    rec.setdefault("created_at", now)
    rec.setdefault("updated_at", now)
    with _engine.begin() as conn:
        conn.execute(text("""
        INSERT INTO outreach (patient_id, measure, clinic, channel, template, payload_json, status, provider_msg_id, error, created_at, updated_at)
        VALUES (:patient_id, :measure, :clinic, :channel, :template, :payload_json, :status, :provider_msg_id, :error, :created_at, :updated_at)
        """), {
            "patient_id": rec.get("patient_id"),
            "measure": rec.get("measure"),
            "clinic": rec.get("clinic"),
            "channel": rec.get("channel"),
            "template": rec.get("template"),
            "payload_json": json.dumps(rec.get("payload", {})),
            "status": rec.get("status","queued"),
            "provider_msg_id": rec.get("provider_msg_id"),
            "error": rec.get("error"),
            "created_at": rec["created_at"],
            "updated_at": rec["updated_at"],
        })
