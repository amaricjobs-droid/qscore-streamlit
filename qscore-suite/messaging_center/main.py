from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jose import jwt
from datetime import datetime, timedelta
from pydantic import BaseModel
from pathlib import Path
import os, sqlite3

SECRET = os.getenv("QSECRET", "dev-secret")
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8001")
CALENDLY_URL = os.getenv("CALENDLY_URL", "https://calendly.com/your-clinic/bp-check")

app = FastAPI(title="Q-Messaging Center")

# Mount /static only if messaging_center/static exists (resolve relative to this file)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

def db():
    con = sqlite3.connect("qmsg.db", check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS patients(
      id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, phone TEXT, email TEXT,
      dob TEXT, preferred_language TEXT, provider TEXT, location TEXT,
      consent_sms INTEGER DEFAULT 1, consent_email INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS outreach_messages(
      id INTEGER PRIMARY KEY, patient_id INTEGER, measure TEXT, channel TEXT,
      status TEXT, sent_at TEXT, delivered_at TEXT, clicked_at TEXT, completed_at TEXT, token_jwt TEXT
    );
    CREATE TABLE IF NOT EXISTS bp_readings(
      id INTEGER PRIMARY KEY, patient_id INTEGER, systolic INTEGER, diastolic INTEGER,
      reported_at TEXT, source TEXT
    );
    CREATE TABLE IF NOT EXISTS referral_requests(
      id INTEGER PRIMARY KEY, patient_id INTEGER, reason TEXT, free_text TEXT,
      created_at TEXT, status TEXT
    );
    """)
    con.commit()
init_db()

def create_magic_token(patient_id: int, measure: str) -> str:
    payload = {"pid": patient_id, "m": measure, "exp": datetime.utcnow() + timedelta(days=10)}
    return jwt.encode(payload, SECRET, algorithm="HS256")

def verify_token(token: str):
    try:
        return jwt.decode(token, SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired link")

class EnqueueItem(BaseModel):
    patient_id: int
    measure: str   # "CBP" | "STATIN" | "DM_A1C"

@app.post("/api/enqueue")
def enqueue(item: EnqueueItem):
    con = db()
    token = create_magic_token(item.patient_id, item.measure)
    con.execute("INSERT INTO outreach_messages (patient_id, measure, channel, status, sent_at, token_jwt) VALUES (?,?,?,?,?,?)",
                (item.patient_id, item.measure, "sms", "queued", datetime.utcnow().isoformat(), token))
    con.commit()
    return {"ok": True}

# Stub sender: flips queued -> sent. (Wire Twilio later.)
@app.post("/api/send_queued")
def send_queued():
    con = db()
    rows = con.execute("SELECT id FROM outreach_messages WHERE status='queued'").fetchall()
    for r in rows:
        con.execute("UPDATE outreach_messages SET status='sent' WHERE id=?", (r["id"],))
    con.commit()
    return {"sent": len(rows)}

@app.get("/go", response_class=HTMLResponse)
def go(t: str):
    data = verify_token(t)
    con = db()
    con.execute("UPDATE outreach_messages SET clicked_at=? WHERE token_jwt=? AND clicked_at IS NULL",
                (datetime.utcnow().isoformat(), t))
    con.commit()
    return f"""
    <html><body style="font-family:sans-serif; max-width:600px; margin:40px auto;">
      <h2>Care actions</h2>
      <ul>
        <li><a href="/bp?t={t}">Enter blood pressure</a></li>
        <li><a href="{CALENDLY_URL}" target="_blank">Schedule an appointment</a></li>
        <li><a href="/referral?t={t}">Request a referral</a></li>
      </ul>
      <p><small>No PHI stored in SMS. Links expire in 10 days.</small></p>
    </body></html>
    """

@app.get("/bp", response_class=HTMLResponse)
def bp_form(t: str):
    verify_token(t)
    return f"""
    <html><body style="font-family:sans-serif; max-width:600px; margin:40px auto;">
      <h3>Submit Blood Pressure</h3>
      <form method="post" action="/bp">
        <input type="hidden" name="t" value="{t}" />
        <label>Systolic</label><br><input name="sys" required type="number" /><br>
        <label>Diastolic</label><br><input name="dia" required type="number" /><br><br>
        <button type="submit">Submit</button>
      </form>
    </body></html>
    """

@app.post("/bp")
def bp_submit(t: str = Form(...), sys: int = Form(...), dia: int = Form(...)):
    data = verify_token(t)
    con = db()
    con.execute("INSERT INTO bp_readings (patient_id, systolic, diastolic, reported_at, source) VALUES (?,?,?,?,?)",
                (data["pid"], sys, dia, datetime.utcnow().isoformat(), "patient_portal"))
    if data["m"] == "CBP" and sys < 140 and dia < 90:
        con.execute("UPDATE outreach_messages SET completed_at=?, status='completed' WHERE token_jwt=?",
                    (datetime.utcnow().isoformat(), t))
    con.commit()
    return RedirectResponse(url="/thanks", status_code=303)

@app.get("/referral", response_class=HTMLResponse)
def referral_form(t: str):
    verify_token(t)
    return f"""
    <html><body style="font-family:sans-serif; max-width:600px; margin:40px auto;">
      <h3>Referral Request</h3>
      <form method="post" action="/referral">
        <input type="hidden" name="t" value="{t}" />
        <label>Reason</label><br>
        <select name="reason" required>
          <option>Cardiology</option><option>Endocrinology</option><option>Behavioral Health</option><option>Other</option>
        </select><br>
        <label>Details (optional)</label><br><textarea name="ft" rows="4"></textarea><br><br>
        <button type="submit">Submit</button>
      </form>
    </body></html>
    """

@app.post("/referral")
def referral_submit(t: str = Form(...), reason: str = Form(...), ft: str = Form("")):
    data = verify_token(t)
    con = db()
    con.execute("INSERT INTO referral_requests (patient_id, reason, free_text, created_at, status) VALUES (?,?,?,?,?)",
                (data["pid"], reason, ft, datetime.utcnow().isoformat(), "new"))
    con.commit()
    return RedirectResponse(url="/thanks", status_code=303)

@app.get("/thanks", response_class=HTMLResponse)
def thanks():
    return "<html><body style='font-family:sans-serif; margin:40px;'>Thanks! Your information has been received.</body></html>"
