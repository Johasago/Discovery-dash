import os
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth
from datetime import timezone, datetime

# --- CONFIGURATION (Now securely pulling from environment variables) ---
JIRA_URL = os.environ.get("JIRA_URL")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")

if not all([JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN]):
    raise ValueError("Missing Jira credentials! Check your environment variables or GitHub Secrets.")
# 1. Put the exact JQL you copied from Jira inside these parentheses
COPIED_JQL = 'project = "PLD" AND status in ("Ready for Test/Build", "In Build (Done)", "Won\'t Do") AND updated >= -90d' 

# 2. Sandwich it with the Project context and an ORDER BY clause
JQL_QUERY = f'project = "PLD" AND ({COPIED_JQL}) ORDER BY created DESC'

# 2. PAIR 3'S LOGIC: The boundaries
START_COLUMN = "To Do Ideas" 

# Change this to a list so we can catch any valid finishing state
END_STATUSES = ["Ready for Test/Build", "In Build (Done)", "Won't Do"]

def fetch_completed_issues():
    """Fetches ALL completed issues using Atlassian's new nextPageToken pagination."""
    url = f"{JIRA_URL}/rest/api/3/search/jql" 
    auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Accept": "application/json"}
    
    all_issues = []
    max_results = 100
    next_page_token = None # The new magic pagination parameter

    print("Paging through Jira API using nextPageToken...")
    
    while True:
        # CIRCUIT BREAKER (Bumped to 1000 just in case)
        if len(all_issues) >= 1000:
            print("🛑 Circuit breaker tripped! Hit 1000 tickets.")
            break

        query = {
            'jql': JQL_QUERY, 
            'maxResults': max_results,
            'expand': 'changelog', 
            'fields': 'summary,status,created, customfield_13923, customfield_10001'

        }
        
        # If Jira gave us a token from the last page, include it in this request
        if next_page_token:
            query['nextPageToken'] = next_page_token

        response = requests.get(url, headers=headers, params=query, auth=auth)
        if response.status_code != 200:
            print(f"Error {response.status_code}: {response.text}")
            break
            
        data = response.json()
        batch = data.get('issues', [])
        
        if not batch:
            break 
            
        all_issues.extend(batch)
        print(f"Fetched {len(all_issues)} tickets so far...")
        
        # Check if Jira gave us a token for the next page. If not, we are done!
        next_page_token = data.get('nextPageToken')
        if not next_page_token:
            print("Reached the final page of results!")
            break
            
    return all_issues

def extract_field_value(raw_data, target_key='value'):
    """Safely extracts a specific string (like 'value' or 'name') from Jira custom fields."""
    if not raw_data:
        return 'Unassigned'
        
    # If Jira sends a list (e.g., [{'name': 'Alpha'}])
    if isinstance(raw_data, list) and len(raw_data) > 0:
        return ", ".join([item.get(target_key, str(item)) for item in raw_data if isinstance(item, dict)])
        
    # If Jira sends a standard dictionary (e.g., {'name': 'Alpha'})
    if isinstance(raw_data, dict):
        return raw_data.get(target_key, 'Unassigned')
        
    # If it's already just plain text
    return str(raw_data)

def process_lead_time(issues):
    """Calculates Lead Time and safely extracts custom fields for filtering."""
    data = []

    for issue in issues:
        # 1. Standard Fields
        key = issue['key']
        summary = issue['fields']['summary']
        
        # 2. Extract Custom Fields safely
        # ⚠️ Make sure these IDs match your actual Jira custom field IDs!
        cap_raw = extract_field_value(issue['fields'].get('customfield_13923'))
        vs_raw = extract_field_value(issue['fields'].get('customfield_10001'), 'name')

        cap_val = cap_raw.get('value', 'Unassigned') if isinstance(cap_raw, dict) else str(cap_raw) if cap_raw else 'Unassigned'
        vs_val = vs_raw.get('value', 'Unassigned') if isinstance(vs_raw, dict) else str(vs_raw) if vs_raw else 'Unassigned'

        # 3. Date Logic
        created_date = pd.to_datetime(issue['fields']['created'], utc=True)
        start_date = None
        end_date = None
        
        changelog = issue.get('changelog', {}).get('histories', [])
        changelog_sorted = sorted(changelog, key=lambda x: x['created'], reverse=False)

        for history in changelog_sorted:
            for item in history['items']:
                if item['field'] == 'status':
                    if item['toString'] == START_COLUMN and start_date is None:
                        start_date = pd.to_datetime(history['created'], utc=True)
                    elif item['toString'] in END_STATUSES:
                        end_date = pd.to_datetime(history['created'], utc=True)

        # 4. Safety Net & Lead Time Calculation
        if end_date is not None:
            if start_date is None:
                start_date = created_date 
                
            lead_time_days = round((end_date - start_date).total_seconds() / 86400, 1)
            
            # 5. Append perfectly matched data for the Lead Time chart
            if lead_time_days >= 0:
                data.append({
                    "Ticket ID": key,
                    "Summary": summary,
                    "Date Completed": end_date.strftime('%Y-%m-%d'),
                    "Lead Time (Days)": lead_time_days,
                    "Capability": cap_val,           # <-- NEW
                    "Value Stream": vs_val      # <-- NEW
                })

    return pd.DataFrame(data)

if __name__ == "__main__":
    print("Fetching completed Discovery items...")
    raw_issues = fetch_completed_issues()
    
    if raw_issues:
        df = process_lead_time(raw_issues)
        print(f"\nSuccessfully processed {len(df)} completed items.")
        
        # Calculate the 85th Percentile mathematically!
        if not df.empty:
            p85 = round(df['Lead Time (Days)'].quantile(0.85))
            print(f"🔥 85th Percentile Lead Time: {p85} Days 🔥")
        
        # Save to a NEW csv file for Pair 2
        df.to_csv("jira_lead_time_data.csv", index=False)
        print("\nSaved to jira_lead_time_data.csv for UI testing!")