import os
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth
from datetime import timezone, datetime

# --- CONFIGURATION ---
JIRA_URL = os.environ.get("JIRA_URL")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")

if not all([JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN]):
    raise ValueError("Missing Jira credentials!")

# Cleaned up the JQL sandwich
JQL_QUERY = 'project = "PLD" AND status in ("Ready for Test/Build", "In Build (Done)", "Won\'t Do") AND updated >= -90d ORDER BY created DESC'

START_COLUMN = "To Do Ideas" 
END_STATUSES = ["Ready for Test/Build", "In Build (Done)", "Won't Do"]

def fetch_completed_issues():
    url = f"{JIRA_URL}/rest/api/3/search/jql" 
    auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Accept": "application/json"}
    
    all_issues = []
    max_results = 100
    next_page_token = None 

    print("Fetching completed items...", flush=True)
    while True:
        if len(all_issues) >= 1000:
            print("🛑 Circuit breaker tripped! Hit 1000 tickets.", flush=True)
            break

        # 🚨 THE FIX: Convert to a payload dictionary with a list for fields
        payload = {
            'jql': JQL_QUERY, 
            'maxResults': max_results,
            'expand': 'changelog', 
            'fields': ['summary', 'status', 'created', 'customfield_13923', 'customfield_10001', 'customfield_13924']
        }
        
        if next_page_token:
            payload['nextPageToken'] = next_page_token

        # 🚨 THE FIX: Use requests.post() and json=payload
        response = requests.post(url, headers=headers, json=payload, auth=auth)
        
        if response.status_code != 200:
            print(f"🚨 JIRA API ERROR: {response.status_code}", flush=True)
            print(response.text, flush=True)
            exit(1)
        
        data = response.json()
        batch = data.get('issues', [])
        
        if not batch:
            break 
            
        all_issues.extend(batch)
        print(f"Fetched {len(all_issues)} tickets so far...", flush=True)
        
        next_page_token = data.get('nextPageToken')
        if not next_page_token:
            print(f"🎯 JIRA SAYS IT FOUND: {len(all_issues)} completed tickets!", flush=True)
            break
            
    return all_issues

def extract_field_value(raw_data, target_key='value'):
    if not raw_data: return 'Unassigned'
    if isinstance(raw_data, list) and len(raw_data) > 0:
        return ", ".join([item.get(target_key, str(item)) for item in raw_data if isinstance(item, dict)])
    if isinstance(raw_data, dict):
        return raw_data.get(target_key, 'Unassigned')
    return str(raw_data)

def process_lead_time(issues):
    data = []

    for issue in issues:
        key = issue['key']
        summary = issue['fields']['summary']
        
        # 'Problem to Address' needs 'value'
        problem_val = extract_field_value(issue['fields'].get('customfield_13923'), 'value')
        
        # 'Team' needs 'name'
        vs_val = extract_field_value(issue['fields'].get('customfield_10001'), 'name')
        
        # 'Roadmap' usually uses 'value' (Change to 'name' if it outputs a dictionary too!)
        roadmap_val = extract_field_value(issue['fields'].get('customfield_13924'), 'value')

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

        if end_date is not None:
            if start_date is None:
                start_date = created_date 
                
            lead_time_days = round((end_date - start_date).total_seconds() / 86400, 1)
            
            if lead_time_days >= 0:
                data.append({
                    "Ticket ID": key,
                    "Summary": summary,
                    "Date Completed": end_date.strftime('%Y-%m-%d'),
                    "Lead Time (Days)": lead_time_days,
                    "Problem to Address": problem_val,
                    "Team": vs_val,      # Swapped to "Team" so Streamlit doesn't crash!
                    "Roadmap": roadmap_val
                })

    return pd.DataFrame(data)

if __name__ == "__main__":
    print("Fetching completed Discovery items...", flush=True)
    raw_issues = fetch_completed_issues()
    
    if raw_issues:
        df = process_lead_time(raw_issues)
        print(f"\nSuccessfully processed {len(df)} completed items.", flush=True)
        
        if not df.empty:
            p85 = round(df['Lead Time (Days)'].quantile(0.85))
            print(f"🔥 85th Percentile Lead Time: {p85} Days 🔥", flush=True)
        
        df.to_csv("jira_lead_time_data.csv", index=False)
        print("\n✅ Saved to jira_lead_time_data.csv!", flush=True)
    else:
        print("⚠️ WARNING: 0 completed issues were found! The CSV will NOT be updated.", flush=True)