"""
dashboard.py — Report Automation Dashboard
Manual Refresh Only
"""

import os
import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import datetime

from config import HR_EMPLOYEES, SALES_EMPLOYEES

st.set_page_config(page_title="Report Automation Dashboard", page_icon="📊", layout="wide")

# Dark mode CSS
st.markdown("""
<style>
.stApp { background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%); }
div[data-testid="stMetric"] { background: linear-gradient(135deg, #1e2a3a 0%, #0f172a 100%); border-radius: 12px; padding: 15px; border: 1px solid #334155; }
div[data-testid="stMetric"] label { color: #94a3b8 !important; }
div[data-testid="stMetric"] .stMetricValue { color: #ffffff !important; }
.dashboard-header { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 1.5rem 2rem; border-radius: 16px; margin-bottom: 2rem; border: 1px solid #334155; }
.dashboard-title { font-size: 1.8rem; font-weight: 700; color: #f1f5f9; }
.dashboard-subtitle { color: #94a3b8; }
.section-header { font-size: 1.2rem; font-weight: 600; color: #e2e8f0; margin: 1.5rem 0 1rem 0; border-left: 4px solid #3b82f6; padding-left: 0.8rem; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%); border-right: 1px solid #334155; }
[data-testid="stDataFrame"] { background: #13161c; border-radius: 12px; border: 1px solid #2a2e38; }
.stButton button { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white !important; border-radius: 8px; }
.footer { text-align: center; padding: 1.5rem; margin-top: 2rem; border-top: 1px solid #334155; font-size: 0.7rem; color: #64748b; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=0)
def load_logs() -> pd.DataFrame:
    path = "logs/processing_logs.csv"
    if not os.path.exists(path):
        return pd.DataFrame(columns=[
            "Timestamp", "Status", "Department", "Employee_Name", "Date", "Reason"
        ])
    df = pd.read_csv(path)
    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    return df


def get_stats(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"total": 0, "success": 0, "failed": 0, "rate": 0}

    total = len(df)
    success = len(df[df["Status"] == "SUCCESS"])
    failed = len(df[df["Status"] == "FAILED"])
    rate = (success / total * 100) if total > 0 else 0

    return {"total": total, "success": success, "failed": failed, "rate": round(rate, 1)}


# Sidebar
with st.sidebar:
    st.markdown("## ⚙️ Dashboard Controls")
    st.markdown("---")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.markdown("---")
    st.markdown("### 👥 Employee Registry")
    st.metric("Sales Team", len(SALES_EMPLOYEES))
    st.metric("HR Team", len(HR_EMPLOYEES))
    st.markdown("---")
    st.markdown("### 📅 Schedule Info")
    st.info("Active Window: 2:30 PM - 11:59 PM | Runs every 20 minutes via GitHub Actions")
    st.markdown("---")
    st.caption("📊 Report Automation System | Powered by Gemini AI")

# Main Header
st.markdown("""
<div class="dashboard-header">
    <div class="dashboard-title">📊 Report Automation Dashboard</div>
    <div class="dashboard-subtitle">Real-time monitoring | AI-powered extraction | Google Sheets integration</div>
</div>
""", unsafe_allow_html=True)

df = load_logs()
stats = get_stats(df)

# KPI Cards
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("📧 Total Processed", stats["total"])
with c2:
    st.metric("✅ Success", stats["success"])
with c3:
    st.metric("❌ Failed", stats["failed"])
with c4:
    st.metric("📈 Success Rate", f"{stats['rate']}%")

st.markdown("---")

if df.empty:
    st.info("📭 No data available. Reports will appear here once processed via GitHub Actions.")
    st.stop()

# Recent Reports
st.markdown('<div class="section-header">📨 Recent Activity</div>', unsafe_allow_html=True)
recent = df.sort_values("Timestamp", ascending=False).head(15)
if not recent.empty:
    display = recent[["Timestamp", "Status", "Department", "Employee_Name", "Date", "Reason"]].copy()
    display.columns = ["Time", "Status", "Dept", "Employee", "Report Date", "Reason"]
    display["Time"] = display["Time"].dt.strftime("%d-%b %I:%M:%S %p")
    st.dataframe(display, use_container_width=True, hide_index=True)

st.markdown("---")

# Trend Chart
st.markdown('<div class="section-header">📈 Daily Trend</div>', unsafe_allow_html=True)
trend = df.dropna(subset=["Timestamp"]).assign(Date=lambda d: d["Timestamp"].dt.date).groupby(["Date", "Status"]).size().reset_index(name="Count")
if not trend.empty:
    fig = px.bar(trend, x="Date", y="Count", color="Status", color_discrete_map={"SUCCESS": "#22c55e", "FAILED": "#ef4444"}, text="Count")
    fig.update_layout(height=350, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

# Department Distribution
st.markdown('<div class="section-header">🏢 Department Distribution</div>', unsafe_allow_html=True)
dept_data = df[df["Status"] == "SUCCESS"]["Department"].value_counts().reset_index()
if not dept_data.empty:
    dept_data.columns = ["Department", "Count"]
    fig = px.pie(dept_data, names="Department", values="Count", color="Department", color_discrete_map={"Sales": "#3b82f6", "HR": "#a855f7"}, hole=0.4)
    fig.update_layout(height=320, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

# Top Contributors
st.markdown('<div class="section-header">🏆 Top Contributors</div>', unsafe_allow_html=True)
top_emp = df[df["Status"] == "SUCCESS"]["Employee_Name"].value_counts().head(8).reset_index()
if not top_emp.empty:
    top_emp.columns = ["Employee", "Reports"]
    fig = px.bar(top_emp, x="Reports", y="Employee", orientation="h", color="Reports", color_continuous_scale="blues", text="Reports")
    fig.update_layout(height=320, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

# Failure Analysis
fail_df = df[df["Status"] == "FAILED"]
if not fail_df.empty:
    st.markdown('<div class="section-header">⚠️ Failure Analysis</div>', unsafe_allow_html=True)
    errors = fail_df["Reason"].str[:80].value_counts().head(8).reset_index()
    errors.columns = ["Error", "Count"]
    fig = px.bar(errors, x="Count", y="Error", orientation="h", color="Count", color_continuous_scale="reds", text="Count")
    fig.update_layout(height=280, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.success("✅ No failures recorded")

# Footer
st.markdown("""
<div class="footer">
    ⚡ Report Automation System · Powered by Gemini AI · Automated via GitHub Actions · Emails remain unread
</div>
""", unsafe_allow_html=True)
