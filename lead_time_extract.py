import os
import requests
import pandas as pd
import numpy as np
from requests.auth import HTTPBasicAuth

# --- CONFIGURATION ---
JIRA_URL = os.environ.get("JIRA_URL")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")

# 🚨 THE FIX: Explicitly forcing both projects, and ONLY pulling completed tickets!
JQL_QUERY = 'project in ("DP", "PLD") AND statusCategory = Done'


def extract_lead_time_data():
    print("🚀 Fetching Historical Lead Time Data...")
    url = f"{JIRA_URL}/rest/api/3/search/jql"
    auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Accept": "application/json"}
    
    all_issues = []
    next_page_token = None
    
    while True:
        payload = {
            "jql": JQL_QUERY,
            "maxResults": 100,
            "fields": [
                "summary", "status", "created", "resolutiondate", "statuscategorychangedate", 
                "customfield_13924", "customfield_13668"  # Your Roadmap IDs
            ]
        }
        if next_page_token:
            payload['nextPageToken'] = next_page_token
            
        response = requests.post(url, headers=headers, json=payload, auth=auth)
        if response.status_code != 200:
            print(f"🚨 API ERROR: {response.text}")
            break
            
        data = response.json()
        issues = data.get('issues', [])
        if not issues: break
        
        all_issues.extend(issues)
        next_page_token = data.get('nextPageToken')
        if not next_page_token: break

    records = []
    for issue in all_issues:
        fields = issue['fields']
        key = issue['key']
        summary = fields.get('summary', 'Unknown')
        
       # Calculate Lead Time (Excluding Weekends!)
        created = pd.to_datetime(fields.get('created')).tz_convert(None)
        
        # 🚨 THE FIX: Try Resolution Date first. If blank, use Status Change Date!
        resolved_str = fields.get('resolutiondate')
        if not resolved_str:
            resolved_str = fields.get('statuscategorychangedate')
            
        if resolved_str:
            resolved = pd.to_datetime(resolved_str).tz_convert(None)
            # numpy calculates business days between two dates
            lead_time = np.busday_count(created.date(), resolved.date())
        else:
            continue # Only skip if BOTH dates are completely missing
        
        # Safely parse Roadmap
        roadmap_field = fields.get('customfield_13924') or fields.get('customfield_13668')
        if isinstance(roadmap_field, dict):
            roadmap = roadmap_field.get('value', 'Unassigned')
        elif isinstance(roadmap_field, list) and len(roadmap_field) > 0:
            roadmap = roadmap_field[0].get('value', 'Unassigned')
        elif isinstance(roadmap_field, str):
            roadmap = roadmap_field
        else:
            roadmap = 'Unassigned'

        records.append({
            'Ticket ID': key, 
            'Summary': summary, 
            'Date Created': created, 
            'Date Completed': resolved,
            'Lead Time (Days)': max(1, lead_time), # Minimum 1 day
            'Roadmap': roadmap
        })

    df = pd.DataFrame(records)
    df.to_csv("jira_lead_time_data.csv", index=False)
    print(f"✅ Success! Saved {len(df)} Historical tickets.")

if __name__ == "__main__":
    extract_lead_time_data()