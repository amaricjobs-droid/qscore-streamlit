import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Nexa Quality Dashboard", page_icon="📊", layout="wide")
st.title("📊 Nexa Quality Measure Dashboard")
st.caption("Demo-ready dashboard with KPIs, trends, and patient table")

# --- Demo data (replace with your real data later) ---
data = {
    "patient_id": [101,102,103,104,105,106,107,108],
    "clinic": ["Cedartown","Rockmart","Rome","Rome","Cartersville","Cedartown","Rockmart","Cartersville"],
    "measure": ["HTN Control","Statin Adherence","30d Follow-up","HTN Control","Statin Adherence","HTN Control","30d Follow-up","HTN Control"],
    "value": [0.82,0.76,0.68,0.91,0.85,0.88,0.71,0.93],
    "date": pd.date_range("2025-01-01", periods=8, freq="M")
}
df = pd.DataFrame(data)
df["compliant"] = df["value"] >= 0.8

# --- Query params (deep link support) ---
params = st.query_params
clinic_param = params.get("clinic", None)

# --- Session state defaults ---
all_clinics  = sorted(df["clinic"].unique().tolist())
all_measures = sorted(df["measure"].unique().tolist())

if "sel_clinics" not in st.session_state:
    st.session_state.sel_clinics = [clinic_param] if clinic_param in all_clinics else all_clinics
if "sel_measures" not in st.session_state:
    st.session_state.sel_measures = all_measures

# --- Sidebar filters (keys are tied to session_state) ---
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

# --- Callback helpers for clinic chips ---
def _set_single_clinic(c: str):
    st.session_state.sel_clinics = [c]
    st.query_params.update({"clinic": c})
    st.rerun()

def _show_all_clinics():
    st.session_state.sel_clinics = all_clinics
    st.query_params.clear()
    st.rerun()

# --- Quick clinic filter chips ---
st.markdown("#### Quick clinic filter")
cols = st.columns(min(len(all_clinics), 6) or 1)
for i, c in enumerate(all_clinics):
    cols[i % len(cols)].button(
        c, key=f"btn_{c}",
        on_click=_set_single_clinic, args=(c,)
    )

st.button("Show All Clinics", key="btn_all", on_click=_show_all_clinics)

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

st.caption("💡 Tip: add ?clinic=Cedartown to the URL to deep-link a clinic.")
