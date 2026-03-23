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
# -----------------------------------

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

for df in [df_wip, df_lead, df_cfd]:
    if not df.empty:
        for col in ['Problem to Address', 'Team', 'Roadmap']:
            if col in df.columns:
                df[col] = df[col].fillna('Unassigned')

# --- 2. SIDEBAR FILTERS ---
st.sidebar.header("Filter Data")

try:
    mtime = os.path.getmtime("jira_discovery_data.csv")
    last_updated = datetime.fromtimestamp(mtime).strftime('%B %d, %Y at %I:%M %p')
    st.sidebar.caption(f"🕒 **Last Data Refresh:** \n{last_updated}")
except FileNotFoundError:
    st.sidebar.caption("🕒 **Last Data Refresh:** Unknown")

def get_unique_options(col_name):
    opts = set()
    if not df_wip.empty and col_name in df_wip.columns:
        opts.update(df_wip[col_name].dropna().unique())
    if not df_lead.empty and col_name in df_lead.columns:
        opts.update(df_lead[col_name].dropna().unique())
    return ["All"] + sorted(list(opts))

selected_problem = st.sidebar.selectbox("Problem to Address", get_unique_options("Problem to Address"))
selected_team = st.sidebar.selectbox("Team", get_unique_options("Team"))
selected_roadmap = st.sidebar.selectbox("Roadmap", get_unique_options("Roadmap"))

# --- 3. FILTERING LOGIC ---
def apply_filters(df):
    if df.empty: return df
    filtered = df.copy()
    if selected_problem != "All" and "Problem to Address" in filtered.columns:
        filtered = filtered[filtered["Problem to Address"] == selected_problem]
    if selected_team != "All" and "Team" in filtered.columns:
        filtered = filtered[filtered["Team"] == selected_team]
    if selected_roadmap != "All" and "Roadmap" in filtered.columns:
        filtered = filtered[filtered["Roadmap"] == selected_roadmap]
    return filtered

wip_filtered = apply_filters(df_wip)
lead_filtered = apply_filters(df_lead)
# Note: We only filter CFD by Team, since that's the only custom field we pulled into the Time Machine!
cfd_filtered = df_cfd.copy()
if selected_team != "All" and not cfd_filtered.empty:
    cfd_filtered = cfd_filtered[cfd_filtered['Team'] == selected_team]


# --- SMART EXECUTIVE SUMMARY ---
if not lead_filtered.empty and not wip_filtered.empty:
    st.subheader("💡 Executive Summary")
    p85 = round(lead_filtered['Lead Time (Days)'].quantile(0.85))
    stalled_tickets = len(wip_filtered[wip_filtered['Days in Current Status'] > p85])
    
    latest_date = lead_filtered['Date Completed'].max()
    last_30_days = latest_date - pd.Timedelta(days=30)
    prev_30_days = latest_date - pd.Timedelta(days=60)
    
    completed_last_30 = len(lead_filtered[lead_filtered['Date Completed'] >= last_30_days])
    completed_prev_30 = len(lead_filtered[(lead_filtered['Date Completed'] >= prev_30_days) & (lead_filtered['Date Completed'] < last_30_days)])
    
    if completed_last_30 > completed_prev_30:
        trend_msg = f"🚀 **Great news:** Delivery is accelerating. The team completed **{completed_last_30}** tickets in the last 30 days, up from {completed_prev_30} the previous month."
    elif completed_last_30 < completed_prev_30:
        trend_msg = f"⚠️ **Attention:** Throughput is down. The team completed **{completed_last_30}** tickets in the last 30 days, compared to {completed_prev_30} the previous month."
    else:
        trend_msg = f"⚖️ **Steady:** Delivery is stable. The team completed **{completed_last_30}** tickets in the last 30 days, matching the previous month's pace."
        
    wip_msg = f"🚨 **Action Needed:** **{stalled_tickets}** active tickets are sitting in the Danger Zone (> {p85} days)." if stalled_tickets > 0 else f"✅ **Healthy Flow:** No active tickets are currently in the Danger Zone."
        
    st.info(f"{trend_msg}\n\n{wip_msg}")
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
        fig_aging = px.strip(wip_filtered, x='Current Status', y='Days in Current Status', color='Team', hover_data=['Ticket ID', 'Summary'])
        fig_aging.update_traces(marker=dict(size=12, opacity=0.8, line=dict(width=1, color='DarkSlateGrey')))
        if not df_lead.empty:
            danger_line = round(df_lead['Lead Time (Days)'].quantile(0.85))
            fig_aging.add_hline(y=danger_line, line_dash="dash", line_color="red", annotation_text=f"85th Percentile ({danger_line}d)")
        st.plotly_chart(fig_aging, use_container_width=True)
else:
    st.info("No active tickets match the current filters.")

st.divider()

# --- 5. HISTORICAL LEAD TIME DASHBOARD (WITH TABS!) ---
st.header("📈 Historical Lead Time & Predictability")

if not lead_filtered.empty:
    p85 = round(lead_filtered['Lead Time (Days)'].quantile(0.85))
    mean_lead = lead_filtered['Lead Time (Days)'].mean()
    std_lead = lead_filtered['Lead Time (Days)'].std()
    std_lead = std_lead if pd.notna(std_lead) else 0

    m1, m2, m3 = st.columns(3)
    m1.metric("🔥 85th Percentile", f"{p85} Days")
    m2.metric("📊 Average (Mean)", f"{round(mean_lead, 1)} Days")
    m3.metric("🎯 Standard Deviation", f"± {round(std_lead, 1)} Days")
    st.write("") 
    
    # 🚨 NEW TAB ADDED HERE!
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Trend (85th %)", 
        "🎯 Predictability", 
        "🚀 Throughput", 
        "🌊 Flow (CFD)",
        "📊 Distribution"
    ])

    with tab1:
        fig_lead = px.scatter(lead_filtered, x='Date Completed', y='Lead Time (Days)', color='Team', hover_data=['Ticket ID', 'Summary'])
        fig_lead.add_hline(y=p85, line_dash="dash", line_color="red", annotation_text=f"85th Percentile ({p85}d)")
        st.plotly_chart(fig_lead, use_container_width=True)

    # TAB 2: Predictability & Variation
    with tab2:
        # 1. The overall Control Chart (Scatter)
        st.subheader("🎯 Predictability (Control Chart)")
        fig_control = px.scatter(lead_filtered, x='Date Completed', y='Lead Time (Days)', color='Team', hover_data=['Ticket ID', 'Summary'])
        fig_control.add_hline(y=mean_lead, line_width=2, line_color="green", annotation_text=f"Overall Avg: {mean_lead:.1f}d")
        fig_control.add_hline(y=mean_lead + std_lead, line_dash="dash", line_color="orange", annotation_text=f"+1 SD ({round(mean_lead + std_lead, 1)}d)")
        if (mean_lead + (2 * std_lead)) < lead_filtered['Lead Time (Days)'].max() * 1.5:
            fig_control.add_hline(y=mean_lead + (2 * std_lead), line_dash="dot", line_color="red")
        st.plotly_chart(fig_control, use_container_width=True)

        st.divider()

       # ==========================================
        # --- NEW: ROLLING COEFFICIENT OF VARIATION (CV) ---
        # ==========================================
        st.subheader("📉 Predictability Trend (Coefficient of Variation)")
        st.caption("Tracks relative variation as a percentage of your average lead time. A downward trend means you are becoming highly predictable!")
        
        # 1. Prep the data chronologically
        var_trend_df = lead_filtered.sort_values('Date Completed').copy()
        var_trend_df = var_trend_df.set_index('Date Completed')
        
        # 2. Calculate both the Rolling Mean and Rolling SD (min 2 data points)
        rolling_mean = var_trend_df['Lead Time (Days)'].rolling('14D', min_periods=2).mean()
        rolling_std = var_trend_df['Lead Time (Days)'].rolling('14D', min_periods=2).std()
        
        # 3. Calculate the Coefficient of Variation (CV) as a Percentage
        var_trend_df['Rolling CV (%)'] = (rolling_std / rolling_mean) * 100
        
        var_trend_df = var_trend_df.reset_index()

        # 4. Clean up blank days
        var_trend_clean = var_trend_df.dropna(subset=['Rolling CV (%)'])

        # 5. Draw the chart
        if not var_trend_clean.empty:
            fig_rolling_cv = px.line(
                var_trend_clean, 
                x='Date Completed', 
                y='Rolling CV (%)',
                markers=True,
                line_shape='spline',
                hover_data=['Ticket ID']
            )
            
            # Make it look great
            fig_rolling_cv.update_traces(line=dict(color='purple', width=3))
            fig_rolling_cv.update_layout(
                yaxis_title="Coefficient of Variation (%)", 
                xaxis_title="Date",
                yaxis_ticksuffix="%" # Adds a % sign to the axis labels
            )
            st.plotly_chart(fig_rolling_cv, use_container_width=True)
        else:
            st.info("Not enough data to calculate a 14-day rolling Coefficient of Variation yet.")
        # ==========================================

    with tab3:
        throughput_df = lead_filtered.copy()
        throughput_df['Completion Week'] = throughput_df['Date Completed'].dt.to_period('W').apply(lambda r: r.start_time)
        weekly_counts = throughput_df.groupby('Completion Week').size().reset_index(name='Tickets Completed')
        fig_throughput = px.bar(weekly_counts, x='Completion Week', y='Tickets Completed', text_auto=True)
        fig_throughput.update_layout(bargap=0.2)
        st.plotly_chart(fig_throughput, use_container_width=True)

    # ==========================================
    # --- NEW: CUMULATIVE FLOW DIAGRAM (CFD) ---
    # ==========================================
    with tab4:
        if not cfd_filtered.empty:
            st.caption("How work accumulates and flows through your statuses over time. Watch out for widening bands!")
            
            # 1. Clean up same-day transitions (keep the final status of the day)
            cfd_clean = cfd_filtered.sort_values('Date').drop_duplicates(subset=['Ticket ID', 'Date'], keep='last')
            
            # 2. Pivot the data: Rows = Dates, Cols = Tickets, Values = Status
            pivot_df = cfd_clean.pivot(index='Date', columns='Ticket ID', values='Status')
            
            # 3. THE MAGIC: Forward fill the blank days!
            all_dates = pd.date_range(start=cfd_clean['Date'].min(), end=pd.Timestamp.today().normalize())
            pivot_df = pivot_df.reindex(all_dates).ffill()
            
            # 4. Count the statuses per day
            cfd_counts = pivot_df.apply(lambda row: row.value_counts(), axis=1).fillna(0)
            cfd_counts = cfd_counts.reset_index().rename(columns={'index': 'Date'})
            
            # 5. Melt back into a format Plotly loves and draw the chart
            cfd_melted = cfd_counts.melt(id_vars='Date', var_name='Status', value_name='Count')
            fig_cfd = px.area(cfd_melted, x='Date', y='Count', color='Status')
            
            st.plotly_chart(fig_cfd, use_container_width=True)
        else:
            st.info("Not enough data to draw the CFD. Run the cfd_extract.py script first!")

    with tab5:
        fig_dist = px.histogram(lead_filtered, x='Lead Time (Days)', nbins=20, color='Team', marginal="box")
        st.plotly_chart(fig_dist, use_container_width=True)