import io
import pandas as pd
import plotly.express as px
import streamlit as st

# ---------- Page & Brand ----------
st.set_page_config(page_title="Nexa Quality Dashboard", page_icon="📊", layout="wide")
st.title("📊 Nexa Quality Measure Dashboard")
st.caption("A client-ready experience with clear navigation, patient messaging, uploads, and dashboards.")

# ---------- Demo / base data ----------
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

# In-memory dataset (upload can replace during the session)
if "dataframe" not in st.session_state:
    st.session_state.dataframe = load_base_data()

df = st.session_state.dataframe.copy()
all_clinics = sorted(df["clinic"].unique().tolist())
all_measures = sorted(df["measure"].unique().tolist())

# ---------- Navigation (top) ----------
# We use tabs as a top nav bar (most visible placement in Streamlit)
home_tab, dash_tab, upload_tab, msg_tab, reports_tab, help_tab = st.tabs(
    ["🏠 Home", "📊 Dashboard", "📤 Upload Data", "📨 Message Patients", "📎 Reports", "❓ Help"]
)

# ============== HOME =================
with home_tab:
    left, right = st.columns([2,1])
    with left:
        st.subheader("Welcome to Nexa Q-Score")
        st.markdown("""
**Fast paths**
- Click **📨 Message Patients** to send outreach by clinic/measure (your #1 value driver)
- Click **📊 Dashboard** to review KPIs and trends
- Click **📤 Upload Data** to load a CSV and refresh clinics/measures
""")
        st.info("Tip: Share deep links like ?clinic=Cedartown to open pre-filtered views.")
        st.link_button("Go to Messaging", "#message-patients", type="primary")
    with right:
        # Quick stats
        st.metric("Clinics detected", len(all_clinics))
        st.metric("Patients in demo", len(df))
        st.metric("Measures tracked", len(all_measures))

    st.divider()
    st.subheader("Shortcuts")
    cols = st.columns(min(len(all_clinics), 6) or 1)
    for i, c in enumerate(all_clinics):
        cols[i % len(cols)].page_link(
            "qscore-suite/app/app.py",
            label=f"Open Dashboard: {c}",
            icon="📍",
            args={"clinic": c}
        )

# Helper to apply filters (used by Dashboard & Messaging)
def apply_filters(_df, clinics, measures):
    return _df[_df["clinic"].isin(clinics) & _df["measure"].isin(measures)].copy()

# ============== DASHBOARD ==============
with dash_tab:
    st.subheader("Dashboard")
    # Read URL params for deep-linking
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

    # KPIs
    col1, col2, col3 = st.columns(3)
    def pct(series): return f"{(series.mean()*100):.1f}%" if len(series) else "—"
    col1.metric("Hypertension Control", pct(fdf.loc[fdf["measure"]=="HTN Control","compliant"]), "Target: 90%")
    col2.metric("Statin Adherence", pct(fdf.loc[fdf["measure"]=="Statin Adherence","compliant"]), "Target: 80%")
    col3.metric("30-Day Follow-Up", pct(fdf.loc[fdf["measure"]=="30d Follow-up","compliant"]), "Target: 75%")

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
Upload a CSV with columns like:  
**patient_id, clinic, measure, value, date, compliant**  

- The file is **only kept for this session** (demo).  
- For production, we recommend a secure database (Postgres) or object storage.
""")
    file = st.file_uploader("Choose CSV file", type=["csv"])
    if file:
        try:
            new_df = pd.read_csv(file)
            # Light coercion
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
    st.markdown('<a id="message-patients"></a>', unsafe_allow_html=True)

    # Separate filters for messaging view
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
        template = st.text_area("Template", value="Hello! Our records show you may be due for follow-up on your health measure. Please contact our clinic to schedule.", height=140)
        placeholders = st.caption("Placeholders coming soon: {patient_id}, {clinic}, {measure}")
        count = len(mdf)
        st.metric("Recipients to send", count)

        # Send button (stubbed)
        if st.button("Send Messages", type="primary", help="Demo action - integrate with SMS/Email provider in production"):
            # Stub: In production, send via Twilio/Email. Log a simple result here.
            st.success(f"Queued {count} messages. (Demo only)")
            st.toast("Messages queued (demo)")

    st.info("To wire this to real messaging, store API keys in Secrets and call your messaging provider (e.g., Twilio, SendGrid).")

# ============== REPORTS ===============
with reports_tab:
    st.subheader("Reports & Exports")
    st.write("Download a CSV extract of current (filtered) dashboard data.")
    # Reuse dashboard filter state if present
    filt_clin = st.session_state.get("dash_sel_clinics", all_clinics)
    filt_meas = st.session_state.get("dash_sel_measures", all_measures)
    rdf = apply_filters(df, filt_clin, filt_meas)

    if not rdf.empty:
        csv = rdf.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, file_name="nexa_export.csv", mime="text/csv")
    else:
        st.info("No data for current filters to export.")

# ============== HELP ==================
with help_tab:
    st.subheader("Help & Support")
    st.markdown("""
**How to use this app**
1. **Upload Data** (CSV) or use the demo data.
2. Open **Dashboard** to see KPIs, trends, and details.
3. Go to **Message Patients** to target outreach by clinic/measure and (optionally) non-compliant status.
4. Use **Reports** to export current filtered data.

**Need assistance?** Contact Nexa Support.
""")
