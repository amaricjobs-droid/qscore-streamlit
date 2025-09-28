import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Q-Score Dashboard", page_icon="📊", layout="wide")
st.title("📊 Q-Score Quality Measure Dashboard")
st.caption("Demo-ready dashboard with KPIs, trends, and patient table")

# --- Demo data (keep it lightweight; replace with your data later) ---
data = {
    "patient_id": [101,102,103,104,105,106,107,108],
    "clinic": ["Cedartown","Rockmart","Rome","Rome","Cartersville","Cedartown","Rockmart","Cartersville"],
    "measure": ["HTN Control","Statin Adherence","30d Follow-up","HTN Control","Statin Adherence","HTN Control","30d Follow-up","HTN Control"],
    "value": [0.82,0.76,0.68,0.91,0.85,0.88,0.71,0.93],
    "date": pd.date_range("2025-01-01", periods=8, freq="M")
}
df = pd.DataFrame(data)
df["compliant"] = df["value"] >= 0.8

# --- Read query params for deep-link filtering (e.g., ?clinic=Cedartown) ---
try:
    params = st.experimental_get_query_params()
except Exception:
    params = {}
clinic_param = params.get("clinic", [])
if isinstance(clinic_param, str):
    clinic_param = [clinic_param]

# --- Sidebar filters with session state so buttons can update them ---
all_clinics  = sorted(df["clinic"].unique().tolist())
all_measures = sorted(df["measure"].unique().tolist())

if "sel_clinics" not in st.session_state:
    st.session_state.sel_clinics = clinic_param or all_clinics
if "sel_measures" not in st.session_state:
    st.session_state.sel_measures = all_measures

st.sidebar.header("Filters")
st.sidebar.multiselect(
    "Clinic(s)", options=all_clinics,
    default=st.session_state.sel_clinics,
    key="sel_clinics"
)
st.sidebar.multiselect(
    "Measure(s)", options=all_measures,
    default=st.session_state.sel_measures,
    key="sel_measures"
)

# --- Quick clinic chips (buttons) across the top ---
st.markdown("#### Quick clinic filter")
cols = st.columns(min(len(all_clinics), 6) or 1)
for i, c in enumerate(all_clinics):
    if cols[i % len(cols)].button(c):
        st.session_state.sel_clinics = [c]
        st.experimental_set_query_params(clinic=c)
        st.experimental_rerun()

# Reset button to show all
if st.button("Show All Clinics"):
    st.session_state.sel_clinics = all_clinics
    st.experimental_set_query_params()  # clear query params
    st.experimental_rerun()

# --- Apply filters ---
fdf = df[
    df["clinic"].isin(st.session_state.sel_clinics)
    & df["measure"].isin(st.session_state.sel_measures)
].copy()

# --- KPIs ---
col1,col2,col3 = st.columns(3)
def pct(series): 
    return f"{(series.mean()*100):.1f}%" if len(series) else "—"
col1.metric("Hypertension Control",   pct(fdf.loc[fdf["measure"]=="HTN Control","compliant"]),       "Target: 90%")
col2.metric("Statin Adherence",       pct(fdf.loc[fdf["measure"]=="Statin Adherence","compliant"]), "Target: 80%")
col3.metric("30-Day Follow-Up",       pct(fdf.loc[fdf["measure"]=="30d Follow-up","compliant"]),    "Target: 75%")

st.divider()

# --- Tabs ---
tab1, tab2 = st.tabs(["📈 Trends","📋 Patient Detail"])

with tab1:
    st.subheader("Compliance Trends")
    if not fdf.empty:
        monthly = fdf.groupby([pd.Grouper(key="date", freq="M"),"measure"])["compliant"].mean().reset_index()
        fig = px.line(monthly, x="date", y="compliant", color="measure", markers=True)
        fig.update_yaxes(tickformat=".0%", range=[0,1])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data for selected filters.")

with tab2:
    st.subheader("Patient Table")
    st.dataframe(fdf.sort_values("date", ascending=False), use_container_width=True)

st.caption("💡 Tip: You can deep-link filters, e.g., add ?clinic=Cedartown to the URL for a pre-filtered view.")
