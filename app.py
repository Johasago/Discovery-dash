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
    
    # Create the 4 columns
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    
    with col_f1:
        status_filter = st.multiselect("Filter by Status:", options=df['Current Status'].unique(), default=df['Current Status'].unique())
    
    with col_f2:
        # 1. Defining problem_filter here!
        problem_options = ["All"] + sorted(list(df['Problem to Address'].dropna().unique()))
        problem_filter = st.selectbox("Filter by Problem to Address:", options=problem_options)
        
    with col_f3:
        # 2. Defining team_filter here!
        team_options = ["All"] + sorted(list(df['Team'].dropna().unique()))
        team_filter = st.selectbox("Filter by Team:", options=team_options)

    with col_f4:
        # 3. Defining roadmap_filter here!
        roadmap_options = ["All"] + sorted(list(df['Roadmap'].dropna().unique()))
        roadmap_filter = st.selectbox("Filter by Roadmap:", options=roadmap_options)

    # --- APPLY FILTERS LOGIC (Top Chart) ---
    # Apply Status
    filtered_df = df[df['Current Status'].isin(status_filter)]
    
    # Apply Problem
    if problem_filter != "All":
        filtered_df = filtered_df[filtered_df['Problem to Address'] == problem_filter]
        
    # Apply Team
    if team_filter != "All":
        filtered_df = filtered_df[filtered_df['Team'] == team_filter]
        
    # Apply Roadmap
    if roadmap_filter != "All":
        filtered_df = filtered_df[filtered_df['Roadmap'] == roadmap_filter]