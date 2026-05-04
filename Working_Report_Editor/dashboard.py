"""
dashboard.py — Report Automation Dashboard
Refresh Button clears logs file AND resets dashboard to zero
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


def clear_logs_file():
    """Clear the contents of processing_logs.csv while keeping headers"""
    # Try multiple possible paths
    possible_paths = [
        "logs/processing_logs.csv",                           # Root logs folder
        "Working_Report_Editor/logs/processing_logs.csv",    # Inside Working_Report_Editor
        "../logs/processing_logs.csv",                       # Parent directory
    ]
    
    headers = ["Timestamp", "Email_ID", "Email_Subject", "Sender_Email", 
               "Sender_Name", "Received_Time", "Status", "Department", 
               "Employee_Name", "Date", "Reason", "Processing_Time_Sec"]
    
    cleared = False
    for log_path in possible_paths:
        if os.path.exists(log_path):
            df_empty = pd.DataFrame(columns=headers)
            df_empty.to_csv(log_path, index=False)
            print(f"Cleared: {log_path}")
            cleared = True
    
    return cleared


def find_logs_file():
    """Find the actual logs file path"""
    possible_paths = [
        "logs/processing_logs.csv",
        "Working_Report_Editor/logs/processing_logs.csv",
        "../logs/processing_logs.csv",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None


def load_logs():
    """Load processing logs from CSV file"""
    log_path = find_logs_file()
    
    if log_path is None:
        return pd.DataFrame(columns=[
            "Timestamp", "Status", "Department", "Employee_Name", "Date", "Reason"
        ])
    
    df = pd.read_csv(log_path)
    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    return df


def get_stats(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"total": 0, "success": 0, "failed": 0, "rate": 0, "today_success": 0}

    total = len(df)
    success = len(df[df["Status"] == "SUCCESS"])
    failed = len(df[df["Status"] == "FAILED"])
    rate = (success / total * 100) if total > 0 else 0
    
    today = datetime.now().date()
    if not df.empty and "Timestamp" in df.columns:
        today_df = df[df["Timestamp"].dt.date == today]
        today_success = len(today_df[today_df["Status"] == "SUCCESS"]) if not today_df.empty else 0
    else:
        today_success = 0

    return {"total": total, "success": success, "failed": failed, "rate": round(rate, 1), "today_success": today_success}


# Initialize session state
if "reset_dashboard" not in st.session_state:
    st.session_state.reset_dashboard = False


# Sidebar
with st.sidebar:
    st.markdown("## ⚙️ Dashboard Controls")
    st.markdown("---")
    
    if st.button("🔄 Refresh Data", use_container_width=True):
        # Clear the actual CSV file
        clear_logs_file()
        st.session_state.reset_dashboard = True
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 👥 Employee Registry")
    st.metric("Sales Team", len(SALES_EMPLOYEES))
    st.metric("HR Team", len(HR_EMPLOYEES))
    st.markdown("---")
    st.markdown("### 📅 Schedule Info")
    st.info("⏰ Active Window: 7:00 PM - 11:59 PM | Runs every 30 minutes via GitHub Actions")
    st.markdown("---")
    st.caption("📊 Report Automation System | Powered by Gemini AI")

# Main Header
st.markdown("""
<div class="dashboard-header">
    <div class="dashboard-title">📊 Report Automation Dashboard</div>
    <div class="dashboard-subtitle">Real-time monitoring | AI-powered extraction | Google Sheets integration</div>
</div>
""", unsafe_allow_html=True)

# Check if reset was triggered
if st.session_state.reset_dashboard:
    st.session_state.reset_dashboard = False
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("📧 Total Processed", 0)
    with col2:
        st.metric("✅ Success", 0)
    with col3:
        st.metric("❌ Failed", 0)
    with col4:
        st.metric("📈 Success Rate", "0%")
    with col5:
        st.metric("📅 Today's Success", 0)
    
    st.markdown("---")
    st.success("✅ Dashboard has been reset. The log file has been cleared.")
    st.stop()

# Normal data load
df = load_logs()
stats = get_stats(df)

# Show message if no data
if df.empty:
    st.info("📭 No data available. Reports will appear here automatically after the next scheduled run (7:00 PM - 11:59 PM).")
    st.stop()

# KPI Cards
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("📧 Total Processed", stats["total"])
with c2:
    st.metric("✅ Success", stats["success"])
with c3:
    st.metric("❌ Failed", stats["failed"])
with c4:
    st.metric("📈 Success Rate", f"{stats['rate']}%")
with c5:
    st.metric("📅 Today's Success", stats["today_success"])

st.markdown("---")

# Recent Reports
st.markdown('<div class="section-header">📨 Recent Activity</div>', unsafe_allow_html=True)
recent = df.sort_values("Timestamp", ascending=False).head(15)
if not recent.empty:
    display_cols = ["Timestamp", "Status", "Department", "Employee_Name", "Date", "Reason"]
    available_cols = [col for col in display_cols if col in recent.columns]
    display = recent[available_cols].copy()
    display.columns = ["Time", "Status", "Dept", "Employee", "Report Date", "Reason"][:len(available_cols)]
    if "Time" in display.columns:
        display["Time"] = display["Time"].dt.strftime("%d-%b %I:%M:%S %p")
    st.dataframe(display, use_container_width=True, hide_index=True)

st.markdown("---")

# Trend Chart
st.markdown('<div class="section-header">📈 Daily Trend</div>', unsafe_allow_html=True)
if "Timestamp" in df.columns and not df.empty:
    trend = df.dropna(subset=["Timestamp"]).assign(Date=lambda d: d["Timestamp"].dt.date).groupby(["Date", "Status"]).size().reset_index(name="Count")
    if not trend.empty:
        fig = px.bar(trend, x="Date", y="Count", color="Status", 
                     color_discrete_map={"SUCCESS": "#22c55e", "FAILED": "#ef4444"}, 
                     text="Count")
        fig.update_layout(height=350, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

# Department Distribution
st.markdown('<div class="section-header">🏢 Department Distribution</div>', unsafe_allow_html=True)
if "Department" in df.columns and "Status" in df.columns:
    dept_data = df[df["Status"] == "SUCCESS"]["Department"].value_counts().reset_index()
    if not dept_data.empty:
        dept_data.columns = ["Department", "Count"]
        fig = px.pie(dept_data, names="Department", values="Count", 
                     color="Department", 
                     color_discrete_map={"Sales": "#3b82f6", "HR": "#a855f7"}, 
                     hole=0.4)
        fig.update_layout(height=320, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

# Top Contributors
success_df = df[df["Status"] == "SUCCESS"]
if not success_df.empty:
    st.markdown('<div class="section-header">🏆 Top Contributors</div>', unsafe_allow_html=True)
    top_emp = success_df["Employee_Name"].value_counts().head(8).reset_index()
    if not top_emp.empty:
        top_emp.columns = ["Employee", "Reports"]
        fig = px.bar(top_emp, x="Reports", y="Employee", orientation="h", 
                     color="Reports", color_continuous_scale="blues", text="Reports")
        fig.update_layout(height=320, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

# Failure Analysis
fail_df = df[df["Status"] == "FAILED"]
if not fail_df.empty:
    st.markdown('<div class="section-header">⚠️ Failure Analysis</div>', unsafe_allow_html=True)
    errors = fail_df["Reason"].astype(str).str[:80].value_counts().head(8).reset_index()
    if not errors.empty:
        errors.columns = ["Error", "Count"]
        fig = px.bar(errors, x="Count", y="Error", orientation="h", 
                     color="Count", color_continuous_scale="reds", text="Count")
        fig.update_layout(height=280, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
        with st.expander("📋 Recent Failures"):
            st.dataframe(fail_df[["Timestamp", "Employee_Name", "Reason"]].head(10), 
                        use_container_width=True, hide_index=True)

# Footer
st.markdown("""
<div class="footer">
    ⚡ Report Automation System · Powered by Gemini AI · Automated via GitHub Actions · Emails remain unread
</div>
""", unsafe_allow_html=True)
