import streamlit as st
import pandas as pd
import plotly.express as px

# ------------ Page config / Branding ------------
st.set_page_config(page_title="Nexa Q-Score", page_icon="📊", layout="wide")
st.title("📊 Nexa Q-Score")
st.caption("Upload → Filter → Insights → (Simulated) Messaging → Export")

# ------------ Base demo data ------------
def load_base_data():
    data = {
        "patient_id": [101,102,103,104,105,106,107,108,109,110],
        "clinic": ["Cedartown","Rockmart","Rome","Rome","Cartersville",
                   "Cedartown","Rockmart","Cartersville","Rome","Cedartown"],
        "measure": ["HTN Control","Statin Adherence","30d Follow-up","HTN Control",
                    "Statin Adherence","HTN Control","30d Follow-up",
                    "HTN Control","Statin Adherence","30d Follow-up"],
        "value": [0.82,0.76,0.68,0.91,0.85,0.88,0.71,0.93,0.79,0.83],
        "date": pd.date_range("2025-01-01", periods=10, freq="M")
    }
    df = pd.DataFrame(data)
    df["compliant"] = df["value"] >= 0.8
    return df

# Keep a working copy in session; uploads can replace it for this session only
if "dataframe" not in st.session_state:
    st.session_state.dataframe = load_base_data()

df = st.session_state.dataframe.copy()

# ------------ Sidebar Filters ------------
with st.sidebar:
    st.subheader("Filters")
    clinics = sorted(df["clinic"].unique().tolist())
    measures = sorted(df["measure"].unique().tolist())

    sel_clinics = st.multiselect("Clinics", clinics, default=clinics)
    sel_measures = st.multiselect("Measures", measures, default=measures)
    only_noncompliant = st.checkbox("Only non-compliant", value=False)

# Apply filters
fdf = df[df["clinic"].isin(sel_clinics) & df["measure"].isin(sel_measures)]
if only_noncompliant:
    fdf = fdf[~fdf["compliant"]]

# ------------ Navigation ------------
tabs = st.tabs(["🏠 Dashboard", "📤 Upload Data", "✉️ Messaging (Demo)", "📄 Reports"])

# ------------ Dashboard ------------
with tabs[0]:
    st.subheader("Quality Overview")

    # KPIs
    total = len(fdf)
    compliant = int(fdf["compliant"].sum())
    rate = (compliant / total * 100) if total else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Patients", total)
    c2.metric("Compliant", compliant)
    c3.metric("Compliance Rate", f"{rate:.1f}%")

    # Trend chart
    if not fdf.empty:
        agg = (fdf.groupby(["date","measure"], as_index=False)
                  .agg(value=("value","mean")))
        fig = px.line(agg, x="date", y="value", color="measure", markers=True,
                      title="Measure Trend (mean value by month)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No rows match the current filters.")

    st.dataframe(fdf, use_container_width=True)

# ------------ Upload ------------
with tabs[1]:
    st.subheader("Upload CSV/XLSX")
    st.write("Required columns (example): `patient_id`, `clinic`, `measure`, `value`, `date`")
    up = st.file_uploader("Choose a file", type=["csv","xlsx"])
    if up is not None:
        try:
            if up.name.lower().endswith(".csv"):
                nd = pd.read_csv(up)
            else:
                nd = pd.read_excel(up)

            # Light coercion
            needed = {"patient_id","clinic","measure","value","date"}
            missing = needed - set(map(str.lower, nd.columns.str.lower()))
            if missing:
                st.error(f"Missing columns: {sorted(list(missing))}")
            else:
                # Normalize column names
                nd.columns = [c.strip().lower() for c in nd.columns]
                nd.rename(columns={
                    "patient_id":"patient_id",
                    "clinic":"clinic",
                    "measure":"measure",
                    "value":"value",
                    "date":"date",
                }, inplace=True)

                # Parse types
                nd["date"] = pd.to_datetime(nd["date"], errors="coerce")
                nd["compliant"] = nd["value"] >= 0.8

                st.session_state.dataframe = nd.rename(columns=str)  # keep simple names
                st.success("Data uploaded for this session.")
        except Exception as e:
            st.error(f"Upload failed: {e}")

# ------------ Messaging (Demo only) ------------
with tabs[2]:
    st.subheader("Patient Messaging (Demo)")
    st.info("This demo simulates sending reminders. No real SMS/Email is sent.")
    st.caption("In production, wire Twilio/SendGrid using secrets.")

    # Choose a template and preview links (mock)
    default_templates = {
        "HTN Reminder": "Hello {patient_id}, your blood pressure needs follow-up for {clinic}. Please schedule: {link}",
        "Statin Reminder": "Hello {patient_id}, please continue your statin therapy for {clinic}. Schedule: {link}",
        "Follow-Up 30d": "Hello {patient_id}, please schedule your 30-day follow-up for {clinic}. Start here: {link}",
    }
    template_name = st.selectbox("Template", list(default_templates.keys()))
    template_body = st.text_area("Message", value=default_templates[template_name], height=120)

    # Choose recipients (filtered view)
    rec_df = fdf.copy()
    st.write(f"Recipients shown below ({len(rec_df)} rows):")
    st.dataframe(rec_df[["patient_id","clinic","measure","value","compliant"]], use_container_width=True)

    # Simulated send
    if st.button("🚀 Queue Messages (Demo)"):
        st.success(f"Queued {len(rec_df)} messages (demo).")
        st.toast("Messages queued (demo)")

# ------------ Reports / Export ------------
with tabs[3]:
    st.subheader("Export")
    if not fdf.empty:
        csv = fdf.to_csv(index=False).encode("utf-8")
        st.download_button("Download filtered CSV", data=csv, file_name="qscore_filtered.csv", mime="text/csv")
    else:
        st.info("Apply filters to generate a report.")
