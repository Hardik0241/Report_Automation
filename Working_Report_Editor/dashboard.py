"""
dashboard.py — Report Automation Dashboard
Manual Refresh Only | Data Persists | Hover Effects | Glowing Animations
"""

import os
import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import datetime

from config import HR_EMPLOYEES, SALES_EMPLOYEES

st.set_page_config(page_title="Report Automation Dashboard", page_icon="📊", layout="wide")

# ============================================================
# ADVANCED CSS WITH HOVER EFFECTS & GLOWING ANIMATIONS
# ============================================================
st.markdown("""
<style>
    /* Main background */
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
    
    /* Specific glowing colors for different cards */
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
    
    /* Header styling with gradient animation */
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
    
    /* Refresh Button - Glowing effect */
    .stButton button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white !important;
        border: none;
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.3s ease;
        animation: none;
    }
    
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 0 20px rgba(59,130,246,0.8), 0 4px 12px rgba(0,0,0,0.2);
        animation: pulse 1.5s infinite;
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
    
    /* Expander */
    .streamlit-expanderHeader {
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
        color: #e2e8f0 !important;
        transition: all 0.2s;
    }
    
    .streamlit-expanderHeader:hover {
        border-color: #3b82f6 !important;
        background: #2a3a4a !important;
    }
    
    /* Selectbox */
    .stSelectbox label, .stMultiSelect label {
        color: #94a3b8 !important;
    }
    
    /* Success Rate Special Card */
    div[data-testid="stMetric"]:nth-child(5):hover {
        border-color: #f59e0b;
        box-shadow: 0 8px 25px rgba(245,158,11,0.4), 0 0 15px rgba(245,158,11,0.3);
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# DATA LOADING - NO CACHE FOR FRESH DATA
# ============================================================
def load_logs():
    """Load processing logs from CSV file - fresh read each time"""
    path = "logs/processing_logs.csv"
    if not os.path.exists(path):
        return pd.DataFrame(columns=[
            "Timestamp", "Status", "Department", "Employee_Name", "Date", "Reason", "Processing_Time_Sec"
        ])
    df = pd.read_csv(path)
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
    today_df = df[df["Timestamp"].dt.date == today] if not df.empty else pd.DataFrame()
    today_success = len(today_df[today_df["Status"] == "SUCCESS"]) if not today_df.empty else 0

    return {"total": total, "success": success, "failed": failed, "rate": round(rate, 1), "today_success": today_success}


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("## ⚙️ Dashboard Controls")
    st.markdown("---")
    
    # Refresh Button with glow effect
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 👥 Employee Registry")
    st.metric("Sales Team", len(SALES_EMPLOYEES))
    st.metric("HR Team", len(HR_EMPLOYEES))
    st.markdown("---")
    st.markdown("### 📅 Schedule Info")
    st.info("Active Window: 7:00 PM - 11:59 PM | Runs every 30 minutes via GitHub Actions")
    st.markdown("---")
    st.caption("📊 Report Automation System | Powered by Gemini AI")


# ============================================================
# MAIN HEADER
# ============================================================
st.markdown("""
<div class="dashboard-header">
    <div class="dashboard-title">📊 Report Automation Dashboard</div>
    <div class="dashboard-subtitle">Real-time monitoring | AI-powered extraction | Google Sheets integration</div>
</div>
""", unsafe_allow_html=True)

# Load data
df = load_logs()
stats = get_stats(df)

# ============================================================
# KPI CARDS - 5 Cards
# ============================================================
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

# Empty state
if df.empty:
    st.info("📭 No data available. Reports will appear here once processed via GitHub Actions.")
    st.stop()

# ============================================================
# RECENT ACTIVITY
# ============================================================
st.markdown('<div class="section-header">📨 Recent Activity</div>', unsafe_allow_html=True)

recent = df.sort_values("Timestamp", ascending=False).head(15)
if not recent.empty:
    display = recent[["Timestamp", "Status", "Department", "Employee_Name", "Date", "Reason"]].copy()
    display.columns = ["Time", "Status", "Dept", "Employee", "Report Date", "Reason"]
    display["Time"] = display["Time"].dt.strftime("%d-%b %I:%M:%S %p")
    st.dataframe(display, use_container_width=True, hide_index=True)

st.markdown("---")

# ============================================================
# TREND CHART
# ============================================================
st.markdown('<div class="section-header">📈 Daily Trend</div>', unsafe_allow_html=True)

trend = df.dropna(subset=["Timestamp"]).assign(Date=lambda d: d["Timestamp"].dt.date).groupby(["Date", "Status"]).size().reset_index(name="Count")
if not trend.empty:
    fig = px.bar(
        trend, x="Date", y="Count", color="Status",
        color_discrete_map={"SUCCESS": "#22c55e", "FAILED": "#ef4444", "DUPLICATE": "#f59e0b"},
        text="Count"
    )
    fig.update_layout(
        height=350,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="top", y=-0.1),
        hovermode="x unified"
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# TWO COLUMN CHARTS
# ============================================================
col_left, col_right = st.columns(2)

with col_left:
    st.markdown('<div class="section-header">🏢 Department Distribution</div>', unsafe_allow_html=True)
    dept_data = df[df["Status"] == "SUCCESS"]["Department"].value_counts().reset_index()
    if not dept_data.empty:
        dept_data.columns = ["Department", "Count"]
        fig = px.pie(
            dept_data, names="Department", values="Count",
            color="Department", color_discrete_map={"Sales": "#3b82f6", "HR": "#a855f7"},
            hole=0.4
        )
        fig.update_layout(height=320, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.markdown('<div class="section-header">🏆 Top Contributors</div>', unsafe_allow_html=True)
    top_emp = df[df["Status"] == "SUCCESS"]["Employee_Name"].value_counts().head(8).reset_index()
    if not top_emp.empty:
        top_emp.columns = ["Employee", "Reports"]
        fig = px.bar(
            top_emp, x="Reports", y="Employee", orientation="h",
            color="Reports", color_continuous_scale="blues", text="Reports"
        )
        fig.update_layout(height=320, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

# ============================================================
# FAILURE ANALYSIS
# ============================================================
fail_df = df[df["Status"] == "FAILED"]
if not fail_df.empty:
    st.markdown('<div class="section-header">⚠️ Failure Analysis</div>', unsafe_allow_html=True)
    
    errors = fail_df["Reason"].str[:80].value_counts().head(8).reset_index()
    if not errors.empty:
        errors.columns = ["Error", "Count"]
        fig = px.bar(
            errors, x="Count", y="Error", orientation="h",
            color="Count", color_continuous_scale="reds", text="Count"
        )
        fig.update_layout(height=280, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("📋 Recent Failures"):
            st.dataframe(
                fail_df[["Timestamp", "Employee_Name", "Reason"]].head(10),
                use_container_width=True, hide_index=True
            )
else:
    st.success("✅ No failures recorded")

# ============================================================
# FOOTER
# ============================================================
st.markdown("""
<div class="footer">
    ⚡ Report Automation System · Powered by Gemini AI · Automated via GitHub Actions · Emails remain unread
</div>
""", unsafe_allow_html=True)
