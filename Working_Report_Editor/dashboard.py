"""
dashboard.py — Advanced Report Automation Dashboard
Professional | Real-time | Dark Theme | Auto-refresh
"""

import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime, timedelta

from config import HR_EMPLOYEES, SALES_EMPLOYEES

st.set_page_config(
    page_title="Report Automation | Production Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# CUSTOM CSS - PROFESSIONAL DARK THEME
# ============================================================
st.markdown("""
<style>
    /* Main background */
    .stApp {
        background: linear-gradient(135deg, #0a0c10 0%, #141824 100%);
    }
    
    /* Metric Cards */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1a1e2c 0%, #0f1219 100%);
        border-radius: 16px;
        padding: 20px;
        border: 1px solid #2a2f3f;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        transition: all 0.3s ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-3px);
        border-color: #3b82f6;
        box-shadow: 0 8px 20px rgba(59,130,246,0.2);
    }
    div[data-testid="stMetric"] label {
        color: #8b92a8 !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.5px;
    }
    div[data-testid="stMetric"] .stMetricValue {
        color: #ffffff !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
    }
    
    /* Header */
    .dashboard-header {
        background: linear-gradient(135deg, #0f1219 0%, #1a1e2c 100%);
        padding: 1.8rem 2rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        border: 1px solid #2a2f3f;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .dashboard-title {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #ffffff 0%, #8b92a8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.3rem;
    }
    .dashboard-subtitle {
        color: #6b7280;
        font-size: 0.85rem;
    }
    
    /* Section Headers */
    .section-header {
        font-size: 1.3rem;
        font-weight: 600;
        color: #e2e8f0;
        margin: 1.5rem 0 1rem 0;
        padding-left: 0.8rem;
        border-left: 4px solid #3b82f6;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f1219 0%, #0a0c10 100%);
        border-right: 1px solid #2a2f3f;
    }
    [data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
    [data-testid="stSidebar"] .stMarkdown h3 {
        color: #e2e8f0 !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
    }
    
    /* Data Table */
    [data-testid="stDataFrame"] {
        background: #13161c;
        border-radius: 14px;
        overflow: hidden;
        border: 1px solid #2a2f3f;
    }
    [data-testid="stDataFrame"] th {
        background: #1a1e2c !important;
        color: #8b92a8 !important;
        font-size: 0.75rem !important;
        font-weight: 600 !important;
    }
    [data-testid="stDataFrame"] td {
        color: #cbd5e1 !important;
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
        box-shadow: 0 4px 12px rgba(59,130,246,0.4);
    }
    
    /* Divider */
    hr {
        border-color: #2a2f3f !important;
        margin: 1rem 0 !important;
    }
    
    /* Footer */
    .footer {
        text-align: center;
        padding: 1.5rem;
        margin-top: 2rem;
        border-top: 1px solid #2a2f3f;
        font-size: 0.7rem;
        color: #5a6075;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background: #1a1e2c !important;
        border: 1px solid #2a2f3f !important;
        border-radius: 10px !important;
        color: #e2e8f0 !important;
    }
    
    /* Success/Info */
    .stAlert {
        background: linear-gradient(135deg, #1a1e2c 0%, #0f1219 100%);
        border: 1px solid #2a2f3f;
        border-radius: 12px;
        color: #8b92a8 !important;
    }
    .stSuccess {
        background: linear-gradient(135deg, #064e3b 0%, #022c22 100%);
        border: 1px solid #22c55e;
        color: #bbf7d0 !important;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# DATA LOADING FUNCTIONS
# ============================================================
@st.cache_data(ttl=10)
def load_logs() -> pd.DataFrame:
    """Load processing logs from CSV file"""
    path = "logs/processing_logs.csv"
    if not os.path.exists(path):
        return pd.DataFrame(columns=[
            "Timestamp", "Status", "Department", "Employee_Name", "Date", "Reason", "Processing_Time_Sec"
        ])
    df = pd.read_csv(path)
    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    if "Processing_Time_Sec" in df.columns:
        df["Processing_Time_Sec"] = pd.to_numeric(df["Processing_Time_Sec"], errors="coerce")
    return df


def get_stats(df: pd.DataFrame) -> dict:
    """Calculate dashboard statistics"""
    if df.empty:
        return {
            "total": 0, "success": 0, "failed": 0, "duplicate": 0,
            "rate": 0, "today_success": 0, "avg_time": 0
        }
    
    total = len(df)
    success = len(df[df["Status"] == "SUCCESS"])
    failed = len(df[df["Status"] == "FAILED"])
    duplicate = len(df[df["Status"] == "DUPLICATE"])
    rate = (success / total * 100) if total > 0 else 0
    
    # Today's stats
    today = datetime.now().date()
    today_df = df[df["Timestamp"].dt.date == today] if not df.empty else pd.DataFrame()
    today_success = len(today_df[today_df["Status"] == "SUCCESS"]) if not today_df.empty else 0
    
    # Average processing time
    avg_time = df[df["Processing_Time_Sec"] > 0]["Processing_Time_Sec"].mean() if not df.empty else 0
    
    return {
        "total": total,
        "success": success,
        "failed": failed,
        "duplicate": duplicate,
        "rate": round(rate, 1),
        "today_success": today_success,
        "avg_time": round(avg_time, 2)
    }


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("## ⚙️ Dashboard Controls")
    st.markdown("---")
    
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 👥 Employee Registry")
    col_s, col_h = st.columns(2)
    with col_s:
        st.metric("Sales", len(SALES_EMPLOYEES))
    with col_h:
        st.metric("HR", len(HR_EMPLOYEES))
    
    st.markdown("---")
    st.markdown("### ⏰ Schedule")
    st.caption("Active Window: 7:00 PM - 11:59 PM")
    st.caption("Frequency: Every 30 minutes")
    st.caption("Platform: GitHub Actions")
    
    st.markdown("---")
    st.markdown("### 📊 System Status")
    st.success("🟢 Online")
    
    st.markdown("---")
    st.caption("⚡ Report Automation System v3.0")
    st.caption("Powered by Google Gemini AI")


# ============================================================
# MAIN HEADER
# ============================================================
st.markdown("""
<div class="dashboard-header">
    <div class="dashboard-title">⌘ Report Automation Dashboard</div>
    <div class="dashboard-subtitle">AI-powered email processing · Real-time monitoring · Google Sheets integration</div>
</div>
""", unsafe_allow_html=True)

# Load data
df = load_logs()
stats = get_stats(df)

# ============================================================
# KPI CARDS
# ============================================================
c1, c2, c3, c4, c5, c6 = st.columns(6)

with c1:
    st.metric("📧 Total", stats["total"])
with c2:
    st.metric("✅ Success", stats["success"])
with c3:
    st.metric("❌ Failed", stats["failed"])
with c4:
    st.metric("🔄 Duplicate", stats["duplicate"])
with c5:
    st.metric("📈 Success Rate", f"{stats['rate']}%")
with c6:
    st.metric("⚡ Today", stats["today_success"])

st.markdown("---")

# Empty state
if df.empty:
    st.info("""
    ### 📭 No Data Available
    
    Reports will appear here once processed via GitHub Actions.
    
    **Next scheduled run:** 7:00 PM IST
    """)
    st.stop()

# ============================================================
# RECENT ACTIVITY
# ============================================================
st.markdown('<div class="section-header">📨 Recent Activity</div>', unsafe_allow_html=True)

recent = df.sort_values("Timestamp", ascending=False).head(20)
if not recent.empty:
    display = recent[["Timestamp", "Status", "Department", "Employee_Name", "Date", "Processing_Time_Sec"]].copy()
    display.columns = ["Time", "Status", "Dept", "Employee", "Report Date", "Time(s)"]
    display["Time"] = display["Time"].dt.strftime("%d-%b %I:%M:%S %p")
    
    # Color-code status
    def color_status(val):
        if val == "SUCCESS":
            return "background-color: #064e3b; color: #bbf7d0; border-radius: 4px; padding: 2px 8px;"
        elif val == "FAILED":
            return "background-color: #7f1d1d; color: #fecaca; border-radius: 4px; padding: 2px 8px;"
        return ""
    
    st.dataframe(display, use_container_width=True, hide_index=True)

st.markdown("---")

# ============================================================
# TWO COLUMN CHARTS
# ============================================================
col_left, col_right = st.columns(2)

with col_left:
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
        )
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.markdown('<div class="section-header">🥧 Department Distribution</div>', unsafe_allow_html=True)
    dept_data = df[df["Status"] == "SUCCESS"]["Department"].value_counts().reset_index()
    if not dept_data.empty:
        dept_data.columns = ["Department", "Count"]
        fig = px.pie(
            dept_data, names="Department", values="Count",
            color="Department", color_discrete_map={"Sales": "#3b82f6", "HR": "#a855f7"},
            hole=0.4
        )
        fig.update_layout(height=350, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

# ============================================================
# TOP PERFORMERS & HOURLY PATTERN
# ============================================================
col_a, col_b = st.columns(2)

with col_a:
    st.markdown('<div class="section-header">🏆 Top Performers</div>', unsafe_allow_html=True)
    top_emp = df[df["Status"] == "SUCCESS"]["Employee_Name"].value_counts().head(8).reset_index()
    if not top_emp.empty:
        top_emp.columns = ["Employee", "Reports"]
        fig = px.bar(
            top_emp, x="Reports", y="Employee", orientation="h",
            color="Reports", color_continuous_scale="teal", text="Reports"
        )
        fig.update_layout(height=350, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

with col_b:
    st.markdown('<div class="section-header">⏰ Hourly Activity</div>', unsafe_allow_html=True)
    if "Timestamp" in df.columns:
        df["Hour"] = df["Timestamp"].dt.hour
        hourly = df[df["Status"] == "SUCCESS"].groupby("Hour").size().reset_index(name="Count")
        if not hourly.empty:
            fig = px.line(
                hourly, x="Hour", y="Count", markers=True,
                line_shape="spline", title="Reports Processed by Hour"
            )
            fig.update_layout(height=350, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
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
        fig.update_layout(height=300, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("📋 Recent Failures"):
            st.dataframe(
                fail_df[["Timestamp", "Department", "Employee_Name", "Reason"]].head(10),
                use_container_width=True, hide_index=True
            )

# ============================================================
# FOOTER
# ============================================================
st.markdown("""
<div class="footer">
    <strong>Report Automation System v3.0</strong> · Powered by Gemini AI · Google Sheets Integration<br>
    Automated via GitHub Actions · Emails remain unread · Real-time processing
</div>
""", unsafe_allow_html=True)
