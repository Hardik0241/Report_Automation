"""
dashboard.py — Modern Production Dashboard for Report Automation System
Design: Corporate | Clean | Data-Driven | Real-time
"""

import os
import time
import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import datetime, timedelta

from config import HR_EMPLOYEES, SALES_EMPLOYEES

# ────────────────────────────────────────────────────────────────────
# PAGE CONFIGURATION
# ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Report Automation Dashboard | Production Monitor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ────────────────────────────────────────────────────────────────────
# CUSTOM CSS - DARK MODERN DESIGN WITH VISIBLE TEXT
# ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main container styling */
    .stApp {
        background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
    }
    
    /* Metric card styling - DARK BACKGROUND WITH WHITE TEXT */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e2a3a 0%, #0f172a 100%);
        border-radius: 12px;
        padding: 15px;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.4);
    }
    div[data-testid="stMetric"] label {
        color: #94a3b8 !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
    }
    div[data-testid="stMetric"] .stMetricValue {
        color: #f1f5f9 !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
    }
    div[data-testid="stMetric"] .stMetricDelta {
        color: #22c55e !important;
    }
    
    /* Header styling */
    .dashboard-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        padding: 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        border: 1px solid #334155;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .dashboard-title {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
        gap: 12px;
        color: #f1f5f9;
    }
    .dashboard-subtitle {
        font-size: 0.9rem;
        color: #94a3b8;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
        border-right: 1px solid #334155;
    }
    [data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
    [data-testid="stSidebar"] .stMarkdown {
        color: #94a3b8 !important;
    }
    [data-testid="stSidebar"] .stMetric label {
        color: #64748b !important;
    }
    
    /* Section headers */
    .section-header {
        font-size: 1.4rem;
        font-weight: 600;
        margin: 1.5rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 3px solid #3b82f6;
        display: inline-block;
        color: #f1f5f9;
    }
    
    /* Info box styling */
    .stAlert {
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        color: #cbd5e1 !important;
    }
    
    /* Data table styling */
    [data-testid="stDataFrame"] {
        background-color: #1e293b !important;
        border-radius: 12px;
        overflow: hidden;
    }
    [data-testid="stDataFrame"] table {
        color: #e2e8f0 !important;
    }
    [data-testid="stDataFrame"] th {
        background-color: #0f172a !important;
        color: #94a3b8 !important;
    }
    
    /* Success message */
    .stSuccess {
        background-color: #064e3b !important;
        border: 1px solid #22c55e !important;
        color: #bbf7d0 !important;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
        color: #e2e8f0 !important;
    }
    .streamlit-expanderContent {
        background-color: #0f172a !important;
        border-radius: 8px !important;
    }
    
    /* Button styling */
    .stButton button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white !important;
        border: none;
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s;
    }
    .stButton button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(59,130,246,0.4);
    }
    
    /* Download button */
    .stDownloadButton button {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    }
    
    /* Footer */
    .footer {
        text-align: center;
        padding: 2rem;
        margin-top: 2rem;
        border-top: 1px solid #334155;
        font-size: 0.8rem;
        color: #64748b;
    }
    
    /* Selectbox styling */
    .stSelectbox label, .stMultiSelect label {
        color: #94a3b8 !important;
    }
    .stSelectbox div, .stMultiSelect div {
        background-color: #1e293b !important;
        color: #e2e8f0 !important;
        border-color: #334155 !important;
    }
    
    /* Date input */
    .stDateInput label {
        color: #94a3b8 !important;
    }
    .stDateInput input {
        background-color: #1e293b !important;
        color: #e2e8f0 !important;
        border-color: #334155 !important;
    }
</style>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────────────
# DATA LOADING
# ────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def load_logs() -> pd.DataFrame:
    """Load and cache processing logs"""
    path = "logs/processing_logs.csv"
    if not os.path.exists(path):
        return pd.DataFrame(columns=[
            "Timestamp", "Email_ID", "Email_Subject", "Status",
            "Department", "Employee_Name", "Date", "Reason", "Processing_Time_Sec"
        ])
    df = pd.read_csv(path)
    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    if "Email_Preview" in df.columns and "Email_Subject" not in df.columns:
        df = df.rename(columns={"Email_Preview": "Email_Subject"})
    return df

def get_realtime_stats(df: pd.DataFrame) -> dict:
    """Calculate real-time statistics with safe defaults"""
    if df.empty:
        return {
            "total": 0, "success": 0, "failed": 0, "duplicate": 0,
            "rate": 0, "last_24h_success": 0, "today_success": 0
        }
    
    total = len(df)
    success = len(df[df["Status"] == "SUCCESS"])
    failed = len(df[df["Status"] == "FAILED"])
    duplicate = len(df[df["Status"] == "DUPLICATE"])
    rate = (success / total * 100) if total > 0 else 0
    
    # Last 24 hours stats - SAFE CHECK
    if not df.empty and "Timestamp" in df.columns:
        last_24h = df[df["Timestamp"] > datetime.now() - timedelta(hours=24)]
        last_24h_success = len(last_24h[last_24h["Status"] == "SUCCESS"]) if not last_24h.empty else 0
        
        # Today's stats
        today = datetime.now().date()
        today_df = df[df["Timestamp"].dt.date == today] if not df.empty else pd.DataFrame()
        today_success = len(today_df[today_df["Status"] == "SUCCESS"]) if not today_df.empty else 0
    else:
        last_24h_success = 0
        today_success = 0
    
    return {
        "total": total,
        "success": success,
        "failed": failed,
        "duplicate": duplicate,
        "rate": round(rate, 1),
        "last_24h_success": last_24h_success,
        "today_success": today_success
    }

# ────────────────────────────────────────────────────────────────────
# SIDEBAR - STATUS & INFO
# ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ System Status")
    st.markdown("---")
    
    # System health indicator
    st.markdown("### 🟢 System Online")
    st.caption("GitHub Actions Active")
    
    st.markdown("---")
    
    # Schedule info
    st.markdown("### 📅 Schedule")
    st.info("""
    **Active Window:** 2:30 PM - 11:59 PM  
    **Frequency:** Every 20 minutes  
    **Platform:** GitHub Actions (24/7)
    """)
    
    st.markdown("---")
    
    # Employee counts
    st.markdown("### 👥 Employee Registry")
    st.metric("Sales Team", len(SALES_EMPLOYEES))
    st.metric("HR Team", len(HR_EMPLOYEES))
    
    st.markdown("---")
    
    # Last update
    st.markdown("### 🔄 Dashboard")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    auto_refresh = st.checkbox("Auto-refresh (30s)", value=True)
    
    st.markdown("---")
    st.caption("📊 Report Automation System v2.0")
    st.caption("Powered by Google Gemini AI")

# ────────────────────────────────────────────────────────────────────
# MAIN DASHBOARD HEADER
# ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="dashboard-header">
    <div class="dashboard-title">
        <span>📊</span> Daily Report Automation Dashboard
    </div>
    <div class="dashboard-subtitle">
        Real-time monitoring | AI-powered data extraction | Automated Google Sheets integration
    </div>
</div>
""", unsafe_allow_html=True)

# Load data
df = load_logs()
stats = get_realtime_stats(df)

# ────────────────────────────────────────────────────────────────────
# KPI CARDS - MODERN METRICS WITH VISIBLE TEXT
# ────────────────────────────────────────────────────────────────────
col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.metric("📧 Total Processed", stats["total"])
with col2:
    st.metric("✅ Success", stats["success"])
with col3:
    st.metric("❌ Failed", stats["failed"])
with col4:
    st.metric("🔄 Duplicate", stats["duplicate"])
with col5:
    st.metric("📈 Today's Success", stats["today_success"])
with col6:
    st.metric("⏱️ Last 24h", stats["last_24h_success"])

st.markdown("---")

# If no data, show empty state
if df.empty:
    st.info("""
    ### 📭 No Data Available
    
    The system is waiting for reports to be submitted. 
    - Reports are processed automatically via GitHub Actions
    - First run will populate data here
    - Check back after 2:30 PM for today's reports
    """)
    st.stop()

# ────────────────────────────────────────────────────────────────────
# SECTION 1: TREND ANALYSIS
# ────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">📈 Processing Trend Analysis</div>', unsafe_allow_html=True)

if "Timestamp" in df.columns and not df["Timestamp"].isna().all():
    trend_df = (
        df.dropna(subset=["Timestamp"])
        .assign(Date=lambda d: d["Timestamp"].dt.date)
        .groupby(["Date", "Status"])
        .size()
        .reset_index(name="Count")
    )
    
    if not trend_df.empty:
        fig = px.line(
            trend_df,
            x="Date",
            y="Count",
            color="Status",
            color_discrete_map={"SUCCESS": "#22c55e", "FAILED": "#ef4444", "DUPLICATE": "#f59e0b"},
            markers=True,
            line_shape="spline"
        )
        fig.update_layout(
            title="Daily Processing Volume",
            title_x=0.5,
            title_font_color="#f1f5f9",
            margin=dict(t=50, b=20, l=20, r=20),
            height=350,
            hovermode="x unified",
            plot_bgcolor="#0f172a",
            paper_bgcolor="#0f172a",
            font_color="#e2e8f0"
        )
        fig.update_xaxes(gridcolor="#334155", tickcolor="#334155")
        fig.update_yaxes(gridcolor="#334155", tickcolor="#334155")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Not enough data for trend analysis yet.")

# ────────────────────────────────────────────────────────────────────
# SECTION 2: DEPARTMENT & EMPLOYEE INSIGHTS
# ────────────────────────────────────────────────────────────────────
col_left, col_right = st.columns(2, gap="large")

with col_left:
    st.markdown('<div class="section-header">🏢 Department Distribution</div>', unsafe_allow_html=True)
    dept_df = df[df["Status"] == "SUCCESS"]["Department"].value_counts().reset_index()
    if not dept_df.empty:
        dept_df.columns = ["Department", "Count"]
        
        fig2 = px.pie(
            dept_df,
            names="Department",
            values="Count",
            color="Department",
            color_discrete_map={"Sales": "#3b82f6", "HR": "#a855f7"},
            hole=0.4,
        )
        fig2.update_layout(
            height=320,
            margin=dict(t=20, b=20, l=20, r=20),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
            plot_bgcolor="#0f172a",
            paper_bgcolor="#0f172a",
            font_color="#e2e8f0"
        )
        fig2.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No department data available.")

with col_right:
    st.markdown('<div class="section-header">🏆 Top Performing Employees</div>', unsafe_allow_html=True)
    emp_df = (
        df[df["Status"] == "SUCCESS"]["Employee_Name"]
        .value_counts()
        .head(8)
        .reset_index()
    )
    if not emp_df.empty:
        emp_df.columns = ["Employee", "Reports"]
        
        fig3 = px.bar(
            emp_df,
            x="Reports",
            y="Employee",
            orientation="h",
            color="Reports",
            color_continuous_scale="greens",
            text="Reports"
        )
        fig3.update_layout(
            height=320,
            margin=dict(t=20, b=20, l=20, r=20),
            xaxis_title="Successful Reports",
            yaxis_title="",
            coloraxis_showscale=False,
            plot_bgcolor="#0f172a",
            paper_bgcolor="#0f172a",
            font_color="#e2e8f0"
        )
        fig3.update_xaxes(gridcolor="#334155")
        fig3.update_traces(textposition="outside", textfont_color="#e2e8f0")
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("No employee data available yet.")

# ────────────────────────────────────────────────────────────────────
# SECTION 3: FAILURE ANALYSIS
# ────────────────────────────────────────────────────────────────────
fail_df = df[df["Status"] == "FAILED"]
if not fail_df.empty:
    st.markdown('<div class="section-header">⚠️ Failure Analysis</div>', unsafe_allow_html=True)
    
    col_f1, col_f2 = st.columns([2, 1])
    
    with col_f1:
        reason_counts = (
            fail_df["Reason"].str[:80]
            .value_counts()
            .head(8)
            .reset_index()
        )
        if not reason_counts.empty:
            reason_counts.columns = ["Reason", "Count"]
            
            fig4 = px.bar(
                reason_counts,
                x="Count",
                y="Reason",
                orientation="h",
                color="Count",
                color_continuous_scale="reds",
                text="Count"
            )
            fig4.update_layout(
                height=300,
                margin=dict(t=20, b=20, l=20, r=20),
                xaxis_title="Occurrences",
                yaxis_title="",
                coloraxis_showscale=False,
                plot_bgcolor="#0f172a",
                paper_bgcolor="#0f172a",
                font_color="#e2e8f0"
            )
            fig4.update_xaxes(gridcolor="#334155")
            fig4.update_traces(textposition="outside", textfont_color="#e2e8f0")
            st.plotly_chart(fig4, use_container_width=True)
    
    with col_f2:
        st.metric("Total Failures", len(fail_df))
        st.metric("Unique Error Types", len(reason_counts))
        
        with st.expander("📋 Recent Failures"):
            st.dataframe(
                fail_df[["Timestamp", "Employee_Name", "Reason"]]
                .head(10)
                .sort_values("Timestamp", ascending=False),
                use_container_width=True,
                hide_index=True
            )
else:
    st.success("""
    ### ✅ No Failures Recorded
    
    All recent reports have been processed successfully!
    """)

# ────────────────────────────────────────────────────────────────────
# SECTION 4: DETAILED LOG TABLE WITH FILTERS
# ────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">📋 Audit Log</div>', unsafe_allow_html=True)

# Filter row
col_f1, col_f2, col_f3, col_f4 = st.columns(4)

with col_f1:
    status_filter = st.multiselect(
        "Status",
        ["SUCCESS", "FAILED", "DUPLICATE"],
        default=["SUCCESS", "FAILED", "DUPLICATE"],
        key="status_filter"
    )

with col_f2:
    dept_options = ["All"] + sorted(df["Department"].dropna().unique().tolist())
    dept_filter = st.selectbox("Department", dept_options, key="dept_filter")

with col_f3:
    emp_options = ["All"] + sorted(df["Employee_Name"].dropna().unique().tolist())
    emp_filter = st.selectbox("Employee", emp_options, key="emp_filter")

with col_f4:
    date_range = st.date_input("Date Range", value=(), key="date_range")

# Apply filters
filtered = df.copy()
if status_filter:
    filtered = filtered[filtered["Status"].isin(status_filter)]
if dept_filter and dept_filter != "All":
    filtered = filtered[filtered["Department"] == dept_filter]
if emp_filter and emp_filter != "All":
    filtered = filtered[filtered["Employee_Name"] == emp_filter]
if len(date_range) == 2:
    start, end = date_range
    filtered = filtered[
        (filtered["Timestamp"].dt.date >= start) &
        (filtered["Timestamp"].dt.date <= end)
    ]

# Display filtered count
st.caption(f"Showing {len(filtered)} of {len(df)} entries")

# Data table
st.dataframe(
    filtered[[
        "Timestamp", "Status", "Department", "Employee_Name",
        "Date", "Email_Subject", "Reason", "Processing_Time_Sec"
    ]].sort_values("Timestamp", ascending=False),
    use_container_width=True,
    height=400,
    hide_index=True,
    column_config={
        "Status": st.column_config.TextColumn("Status", width="small"),
        "Processing_Time_Sec": st.column_config.NumberColumn("Time (s)", format="%.2f"),
    }
)

# Export button
if not filtered.empty:
    csv_data = filtered.to_csv(index=False).encode()
    st.download_button(
        "📥 Export to CSV",
        csv_data,
        f"report_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        "text/csv",
        use_container_width=True
    )

# ────────────────────────────────────────────────────────────────────
# FOOTER
# ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="footer">
    <strong>Report Automation System</strong> | Powered by Gemini AI | Google Sheets Integration<br>
    Automated processing via GitHub Actions | Emails remain unread | Data written in Calibri 13pt Center
</div>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────────────
# AUTO-REFRESH
# ────────────────────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(30)
    st.cache_data.clear()
    st.rerun()
