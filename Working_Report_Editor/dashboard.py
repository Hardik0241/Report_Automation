"""
dashboard.py — Report Automation Dashboard
Refresh Button clears logs file AND resets dashboard to zero
With hover effects, glow animations, and button press effects
UPDATED: Statistics now count unique employees per date (no duplicates)
"""

import os
import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import datetime

from config import HR_EMPLOYEES, SALES_EMPLOYEES

st.set_page_config(page_title="Report Automation Dashboard", page_icon="📊", layout="wide")

# Dark mode CSS with Hover Effects & Glowing Animations
st.markdown("""
<style>
    /* Main container */
    .stApp {
        background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
    }
    
    /* Metric Cards - With Glow Effect on Hover */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e2a3a 0%, #0f172a 100%);
        border-radius: 16px;
        padding: 20px;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
    }
    
    /* Hover Effect - Glow and Lift */
    div[data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        border-color: #3b82f6;
        box-shadow: 0 8px 25px rgba(59,130,246,0.4), 0 0 15px rgba(59,130,246,0.3);
    }
    
    /* Different glowing colors for different cards */
    div[data-testid="stMetric"]:nth-child(2):hover {
        border-color: #3b82f6;
        box-shadow: 0 8px 25px rgba(59,130,246,0.4), 0 0 15px rgba(59,130,246,0.3);
    }
    
    div[data-testid="stMetric"]:nth-child(3):hover {
        border-color: #22c55e;
        box-shadow: 0 8px 25px rgba(34,197,94,0.4), 0 0 15px rgba(34,197,94,0.3);
    }
    
    div[data-testid="stMetric"]:nth-child(4):hover {
        border-color: #ef4444;
        box-shadow: 0 8px 25px rgba(239,68,68,0.4), 0 0 15px rgba(239,68,68,0.3);
    }
    
    div[data-testid="stMetric"]:nth-child(5):hover {
        border-color: #f59e0b;
        box-shadow: 0 8px 25px rgba(245,158,11,0.4), 0 0 15px rgba(245,158,11,0.3);
    }
    
    div[data-testid="stMetric"]:nth-child(6):hover {
        border-color: #8b5cf6;
        box-shadow: 0 8px 25px rgba(139,92,246,0.4), 0 0 15px rgba(139,92,246,0.3);
    }
    
    /* Metric text styling */
    div[data-testid="stMetric"] label {
        color: #94a3b8 !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px;
        transition: color 0.2s;
    }
    
    div[data-testid="stMetric"]:hover label {
        color: #e2e8f0 !important;
    }
    
    div[data-testid="stMetric"] .stMetricValue {
        color: #ffffff !important;
        font-size: 2.2rem !important;
        font-weight: 700 !important;
        transition: all 0.2s;
    }
    
    div[data-testid="stMetric"]:hover .stMetricValue {
        transform: scale(1.05);
        display: inline-block;
    }
    
    /* Header styling with hover effect */
    .dashboard-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        padding: 1.5rem 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        border: 1px solid #334155;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        transition: all 0.3s;
    }
    
    .dashboard-header:hover {
        border-color: #3b82f6;
        box-shadow: 0 8px 25px rgba(59,130,246,0.2);
    }
    
    .dashboard-title {
        font-size: 1.8rem;
        font-weight: 700;
        color: #f1f5f9;
        margin-bottom: 0.3rem;
    }
    
    .dashboard-subtitle {
        color: #94a3b8;
        font-size: 0.85rem;
    }
    
    /* Section Headers with underline animation */
    .section-header {
        font-size: 1.2rem;
        font-weight: 600;
        color: #e2e8f0;
        margin: 1.5rem 0 1rem 0;
        padding-left: 0.8rem;
        border-left: 4px solid #3b82f6;
        transition: all 0.2s;
    }
    
    .section-header:hover {
        border-left-width: 6px;
        padding-left: 1rem;
        color: #ffffff;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
        border-right: 1px solid #334155;
    }
    
    [data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
    
    [data-testid="stSidebar"] .stMarkdown h3 {
        color: #e2e8f0 !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
    }
    
    /* Refresh Button - Glowing effect and press animation */
    .stButton button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white !important;
        border: none;
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.3s ease;
        animation: none;
        width: 100%;
        padding: 0.5rem 1rem;
    }
    
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 0 20px rgba(59,130,246,0.8), 0 4px 12px rgba(0,0,0,0.2);
        animation: pulse 1.5s infinite;
    }
    
    .stButton button:active {
        transform: translateY(2px);
        box-shadow: 0 2px 8px rgba(59,130,246,0.4);
    }
    
    @keyframes pulse {
        0% {
            box-shadow: 0 0 0 0 rgba(59,130,246,0.7);
        }
        70% {
            box-shadow: 0 0 0 10px rgba(59,130,246,0);
        }
        100% {
            box-shadow: 0 0 0 0 rgba(59,130,246,0);
        }
    }
    
    /* Data Table styling with hover effect */
    [data-testid="stDataFrame"] {
        background: #13161c;
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #2a2e38;
        transition: all 0.2s;
    }
    
    [data-testid="stDataFrame"]:hover {
        border-color: #3b82f6;
        box-shadow: 0 4px 12px rgba(59,130,246,0.2);
    }
    
    [data-testid="stDataFrame"] th {
        background: #1a1d24 !important;
        color: #94a3b8 !important;
        font-size: 0.75rem !important;
        font-weight: 600 !important;
    }
    
    [data-testid="stDataFrame"] td {
        color: #cbd5e1 !important;
        font-size: 0.8rem !important;
    }
    
    [data-testid="stDataFrame"] tbody tr:hover {
        background-color: #1e293b !important;
    }
    
    /* Info Box */
    .stAlert {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        color: #94a3b8 !important;
    }
    
    /* Success message */
    .stSuccess {
        background: linear-gradient(135deg, #064e3b 0%, #022c22 100%);
        border: 1px solid #22c55e;
        color: #bbf7d0 !important;
        transition: all 0.2s;
    }
    
    .stSuccess:hover {
        box-shadow: 0 4px 12px rgba(34,197,94,0.3);
    }
    
    /* Footer */
    .footer {
        text-align: center;
        padding: 1.5rem;
        margin-top: 2rem;
        border-top: 1px solid #334155;
        font-size: 0.7rem;
        color: #64748b;
        transition: all 0.2s;
    }
    
    .footer:hover {
        border-top-color: #3b82f6;
    }
    
    /* Divider */
    hr {
        border-color: #334155 !important;
        margin: 1rem 0 !important;
    }
</style>
""", unsafe_allow_html=True)


def clear_logs_file():
    """Clear the contents of processing_logs.csv while keeping headers"""
    possible_paths = [
        "logs/processing_logs.csv",
        "Working_Report_Editor/logs/processing_logs.csv",
        "../logs/processing_logs.csv",
    ]
    
    headers = ["Timestamp", "Email_ID", "Email_Subject", "Sender_Email", 
               "Sender_Name", "Received_Time", "Status", "Department", 
               "Employee_Name", "Date", "Reason", "Processing_Time_Sec"]
    
    cleared = False
    for log_path in possible_paths:
        if os.path.exists(log_path):
            df_empty = pd.DataFrame(columns=headers)
            df_empty.to_csv(log_path, index=False)
            cleared = True
    
    return cleared


def find_logs_file():
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
    log_path = find_logs_file()
    if log_path is None:
        return pd.DataFrame(columns=[
            "Timestamp", "Email_ID", "Status", "Department", "Employee_Name", "Date", "Reason"
        ])
    df = pd.read_csv(log_path)
    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    return df


def get_stats(df: pd.DataFrame) -> dict:
    """Get statistics with unique employee counts (no duplicates per day)"""
    if df.empty:
        return {"total": 0, "success": 0, "failed": 0, "rate": 0, "today_success": 0}

    # Count unique successes (by employee + date) - prevents duplicates
    success_df = df[df["Status"] == "SUCCESS"]
    unique_successes = success_df[["Department", "Employee_Name", "Date"]].drop_duplicates()
    success = len(unique_successes)
    
    failed = len(df[df["Status"] == "FAILED"])
    total = success + failed
    
    rate = (success / total * 100) if total > 0 else 0

    return {"total": total, "success": success, "failed": failed, "rate": round(rate, 1), "today_success": success}


# Initialize session state for reset flag
if "reset_dashboard" not in st.session_state:
    st.session_state.reset_dashboard = False


with st.sidebar:
    st.markdown("## ⚙️ Dashboard Controls")
    st.markdown("---")
    
    if st.button("🔄 Refresh Data", use_container_width=True):
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

if df.empty:
    st.info("📭 No data available. Reports will appear here automatically after the next scheduled run (7:00 PM - 11:59 PM).")
    st.stop()

# KPI Cards - 5 cards
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

st.markdown('<div class="section-header">📨 Recent Activity</div>', unsafe_allow_html=True)
recent = df.sort_values("Timestamp", ascending=False).head(15)

if not recent.empty:
    display = recent[["Timestamp", "Status", "Department", "Employee_Name", "Date", "Reason"]].copy()
    display.columns = ["Time", "Status", "Dept", "Employee", "Report Date", "Reason"]
    display["Time"] = display["Time"].dt.strftime("%d-%b %I:%M:%S %p")
    st.dataframe(display, use_container_width=True, hide_index=True)

st.markdown("---")

st.markdown('<div class="section-header">🏢 Department Distribution</div>', unsafe_allow_html=True)
if "Department" in df.columns and "Status" in df.columns:
    success_df = df[df["Status"] == "SUCCESS"]
    # Use unique successes for pie chart
    unique_successes = success_df[["Department", "Employee_Name", "Date"]].drop_duplicates()
    dept_data = unique_successes["Department"].value_counts().reset_index()
    if not dept_data.empty:
        dept_data.columns = ["Department", "Count"]
        fig = px.pie(dept_data, names="Department", values="Count", 
                     color="Department", 
                     color_discrete_map={"Sales": "#3b82f6", "HR": "#a855f7"}, 
                     hole=0.4)
        fig.update_layout(height=320, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

st.markdown("""
<div class="footer">
    ⚡ Report Automation System · Powered by Gemini AI · Automated via GitHub Actions · Emails remain unread
</div>
""", unsafe_allow_html=True)
