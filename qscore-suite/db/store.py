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
# ---- Added utilities for outreach/appointments (non-breaking) ----
from sqlalchemy import inspect

APPT_DDL_SQLITE = """
CREATE TABLE IF NOT EXISTS appointments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id TEXT,
  measure TEXT,
  clinic TEXT,
  scheduled_at TIMESTAMP,
  status TEXT,              -- 'confirmed','completed','cancelled'
  source TEXT,              -- 'demo','ehr','cal'
  external_id TEXT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
"""

APPT_DDL_PG = """
CREATE TABLE IF NOT EXISTS appointments (
  id BIGSERIAL PRIMARY KEY,
  patient_id TEXT,
  measure TEXT,
  clinic TEXT,
  scheduled_at TIMESTAMP,
  status TEXT,
  source TEXT,
  external_id TEXT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
"""

def get_engine():
    return _engine

def ensure_schema_all():
    """Ensure both outreach and appointments tables exist."""
    ensure_schema()
    with _engine.begin() as conn:
        if _db_url().startswith("sqlite"):
            conn.exec_driver_sql(APPT_DDL_SQLITE)
        else:
            conn.execute(text(APPT_DDL_PG))

def seed_demo_data():
    """Insert a few demo outreach rows + a confirmed appointment for demo viewing."""
    ensure_schema_all()
    import datetime as dt
    now = dt.datetime.utcnow()
    rows = [
        {"patient_id": "102","measure":"Diabetes Statin Therapy (SUPD)","clinic":"Rockmart","channel":"sms","template":"default","payload":{"body":"Demo SUPD outreach"},"status":"sent","provider_msg_id":"demo-sms-001","created_at":now, "updated_at":now},
        {"patient_id": "103","measure":"High Blood Pressure Control <140/90>","clinic":"Rome","channel":"email","template":"default","payload":{"body":"Demo HTN outreach"},"status":"sent","provider_msg_id":"demo-email-002","created_at":now, "updated_at":now},
        {"patient_id": "104","measure":"Hemoglobin A1c Control <8","clinic":"Cedartown","channel":"sms","template":"default","payload":{"body":"Demo A1c outreach"},"status":"delivered","provider_msg_id":"demo-sms-003","created_at":now, "updated_at":now},
    ]
    for r in rows:
        try:
            log_outreach(r)
        except Exception:
            pass
    # One demo appointment
    with _engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO appointments (patient_id, measure, clinic, scheduled_at, status, source, external_id, created_at, updated_at)
            VALUES (:patient_id, :measure, :clinic, :scheduled_at, :status, :source, :external_id, :created_at, :updated_at)
        """), {
            "patient_id":"105","measure":"Hemoglobin A1c Control <8","clinic":"Cartersville",
            "scheduled_at": now + dt.timedelta(days=3),
            "status":"confirmed","source":"demo","external_id":"apt-demo-001",
            "created_at": now,"updated_at": now
        })

def create_appointment_from_outreach(outreach_row, when_utc):
    """Create a confirmed appointment based on an outreach row (demo flow)."""
    ensure_schema_all()
    with _engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO appointments (patient_id, measure, clinic, scheduled_at, status, source, external_id, created_at, updated_at)
            VALUES (:patient_id, :measure, :clinic, :scheduled_at, 'confirmed', 'demo', NULL, now(), now())
        """), {
            "patient_id": outreach_row.get("patient_id"),
            "measure": outreach_row.get("measure"),
            "clinic": outreach_row.get("clinic"),
            "scheduled_at": when_utc,
        })
