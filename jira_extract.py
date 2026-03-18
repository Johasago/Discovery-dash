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
JQL_QUERY = 'project = "PLD" AND statusCategory != Done' 

def fetch_jira_issues():
    """Fetches issues from Jira using the updated v3 search/jql GET API."""
    # The new correct endpoint:
    url = f"{JIRA_URL}/rest/api/3/search/jql" 
    auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
    
    headers = {
        "Accept": "application/json"
    }
    
    # Back to the standard dictionary parameters
    query = {
        'jql': JQL_QUERY,
        'maxResults': 100, 
        'expand': 'changelog', 
        # ADD 'created' to the list below:
        # Add both custom field IDs to the fields list
        'fields': 'summary,status,created, customfield_13923, customfield_10001, customfield_13924'
    }

    # Back to requests.get!
    response = requests.get(url, headers=headers, params=query, auth=auth)
    
    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")
        return []
        
    return response.json().get('issues', [])

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

def process_issues_to_dataframe(issues):
    """Flattens the Jira JSON into a DataFrame, including custom fields and dates."""
    data = []
    now = datetime.now(timezone.utc)

    for issue in issues:
        # 1. Standard Fields
        key = issue['key']
        summary = issue['fields']['summary']
        current_status = issue['fields']['status']['name']
        
        # 2. Custom Fields (Safely extract Team and Value Stream)
        # ⚠️ Make sure these IDs match your actual Jira custom field IDs!
        cap_raw = extract_field_value(issue['fields'].get('customfield_13924'))
        vs_raw = extract_field_value(issue['fields'].get('customfield_10001'), 'name')

        cap_val = cap_raw.get('value', 'Unassigned') if isinstance(cap_raw, dict) else str(cap_raw) if cap_raw else 'Unassigned'
        vs_val = vs_raw.get('name', 'Unassigned') if isinstance(vs_raw, dict) else str(vs_raw) if vs_raw else 'Unassigned'

        # 3. Date Logic (Fallback to created date)
        status_start_date_str = issue['fields'].get('created')
        
        # Dig into the changelog
        changelog = issue.get('changelog', {}).get('histories', [])
        for history in sorted(changelog, key=lambda x: x['created'], reverse=True):
            for item in history['items']:
                if item['field'] == 'status' and item['toString'] == current_status:
                    status_start_date_str = history['created']
                    break 
            else:
                continue
            break

        # 4. Safe Conversion
        status_start_date = pd.to_datetime(status_start_date_str, utc=True)
        
        # THE SAFETY NET
        if pd.isna(status_start_date):
            status_start_date = now
            days_in_status = 0
        else:
            days_in_status = (now - status_start_date).days

        # 5. Append everything to the list
        data.append({
            "Ticket ID": key,
            "Summary": summary,
            "Current Status": current_status,
            "Date Entered Status": status_start_date.strftime('%Y-%m-%d'),
            "Days in Current Status": days_in_status,
            "Capability": cap_val,
            "Team": vs_val
        })

    return pd.DataFrame(data)

if __name__ == "__main__":
    print("Fetching data from Jira...")
    raw_issues = fetch_jira_issues()
    
    if raw_issues:
        print(f"Found {len(raw_issues)} issues. Processing data...")
        df = process_issues_to_dataframe(raw_issues)
        
        print("\n--- LIVE JIRA DATA ---")
        print(df.head(10)) # Print the first 10 rows to the terminal
        
        # Optional: Save to CSV so Pair 2 (UI) can build charts without hitting the API constantly during the hackathon
        df.to_csv("jira_discovery_data.csv", index=False)
        print("\nSaved to jira_discovery_data.csv for UI testing!")