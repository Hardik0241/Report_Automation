"""
dashboard.py — Advanced Report Automation Dashboard
Modern | Sleek | Data-Driven | Real-time Monitoring
"""

import os
import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import datetime

from config import HR_EMPLOYEES, SALES_EMPLOYEES

# ────────────────────────────────────────────────────────────────────
# PAGE CONFIGURATION
# ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Advanced Report Automation | Production Monitor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ────────────────────────────────────────────────────────────────────
# CUSTOM CSS - MODERN DARK DESIGN
# ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main container */
    .stApp {
        background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
    }
    
    /* Metric Cards */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e2a3a 0%, #0f172a 100%);
        border-radius: 12px;
        padding: 15px;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        transition: all 0.3s ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-3px);
        border-color: #3b82f6;
        box-shadow: 0 8px 20px rgba(59,130,246,0.15);
    }
    div[data-testid="stMetric"] label {
        color: #94a3b8 !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.5px;
    }
    div[data-testid="stMetric"] .stMetricValue {
        color: #ffffff !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
    }
    
    /* Header styling */
    .dashboard-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        padding: 1.5rem 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        border: 1px solid #334155;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .dashboard-title {
        font-size: 1.8rem;
        font-weight: 700;
        margin-bottom: 0.3rem;
        display: flex;
        align-items: center;
        gap: 12px;
        color: #f1f5f9;
    }
    .dashboard-subtitle {
        font-size: 0.85rem;
        color: #94a3b8;
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
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
        border-right: 1px solid #334155;
    }
    [data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
    [data-testid="stSidebar"] .stMarkdown {
        color: #94a3b8 !important;
    }
    [data-testid="stSidebar"] .stMarkdown h3 {
        color: #e2e8f0 !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
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
        background-color: #064e3b !important;
        border: 1px solid #22c55e !important;
        color: #bbf7d0 !important;
    }
    
    /* Data Table */
    [data-testid="stDataFrame"] {
        background: #13161c;
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #2a2e38;
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
    
    /* Button */
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
        box-shadow: 0 4px 12px rgba(59,130,246,0.3);
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
        color: #e2e8f0 !important;
    }
    .streamlit-expanderContent {
        background: #0f172a !important;
        border-radius: 8px !important;
    }
    
    /* Selectbox */
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
    
    /* Divider */
    hr {
        border-color: #334155 !important;
        margin: 1rem 0 !important;
    }
    
    /* Footer */
    .footer {
        text-align: center;
        padding: 1.5rem;
        margin-top: 2rem;
        border-top: 1px solid #334155;
        font-size: 0.7rem;
        color: #64748b;
    }
</style>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────────────
# DATA LOADING
# ────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_logs() -> pd.DataFrame:
    """Load and cache processing logs"""
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
        return {"total": 0, "success": 0, "failed": 0, "duplicate": 0, "rate": 0, "today_success": 0}
    
    total = len(df)
    success = len(df[df["Status"] == "SUCCESS"])
    failed = len(df[df["Status"] == "FAILED"])
    duplicate = len(df[df["Status"] == "DUPLICATE"])
    rate = (success / total * 100) if total > 0 else 0
    
    today = datetime.now().date()
    today_df = df[df["Timestamp"].dt.date == today] if not df.empty else pd.DataFrame()
    today_success = len(today_df[today_df["Status"] == "SUCCESS"]) if not today_df.empty else 0
    
    return {
        "total": total,
        "success": success,
        "failed": failed,
        "duplicate": duplicate,
        "rate": round(rate, 1),
        "today_success": today_success
    }

# ────────────────────────────────────────────────────────────────────
# SIDEBAR
# ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ System Status")
    st.markdown("---")
    
    st.markdown("### 🟢 System Online")
    st.caption("GitHub Actions Active")
    
    st.markdown("---")
    
    st.markdown("### 📅 Schedule")
    st.info("""
    **Active Window:** 2:30 PM - 11:59 PM  
    **Frequency:** Every 20 minutes  
    **Platform:** GitHub Actions (24/7)
    """)
    
    st.markdown("---")
    
    st.markdown("### 👥 Employee Registry")
    st.metric("Sales Team", len(SALES_EMPLOYEES))
    st.metric("HR Team", len(HR_EMPLOYEES))
    
    st.markdown("---")
    
    st.markdown("### Dashboard Page")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    st.caption("📊 Advanced Report Automation System")
    st.caption("Powered by Google Gemini AI")

# ────────────────────────────────────────────────────────────────────
# MAIN HEADER
# ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="dashboard-header">
    <div class="dashboard-title">
        <span>📊</span> Advanced Report Automation System
    </div>
    <div class="dashboard-subtitle">
        Real-time monitoring | AI-powered data extraction | Automated Google Sheets integration
    </div>
</div>
""", unsafe_allow_html=True)

# Load data
df = load_logs()
stats = get_stats(df)

# ────────────────────────────────────────────────────────────────────
# KPI CARDS
# ────────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.metric("📧 Total Processed", stats["total"])
with c2:
    st.metric("✅ Success", stats["success"])
with c3:
    st.metric("❌ Failed", stats["failed"])
with c4:
    st.metric("🔄 Duplicate", stats["duplicate"])
with c5:
    st.metric("📈 Today's Success", stats["today_success"])

st.markdown("---")

# Empty state
if df.empty:
    st.info("📭 No data available. Reports will appear here once processed via GitHub Actions.")
    st.stop()

# ────────────────────────────────────────────────────────────────────
# SECTION 1: RECENT ACTIVITY
# ────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">📨 Recent Reports (Sender & Time)</div>', unsafe_allow_html=True)

recent = df[df["Status"] == "SUCCESS"].sort_values("Received_Time", ascending=False).head(15)

if not recent.empty:
    display = recent[["Received_Time", "Sender_Name", "Employee_Name", "Department", "Date"]].copy()
    display.columns = ["📅 Received Time", "👤 Sender", "👥 Employee", "🏢 Dept", "📆 Report Date"]
    display["📅 Received Time"] = display["📅 Received Time"].dt.strftime("%d-%b-%Y %I:%M:%S %p")
    
    st.dataframe(display, use_container_width=True, hide_index=True)
else:
    st.info("No recent submissions.")

st.markdown("---")

# ────────────────────────────────────────────────────────────────────
# SECTION 2: TREND & INSIGHTS
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
            color_discrete_map={"SUCCESS": "#22c55e", "FAILED": "#ef4444", "DUPLICATE": "#f59e0b"},
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
    else:
        st.info("Not enough data for trend analysis.")

with col_b:
    st.markdown('<div class="section-header">🏆 Top Contributors</div>', unsafe_allow_html=True)
    
    top_emp = (
        df[df["Status"] == "SUCCESS"]["Employee_Name"]
        .value_counts()
        .head(8)
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
    else:
        st.info("No employee data available.")

# ────────────────────────────────────────────────────────────────────
# SECTION 3: DEPARTMENT PERFORMANCE
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
        hole=0.4,
    )
    fig.update_layout(
        height=300,
        margin=dict(t=10, b=10, l=10, r=10),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.1),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig, use_container_width=True)

# ────────────────────────────────────────────────────────────────────
# SECTION 4: HOURLY SUBMISSION PATTERN
# ────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">⏰ Submission Time Pattern</div>', unsafe_allow_html=True)

if "Received_Time" in df.columns and not df["Received_Time"].isna().all():
    hourly_df = df[df["Status"] == "SUCCESS"].copy()
    hourly_df["Hour"] = hourly_df["Received_Time"].dt.hour
    hourly_counts = hourly_df.groupby(["Hour", "Department"]).size().reset_index(name="Count")

    if not hourly_counts.empty:
        fig_hourly = px.bar(
            hourly_counts,
            x="Hour",
            y="Count",
            color="Department",
            color_discrete_map={"Sales": "#3b82f6", "HR": "#a855f7"},
            barmode="group",
            text="Count"
        )
        fig_hourly.update_layout(
            title="Reports Submitted by Hour",
            title_x=0.5,
            title_font_color="#f1f5f9",
            height=320,
            margin=dict(t=50, b=20, l=20, r=20),
            xaxis_title="Hour of Day (24h format)",
            yaxis_title="Number of Reports",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#e2e8f0"
        )
        fig_hourly.update_xaxes(gridcolor="#334155", tickmode="linear", tick0=0, dtick=2)
        fig_hourly.update_yaxes(gridcolor="#334155")
        fig_hourly.update_traces(textposition="outside", textfont_color="#e2e8f0")
        st.plotly_chart(fig_hourly, use_container_width=True)
    else:
        st.info("Not enough data for hourly analysis.")

# ────────────────────────────────────────────────────────────────────
# SECTION 5: FAILURE ANALYSIS
# ────────────────────────────────────────────────────────────────────
fail_df = df[df["Status"] == "FAILED"]
if not fail_df.empty:
    st.markdown('<div class="section-header">⚠️ Failure Analysis</div>', unsafe_allow_html=True)
    
    col_f1, col_f2 = st.columns([2, 1])

    with col_f1:
        errors = fail_df["Reason"].str[:80].value_counts().head(8).reset_index()
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
            height=280,
            margin=dict(t=20, b=20, l=20, r=20),
            xaxis_title="Occurrences",
            yaxis_title="",
            coloraxis_showscale=False,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

    with col_f2:
        st.metric("Total Failures", len(fail_df))
        st.metric("Unique Errors", len(errors))
        
        with st.expander("📋 Recent Failures"):
            st.dataframe(
                fail_df[["Received_Time", "Sender_Name", "Employee_Name", "Reason"]]
                .head(10)
                .sort_values("Received_Time", ascending=False),
                use_container_width=True,
                hide_index=True
            )
else:
    st.success("✅ No failures recorded. All reports processed successfully!")

# ────────────────────────────────────────────────────────────────────
# SECTION 6: AUDIT LOG
# ────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">📋 Audit Log</div>', unsafe_allow_html=True)

# Filters
f1, f2, f3, f4 = st.columns(4)

with f1:
    status_f = st.multiselect("Status", ["SUCCESS", "FAILED", "DUPLICATE"], default=["SUCCESS", "FAILED", "DUPLICATE"])
with f2:
    dept_f = st.selectbox("Department", ["All"] + sorted(df["Department"].dropna().unique().tolist()))
with f3:
    emp_f = st.selectbox("Employee", ["All"] + sorted(df["Employee_Name"].dropna().unique().tolist()))
with f4:
    date_range = st.date_input("Date Range", value=())

# Apply filters
filtered = df.copy()
if status_f:
    filtered = filtered[filtered["Status"].isin(status_f)]
if dept_f and dept_f != "All":
    filtered = filtered[filtered["Department"] == dept_f]
if emp_f and emp_f != "All":
    filtered = filtered[filtered["Employee_Name"] == emp_f]
if len(date_range) == 2:
    start, end = date_range
    filtered = filtered[
        (filtered["Received_Time"].dt.date >= start) &
        (filtered["Received_Time"].dt.date <= end)
    ]

st.caption(f"📋 Showing {len(filtered)} of {len(df)} entries")

if not filtered.empty:
    log_display = filtered[[
        "Received_Time", "Sender_Name", "Employee_Name", "Department",
        "Date", "Status", "Processing_Time_Sec"
    ]].copy()
    log_display.columns = ["Time", "Sender", "Employee", "Dept", "Report Date", "Status", "Time(s)"]
    log_display["Time"] = log_display["Time"].dt.strftime("%d-%b %H:%M:%S")
    
    st.dataframe(log_display.sort_values("Time", ascending=False), use_container_width=True, hide_index=True)

# ────────────────────────────────────────────────────────────────────
# FOOTER
# ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="footer">
    <span>⚡ Advanced Report Automation System · Powered by Gemini AI · Real-time Processing</span><br>
    <span>Automated via GitHub Actions · Emails remain unread · Calibri 13pt Center formatting</span>
</div>
""", unsafe_allow_html=True)
