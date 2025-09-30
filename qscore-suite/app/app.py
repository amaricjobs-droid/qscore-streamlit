import streamlit as st
import pandas as pd

def render_brand_header():
    st.markdown(
        "<h1 style='color:#0A3D91;margin-bottom:0;'>Nexa Q-Score Suite</h1>"
        "<div style='color:#64748B;margin-top:4px;'>Population Health • NCQA Aligned • HIPAA+ Secure</div>",
        unsafe_allow_html=True
    )

ROLES = ["Physician", "Nurse Practitioner", "Medical Assistant", "Quality Coordinator", "Administrator"]
EDIT_ROLES = {"Quality Coordinator", "Administrator"}
PAGES = ["Home", "Dashboard", "Upload Data", "Message Patients", "Reports", "Help"]

def can_edit():
    return st.session_state.get("user_role") in EDIT_ROLES

def render_top_nav():
    if "page" not in st.session_state:
        st.session_state.page = "Home"
    cols = st.columns(len(PAGES))
    for i, p in enumerate(PAGES):
        with cols[i]:
            if st.button(p, use_container_width=True):
                st.session_state.page = p
                st.rerun()
    st.markdown("<hr style='margin:8px 0 16px 0; opacity:0.15;'>", unsafe_allow_html=True)

def render_role_gate():
    if "user_role" not in st.session_state:
        st.markdown("### Select your department / role")
        role = st.selectbox("Role", ROLES, index=3)
        c1, c2 = st.columns(2)
        if c1.button("Continue", use_container_width=True):
            st.session_state.user_role = role
            st.rerun()
        if c2.button("Cancel", use_container_width=True):
            st.stop()
        st.stop()

def page_home():
    st.subheader(f"Welcome, {st.session_state.get('user_role','User')}!")

    # Pull current session dataframe if present
    df = st.session_state.get("dataframe")

    # Optional clinic filter
    if df is not None and "clinic" in df.columns:
        clinics = sorted([c for c in df["clinic"].dropna().unique().tolist() if str(c).strip() != ""])
        if clinics:
            selected = st.multiselect("Filter by clinic", clinics, clinics)
            if selected:
                df = df[df["clinic"].isin(selected)]
    else:
        selected = None

    # KPIs
    m = _compute_overview_metrics(df)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Patients", f"{m['total']:,}")
    with c2:
        st.metric("Open Care Gaps", f"{m['open_gaps']:,}")
    with c3:
        st.metric("Compliance Rate", f"{m['compliant_rate']:.1f}%")
    with c4:
        st.metric("Due in 30 Days", f"{m['due_30']:,}")

    st.markdown("---")

    # Trend (real if data provides monthly percentages; otherwise a friendly demo sparkline)
    try:
        import numpy as np
        if df is not None and "date" in df.columns and "compliant" in df.columns:
            tmp = df.copy()
            tmp["date"] = pd.to_datetime(tmp["date"], errors="coerce")
            tmp = tmp.dropna(subset=["date"])
            if len(tmp) > 0:
                grp = tmp.groupby(pd.Grouper(key="date", freq="M"))["compliant"].mean().mul(100.0)
                if grp.dropna().shape[0] >= 2:
                    st.caption("Compliance trend")
                    st.line_chart(grp)
                else:
                    raise ValueError("not enough points")
            else:
                raise ValueError("no dated rows")
        else:
            raise ValueError("no date/compliant")
    except Exception:
        # Demo sparkline so the page never looks empty
        st.caption("Compliance trend (demo)")
        demo = pd.Series([72, 75, 74, 78, 80, 82], index=pd.date_range("2025-01-31", periods=6, freq="M"))
        st.line_chart(demo)

    # Quick actions
    st.markdown("### Quick actions")
    q1, q2, q3 = st.columns(3)
    with q1:
        if st.button("Open Dashboard", use_container_width=True):
            st.session_state.page = "Dashboard"; st.rerun()
    with q2:
        if st.button("Upload Data", use_container_width=True):
            st.session_state.page = "Upload Data"; st.rerun()
    with q3:
        if st.button("Message Patients", use_container_width=True):
            st.session_state.page = "Message Patients"; st.rerun()
def page_dashboard():
    st.subheader("Quality Measures Dashboard")
    df = pd.DataFrame({
        "Measure": ["A1c < 8", "BP < 140/90", "Statin Therapy (SPC)"],
        "Current %": [78.2, 71.5, 83.0],
        "Target %": [80, 75, 85]
    })
    st.dataframe(df, use_container_width=True)

def page_upload():
    st.subheader("Upload Data")
    if can_edit():
        f = st.file_uploader("Upload CSV/Excel", type=["csv","xlsx"])
        if f is not None:
            df = pd.read_csv(f) if f.name.endswith(".csv") else pd.read_excel(f)
            st.dataframe(df.head(25), use_container_width=True)
    else:
        st.warning("Upload restricted to Coordinator/Admin.")

def page_message_patients():
    st.subheader("Message Patients")
    if can_edit():
        st.text_area("Message template", "Hello, please schedule your follow-up.")
        if st.button("Send Messages"):
            st.success("Messages queued (demo).")
    else:
        st.warning("Messaging restricted to Coordinator/Admin.")

def page_reports():
    st.subheader("Reports")
    if can_edit():
        if st.button("Generate Report"):
            st.success("Report generated (demo).")
    else:
        st.info("Reports are view-only for this role.")

def page_help():
    st.subheader("Help & Docs")
    st.write("All roles can view this page.")

def main():
    render_brand_header()
    render_role_gate()
    render_top_nav()
    page = st.session_state.get("page", "Home")
    if page == "Home": page_home()
    elif page == "Dashboard": page_dashboard()
    elif page == "Upload Data": page_upload()
    elif page == "Message Patients": page_message_patients()
    elif page == "Reports": page_reports()
    else: page_help()

if __name__ == "__main__":
    main()


def _compute_overview_metrics(df):
    """Return totals needed for enterprise overview."""
    if df is None or len(df) == 0:
        return dict(total=0, open_gaps=0, compliant_rate=0.0, due_30=0)

    import numpy as np
    total = len(df)

    # Open gaps: treat rows where 'compliant' is False as open
    if "compliant" in df.columns:
        open_gaps = int((~df["compliant"].fillna(False)).sum())
        compliant_rate = float(df["compliant"].fillna(False).mean() * 100.0)
    else:
        open_gaps = 0
        compliant_rate = 0.0

    # Due in next 30 days if 'due_date' exists
    due_30 = 0
    if "due_date" in df.columns:
        s = pd.to_datetime(df["due_date"], errors="coerce")
        now = pd.Timestamp.utcnow().normalize()
        soon = now + pd.Timedelta(days=30)
        due_30 = int(((s >= now) & (s <= soon)).sum())

    return dict(total=total, open_gaps=open_gaps, compliant_rate=compliant_rate, due_30=due_30)
