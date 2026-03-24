import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Discovery Dashboard", layout="wide", initial_sidebar_state="expanded")

# --- 🔒 PASSWORD PROTECTION GATE ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 Restricted Access")
    pwd = st.text_input("Please enter the password to view the dashboard:", type="password")
    
    if st.button("Login"):
        if pwd == st.secrets.get("dashboard_password", "hackathon2024"):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password. Please try again.")
    st.stop()

st.title("📊 Discovery Dashboard")

# --- 1. DATA LOADING & CLEANING ---
@st.cache_data(ttl=600)
def load_data():
    try:
        df_wip = pd.read_csv("jira_discovery_data.csv")
        df_wip['Date Entered Status'] = pd.to_datetime(df_wip['Date Entered Status'])
    except FileNotFoundError:
        df_wip = pd.DataFrame()

    try:
        df_lead = pd.read_csv("jira_lead_time_data.csv")
        df_lead['Date Completed'] = pd.to_datetime(df_lead['Date Completed'])
    except FileNotFoundError:
        df_lead = pd.DataFrame()
        
    try:
        df_cfd = pd.read_csv("jira_cfd_data.csv")
        df_cfd['Date'] = pd.to_datetime(df_cfd['Date'])
    except FileNotFoundError:
        df_cfd = pd.DataFrame()

    return df_wip, df_lead, df_cfd

df_wip, df_lead, df_cfd = load_data()

if df_wip.empty and df_lead.empty:
    st.warning("⚠️ No data found. Please run the Python extraction scripts first.")
    st.stop()

# Safety net: Ensure missing custom fields are labeled "Unassigned" and map Projects
for df in [df_wip, df_lead, df_cfd]:
    if not df.empty:
        if 'Roadmap' in df.columns:
            df['Roadmap'] = df['Roadmap'].fillna('Unassigned')
            
        # Extract the project prefix (e.g., "PLD" from "PLD-123") and map it to a friendly name
        if 'Ticket ID' in df.columns:
            df['Project Category'] = df['Ticket ID'].apply(lambda x: str(x).split('-')[0])
            df['Project Category'] = df['Project Category'].map({
                'PLD': 'All Platform (PLD)', 
                'DP': 'All Discovery (DP)'
            }).fillna(df['Project Category']) # Keeps any other prefixes intact just in case

# --- 2. SIDEBAR FILTERS ---
st.sidebar.header("Filter Data")

try:
    mtime = os.path.getmtime("jira_discovery_data.csv")
    last_updated = datetime.fromtimestamp(mtime).strftime('%B %d, %Y at %I:%M %p')
    st.sidebar.caption(f"🕒 **Last Data Refresh:** \n{last_updated}")
except FileNotFoundError:
    st.sidebar.caption("🕒 **Last Data Refresh:** Unknown")

# 1. Grab Project Options
def get_project_options():
    opts = set()
    for df in [df_wip, df_lead]:
        if not df.empty and "Project Category" in df.columns:
            opts.update(df["Project Category"].dropna().unique())
    return ["All"] + sorted(list(opts))

selected_project = st.sidebar.selectbox("Project Category", get_project_options())

# 2. 🚨 THE FIX: Dynamic Cascading Roadmap Options
# This looks at what Project you just selected, and ONLY returns Roadmaps for that Project!
def get_roadmap_options(project_filter):
    opts = set()
    for df in [df_wip, df_lead]:
        if not df.empty and "Roadmap" in df.columns:
            temp_df = df.copy()
            # If a specific project is selected, filter the temporary dataframe first
            if project_filter != "All" and "Project Category" in temp_df.columns:
                temp_df = temp_df[temp_df["Project Category"] == project_filter]
            
            # Now grab whatever Roadmaps are left
            opts.update(temp_df["Roadmap"].dropna().unique())
    return ["All"] + sorted(list(opts))

selected_roadmap = st.sidebar.selectbox("Roadmap", get_roadmap_options(selected_project))

st.sidebar.divider()
st.sidebar.header("⚖️ Compare Periods")
today = datetime.today().date()
p1_default = (today - pd.Timedelta(days=30), today)
p2_default = (today - pd.Timedelta(days=60), today - pd.Timedelta(days=31))
period1 = st.sidebar.date_input("Primary Period (P1)", value=p1_default)
period2 = st.sidebar.date_input("Comparison Period (P2)", value=p2_default)

# --- 3. FILTERING LOGIC ---
def apply_filters(df):
    if df.empty: return df
    filtered = df.copy()
    
    # Filter by Project Category
    if selected_project != "All" and "Project Category" in filtered.columns:
        filtered = filtered[filtered["Project Category"] == selected_project]
        
    # Filter by Roadmap
    if selected_roadmap != "All" and "Roadmap" in filtered.columns:
        filtered = filtered[filtered["Roadmap"] == selected_roadmap]
        
    return filtered

wip_filtered = apply_filters(df_wip)
lead_filtered = apply_filters(df_lead)
cfd_filtered = apply_filters(df_cfd)

# --- DYNAMIC PERIOD COMPARISON ---
if not lead_filtered.empty:
    st.subheader("⚖️ Period-over-Period Performance")
    st.caption("Compare your Primary Period (P1) against your Comparison Period (P2) using the sidebar controls.")
    
    def get_dates(date_input, default_dates):
        if isinstance(date_input, tuple) and len(date_input) == 2:
            return pd.to_datetime(date_input[0]), pd.to_datetime(date_input[1])
        return pd.to_datetime(default_dates[0]), pd.to_datetime(default_dates[1])
        
    p1_start, p1_end = get_dates(period1, p1_default)
    p2_start, p2_end = get_dates(period2, p2_default)
    
    p1_df = lead_filtered[(lead_filtered['Date Completed'] >= p1_start) & (lead_filtered['Date Completed'] <= p1_end)]
    p2_df = lead_filtered[(lead_filtered['Date Completed'] >= p2_start) & (lead_filtered['Date Completed'] <= p2_end)]
    
    p1_throughput, p2_throughput = len(p1_df), len(p2_df)
    p1_avg = p1_df['Lead Time (Days)'].mean() if not p1_df.empty else 0
    p2_avg = p2_df['Lead Time (Days)'].mean() if not p2_df.empty else 0
    p1_85th = p1_df['Lead Time (Days)'].quantile(0.85) if not p1_df.empty else 0
    p2_85th = p2_df['Lead Time (Days)'].quantile(0.85) if not p2_df.empty else 0
    
    # 4. Draw the UI Cards Side-by-Side
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown("**🚀 Throughput (Tickets)**")
        sc1, sc2 = st.columns(2)
        sc1.metric("Primary (P1)", p1_throughput)
        sc2.metric("Comparison (P2)", p2_throughput, delta=int(p1_throughput - p2_throughput))
        
    with c2:
        st.markdown("**📊 Avg Lead Time**")
        sc1, sc2 = st.columns(2)
        sc1.metric("Primary (P1)", f"{p1_avg:.1f}d")
        sc2.metric("Comparison (P2)", f"{p2_avg:.1f}d", delta=f"{p1_avg - p2_avg:.1f}d", delta_color="inverse")
        
    with c3:
        st.markdown("**🔥 85th Percentile**")
        sc1, sc2 = st.columns(2)
        sc1.metric("Primary (P1)", f"{p1_85th:.1f}d")
        sc2.metric("Comparison (P2)", f"{p2_85th:.1f}d", delta=f"{p1_85th - p2_85th:.1f}d", delta_color="inverse")
        
    st.divider()

# --- 4. ACTIVE WIP DASHBOARD ---
st.header("🔄 Active Work In Progress")
if not wip_filtered.empty:
    col1, col2 = st.columns(2)
    with col1:
        status_counts = wip_filtered['Current Status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']
        fig_status = px.bar(status_counts, x='Status', y='Count', text_auto=True, color='Status', title="Tickets by Status")
        st.plotly_chart(fig_status, use_container_width=True)
        
    with col2:
        st.subheader("⚠️ Aging WIP (Danger Zone)")
        # Changed color to Roadmap
        fig_aging = px.strip(wip_filtered, x='Current Status', y='Days in Current Status', color='Roadmap', hover_data=['Ticket ID', 'Summary'])
        fig_aging.update_traces(marker=dict(size=12, opacity=0.8, line=dict(width=1, color='DarkSlateGrey')))
        if not df_lead.empty:
            danger_line = round(df_lead['Lead Time (Days)'].quantile(0.85))
            fig_aging.add_hline(y=danger_line, line_dash="dash", line_color="red", annotation_text=f"85th Percentile ({danger_line}d)")
        st.plotly_chart(fig_aging, use_container_width=True)
else:
    st.info("No active tickets match the current filters.")

st.divider()

# --- 5. HISTORICAL LEAD TIME DASHBOARD ---
st.header("📈 Historical Lead Time & Predictability")

if not lead_filtered.empty:
    p85 = round(lead_filtered['Lead Time (Days)'].quantile(0.85))
    mean_lead = lead_filtered['Lead Time (Days)'].mean()
    std_lead = lead_filtered['Lead Time (Days)'].std()
    std_lead = std_lead if pd.notna(std_lead) else 0

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Trend (85th %)", 
        "🎯 Predictability", 
        "🚀 Throughput", 
        "🌊 Flow (CFD)",
        "📊 Distribution"
    ])

    with tab1:
        st.subheader("📈 Lead Time Trend & Rolling Average")
        trend_df = lead_filtered.sort_values('Date Completed').copy()
        trend_df = trend_df.set_index('Date Completed')
        trend_df['Rolling Avg (14 Days)'] = trend_df['Lead Time (Days)'].rolling('14D', min_periods=1).mean()
        trend_df = trend_df.reset_index()

        # Changed color to Roadmap
        fig_lead = px.scatter(trend_df, x='Date Completed', y='Lead Time (Days)', color='Roadmap', hover_data=['Ticket ID', 'Summary'])
        fig_lead.add_scatter(x=trend_df['Date Completed'], y=trend_df['Rolling Avg (14 Days)'], mode='lines', name='14-Day Rolling Avg', line=dict(color='blue', width=3, shape='spline'))
        fig_lead.add_hline(y=p85, line_dash="dash", line_color="red", annotation_text=f"Overall 85th % ({p85}d)")
        st.plotly_chart(fig_lead, use_container_width=True)

    with tab2:
        st.subheader("🎯 Predictability (Control Chart)")
        # Changed color to Roadmap
        fig_control = px.scatter(lead_filtered, x='Date Completed', y='Lead Time (Days)', color='Roadmap', hover_data=['Ticket ID', 'Summary'])
        fig_control.add_hline(y=mean_lead, line_width=2, line_color="green", annotation_text=f"Overall Avg: {mean_lead:.1f}d")
        fig_control.add_hline(y=mean_lead + std_lead, line_dash="dash", line_color="orange", annotation_text=f"+1 SD ({round(mean_lead + std_lead, 1)}d)")
        if (mean_lead + (2 * std_lead)) < lead_filtered['Lead Time (Days)'].max() * 1.5:
            fig_control.add_hline(y=mean_lead + (2 * std_lead), line_dash="dot", line_color="red")
        st.plotly_chart(fig_control, use_container_width=True)

        st.divider()
        st.subheader("📉 Monthly Predictability (Coefficient of Variation)")
        cv_monthly_df = lead_filtered.copy()
        cv_monthly_df['Completion Month'] = cv_monthly_df['Date Completed'].dt.to_period('M')
        monthly_stats = cv_monthly_df.groupby('Completion Month')['Lead Time (Days)'].agg(['mean', 'std']).reset_index()
        monthly_stats['CV (%)'] = (monthly_stats['std'] / monthly_stats['mean']) * 100
        monthly_stats['Month'] = monthly_stats['Completion Month'].dt.to_timestamp()
        monthly_stats = monthly_stats.dropna(subset=['CV (%)'])
        
        if not monthly_stats.empty:
            fig_monthly_cv = px.bar(monthly_stats, x='Month', y='CV (%)', text_auto='.1f')
            fig_monthly_cv.update_traces(marker_color='#636EFA', textposition='outside')
            fig_monthly_cv.add_scatter(x=monthly_stats['Month'], y=monthly_stats['CV (%)'], mode='lines+markers', name='CV Trend', line=dict(color='#FF7F0E', width=3, shape='spline'), marker=dict(size=8))
            fig_monthly_cv.update_layout(xaxis_title="Month Completed", yaxis_title="Coefficient of Variation (%)", xaxis_tickformat='%b %Y', yaxis_ticksuffix="%", showlegend=False)
            st.plotly_chart(fig_monthly_cv, use_container_width=True)

    with tab3:
        throughput_df = lead_filtered.copy()
        throughput_df['Completion Week'] = throughput_df['Date Completed'].dt.to_period('W').apply(lambda r: r.start_time)
        weekly_counts = throughput_df.groupby('Completion Week').size().reset_index(name='Tickets Completed')
        fig_throughput = px.bar(weekly_counts, x='Completion Week', y='Tickets Completed', text_auto=True)
        fig_throughput.update_layout(bargap=0.2)
        st.plotly_chart(fig_throughput, use_container_width=True)

    with tab4:
        if not cfd_filtered.empty:
            cfd_clean = cfd_filtered.sort_values('Date').drop_duplicates(subset=['Ticket ID', 'Date'], keep='last')
            pivot_df = cfd_clean.pivot(index='Date', columns='Ticket ID', values='Status')
            all_dates = pd.date_range(start=cfd_clean['Date'].min(), end=pd.Timestamp.today().normalize())
            pivot_df = pivot_df.reindex(all_dates).ffill()
            cfd_counts = pivot_df.apply(lambda row: row.value_counts(), axis=1).fillna(0)
            cfd_counts = cfd_counts.reset_index().rename(columns={'index': 'Date'})
            cfd_melted = cfd_counts.melt(id_vars='Date', var_name='Status', value_name='Count')
            fig_cfd = px.area(cfd_melted, x='Date', y='Count', color='Status')
            st.plotly_chart(fig_cfd, use_container_width=True)
        else:
            st.info("Not enough data to draw the CFD. Run the cfd_extract.py script first!")

    with tab5:
        # Changed color to Roadmap
        fig_dist = px.histogram(lead_filtered, x='Lead Time (Days)', nbins=20, color='Roadmap', marginal="box")
        st.plotly_chart(fig_dist, use_container_width=True)