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

# --- SIDEBAR: PERIOD COMPARISON DATES ---
st.sidebar.divider()
st.sidebar.header("⚖️ Compare Periods")

# Default to comparing the last 30 days vs the 30 days before that
today = datetime.today().date()
p1_default = (today - pd.Timedelta(days=30), today)
p2_default = (today - pd.Timedelta(days=60), today - pd.Timedelta(days=31))

# Streamlit allows users to select a start and end date in a single click!
period1 = st.sidebar.date_input("Primary Period (P1)", value=p1_default)
period2 = st.sidebar.date_input("Comparison Period (P2)", value=p2_default)

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


# ==========================================
# --- NEW: DYNAMIC PERIOD COMPARISON ---
# ==========================================
if not lead_filtered.empty:
    st.subheader("⚖️ Period-over-Period Performance")
    st.caption("Compare your Primary Period (P1) against your Comparison Period (P2) using the sidebar controls.")
    
    # 1. Safety Catch: Streamlit date_input returns a tuple of 1 if the user hasn't clicked their end date yet!
    def get_dates(date_input, default_dates):
        if isinstance(date_input, tuple) and len(date_input) == 2:
            return pd.to_datetime(date_input[0]), pd.to_datetime(date_input[1])
        return pd.to_datetime(default_dates[0]), pd.to_datetime(default_dates[1])
        
    p1_start, p1_end = get_dates(period1, p1_default)
    p2_start, p2_end = get_dates(period2, p2_default)
    
    # 2. Filter the data into two distinct buckets based on when the ticket finished
    p1_df = lead_filtered[(lead_filtered['Date Completed'] >= p1_start) & (lead_filtered['Date Completed'] <= p1_end)]
    p2_df = lead_filtered[(lead_filtered['Date Completed'] >= p2_start) & (lead_filtered['Date Completed'] <= p2_end)]
    
    # 3. Calculate the metrics for both periods
    p1_throughput = len(p1_df)
    p2_throughput = len(p2_df)
    
    p1_avg = p1_df['Lead Time (Days)'].mean() if not p1_df.empty else 0
    p2_avg = p2_df['Lead Time (Days)'].mean() if not p2_df.empty else 0
    
    p1_85th = p1_df['Lead Time (Days)'].quantile(0.85) if not p1_df.empty else 0
    p2_85th = p2_df['Lead Time (Days)'].quantile(0.85) if not p2_df.empty else 0
    
    # 4. Draw the UI Cards
    c1, c2, c3 = st.columns(3)
    
    # Throughput (Higher is better, normal delta)
    c1.metric(
        label="🚀 Throughput (Tickets)", 
        value=p1_throughput, 
        delta=int(p1_throughput - p2_throughput)
    )
    
    # Average Lead Time (Lower is better, so we INVERSE the delta color!)
    c2.metric(
        label="📊 Avg Lead Time", 
        value=f"{p1_avg:.1f}d", 
        delta=f"{p1_avg - p2_avg:.1f}d",
        delta_color="inverse" 
    )
    
    # 85th Percentile (Lower is better, so we INVERSE the delta color!)
    c3.metric(
        label="🔥 85th Percentile", 
        value=f"{p1_85th:.1f}d", 
        delta=f"{p1_85th - p2_85th:.1f}d",
        delta_color="inverse"
    )
    
    st.divider()
# ==========================================

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
        # --- NEW: MONTHLY COEFFICIENT OF VARIATION (CV) WITH TREND LINE ---
        # ==========================================
        st.subheader("📉 Monthly Predictability (Coefficient of Variation)")
        st.caption("Tracks relative variation as a percentage of your average lead time per month. A lower percentage means the team is becoming more predictable!")
        
        # 1. Create a "Month" column for grouping
        cv_monthly_df = lead_filtered.copy()
        cv_monthly_df['Completion Month'] = cv_monthly_df['Date Completed'].dt.to_period('M')
        
        # 2. Group by month and calculate the Mean and Standard Deviation
        monthly_stats = cv_monthly_df.groupby('Completion Month')['Lead Time (Days)'].agg(['mean', 'std']).reset_index()
        
        # 3. Calculate the Coefficient of Variation (%)
        monthly_stats['CV (%)'] = (monthly_stats['std'] / monthly_stats['mean']) * 100
        
        # 4. Clean up the dates so Plotly can read them perfectly
        monthly_stats['Month'] = monthly_stats['Completion Month'].dt.to_timestamp()
        
        # Drop any months that only had 1 ticket (Standard Deviation requires at least 2)
        monthly_stats = monthly_stats.dropna(subset=['CV (%)'])
        
        if not monthly_stats.empty:
            # 5. Draw the Base Bar Chart
            fig_monthly_cv = px.bar(
                monthly_stats, 
                x='Month', 
                y='CV (%)',
                text_auto='.1f', # Prints the exact percentage on the bars
            )
            
            fig_monthly_cv.update_traces(marker_color='#636EFA', textposition='outside')
            
            # 6. OVERLAY THE TREND LINE
            fig_monthly_cv.add_scatter(
                x=monthly_stats['Month'], 
                y=monthly_stats['CV (%)'],
                mode='lines+markers',
                name='CV Trend',
                line=dict(color='#FF7F0E', width=3, shape='spline'), # Smooth orange line
                marker=dict(size=8)
            )
            
            # 7. Final Polish
            fig_monthly_cv.update_layout(
                xaxis_title="Month Completed",
                yaxis_title="Coefficient of Variation (%)",
                xaxis_tickformat='%b %Y', 
                yaxis_ticksuffix="%",
                showlegend=False # Hides the unnecessary legend since it's obvious what the line is
            )
            st.plotly_chart(fig_monthly_cv, use_container_width=True)
        else:
            st.info("Not enough data to calculate monthly Coefficient of Variation yet (requires at least 2 tickets completed in a single month).")
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