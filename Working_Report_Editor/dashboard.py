"""
dashboard.py — Streamlit monitoring dashboard for the Report Automation System.

Run with:  streamlit run dashboard.py
"""

import os

import pandas as pd
import plotly.express as px
import streamlit as st

from config import HR_EMPLOYEES, SALES_EMPLOYEES
from tracker import Tracker

# ─────────────────────────────────────────────
# Page setup
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Report Automation",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""


<style>
    .block-container { padding-top: 1.5rem; }
    .metric-label    { font-size: 0.85rem !important; }
    div[data-testid="stMetric"] > div { border-radius: 8px; padding: 0.5rem; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Data helpers
# ─────────────────────────────────────────────

def load_logs() -> pd.DataFrame:
    """Load logs from CSV. No caching — always fresh on each page load."""
    path = "logs/processing_logs.csv"
    if not os.path.exists(path):
        return pd.DataFrame(columns=[
            "Timestamp", "Email_ID", "Email_Subject", "Status",
            "Department", "Employee_Name", "Date", "Reason",
            "Processing_Time_Sec",
        ])
    df = pd.read_csv(path)
    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    
    # Handle column name change from Email_Preview to Email_Subject
    if "Email_Preview" in df.columns and "Email_Subject" not in df.columns:
        df = df.rename(columns={"Email_Preview": "Email_Subject"})
    elif "Email_Preview" in df.columns and "Email_Subject" in df.columns:
        # If both exist, use Email_Subject and drop Email_Preview
        df = df.drop(columns=["Email_Preview"])
    
    return df


# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Controls")

    if st.button("🔄 Refresh data", use_container_width=True):
        with st.spinner("Clearing data and refreshing …"):
            # Clear logs and cache
            logs_file = "logs/processing_logs.csv"
            cache_file = "logs/duplicate_cache.json"
            
            if os.path.exists(logs_file):
                os.remove(logs_file)
            if os.path.exists(cache_file):
                os.remove(cache_file)
            
            # Clear session state
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            
            st.success("Data cleared! Refreshing dashboard …")
            st.rerun()

    st.divider()

    if st.button("🚀 Run processor now", use_container_width=True):
        with st.spinner("Processing emails …"):
            try:
                # Ensure we're in the correct working directory
                import os
                import sys
                
                # Get the directory where dashboard.py is located
                dashboard_dir = os.path.dirname(os.path.abspath(__file__))
                
                # Change to that directory
                original_dir = os.getcwd()
                os.chdir(dashboard_dir)
                
                # Add the directory to Python path if not already there
                if dashboard_dir not in sys.path:
                    sys.path.insert(0, dashboard_dir)
                
                try:
                    from main import ReportProcessor
                    processor = ReportProcessor()
                    results = processor.run()
                    ok  = sum(1 for r in results if r["status"] == "SUCCESS")
                    bad = sum(1 for r in results if r["status"] == "FAILED")
                    st.success(f"Done — ✅ {ok} success, ❌ {bad} failed")
                    st.rerun()
                finally:
                    # Restore original directory
                    os.chdir(original_dir)
            except Exception as exc:
                st.error(f"Error: {exc}")
                import traceback
                st.error(traceback.format_exc())

    st.divider()
    st.caption(f"Sales employees: {len(SALES_EMPLOYEES)}")
    st.caption(f"HR employees:    {len(HR_EMPLOYEES)}")

    st.caption("📌 Processor runs ONLY when you click 'Run processor now'")
    st.caption("No automatic processing on dashboard startup")

# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

st.title("📊 Daily Report Automation Dashboard")

df = load_logs()

# ── Metrics row ──────────────────────────────
total   = len(df)
success = int((df["Status"] == "SUCCESS").sum())  if not df.empty else 0
failed  = int((df["Status"] == "FAILED").sum())   if not df.empty else 0
dupes   = int((df["Status"] == "DUPLICATE").sum()) if not df.empty else 0
rate    = f"{success / total * 100:.1f}%" if total else "—"

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Emails",  total)
c2.metric("✅ Success",    success)
c3.metric("❌ Failed",     failed)
c4.metric("🔁 Duplicate",  dupes)
c5.metric("Success Rate",  rate)

st.divider()

if df.empty:
    st.info("No logs yet. Click **Run processor now** to start.")
    st.stop()

# ── Trend chart ───────────────────────────────
st.subheader("📈 Processing Trend")

if "Timestamp" in df.columns and not df["Timestamp"].isna().all():
    trend_df = (
        df.dropna(subset=["Timestamp"])
          .assign(Date=lambda d: d["Timestamp"].dt.date)
          .groupby(["Date", "Status"])
          .size()
          .reset_index(name="Count")
    )
    fig = px.bar(
        trend_df, x="Date", y="Count", color="Status",
        color_discrete_map={"SUCCESS": "#22c55e", "FAILED": "#ef4444", "DUPLICATE": "#f59e0b"},
        barmode="group",
    )
    fig.update_layout(margin=dict(t=20, b=20), height=280)
    st.plotly_chart(fig, use_container_width=True)

# ── Department & employee charts ─────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🏢 By Department")
    dept_df = (
        df[df["Status"] == "SUCCESS"]["Department"]
          .value_counts()
          .reset_index(name="Count")
    )
    dept_df.columns = ["Department", "Count"]
    if not dept_df.empty:
        fig2 = px.pie(dept_df, names="Department", values="Count",
                      color_discrete_sequence=["#3b82f6", "#a855f7"])
        fig2.update_layout(height=260, margin=dict(t=10, b=10))
        st.plotly_chart(fig2, use_container_width=True)

with col_right:
    st.subheader("👤 Top Employees (Success)")
    emp_df = (
        df[df["Status"] == "SUCCESS"]["Employee_Name"]
          .value_counts()
          .head(10)
          .reset_index(name="Count")
    )
    emp_df.columns = ["Employee", "Count"]
    if not emp_df.empty:
        fig3 = px.bar(
            emp_df, x="Count", y="Employee", orientation="h",
            color_discrete_sequence=["#22c55e"],
        )
        fig3.update_layout(height=260, margin=dict(t=10, b=10), yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig3, use_container_width=True)

# ── Failure analysis ──────────────────────────
st.subheader("❌ Failure Analysis")
fail_df = df[df["Status"] == "FAILED"]
if not fail_df.empty:
    reason_counts = (
        fail_df["Reason"].str[:80].value_counts().head(10)
          .reset_index(name="Count")
    )
    reason_counts.columns = ["Reason", "Count"]
    fig4 = px.bar(
        reason_counts, x="Count", y="Reason", orientation="h",
        color_discrete_sequence=["#ef4444"],
    )
    fig4.update_layout(height=240, margin=dict(t=10, b=10), yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig4, use_container_width=True)

    with st.expander("Show recent failures"):
        st.dataframe(
            fail_df[["Timestamp", "Department", "Employee_Name", "Date", "Reason"]]
              .sort_values("Timestamp", ascending=False)
              .head(30),
            use_container_width=True,
        )
else:
    st.success("No failures recorded 🎉")

st.divider()

# ── Detailed log table ────────────────────────
st.subheader("📋 Full Log")

# Filters
fc1, fc2, fc3 = st.columns(3)
with fc1:
    status_filter = st.multiselect(
        "Status", ["SUCCESS", "FAILED", "DUPLICATE"],
        default=["SUCCESS", "FAILED", "DUPLICATE"],
    )
with fc2:
    dept_options = ["All"] + sorted(df["Department"].dropna().unique().tolist())
    dept_filter  = st.selectbox("Department", dept_options)
with fc3:
    date_range = st.date_input("Date range", value=())

filtered = df.copy()
if status_filter:
    filtered = filtered[filtered["Status"].isin(status_filter)]
if dept_filter and dept_filter != "All":
    filtered = filtered[filtered["Department"] == dept_filter]
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    s, e = date_range
    filtered = filtered[
        (filtered["Timestamp"].dt.date >= s) &
        (filtered["Timestamp"].dt.date <= e)
    ]

st.dataframe(
    filtered[["Timestamp", "Status", "Department", "Employee_Name",
              "Date", "Email_Subject", "Reason", "Processing_Time_Sec"]]
      .sort_values("Timestamp", ascending=False),
    use_container_width=True,
    height=400,
)

# Download
csv_bytes = filtered.to_csv(index=False).encode()
st.download_button("📥 Download CSV", csv_bytes, "report_logs.csv", "text/csv")
