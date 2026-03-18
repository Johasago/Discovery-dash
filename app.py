import streamlit as st
import pandas as pd
import plotly.express as px

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Discovery Dashboard", layout="wide")
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

    return df_wip, df_lead

df_wip, df_lead = load_data()

if df_wip.empty and df_lead.empty:
    st.warning("⚠️ No data found. Please run the Python extraction scripts first.")
    st.stop()

for df in [df_wip, df_lead]:
    if not df.empty:
        for col in ['Problem to Address', 'Team', 'Roadmap']:
            if col in df.columns:
                df[col] = df[col].fillna('Unassigned')

# --- 2. SIDEBAR FILTERS ---
st.sidebar.header("Filter Data")

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


# --- 4. ACTIVE WIP DASHBOARD ---
st.header("🔄 Active Work In Progress")

if not wip_filtered.empty:
    st.metric("Total Active Tickets", len(wip_filtered))
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Tickets by Status")
        status_counts = wip_filtered['Current Status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']
        fig_status = px.bar(status_counts, x='Status', y='Count', text_auto=True, color='Status')
        st.plotly_chart(fig_status, use_container_width=True)
        
    with col2:
        st.subheader("Days in Current Status")
        fig_days = px.histogram(wip_filtered, x='Days in Current Status', nbins=20, color='Current Status')
        st.plotly_chart(fig_days, use_container_width=True)
else:
    st.info("No active tickets match the current filters.")

st.divider()

# --- 5. HISTORICAL LEAD TIME DASHBOARD (WITH TABS!) ---
st.header("📈 Historical Lead Time & Predictability")

if not lead_filtered.empty:
    # Math for the top metrics
    p85 = round(lead_filtered['Lead Time (Days)'].quantile(0.85))
    mean_lead = lead_filtered['Lead Time (Days)'].mean()
    # Safety catch in case there's only 1 ticket (standard deviation needs at least 2)
    std_lead = lead_filtered['Lead Time (Days)'].std()
    std_lead = std_lead if pd.notna(std_lead) else 0

    # Display clean metric cards at the top
    m1, m2, m3 = st.columns(3)
    m1.metric("🔥 85th Percentile", f"{p85} Days")
    m2.metric("📊 Average (Mean)", f"{round(mean_lead, 1)} Days")
    m3.metric("🎯 Standard Deviation", f"± {round(std_lead, 1)} Days")
    
    st.write("") # Add a little vertical space
    
    # --- CREATE THE TABS ---
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Trend (85th %)", 
        "🎯 Predictability (Control)", 
        "🚀 Throughput", 
        "📊 Distribution",
        "🗄️ Raw Data"
    ])

    # TAB 1: The original scatter plot
    with tab1:
        fig_lead = px.scatter(
            lead_filtered, x='Date Completed', y='Lead Time (Days)', color='Team',
            hover_data=['Ticket ID', 'Summary', 'Problem to Address']
        )
        fig_lead.add_hline(y=p85, line_dash="dash", line_color="red", annotation_text=f"85th Percentile ({p85}d)")
        st.plotly_chart(fig_lead, use_container_width=True)

    # TAB 2: The new Standard Deviation Control Chart
    with tab2:
        fig_control = px.scatter(
            lead_filtered, x='Date Completed', y='Lead Time (Days)', color='Team',
            hover_data=['Ticket ID', 'Summary']
        )
        # Average Line
        fig_control.add_hline(y=mean_lead, line_width=2, line_color="green", annotation_text=f"Average: {mean_lead:.1f}d")
        # +1 Standard Deviation (Warning Band)
        fig_control.add_hline(y=mean_lead + std_lead, line_dash="dash", line_color="orange", annotation_text=f"+1 SD ({round(mean_lead + std_lead, 1)}d)")
        # +2 Standard Deviations (Outlier Band)
        if (mean_lead + (2 * std_lead)) < lead_filtered['Lead Time (Days)'].max() * 1.5:
            fig_control.add_hline(y=mean_lead + (2 * std_lead), line_dash="dot", line_color="red", annotation_text=f"+2 SD ({round(mean_lead + (2 * std_lead), 1)}d)")
        st.plotly_chart(fig_control, use_container_width=True)

    # TAB 3: The new Throughput Velocity Chart
    with tab3:
        throughput_df = lead_filtered.copy()
        # Group by week starting on Monday
        throughput_df['Completion Week'] = throughput_df['Date Completed'].dt.to_period('W').apply(lambda r: r.start_time)
        weekly_counts = throughput_df.groupby('Completion Week').size().reset_index(name='Tickets Completed')
        
        fig_throughput = px.bar(weekly_counts, x='Completion Week', y='Tickets Completed', text_auto=True)
        fig_throughput.update_layout(bargap=0.2, xaxis_title="Week of", yaxis_title="Tickets Completed")
        st.plotly_chart(fig_throughput, use_container_width=True)

    # TAB 4: The new Histogram Distribution
    with tab4:
        fig_dist = px.histogram(
            lead_filtered, x='Lead Time (Days)', nbins=20, color='Team', 
            marginal="box", hover_data=['Ticket ID']
        )
        fig_dist.update_layout(xaxis_title="Lead Time (Days)", yaxis_title="Number of Tickets")
        st.plotly_chart(fig_dist, use_container_width=True)

    # TAB 5: Raw Data Table
    with tab5:
        st.dataframe(lead_filtered, use_container_width=True)

else:
    st.info("No completed tickets match the current filters.")