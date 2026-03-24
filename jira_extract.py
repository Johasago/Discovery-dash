import os
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth
from datetime import timezone, datetime

# --- CONFIGURATION ---
JIRA_URL = os.environ.get("JIRA_URL")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")

def extract_wip_data():
    print("🔄 Fetching Active WIP Data...")
    url = f"{JIRA_URL}/rest/api/3/search/jql"
    auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Accept": "application/json"}
    
    all_issues = []
    next_page_token = None
    
    while True:
        payload = {
            "jql": JQL_QUERY,
            "maxResults": 100,
            # Make sure these are the EXACT IDs you found earlier
            "fields": [
                "summary", "status", "statuscategorychangedate", 
                "customfield_13924", "customfield_13668" 
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

    print(f"📥 Total tickets fetched: {len(all_issues)}")

    # ==========================================
    # 🚨 THE TRUTH SERUM: Print the raw data for Ticket #1
    # ==========================================
    if all_issues:
        first_ticket = all_issues[0]
        print(f"\n--- RAW DATA FOR {first_ticket['key']} ---")
        for field_key, field_value in first_ticket['fields'].items():
            if "customfield" in field_key or field_key == "summary":
                print(f"{field_key}: {field_value}")
        print("--------------------------------------\n")
    # ==========================================

    records = []
    for issue in all_issues:
        fields = issue['fields']
        key = issue['key']
        summary = fields.get('summary', 'Unknown')
        status = fields.get('status', {}).get('name', 'Unknown')
        
        status_date_str = fields.get('statuscategorychangedate')
        if status_date_str:
            status_date = pd.to_datetime(status_date_str).tz_convert(None)
            days_in_status = (pd.Timestamp.now() - status_date).days
        else:
            status_date, days_in_status = None, 0

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
            'Ticket ID': key, 'Summary': summary, 'Current Status': status,
            'Days in Current Status': max(0, days_in_status),
            'Date Entered Status': status_date,
            'Roadmap': roadmap
        })

    df = pd.DataFrame(records)
    df.to_csv("jira_discovery_data.csv", index=False)
    print(f"✅ Success! Saved {len(df)} WIP tickets.")

if __name__ == "__main__":
    extract_wip_data()