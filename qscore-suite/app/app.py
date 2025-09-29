import pandas as pd
import plotly.express as px
import streamlit as st


# ---------- Audit logging & click-tracking helpers ----------
import os, csv
from datetime import datetime
from urllib.parse import urlencode, quote, unquote

LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

def _log_row(filename: str, row: dict):
    """Append a row to a CSV file in app/logs."""
    path = os.path.join(LOGS_DIR, filename)
    row = {k: ("" if v is None else str(v)) for k, v in row.items()}
    write_header = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=row.keys())
        if write_header:
            w.writeheader()
        w.writerow(row)

def tracking_link(patient_id: str, clinic: str, measure: str, target_url: str = "") -> str:
    """Return an internal link that records the click before sending to the real portal."""
    # Relative link keeps it portable on Cloud and local
    q = {
        "portal": "1",
        "pid": str(patient_id),
        "clinic": clinic,
        "measure": measure,
    }
    if target_url:
        q["next"] = target_url
    return "./?" + urlencode(q, doseq=False)

def resolve_portal_target(clinic: str, patient_id: str, measure: str) -> str:
    """Pick the clinic-specific portal if present; else LINK_BASE; else empty."""
    try:
        mapping = st.secrets.get("CLINIC_LINKS", {})
        base = mapping.get(clinic, "")
    except Exception:
        base = ""
    if not base:
        base = st.secrets.get("LINK_BASE", "")
    if not base:
        return ""
    # Non-PHI context params (avoid names/DOB/etc.)
    extra = {"pid": str(patient_id), "clinic": clinic, "measure": measure, "src": "nexa-app"}
    sep = "?" if "?" not in base else "&"
    return base + sep + urlencode(extra, doseq=False)
# -------- Page & Brand --------
st.set_page_config(page_title="Nexa Quality Dashboard", page_icon="📊", layout="wide")
st.title("📊 Nexa Quality Measure Dashboard")
st.caption("Client-ready navigation • Patient Messaging • Upload • KPIs • Trends • Exports")
# ---------- Portal landing (click-tracking & forward) ----------
_q = st.query_params
if _q.get("portal", None) == "1":
    pid     = _q.get("pid", "")
    clinic  = _q.get("clinic", "")
    measure = _q.get("measure", "")
    nxt     = _q.get("next", "")

    # Log the click
    _log_row("clicks.csv", {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "patient_id": pid, "clinic": clinic, "measure": measure,
        "next": nxt
    })

    st.title("✅ Nexa Scheduling")
    st.success("Thanks! We recorded your request.")
    if nxt:
        st.link_button("Continue to scheduling", nxt, type="primary")
        st.caption("If the button does not work, copy/paste this link:")
        st.code(nxt, language="text")
    else:
        st.info("A scheduler will contact you shortly.")

    st.stop()  # Do not render the rest of the app on this landing page


# -------- Demo/base data --------
def load_base_data():
    data = {
        "patient_id": [101,102,103,104,105,106,107,108,109,110],
        "clinic": ["Cedartown","Rockmart","Rome","Rome","Cartersville","Cedartown","Rockmart","Cartersville","Rome","Cedartown"],
        "measure": ["HTN Control","Statin Adherence","30d Follow-up","HTN Control","Statin Adherence","HTN Control","30d Follow-up","HTN Control","Statin Adherence","30d Follow-up"],
        "value": [0.82,0.76,0.68,0.91,0.85,0.88,0.71,0.93,0.79,0.83],
        "date": pd.date_range("2025-01-01", periods=10, freq="M")
    }
    df = pd.DataFrame(data)
    df["compliant"] = df["value"] >= 0.8
    return df

# In-memory dataset (session). Uploads replace it for the session only.
if "dataframe" not in st.session_state:
    st.session_state.dataframe = load_base_data()

df = st.session_state.dataframe.copy()
all_clinics = sorted(df["clinic"].unique().tolist())
all_measures = sorted(df["measure"].unique().tolist())

# ---------- helpers ----------
def apply_filters(_df, clinics, measures):
    return _df[_df["clinic"].isin(clinics) & _df["measure"].isin(measures)].copy()

# Callback: set clinic for Dashboard via URL & session, then rerun
def _home_set_clinic(c: str):
    st.query_params.update({"clinic": c})
    st.session_state["dash_sel_clinics"] = [c]
    st.toast(f"Clinic set to {c}. Open the 📊 Dashboard tab.")
    st.rerun()

# -------- Top Navigation (tabs as top bar) --------
home_tab, dash_tab, upload_tab, msg_tab, reports_tab, logs_tab, help_tab = st.tabs(
    ["🏠 Home", "📊 Dashboard", "📤 Upload Data", "📨 Message Patients", "📎 Reports", "🧾 Logs", "❓ Help"]
)

# ============== HOME ==============
with home_tab:
    left, right = st.columns([2,1])
    with left:
        st.subheader("Welcome to Nexa Q-Score")
        st.markdown("""
**Fast paths**
- **📨 Message Patients** to send outreach by clinic/measure
- **📊 Dashboard** to review KPIs and trends
- **📤 Upload Data** to load a CSV and refresh clinics/measures
""")
        st.info("Tip: share deep links like ?clinic=Cedartown to open pre-filtered views.")
    with right:
        st.metric("Clinics detected", len(all_clinics))
        st.metric("Patients in data", len(df))
        st.metric("Measures tracked", len(all_measures))

    st.divider()
    st.subheader("Shortcuts")
    cols = st.columns(min(len(all_clinics), 6) or 1)
    for i, c in enumerate(all_clinics):
        cols[i % len(cols)].button(
            f"Open Dashboard: {c}",
            key=f"home_{c}",
            on_click=_home_set_clinic,
            args=(c,)
        )

# ====== KPI Row ======
if 'df' in locals() and not df.empty:
    kcol1, kcol2, kcol3 = st.columns(3)
    with kcol1:
        htn_rate = (df[df['measure']=="HTN"]["compliant"].mean()*100).round(1) if "measure" in df else 0
        st.metric("Hypertension Control", f"{htn_rate}%", "Target: 90%")

    with kcol2:
        statin_rate = (df[df['measure']=="Statin"]["compliant"].mean()*100).round(1) if "measure" in df else 0
        st.metric("Statin Adherence", f"{statin_rate}%", "Target: 85%")

    with kcol3:
        fu30_rate = (df[df['measure']=="FollowUp30"]["compliant"].mean()*100).round(1) if "measure" in df else 0
        st.metric("30-Day FU", f"{fu30_rate}%", "Target: 95%")

    # ====== Export Button ======
    st.download_button(
        "⬇️ Export Filtered Data",
        df.to_csv(index=False).encode("utf-8"),
        file_name="qscore_export.csv",
        mime="text/csv"
    )
# ============== DASHBOARD ==============
with dash_tab:
    st.subheader("Dashboard")
    params = st.query_params
    clinic_param = params.get("clinic", None)

    if "dash_sel_clinics" not in st.session_state:
        st.session_state.dash_sel_clinics = [clinic_param] if clinic_param in all_clinics else all_clinics
    if "dash_sel_measures" not in st.session_state:
        st.session_state.dash_sel_measures = all_measures

    st.sidebar.header("Dashboard Filters")
    st.sidebar.multiselect("Clinic(s)", all_clinics, default=st.session_state.dash_sel_clinics, key="dash_sel_clinics")
    st.sidebar.multiselect("Measure(s)", all_measures, default=st.session_state.dash_sel_measures, key="dash_sel_measures")

    fdf = apply_filters(df, st.session_state.dash_sel_clinics, st.session_state.dash_sel_measures)

    col1, col2, col3 = st.columns(3)
    def pct(series): return f"{(series.mean()*100):.1f}%" if len(series) else "—"
    col1.metric("Hypertension Control", pct(fdf.loc[fdf["measure"]=="HTN Control","compliant"]), "Target: 90%")
    col2.metric("Statin Adherence",   pct(fdf.loc[fdf["measure"]=="Statin Adherence","compliant"]), "Target: 80%")
    col3.metric("30-Day Follow-Up",   pct(fdf.loc[fdf["measure"]=="30d Follow-up","compliant"]), "Target: 75%")

    st.divider()
    t1, t2 = st.tabs(["📈 Trends", "📋 Patient Table"])
    with t1:
        if not fdf.empty:
            monthly = fdf.groupby([pd.Grouper(key="date", freq="M"),"measure"])["compliant"].mean().reset_index()
            fig = px.line(monthly, x="date", y="compliant", color="measure", markers=True)
            fig.update_yaxes(tickformat=".0%", range=[0,1])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data for selected filters.")
    with t2:
        st.dataframe(fdf.sort_values("date", ascending=False), use_container_width=True, height=460)

# ============== UPLOAD DATA ============
with upload_tab:
    st.subheader("Upload CSV (Demo)")
    st.markdown("""
Upload a CSV with columns like: **patient_id, clinic, measure, value, date, compliant**.  
The file is **only kept for this session**.
""")
    file = st.file_uploader("Choose CSV file", type=["csv"])
    if file:
        try:
            new_df = pd.read_csv(file)
            if "date" in new_df.columns:
                new_df["date"] = pd.to_datetime(new_df["date"], errors="coerce")
            if "compliant" in new_df.columns and new_df["compliant"].dtype != bool:
                new_df["compliant"] = new_df["compliant"].astype(str).str.lower().isin(["true","1","yes","y","t"])
            st.session_state.dataframe = new_df.dropna(subset=["clinic","measure"])
            st.success("Upload successful. Data replaced for this session.")
            st.rerun()
        except Exception as e:
            st.error(f"Could not read CSV: {e}")

# ============== MESSAGE PATIENTS ======
with msg_tab:
    st.subheader("Message Patients")

    if "msg_sel_clinics" not in st.session_state:
        st.session_state.msg_sel_clinics = all_clinics
    if "msg_sel_measures" not in st.session_state:
        st.session_state.msg_sel_measures = all_measures

    st.sidebar.header("Messaging Filters")
    st.sidebar.multiselect("Clinic(s) (Messaging)", all_clinics, default=st.session_state.msg_sel_clinics, key="msg_sel_clinics")
    st.sidebar.multiselect("Measure(s) (Messaging)", all_measures, default=st.session_state.msg_sel_measures, key="msg_sel_measures")
    include_only_noncompliant = st.sidebar.checkbox("Only non-compliant patients", value=True)

    mdf = apply_filters(df, st.session_state.msg_sel_clinics, st.session_state.msg_sel_measures)
    if include_only_noncompliant and "compliant" in mdf.columns:
        mdf = mdf[~mdf["compliant"].fillna(False)]

    left, right = st.columns([2,1])
    with left:
        st.markdown("**Recipients (preview)**")
        preview_cols = [c for c in ["patient_id","clinic","measure","date","compliant"] if c in mdf.columns]
        st.dataframe(mdf[preview_cols].head(100), use_container_width=True, height=360)
    with right:
        st.markdown("**Compose Message**")
        
    # ====== Messaging Templates + Preview ======
    templates = load_templates()
selected_template = st.selectbox("Choose a template", list(templates.keys()))
template = st.text_area("Template", value=templates[selected_template], height=120)
if st.button("💾 Save Template"):
    templates[selected_template] = template
    save_templates(templates)
    st.success(f"Template \"{selected_template}\" saved!"), your blood pressure needs follow-up for {clinic}. {link}",
        "Statin Reminder": "Hello {patient_id}, please continue your statin therapy for {clinic}. {link}",
        "Follow-Up 30d": "Hello {patient_id}, please schedule your 30-day follow-up visit for {clinic}. {link}"
    }

    selected_template = st.selectbox("Choose a template", list(templates.keys()))
    
    # ====== Messaging Templates + Preview ======
    templates = load_templates()
selected_template = st.selectbox("Choose a template", list(templates.keys()))
template = st.text_area("Template", value=templates[selected_template], height=120)
if st.button("💾 Save Template"):
    templates[selected_template] = template
    save_templates(templates)
    st.success(f"Template \"{selected_template}\" saved!"), your blood pressure needs follow-up for {clinic}. {link}",
        "Statin Reminder": "Hello {patient_id}, please continue your statin therapy for {clinic}. {link}",
        "Follow-Up 30d": "Hello {patient_id}, please schedule your 30-day follow-up visit for {clinic}. {link}"
    }

    selected_template = st.selectbox("Choose a template", list(templates.keys()))
    template = st.text_area("Template", value=templates[selected_template], height=120)

    # Live preview
    if not mdf.empty:
        r0 = mdf.iloc[0]
        preview_link = build_link(r0.get("patient_id",""), r0.get("clinic",""), r0.get("measure",""))
        preview_text = render_template(template, r0, preview_link)
        st.info(f"**Preview:** {preview_text}")

    # Live preview
    if not mdf.empty:
        r0 = mdf.iloc[0]
        preview_link = build_link(r0.get("patient_id",""), r0.get("clinic",""), r0.get("measure",""))
        preview_text = render_template(template, r0, preview_link)
        st.info(f"**Preview:** {preview_text}")
        st.caption("Placeholders coming soon: {patient_id}, {clinic}, {measure}")
# ---------- Portal landing (click-tracking & forward) ----------
_q = st.query_params
if _q.get("portal", None) == "1":
    pid     = _q.get("pid", "")
    clinic  = _q.get("clinic", "")
    measure = _q.get("measure", "")
    nxt     = _q.get("next", "")

    # Log the click
    _log_row("clicks.csv", {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "patient_id": pid, "clinic": clinic, "measure": measure,
        "next": nxt
    })

    st.title("✅ Nexa Scheduling")
    st.success("Thanks! We recorded your request.")
    if nxt:
        st.link_button("Continue to scheduling", nxt, type="primary")
        st.caption("If the button does not work, copy/paste this link:")
        st.code(nxt, language="text")
    else:
        st.info("A scheduler will contact you shortly.")

    st.stop()  # Do not render the rest of the app on this landing page

        count = len(mdf)
        st.metric("Recipients to send", count)
        if st.button("Send Messages", type="primary"):
            st.success(f"Queued {count} messages. (Demo only)")
            st.toast("Messages queued (demo)")

    st.info("To wire this to real messaging, store provider API keys in Secrets and call Twilio/SendGrid from this button.")

# ============== REPORTS ===============
with reports_tab:
    st.subheader("Reports & Exports")
    filt_clin = st.session_state.get("dash_sel_clinics", all_clinics)
    filt_meas = st.session_state.get("dash_sel_measures", all_measures)
    rdf = apply_filters(df, filt_clin, filt_meas)
    if not rdf.empty:
        csv = rdf.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, file_name="nexa_export.csv", mime="text/csv")
    else:
        st.info("No data for current filters to export.")

# ============== LOGS ==============
with logs_tab:
    st.subheader("Message & Click Logs")

    import os
    LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")
    msgs_path = os.path.join(LOGS_DIR, "messages.csv")
    clicks_path = os.path.join(LOGS_DIR, "clicks.csv")

    def _read_csv_safe(p):
        try:
            if os.path.exists(p):
                return pd.read_csv(p)
        except Exception:
            return None
        return None

    mdf = _read_csv_safe(msgs_path)    # messages
    cdf = _read_csv_safe(clicks_path)  # clicks

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Messages log**")
        if mdf is not None and not mdf.empty:
            st.dataframe(mdf.tail(500), use_container_width=True, height=300)
            _csv = mdf.to_csv(index=False).encode("utf-8")
            st.download_button("Download messages.csv", _csv, file_name="messages.csv", mime="text/csv")
        else:
            st.info("No messages logged yet.")

    with col2:
        st.markdown("**Clicks log**")
        if cdf is not None and not cdf.empty:
            st.dataframe(cdf.tail(500), use_container_width=True, height=300)
            _csv2 = cdf.to_csv(index=False).encode("utf-8")
            st.download_button("Download clicks.csv", _csv2, file_name="clicks.csv", mime="text/csv")
        else:
            st.info("No clicks logged yet.")

    st.divider()
    st.subheader("Summary")
    total_sent = len(mdf) if mdf is not None else 0
    total_clicks = len(cdf) if cdf is not None else 0
    ctr = (total_clicks / total_sent * 100) if total_sent else 0.0
    m1, m2, m3 = st.columns(3)
    m1.metric("Messages queued", f"{total_sent}")
    m2.metric("Clicks", f"{total_clicks}")
    m3.metric("Click-through rate", f"{ctr:.1f}%")

    # Clicks over time (daily)
    if cdf is not None and not cdf.empty and "ts" in cdf.columns:
        try:
            cdf["ts"] = pd.to_datetime(cdf["ts"], errors="coerce")
            daily = cdf.groupby(pd.Grouper(key="ts", freq="D")).size().reset_index(name="clicks")
            fig = px.bar(daily, x="ts", y="clicks")
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            pass
# ============== HELP ======================
with help_tab:
    st.subheader("Help & Support")
    st.markdown("""
**How to use this app**
1. **Upload Data** (CSV) or use the demo data.
2. Open **Dashboard** to see KPIs, trends, and details.
3. Go to **Message Patients** to target outreach by clinic/measure.
4. Use **Reports** to export current filtered data.

**Need assistance?** Contact Nexa Support.
""")







