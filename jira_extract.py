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

# ⚠️ Check this! Is "PLD" the right project? If it should be "DISC", change it here!
JQL_QUERY = 'project = "PLD" AND statusCategory != Done' 

def fetch_jira_issues():
    url = f"{JIRA_URL}/rest/api/3/search/jql" 
    auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Accept": "application/json"}
    
    query = {
        'jql': JQL_QUERY,
        'maxResults': 100, 
        'expand': 'changelog', 
        # Aligned these IDs so they perfectly match the extraction loop below
        'fields': 'summary,status,created,customfield_13923,customfield_10001,customfield_13924'
    }

    response = requests.get(url, headers=headers, params=query, auth=auth)

    if response.status_code != 200:
        print(f"🚨 JIRA API ERROR: {response.status_code}", flush=True)
        print(response.text, flush=True)
        exit(1) 

    jira_data = response.json()
    print(f"🎯 JIRA SAYS IT FOUND: {jira_data.get('total', 'UNKNOWN')} tickets!", flush=True)
    
    return jira_data.get('issues', [])

def extract_field_value(raw_data, target_key='value'):
    if not raw_data: return 'Unassigned'
    if isinstance(raw_data, list) and len(raw_data) > 0:
        return ", ".join([item.get(target_key, str(item)) for item in raw_data if isinstance(item, dict)])
    if isinstance(raw_data, dict):
        return raw_data.get(target_key, 'Unassigned')
    return str(raw_data)

def process_issues_to_dataframe(issues):
    data = []
    now = datetime.now(timezone.utc)

    for issue in issues:
        key = issue['key']
        summary = issue['fields']['summary']
        current_status = issue['fields']['status']['name']
        
        # 'Problem to Address' needs 'value'
        problem_val = extract_field_value(issue['fields'].get('customfield_13923'), 'value')
        
        # 'Team' needs 'name'
        vs_val = extract_field_value(issue['fields'].get('customfield_10001'), 'name')
        
        # 'Roadmap' usually uses 'value' (Change to 'name' if it outputs a dictionary too!)
        roadmap_val = extract_field_value(issue['fields'].get('customfield_13924'), 'value')

        status_start_date_str = issue['fields'].get('created')
        changelog = issue.get('changelog', {}).get('histories', [])
        for history in sorted(changelog, key=lambda x: x['created'], reverse=True):
            for item in history['items']:
                if item['field'] == 'status' and item['toString'] == current_status:
                    status_start_date_str = history['created']
                    break 
            else: continue
            break

        status_start_date = pd.to_datetime(status_start_date_str, utc=True)
        
        if pd.isna(status_start_date):
            status_start_date = now
            days_in_status = 0
        else:
            days_in_status = (now - status_start_date).days

        data.append({
            "Ticket ID": key,
            "Summary": summary,
            "Current Status": current_status,
            "Date Entered Status": status_start_date.strftime('%Y-%m-%d'),
            "Days in Current Status": days_in_status,
            "Problem to Address": problem_val,
            "Team": vs_val,
            "Roadmap": roadmap_val
        })

    return pd.DataFrame(data)

if __name__ == "__main__":
    print("Fetching data from Jira...", flush=True)
    raw_issues = fetch_jira_issues()
    
    if raw_issues:
        print(f"Found {len(raw_issues)} issues. Processing data...", flush=True)
        df = process_issues_to_dataframe(raw_issues)
        
        df.to_csv("jira_discovery_data.csv", index=False)
        print("\n✅ Saved to jira_discovery_data.csv!", flush=True)
    else:
        print("⚠️ WARNING: 0 issues were found! The CSV will NOT be updated.", flush=True)