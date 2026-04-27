"""
dashboard.py — Advanced Report Automation Dashboard
Modern | Sleek | Data-Driven | Real-time Monitoring
"""

import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime, timedelta

from config import HR_EMPLOYEES, SALES_EMPLOYEES

# ────────────────────────────────────────────────────────────────────
# PAGE CONFIGURATION
# ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Report Automation | Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ────────────────────────────────────────────────────────────────────
# CUSTOM CSS - CLEAN MODERN DARK DESIGN
# ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Hide default Streamlit elements */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Main container */
    .stApp {
        background: #0a0c10;
    }
    
    /* Metric Cards */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1a1d24 0%, #13161c 100%);
        border-radius: 16px;
        padding: 20px 15px;
        border: 1px solid #2a2e38;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        transition: all 0.3s ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-3px);
        border-color: #3b82f6;
        box-shadow: 0 8px 20px rgba(59,130,246,0.15);
    }
    div[data-testid="stMetric"] label {
        color: #8b92a8 !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.5px;
    }
    div[data-testid="stMetric"] .stMetricValue {
        color: #ffffff !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
    }
    
    /* Headers */
    .main-header {
        background: linear-gradient(135deg, #0f1219 0%, #0a0c10 100%);
        padding: 1.5rem 2rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        border: 1px solid #2a2e38;
    }
    .main-title {
        font-size: 1.8rem;
        font-weight: 700;
        background: linear-gradient(135deg, #ffffff 0%, #8b92a8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.3rem;
    }
    .main-subtitle {
        color: #5a6075;
        font-size: 0.85rem;
    }
    
    /* Section Headers */
    .section-header {
        font-size: 1.2rem;
        font-weight: 600;
        color: #e2e8f0;
        margin: 1.5rem 0 1rem 0;
        padding-left: 0.8rem;
        border-left: 4px solid #3b82f6;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f1219 0%, #0a0c10 100%);
        border-right: 1px solid #1f232b;
    }
    [data-testid="stSidebar"] * {
        color: #a0a6b8 !important;
    }
    [data-testid="stSidebar"] .stMarkdown h3 {
        color: #e2e8f0 !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
    }
    
    /* Info Box */
    .stAlert {
        background: linear-gradient(135deg, #1a1d24 0%, #13161c 100%);
        border: 1px solid #2a2e38;
        border-radius: 12px;
        color: #8b92a8 !important;
    }
    
    /* Data Table */
    [data-testid="stDataFrame"] {
        background: #13161c;
        border-radius: 16px;
        overflow: hidden;
        border: 1px solid #2a2e38;
    }
    [data-testid="stDataFrame"] th {
        background: #1a1d24 !important;
        color: #8b92a8 !important;
        font-size: 0.75rem !important;
        font-weight: 600 !important;
    }
    [data-testid="stDataFrame"] td {
        color: #c0c5d4 !important;
        font-size: 0.8rem !important;
    }
    
    /* Buttons */
    .stButton button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white !important;
        border: none;
        border-radius: 10px;
        font-weight: 500;
        transition: all 0.2s;
    }
    .stButton button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(59,130,246,0.3);
    }
    
    /* Download Button */
    .stDownloadButton button {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    }
    
    /* Divider */
    hr {
        border-color: #2a2e38 !important;
        margin: 1rem 0 !important;
    }
    
    /* Footer */
    .footer {
        text-align: center;
        padding: 1.5rem;
        margin-top: 2rem;
        border-top: 1px solid #2a2e38;
        font-size: 0.7rem;
        color: #5a6075;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background: #1a1d24 !important;
        border: 1px solid #2a2e38 !important;
        border-radius: 10px !important;
        color: #c0c5d4 !important;
    }
    .streamlit-expanderContent {
        background: #13161c !important;
    }
    
    /* Selectbox */
    [data-baseweb="select"] {
        background: #1a1d24 !important;
        border-radius: 8px !important;
    }
</style>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────────────
# DATA LOADING
# ────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_logs() -> pd.DataFrame:
    """Load processing logs"""
    path = "logs/processing_logs.csv"
    expected_cols = [
        "Timestamp", "Email_ID", "Email_Subject", "Sender_Email",
        "Sender_Name", "Received_Time", "Status", "Department",
        "Employee_Name", "Date", "Reason", "Processing_Time_Sec"
    ]
    if not os.path.exists(path):
        return pd.DataFrame(columns=expected_cols)
    
    df = pd.read_csv(path)
    for col in expected_cols:
        if col not in df.columns:
            df[col] = pd.NA
    
    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    if "Received_Time" in df.columns:
        df["Received_Time"] = pd.to_datetime(df["Received_Time"], errors="coerce")
    return df

def get_stats(df: pd.DataFrame) -> dict:
    """Get main statistics"""
    if df.empty:
        return {"total": 0, "success": 0, "failed": 0, "rate": 0}
    
    total = len(df)
    success = len(df[df["Status"] == "SUCCESS"])
    failed = len(df[df["Status"] == "FAILED"])
    rate = (success / total * 100) if total > 0 else 0
    
    return {"total": total, "success": success, "failed": failed, "rate": round(rate, 1)}

# ────────────────────────────────────────────────────────────────────
# SIDEBAR
# ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚡ Quick Actions")
    st.markdown("---")
    
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 📊 Overview")
    st.markdown(f"**Sales Team:** {len(SALES_EMPLOYEES)} members")
    st.markdown(f"**HR Team:** {len(HR_EMPLOYEES)} members")
    
    st.markdown("---")
    st.markdown("### ⏰ Schedule")
    st.markdown("""
    - **Window:** 2:30 PM - 11:59 PM
    - **Frequency:** Every 20 min
    - **Platform:** GitHub Actions
    """)
    
    st.markdown("---")
    st.markdown("### ✅ Features")
    st.markdown("""
    - 🤖 AI-powered extraction
    - 📧 Auto email processing
    - 📊 Real-time monitoring
    - 🔒 Emails stay unread
    """)

# ────────────────────────────────────────────────────────────────────
# MAIN HEADER
# ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <div class="main-title">⌘ Report Automation Dashboard</div>
    <div class="main-subtitle">AI-powered email processing · Google Sheets integration · Real-time analytics</div>
</div>
""", unsafe_allow_html=True)

# Load data
df = load_logs()
stats = get_stats(df)

# ────────────────────────────────────────────────────────────────────
# KPI CARDS
# ────────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("📧 Total Reports", stats["total"])
with c2:
    st.metric("✅ Successful", stats["success"])
with c3:
    st.metric("❌ Failed", stats["failed"])
with c4:
    st.metric("📈 Success Rate", f"{stats['rate']}%")

st.markdown("---")

# Empty state
if df.empty:
    st.info("📭 No data available. Reports will appear here once processed via GitHub Actions.")
    st.stop()

# ────────────────────────────────────────────────────────────────────
# RECENT ACTIVITY
# ────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">📨 Recent Submissions</div>', unsafe_allow_html=True)

recent = df[df["Status"] == "SUCCESS"].sort_values("Received_Time", ascending=False).head(10)

if not recent.empty:
    display = recent[["Received_Time", "Sender_Name", "Employee_Name", "Department"]].copy()
    display.columns = ["Time", "Sender", "Employee", "Dept"]
    display["Time"] = display["Time"].dt.strftime("%d %b %H:%M")
    
    st.dataframe(display, use_container_width=True, hide_index=True)
else:
    st.info("No recent submissions.")

# ────────────────────────────────────────────────────────────────────
# TREND & INSIGHTS
# ────────────────────────────────────────────────────────────────────
col_a, col_b = st.columns(2)

with col_a:
    st.markdown('<div class="section-header">📈 Daily Trend</div>', unsafe_allow_html=True)
    
    trend = (
        df.dropna(subset=["Timestamp"])
        .assign(Date=lambda d: d["Timestamp"].dt.date)
        .groupby(["Date", "Status"])
        .size()
        .reset_index(name="Count")
    )
    
    if not trend.empty:
        fig = px.bar(
            trend,
            x="Date",
            y="Count",
            color="Status",
            color_discrete_map={"SUCCESS": "#22c55e", "FAILED": "#ef4444"},
            text="Count"
        )
        fig.update_layout(
            height=320,
            margin=dict(t=20, b=20, l=20, r=20),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="top", y=-0.1),
        )
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

with col_b:
    st.markdown('<div class="section-header">🏆 Top Contributors</div>', unsafe_allow_html=True)
    
    top_emp = (
        df[df["Status"] == "SUCCESS"]["Employee_Name"]
        .value_counts()
        .head(6)
        .reset_index()
    )
    top_emp.columns = ["Employee", "Reports"]
    
    if not top_emp.empty:
        fig = px.bar(
            top_emp,
            x="Reports",
            y="Employee",
            orientation="h",
            color="Reports",
            color_continuous_scale="blues",
            text="Reports"
        )
        fig.update_layout(
            height=320,
            margin=dict(t=20, b=20, l=20, r=20),
            xaxis_title="",
            yaxis_title="",
            coloraxis_showscale=False,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

# ────────────────────────────────────────────────────────────────────
# DEPARTMENT BREAKDOWN
# ────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">🏢 Department Performance</div>', unsafe_allow_html=True)

dept_data = df[df["Status"] == "SUCCESS"]["Department"].value_counts().reset_index()
if not dept_data.empty:
    dept_data.columns = ["Department", "Count"]
    
    fig = px.pie(
        dept_data,
        names="Department",
        values="Count",
        color="Department",
        color_discrete_map={"Sales": "#3b82f6", "HR": "#a855f7"},
        hole=0.5,
    )
    fig.update_layout(
        height=280,
        margin=dict(t=0, b=0, l=0, r=0),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.1),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

# ────────────────────────────────────────────────────────────────────
# FAILURE ANALYSIS (if any)
# ────────────────────────────────────────────────────────────────────
fail_df = df[df["Status"] == "FAILED"]
if not fail_df.empty:
    st.markdown('<div class="section-header">⚠️ Failure Insights</div>', unsafe_allow_html=True)
    
    errors = fail_df["Reason"].str[:60].value_counts().head(5).reset_index()
    errors.columns = ["Error", "Count"]
    
    fig = px.bar(
        errors,
        x="Count",
        y="Error",
        orientation="h",
        color="Count",
        color_continuous_scale="reds",
        text="Count"
    )
    fig.update_layout(
        height=220,
        margin=dict(t=10, b=10, l=10, r=10),
        xaxis_title="",
        yaxis_title="",
        coloraxis_showscale=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

# ────────────────────────────────────────────────────────────────────
# AUDIT LOG
# ────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">📋 Audit Log</div>', unsafe_allow_html=True)

# Simple filters
f1, f2, f3 = st.columns(3)

with f1:
    status_f = st.multiselect("Status", ["SUCCESS", "FAILED"], default=["SUCCESS", "FAILED"])
with f2:
    dept_f = st.selectbox("Department", ["All"] + sorted(df["Department"].dropna().unique().tolist()))
with f3:
    emp_f = st.selectbox("Employee", ["All"] + sorted(df["Employee_Name"].dropna().unique().tolist()))

# Apply filters
filtered = df.copy()
if status_f:
    filtered = filtered[filtered["Status"].isin(status_f)]
if dept_f and dept_f != "All":
    filtered = filtered[filtered["Department"] == dept_f]
if emp_f and emp_f != "All":
    filtered = filtered[filtered["Employee_Name"] == emp_f]

st.caption(f"📋 Showing {len(filtered)} of {len(df)} entries")

if not filtered.empty:
    log_display = filtered[[
        "Received_Time", "Sender_Name", "Employee_Name", "Department",
        "Status", "Processing_Time_Sec"
    ]].copy()
    log_display.columns = ["Time", "Sender", "Employee", "Dept", "Status", "Time(s)"]
    log_display["Time"] = log_display["Time"].dt.strftime("%d %b %H:%M:%S")
    
    st.dataframe(log_display.sort_values("Time", ascending=False), use_container_width=True, hide_index=True)
    
    # Export
    csv = filtered.to_csv(index=False).encode()
    st.download_button("📥 Export CSV", csv, f"report_log_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", "text/csv", use_container_width=True)

# ────────────────────────────────────────────────────────────────────
# FOOTER
# ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="footer">
    <span>⚡ Advanced Report Automation System · Powered by Gemini AI · Real-time Processing</span>
</div>
""", unsafe_allow_html=True)
