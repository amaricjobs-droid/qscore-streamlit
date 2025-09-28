import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import requests, os

st.set_page_config(page_title="Q-Score • Quality Measure Scorecard", layout="wide")

# ---- Messaging Center glue
MSG_API = os.getenv("MSG_API", "http://127.0.0.1:8001")

def enqueue_outreach(patient_id: int, measure: str):
    try:
        r = requests.post(f"{MSG_API}/api/enqueue", json={"patient_id": int(patient_id), "measure": measure})
        return r.ok
    except Exception:
        return False

# ---- Helpers
def pct(n, d): return (n / d * 100.0) if d else 0.0
def safe_float(x):
    try: return float(x)
    except: return np.nan
def yes(x): return str(x).strip().lower() in {"1","true","yes","y","t"}

# ---- UI
st.title("Q-Score: Quality Measure Scorecard & Gap Finder")
st.caption("Upload a CSV export (patients) with columns like: patient_id, patient_name, provider, location, phone, has_htn, last_bp_systolic, last_bp_diastolic, has_ascvd, on_statin, has_diabetes, last_a1c, last_a1c_date, last_visit_date, payer")

file = st.file_uploader("Upload patient CSV", type=["csv"])
with st.expander("Targets"):
    target_cbp = st.number_input("CBP ≥", value=70.0, step=1.0)
    target_sta = st.number_input("Statin (ASCVD) ≥", value=80.0, step=1.0)
    target_dm  = st.number_input("Diabetes good control (≤9%) ≥", value=70.0, step=1.0)

if not file:
    st.info("Tip: you can test with app/sample_data/patients_sample.csv")
    st.stop()

df = pd.read_csv(file)

# Normalize
for col in ["has_htn","has_ascvd","on_statin","has_diabetes"]:
    if col in df.columns: df[col] = df[col].apply(yes)
for col in ["last_bp_systolic","last_bp_diastolic","last_a1c"]:
    if col in df.columns: df[col] = df[col].apply(safe_float)

required = ["patient_id","patient_name","provider","location"]
missing = [c for c in required if c not in df.columns]
if missing:
    st.error(f"Missing required columns: {missing}")
    st.stop()

# ---- Measures (simple, spec-agnostic)
cbp_den = df[df.get("has_htn", False) == True].copy()
cbp_num = cbp_den[(cbp_den["last_bp_systolic"] < 140) & (cbp_den["last_bp_diastolic"] < 90)]
cbp_rate = pct(len(cbp_num), len(cbp_den))

sta_den = df[df.get("has_ascvd", False) == True].copy()
sta_num = sta_den[sta_den.get("on_statin", False) == True]
sta_rate = pct(len(sta_num), len(sta_den))

dm_den = df[(df.get("has_diabetes", False) == True) & (df["last_a1c"].notna())].copy()
dm_good = dm_den[dm_den["last_a1c"] <= 9.0]
dm_good_rate = pct(len(dm_good), len(dm_den))

def status(val, target): return "✅ On Track" if val >= target else "⚠️ Needs Attention"

scorecard = pd.DataFrame([
    {"Measure":"CBP (BP <140/90 among HTN)","Numerator":len(cbp_num),"Denominator":len(cbp_den),"Rate %":round(cbp_rate,1),"Target %":target_cbp,"Status":status(cbp_rate,target_cbp)},
    {"Measure":"Statin (ASCVD on statin)","Numerator":len(sta_num),"Denominator":len(sta_den),"Rate %":round(sta_rate,1),"Target %":target_sta,"Status":status(sta_rate,target_sta)},
    {"Measure":"Diabetes A1c Good Control (≤9%)","Numerator":len(dm_good),"Denominator":len(dm_den),"Rate %":round(dm_good_rate,1),"Target %":target_dm,"Status":status(dm_good_rate,target_dm)},
])

st.subheader("Practice Scorecard")
st.dataframe(scorecard, hide_index=True, use_container_width=True)

# ---- Provider drilldowns
def group_rate(den_df, num_df):
    if den_df.empty: return pd.DataFrame(columns=["Provider","Den","Num","Rate %"])
    g = den_df.groupby("provider").size().rename("Den").to_frame()
    n = num_df.groupby("provider").size().rename("Num").to_frame()
    out = g.join(n, how="left").fillna(0)
    out["Rate %"] = (out["Num"] / out["Den"] * 100).round(1)
    return out.reset_index().rename(columns={"provider":"Provider"}).sort_values("Rate %", ascending=False)

tab1, tab2, tab3 = st.tabs(["CBP","Statin","Diabetes"])
with tab1:
    st.dataframe(group_rate(cbp_den, cbp_num), use_container_width=True, hide_index=True)
with tab2:
    st.dataframe(group_rate(sta_den, sta_num), use_container_width=True, hide_index=True)
with tab3:
    st.dataframe(group_rate(dm_den, dm_good), use_container_width=True, hide_index=True)

# ---- Gap lists + outreach buttons
st.subheader("Gap Lists")

cbp_gaps = cbp_den[~cbp_den["patient_id"].isin(cbp_num["patient_id"])][
    ["patient_id","patient_name","provider","location","last_bp_systolic","last_bp_diastolic","phone","last_visit_date","payer"]
].rename(columns={"last_bp_systolic":"systolic","last_bp_diastolic":"diastolic"})

sta_gaps = sta_den[~sta_den["patient_id"].isin(sta_num["patient_id"])][
    ["patient_id","patient_name","provider","location","on_statin","phone","last_visit_date","payer"]
]

dm_gaps = dm_den[~dm_den["patient_id"].isin(dm_good["patient_id"])][
    ["patient_id","patient_name","provider","location","last_a1c","last_a1c_date","phone","last_visit_date","payer"]
]

def export_button(df_out, label):
    csv = df_out.to_csv(index=False).encode("utf-8")
    st.download_button(label=f"Download {label} (CSV)", data=csv, file_name=f"{label.replace(' ','_').lower()}.csv", mime="text/csv")

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("**CBP (not controlled)**")
    st.dataframe(cbp_gaps, use_container_width=True, hide_index=True)
    if st.button("Send CBP outreach to all", key="send_cbp"):
        count = 0
        for pid in cbp_gaps["patient_id"].tolist():
            if enqueue_outreach(pid, "CBP"): count += 1
        st.success(f"Queued {count} CBP messages to Messaging Center.")
    export_button(cbp_gaps, "CBP_Gap_List")

with col2:
    st.markdown("**Statin (ASCVD not on statin)**")
    st.dataframe(sta_gaps, use_container_width=True, hide_index=True)
    if st.button("Send Statin outreach to all", key="send_sta"):
        count = 0
        for pid in sta_gaps["patient_id"].tolist():
            if enqueue_outreach(pid, "STATIN"): count += 1
        st.success(f"Queued {count} Statin messages.")
    export_button(sta_gaps, "Statin_Gap_List")

with col3:
    st.markdown("**Diabetes (A1c > 9%)**")
    st.dataframe(dm_gaps, use_container_width=True, hide_index=True)
    if st.button("Send Diabetes outreach to all", key="send_dm"):
        count = 0
        for pid in dm_gaps["patient_id"].tolist():
            if enqueue_outreach(pid, "DM_A1C"): count += 1
        st.success(f"Queued {count} Diabetes messages.")
    export_button(dm_gaps, "Diabetes_Gap_List")

st.caption("No PHI in SMS content; patients receive expiring magic links to a secure page.")
