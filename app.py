import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. PAGE SETUP ---
st.set_page_config(page_title="Discovery Process Dashboard", layout="wide")
st.title("🎯 Discovery Process Dashboard")
st.markdown("Monitoring flow and spotting bottlenecks in our Discovery pipeline.")

# --- 2. LOAD DATA ---
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("jira_discovery_data.csv")
        return df
    except FileNotFoundError:
        st.error("Data file not found. Have Pair 1 run the extraction script!")
        return pd.DataFrame() 

df = load_data()

if not df.empty:
    # --- 3. PAIR 3's LOGIC (Column-Specific Thresholds) ---
    # Update these keys to perfectly match your actual Jira statuses
    COLUMN_THRESHOLDS = {
        "Under Consideration": {"warn": 10, "breach": 14},
        "Research": {"warn": 4, "breach": 7},
        "Solutioning": {"warn": 5, "breach": 8},
        "Ready for Test": {"warn": 2, "breach": 3},
        "Done": {"warn": 999, "breach": 999} # Keeps done items green
    }

    # Fallback limits just in case a new status appears in Jira unexpectedly
    DEFAULT_WARN = 7
    DEFAULT_BREACH = 14

    def determine_health(row):
        """Looks at both the status and the age to determine color."""
        status = row['Current Status']
        days = row['Days in Current Status']
        
        # Get the specific limits for this status, or use defaults
        limits = COLUMN_THRESHOLDS.get(status, {"warn": DEFAULT_WARN, "breach": DEFAULT_BREACH})
        
        if days >= limits["breach"]:
            return "Breached (Red)"
        elif days >= limits["warn"]:
            return "Warning (Yellow)"
        else:
            return "Healthy (Green)"

    # Apply the logic across the dataframe rows (axis=1 is critical here)
    df['Health'] = df.apply(determine_health, axis=1)
    
    # Add the breach limit to the dataframe so it shows up when hovering
    df['Max Days Allowed'] = df['Current Status'].apply(
        lambda x: COLUMN_THRESHOLDS.get(x, {"breach": DEFAULT_BREACH})["breach"]
    )
    
    # Custom color mapping for Plotly
    color_map = {"Healthy (Green)": "#2ecc71", "Warning (Yellow)": "#f1c40f", "Breached (Red)": "#e74c3c"}

    # --- 4. GLOBAL FILTERS (Control Bar) ---
    st.markdown("### Global Filters")
    
    # Create 3 columns for our dropdowns
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        status_filter = st.multiselect("Filter by Status:", options=df['Current Status'].unique(), default=df['Current Status'].unique())
    
    with col_f2:
        # Looking for 'Problem to Address' instead of 'Team'
        problem_options = ["All"] + sorted(list(df['Capability'].dropna().unique()))
        problem_filter = st.selectbox("Filter by Capability:", options=problem_options)
        
    with col_f3:
        vs_options = ["All"] + sorted(list(df['Team'].dropna().unique()))
        vs_filter = st.selectbox("Filter by Team:", options=vs_options)

    # --- APPLY FILTERS LOGIC (Top Chart) ---
    filtered_df = df[df['Current Status'].isin(status_filter)]
    
    if problem_filter != "All":
        filtered_df = filtered_df[filtered_df['Capability'] == problem_filter]
        
    if vs_filter != "All":
        filtered_df = filtered_df[filtered_df['Team'] == vs_filter]

    # --- 5. AT-A-GLANCE METRICS (Top Row) ---
    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    
    current_wip = len(filtered_df)
    avg_age = round(filtered_df['Days in Current Status'].mean(), 1) if not filtered_df.empty else 0
    # Count how many items currently have the "Breached (Red)" health status
    stalled_items = len(filtered_df[filtered_df['Health'] == 'Breached (Red)'])

    m1.metric("Current WIP (Active Items)", current_wip)
    m2.metric("Average Days in Current Status", f"{avg_age} Days")
    m3.metric("🚨 Stalled Items (Breached Threshold)", stalled_items)
    
    st.markdown("---")

    # --- 6. THE AGING WIP CHART (Centerpiece) ---
    st.subheader("Aging Work in Progress (WIP)")
    
    # The explicit order of your workflow from left to right
    workflow_order = ["Under Consideration", "Research", "Solutioning", "Ready for Test", "Done"]
    
    fig = px.scatter(
        filtered_df, 
        x="Current Status", 
        y="Days in Current Status", 
        color="Health",
        color_discrete_map=color_map,
        hover_data=["Ticket ID", "Summary", "Max Days Allowed"], 
        category_orders={"Current Status": workflow_order},
        size_max=15
    )
    
    # Make the dots a bit larger and more legible
    fig.update_traces(marker=dict(size=12, line=dict(width=1, color='DarkSlateGrey')))
    fig.update_layout(yaxis_title="Days in Current Status", xaxis_title="JPD Workflow Column", height=500)
    
    # Render the chart in Streamlit
    st.plotly_chart(fig, width='stretch')

    # --- 7. RAW DATA TABLE (Bottom) ---
    with st.expander("View Raw Data & Stalled Items List"):
        st.dataframe(filtered_df.sort_values(by="Days in Current Status", ascending=False))

        # ==========================================
    # --- 8. LEAD TIME VARIATION (New Chart) ---
    # ==========================================
    st.markdown("---")
    st.header("📈 Lead Time Variation & Predictability")
    st.markdown("Analyzing completed items to understand our consistency and forecast future work.")

    # Load the second CSV generated by Pair 1
    @st.cache_data
    def load_lead_time_data():
        try:
            return pd.read_csv("jira_lead_time_data.csv")
        except FileNotFoundError:
            return pd.DataFrame()

    df_lt = load_lead_time_data()

    if not df_lt.empty:
        # --- APPLY FILTERS LOGIC (Bottom Chart) ---
        filtered_df_lt = df_lt.copy()
        
        # Apply the exact same dropdown filters to the historical data
        if problem_filter != "All" and 'Problem to Address' in filtered_df_lt.columns:
            filtered_df_lt = filtered_df_lt[filtered_df_lt['Problem to Address'] == problem_filter]
            
        if vs_filter != "All" and 'Value Stream' in filtered_df_lt.columns:
            filtered_df_lt = filtered_df_lt[filtered_df_lt['Value Stream'] == vs_filter]

        # Now, calculate the math using the FILTERED dataframe
        if not filtered_df_lt.empty:
            p85 = round(filtered_df_lt['Lead Time (Days)'].quantile(0.85))
            avg_lt = round(filtered_df_lt['Lead Time (Days)'].mean(), 1)
            
            # ... (the rest of the Pair 2 charting code stays exactly the same, 
            # just make sure px.scatter uses filtered_df_lt instead of df_lt!) ...

    if not df_lt.empty:
        # Calculate the magical 85th Percentile mathematically
        p85 = round(df_lt['Lead Time (Days)'].quantile(0.85))
        
        # Calculate the Average just for comparison
        avg_lt = round(df_lt['Lead Time (Days)'].mean(), 1)

        # Create a 2-column layout (Metrics on left, Chart on right)
        col_metrics, col_chart = st.columns([1, 3])
        
        with col_metrics:
            st.info("🎯 **Predictability Standard**")
            st.metric("85th Percentile Lead Time", f"{p85} Days")
            st.markdown(f"*We have an 85% confidence rate that new Discovery items will finish in **{p85} days or less**.*")
            
            st.divider()
            st.metric("Average Lead Time", f"{avg_lt} Days")
            st.markdown("*Note: Averages hide outliers. Trust the 85th percentile for forecasting!*")
            
        with col_chart:
            # Build the Scatterplot using Plotly
            fig_lt = px.scatter(
                df_lt,
                x="Date Completed",
                y="Lead Time (Days)",
                hover_data=["Ticket ID", "Summary"],
                title="Historical Lead Time Spread (Completed Items)"
            )
            
            # Make the dots slightly transparent so overlapping dots are visible
            fig_lt.update_traces(marker=dict(size=10, color='#3498db', opacity=0.6, line=dict(width=1, color='DarkSlateGrey')))
            
            # Draw the 85th Percentile Threshold Line
            fig_lt.add_hline(
                y=p85, 
                line_dash="dash", 
                line_color="#e74c3c", 
                annotation_text=f"85th Percentile ({p85} Days)",
                annotation_position="top left"
            )
            
            fig_lt.update_layout(xaxis_title="Date Completed", yaxis_title="Total Lead Time (Days)", height=450)
            
            # Render the chart
            st.plotly_chart(fig_lt, use_container_width=True)
    else:
        st.warning("Lead Time data not found. Make sure Pair 1 has successfully run `lead_time_extract.py`!")