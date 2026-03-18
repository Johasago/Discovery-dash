import streamlit as st
import pandas as pd
import plotly.express as px

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Discovery Dashboard", layout="wide")
st.title("📊 Discovery Dashboard")

# --- 1. DATA LOADING & CLEANING ---
@st.cache_data(ttl=600) # Caches data for 10 minutes to keep the app fast
def load_data():
    # Load Active WIP
    try:
        df_wip = pd.read_csv("jira_discovery_data.csv")
        df_wip['Date Entered Status'] = pd.to_datetime(df_wip['Date Entered Status'])
    except FileNotFoundError:
        df_wip = pd.DataFrame()

    # Load Historical Lead Time
    try:
        df_lead = pd.read_csv("jira_lead_time_data.csv")
        df_lead['Date Completed'] = pd.to_datetime(df_lead['Date Completed'])
    except FileNotFoundError:
        df_lead = pd.DataFrame()

    return df_wip, df_lead

df_wip, df_lead = load_data()

# Stop the app completely if no CSVs are found
if df_wip.empty and df_lead.empty:
    st.warning("⚠️ No data found. Please run the Python extraction scripts first.")
    st.stop()

# Safety net: Ensure missing custom fields are labeled "Unassigned" instead of crashing
for df in [df_wip, df_lead]:
    if not df.empty:
        for col in ['Problem to Address', 'Team', 'Roadmap']:
            if col in df.columns:
                df[col] = df[col].fillna('Unassigned')

# --- 2. SIDEBAR FILTERS ---
st.sidebar.header("Filter Data")

# Helper function to grab unique dropdown options safely across both files
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

# --- 3. FILTERING LOGIC (The Fix for the Vanishing Charts!) ---
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

    with st.expander("View Raw Active WIP Data"):
        st.dataframe(wip_filtered)
else:
    st.info("No active tickets match the current filters.")

st.divider()

# --- 5. HISTORICAL LEAD TIME DASHBOARD ---
st.header("📈 Historical Lead Time")

if not lead_filtered.empty:
    # Math for the 85th Percentile
    p85 = round(lead_filtered['Lead Time (Days)'].quantile(0.85))
    st.metric("85th Percentile Lead Time", f"{p85} Days")
    
    st.subheader("Lead Time Trend")
    fig_lead = px.scatter(
        lead_filtered, 
        x='Date Completed', 
        y='Lead Time (Days)', 
        color='Team',
        hover_data=['Ticket ID', 'Summary', 'Problem to Address']
    )
    # Draw the red target line on the chart
    fig_lead.add_hline(y=p85, line_dash="dash", line_color="red", annotation_text=f"85th Percentile ({p85}d)")
    st.plotly_chart(fig_lead, use_container_width=True)

    with st.expander("View Raw Completed Lead Time Data"):
        st.dataframe(lead_filtered)
else:
    st.info("No completed tickets match the current filters.")