import pandas as pd
import plotly.express as px
import streamlit as st
# --- make local packages importable (qscore-suite/) ---
import sys, pathlib
_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from db.store import ensure_schema, log_outreach, get_engine, ensure_schema_all, seed_demo_data, create_appointment_from_outreach
from services.messaging import send_sms, send_email
# --- make local packages importable ---
import sys, pathlib
_ROOT = pathlib.Path(__file__).resolve().parent.parent  # points to qscore-suite/
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ============== CONFIG: official measures & goals (EDIT HERE) ==============
MEASURE_WHITELIST = [
    "Hemoglobin A1c Control <8",
    "Kidney Eval: eGFR",
    "Kidney Eval: ACR",
    "High Blood Pressure Control <140/90",
    "Breast Cancer Screening",
    "CAD/IVD Statin Therapy (SPC)",
    "Diabetes Statin Therapy (SUPD)",
    "Childhood Immunization Status (Combo 7)",
    "Well Care Visit 3–21 Years Old",
]

# Targets & Stretch as proportions (0.716 = 71.6%)
TARGETS = {
    "Hemoglobin A1c Control <8": (0.716, 0.750),  # from your scorecard (Dec sheet)
    "Kidney Eval: eGFR": (0.750, 0.800),
    "Kidney Eval: ACR": (0.720, 0.760),
    "High Blood Pressure Control <140/90": (0.700, 0.750),
    "Breast Cancer Screening": (0.640, 0.680),
    "CAD/IVD Statin Therapy (SPC)": (0.830, 0.860),
    "Diabetes Statin Therapy (SUPD)": (0.780, 0.820),
    "Childhood Immunization Status (Combo 7)": (0.600, 0.650),
    "Well Care Visit 3–21 Years Old": (0.600, 0.650),
}

# ============== PAGE & BRAND ==============
st.set_page_config(page_title="Nexa Quality Dashboard", page_icon="📊", layout="wide")
st.title("📊 Nexa Quality Measure Dashboard")
st.caption("Official measures only • Targets & Stretch displayed • Whole percent formatting")

# ============== DEMO/BASE DATA (replace during Upload tab) ==============
def load_base_data():
    data = {
        "patient_id": [101,102,103,104,105,106,107,108,109,110],
        "clinic": ["Cedartown","Rockmart","Rome","Rome","Cartersville","Cedartown","Rockmart","Cartersville","Rome","Cedartown"],
        "measure": [
            "Hemoglobin A1c Control <8","Diabetes Statin Therapy (SUPD)","High Blood Pressure Control <140/90",
            "Hemoglobin A1c Control <8","CAD/IVD Statin Therapy (SPC)","Hemoglobin A1c Control <8",
            "Breast Cancer Screening","Kidney Eval: eGFR","Kidney Eval: ACR","Well Care Visit 3–21 Years Old",
        ],
        # 'value' is a per-patient measure score (0..1). We'll compute compliant against TARGETS per measure.
        "value": [0.82,0.76,0.68,0.91,0.85,0.88,0.71,0.79,0.83,0.60],
        "date": pd.date_range("2025-01-01", periods=10, freq="M")
    }
    return pd.DataFrame(data)

if "dataframe" not in st.session_state:
    st.session_state.dataframe = load_base_data()

df = st.session_state.dataframe.copy()

# ================== FILTER TO OFFICIAL MEASURES & RECOMPUTE COMPLIANCE ==================
# Drop anything not on the whitelist (e.g., 30-day follow-up)
df = df[df["measure"].isin(MEASURE_WHITELIST)].copy()

# If date exists, ensure datetime
if "date" in df.columns:
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

# Recompute "compliant" using per-measure TARGET threshold when available
def row_compliant(row):
    m = row.get("measure")
    v = row.get("value")
    if pd.isna(v) or m not in TARGETS: 
        return row.get("compliant", False)
    target, _ = TARGETS[m]
    try:
        return float(v) >= float(target)
    except Exception:
        return False

df["compliant"] = df.apply(row_compliant, axis=1)

# Detect clinics & measures from the filtered data
all_clinics  = sorted(df["clinic"].dropna().unique().tolist()) if "clinic" in df.columns else []
all_measures = [m for m in MEASURE_WHITELIST if m in df["measure"].unique()]

# ============== NAV ==============
home_tab, dash_tab, upload_tab, msg_tab, reports_tab, help_tab = st.tabs(
    ["🏠 Home", "📊 Dashboard", "📤 Upload Data", "📨 Message Patients", "📎 Reports", "❓ Help"]
)

# Helper: format %
def pct_str(x: float | int | None) -> str:
    if x is None or pd.isna(x): return "—"
    try: return f"{round(100*float(x))}%"
    except: return "—"

# Helper: apply filters
def apply_filters(_df, clinics, measures):
    return _df[_df["clinic"].isin(clinics) & _df["measure"].isin(measures)].copy()

# ============== HOME ==============
with home_tab:
    st.subheader("Welcome")
    st.write("This view shows only your official measures. Targets & Stretch are applied per measure, and all charts display whole percentages.")
    st.markdown("**Tracked measures:**")
    st.write(", ".join(all_measures) if all_measures else "_No measures present in the data_")

    st.divider()
    st.subheader("Quick Clinics")
    def _home_set_clinic(c: str):
        st.query_params.update({"clinic": c})
        st.session_state["dash_sel_clinics"] = [c]
        st.toast(f"Clinic set to {c}. Open the 📊 Dashboard tab.")
        st.rerun()
    cols = st.columns(min(len(all_clinics), 6) or 1)
    for i, c in enumerate(all_clinics):
        cols[i % len(cols)].button(f"Open Dashboard: {c}", key=f"home_{c}", on_click=_home_set_clinic, args=(c,))

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

    # ===== KPI ROW: build dynamically from whitelisted measures =====
    st.markdown("#### Scorecard")
    # Compute per-measure current compliance (% meeting target)
    kpi_cols = st.columns(3)
    for idx, m in enumerate(all_measures[:9]):  # show up to 9 in 3 rows if needed
        col = kpi_cols[idx % 3]
        sub = fdf[fdf["measure"] == m]
        rate = float(sub["compliant"].mean()) if not sub.empty else None
        target, stretch = TARGETS.get(m, (None, None))
        label = m
        delta = " | ".join([f"Target: {pct_str(target)}", f"Stretch: {pct_str(stretch)}"])
        col.metric(label, pct_str(rate), delta)

        if idx % 3 == 2 and idx < len(all_measures)-1:
            kpi_cols = st.columns(3)

    st.divider()
    t1, t2 = st.tabs(["📈 Trends", "📋 Patient Table"])
    with t1:
        if not fdf.empty and "date" in fdf.columns:
            monthly = (
                fdf.assign(month=fdf["date"].dt.to_period("M").dt.to_timestamp())
                   .groupby(["month","measure"])["compliant"]
                   .mean()
                   .reset_index()
            )
            fig = px.line(monthly, x="month", y="compliant", color="measure", markers=True)
            fig.update_yaxes(tickformat=".0%", range=[0,1])
            fig.update_layout(yaxis_tickformat="%", yaxis=dict(ticksuffix=""))  # keep chart in %
            st.plotly_chart(fig, use_container_width=True, theme="streamlit")
        else:
            st.info("No data for selected filters.")
    with t2:
        show_cols = [c for c in ["patient_id","clinic","measure","value","compliant","date"] if c in fdf.columns]
        st.dataframe(fdf.sort_values("date", ascending=False)[show_cols], use_container_width=True, height=460)

# ============== UPLOAD DATA ============
with upload_tab:
    st.subheader("Upload CSV (session-only)")
    st.markdown("""
Your CSV must include: **patient_id, clinic, measure, value, date** (and optionally **compliant**).  
Rows with measures not in the official list will be ignored. Compliance is recomputed using per-measure **Target**.
""")
    file = st.file_uploader("Choose CSV file", type=["csv"])
    if file:
        try:
            new_df = pd.read_csv(file)
            if "date" in new_df.columns:
                new_df["date"] = pd.to_datetime(new_df["date"], errors="coerce")
            # filter to official measures
            new_df = new_df[new_df["measure"].isin(MEASURE_WHITELIST)].copy()
            # recompute compliant from TARGETS
            def _comp(row):
                m, v = row.get("measure"), row.get("value")
                if pd.isna(v) or m not in TARGETS: return False
                t, _ = TARGETS[m]
                try: return float(v) >= float(t)
                except: return False
            new_df["compliant"] = new_df.apply(_comp, axis=1)
            st.session_state.dataframe = new_df.dropna(subset=["clinic","measure"])
            st.success("Upload successful. Data replaced for this session.")
            st.rerun()
        except Exception as e:
            st.error(f"Could not read CSV: {e}")

# ============== MESSAGE PATIENTS (demo) ============
with msg_tab:
    st.subheader("Message Patients (demo)")
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
        st.dataframe(mdf[preview_cols].head(200), use_container_width=True, height=360)
    with right:
        st.markdown("**Compose Message**")
        st.text_area("Template", value="Hello! Our records show you may be due for follow-up. Please contact our clinic to schedule.", height=140)
        st.caption("Placeholders coming soon: `{patient_id}`, `{clinic}`, `{measure}`")
        st.metric("Recipients to send", len(mdf))
        if st.button("Send Messages", type="primary"):
            st.success(f"Queued {len(mdf)} messages. (Demo only)")
            st.toast("Messages queued (demo)")

# ============== REPORTS ============
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

# ============== HELP ============
with help_tab:
    st.subheader("Help & Support")
    st.markdown("""
**What you see**
- Only official Population Health measures are included.
- **Target** and **Stretch** thresholds are applied per measure.
- All percentages are formatted as whole numbers (e.g., 72%).

**Need updates?** Edit the `TARGETS` dict at the top of this file to match your scorecard for each measure.
""")

def _best_contact(row):
    # In real use, pull from your patient master table. For demo, fabricate placeholders by patient_id.
    pid = str(row.get("patient_id",""))
    phone = f"+1555{pid[-7:]}" if pid else None
    email = f"patient{pid}@example.com" if pid else None
    return phone, email



# ================= EXTRA: Messaging Ops Console & Explainer (additive) =================
if "msg_extra_initialized" not in st.session_state:
    st.session_state.msg_extra_initialized = True
    try:
        ensure_schema_all()
    except Exception:
        pass

with msg_tab:
    st.divider()
    st.markdown("### How this works (at a glance)")
    st.write("""
- **Select patients** via filters on the left (optionally non-compliant only).
- Compose a message and click **Send Messages**. If messaging keys are set (Twilio/SendGrid), messages go out; otherwise demo-sends log to the database.
- Every attempt is written to an **Outreach Log** (status: sent/delivered/failed).
- You can **seed demo rows**, **search past outreach**, and **mark confirmed appointments** to simulate a live environment.
    """)

    st.markdown("### Quick demo controls")
    c1, c2, c3 = st.columns([1,1,2])
    with c1:
        if st.button("Seed demo data (logs + 1 appt)"):
            try:
                seed_demo_data()
                st.success("Seeded demo outreach + appointment.")
            except Exception as e:
                st.error(f"Seed failed: {e}")
    with c2:
        refresh = st.button("Refresh log & appointments")

    # Fetch log & appointments for the console
    engine = get_engine()
    import pandas as _pd
    import datetime as _dt

    log_df = _pd.read_sql_query("SELECT * FROM outreach ORDER BY created_at DESC LIMIT 1000", engine)
    appt_df = _pd.read_sql_query("SELECT * FROM appointments ORDER BY scheduled_at DESC LIMIT 500", engine) if refresh or True else _pd.DataFrame()

    st.markdown("### Past outreach (searchable)")
    # Client-side filters for demo simplicity
    f1, f2, f3, f4 = st.columns([1.2,1.2,1,1.4])
    with f1:
        q = st.text_input("Search (patient/measure/clinic)", "")
    with f2:
        ch = st.multiselect("Channel", ["sms","email"], [])
    with f3:
        stts = st.multiselect("Status", ["queued","sent","delivered","failed"], [])
    with f4:
        days = st.selectbox("Lookback (days)", [7,14,30,90,365], index=2)

    if not log_df.empty:
        cutoff = _dt.datetime.utcnow() - _dt.timedelta(days=int(days))
        log_df = log_df[ _pd.to_datetime(log_df["created_at"], errors="coerce") >= cutoff ]
        if q:
            ql = q.lower()
            log_df = log_df[
                log_df["patient_id"].astype(str).str.lower().str.contains(ql)
                | log_df["measure"].astype(str).str.lower().str.contains(ql)
                | log_df["clinic"].astype(str).str.lower().str.contains(ql)
            ]
        if ch:
            log_df = log_df[ log_df["channel"].isin(ch) ]
        if stts:
            log_df = log_df[ log_df["status"].isin(stts) ]

        st.dataframe(log_df, use_container_width=True, height=300)
        csv = log_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download outreach CSV", csv, file_name="outreach_log.csv", mime="text/csv")
    else:
        st.info("No outreach yet — use **Seed demo data** or send a batch.")

    st.markdown("### Mark confirmed appointments (demo)")
    if not log_df.empty:
        # Let user pick some outreach rows to turn into appointments
        sel = st.multiselect("Select outreach IDs to confirm", log_df["id"].astype(str).tolist()[:50])
        when = st.date_input("Appointment date", value=_dt.date.today() + _dt.timedelta(days=3))
        if st.button("Create confirmed appointments"):
            try:
                # Create appointments for each selected outreach
                for oid in sel:
                    row = log_df[ log_df["id"].astype(str) == oid ].iloc[0].to_dict()
                    when_dt = _dt.datetime.combine(when, _dt.time(hour=14, minute=0))
                    create_appointment_from_outreach(row, when_dt)
                st.success(f"Created {len(sel)} confirmed appointment(s).")
                # refresh appt_df
                appt_df = _pd.read_sql_query("SELECT * FROM appointments ORDER BY scheduled_at DESC LIMIT 500", engine)
            except Exception as e:
                st.error(f"Could not create appointments: {e}")
    else:
        st.caption("Send or seed some outreach to enable appointments.")

    st.markdown("### Recent appointments")
    if appt_df is not None and not appt_df.empty:
        st.dataframe(appt_df, use_container_width=True, height=240)
    else:
        st.info("No appointments recorded yet.")

