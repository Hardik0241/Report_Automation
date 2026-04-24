"""
dashboard.py — Streamlit monitoring dashboard for the Report Automation System.
Run with:  streamlit run dashboard.py
"""

import os
import time
import subprocess
import sys
import pandas as pd
import plotly.express as px
import streamlit as st

from config import HR_EMPLOYEES, SALES_EMPLOYEES

st.set_page_config(
    page_title="Report Automation",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .block-container { padding-top: 1.5rem; }
    .metric-label    { font-size: 0.85rem !important; }
    div[data-testid="stMetric"] > div { border-radius: 8px; padding: 0.5rem; }
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=30)
def load_logs() -> pd.DataFrame:
    path = "logs/processing_logs.csv"
    if not os.path.exists(path):
        return pd.DataFrame(
            columns=[
                "Timestamp",
                "Email_ID",
                "Email_Subject",
                "Status",
                "Department",
                "Employee_Name",
                "Date",
                "Reason",
                "Processing_Time_Sec",
            ]
        )
    df = pd.read_csv(path)
    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")

    if "Email_Preview" in df.columns and "Email_Subject" not in df.columns:
        df = df.rename(columns={"Email_Preview": "Email_Subject"})
    elif "Email_Preview" in df.columns and "Email_Subject" in df.columns:
        df = df.drop(columns=["Email_Preview"])

    return df


with st.sidebar:
    st.title("⚙️ Controls")

    if st.button("🔄 Refresh Dashboard", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    if st.button("🚀 Run processor now", use_container_width=True):
        with st.spinner("Processing emails …"):
            try:
                result = subprocess.run(
                    [sys.executable, "main.py"],
                    capture_output=True,
                    text=True,
                    cwd=os.path.dirname(os.path.abspath(__file__)),
                )

                if result.returncode == 0:
                    st.success("✅ Processor completed successfully!")
                else:
                    st.error(f"❌ Processor failed: {result.stderr}")

                st.cache_data.clear()
                time.sleep(2)
                st.rerun()
            except Exception as exc:
                st.error(f"Error: {exc}")

    st.divider()
    st.caption(f"Sales employees: {len(SALES_EMPLOYEES)}")
    st.caption(f"HR employees:    {len(HR_EMPLOYEES)}")

    auto_refresh = st.checkbox("Auto-refresh (30 seconds)", value=True)


st.title("📊 Daily Report Automation Dashboard")

df = load_logs()

total = len(df)
success = int((df["Status"] == "SUCCESS").sum()) if not df.empty else 0
failed = int((df["Status"] == "FAILED").sum()) if not df.empty else 0
dupes = int((df["Status"] == "DUPLICATE").sum()) if not df.empty else 0
rate = f"{success / total * 100:.1f}%" if total else "—"

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Emails", total)
c2.metric("✅ Success", success)
c3.metric("❌ Failed", failed)
c4.metric("🔁 Duplicate", dupes)
c5.metric("Success Rate", rate)

st.divider()

if df.empty:
    st.info("No logs yet. Click **Run processor now** to start.")
    st.stop()

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
        trend_df,
        x="Date",
        y="Count",
        color="Status",
        color_discrete_map={
            "SUCCESS": "#22c55e",
            "FAILED": "#ef4444",
            "DUPLICATE": "#f59e0b",
        },
        barmode="group",
    )
    fig.update_layout(margin=dict(t=20, b=20), height=280)
    st.plotly_chart(fig, use_container_width=True)

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
        fig2 = px.pie(
            dept_df,
            names="Department",
            values="Count",
            color_discrete_sequence=["#3b82f6", "#a855f7"],
        )
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
            emp_df,
            x="Count",
            y="Employee",
            orientation="h",
            color_discrete_sequence=["#22c55e"],
        )
        fig3.update_layout(
            height=260, margin=dict(t=10, b=10), yaxis=dict(autorange="reversed")
        )
        st.plotly_chart(fig3, use_container_width=True)

st.subheader("❌ Failure Analysis")
fail_df = df[df["Status"] == "FAILED"]
if not fail_df.empty:
    reason_counts = (
        fail_df["Reason"].str[:80]
        .value_counts()
        .head(10)
        .reset_index(name="Count")
    )
    reason_counts.columns = ["Reason", "Count"]
    fig4 = px.bar(
        reason_counts,
        x="Count",
        y="Reason",
        orientation="h",
        color_discrete_sequence=["#ef4444"],
    )
    fig4.update_layout(
        height=240, margin=dict(t=10, b=10), yaxis=dict(autorange="reversed")
    )
    st.plotly_chart(fig4, use_container_width=True)

    with st.expander("Show recent failures"):
        st.dataframe(
            fail_df[
                [
                    "Timestamp",
                    "Department",
                    "Employee_Name",
                    "Date",
                    "Reason",
                ]
            ]
            .sort_values("Timestamp", ascending=False)
            .head(30),
            use_container_width=True,
        )
else:
    st.success("No failures recorded 🎉")

st.divider()

st.subheader("📋 Full Log")

fc1, fc2, fc3 = st.columns(3)
with fc1:
    status_filter = st.multiselect(
        "Status",
        ["SUCCESS", "FAILED", "DUPLICATE"],
        default=["SUCCESS", "FAILED", "DUPLICATE"],
    )
with fc2:
    dept_options = ["All"] + sorted(df["Department"].dropna().unique().tolist())
    dept_filter = st.selectbox("Department", dept_options)
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
        (filtered["Timestamp"].dt.date >= s) & (filtered["Timestamp"].dt.date <= e)
    ]

st.dataframe(
    filtered[
        [
            "Timestamp",
            "Status",
            "Department",
            "Employee_Name",
            "Date",
            "Email_Subject",
            "Reason",
            "Processing_Time_Sec",
        ]
    ]
    .sort_values("Timestamp", ascending=False),
    use_container_width=True,
    height=400,
)

csv_bytes = filtered.to_csv(index=False).encode()
st.download_button("📥 Download CSV", csv_bytes, "report_logs.csv", "text/csv")

if auto_refresh:
    time.sleep(30)
    st.cache_data.clear()
    st.rerun()
