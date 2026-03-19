import requests
import pandas as pd
from requests.auth import HTTPBasicAuth

# --- CONFIGURATION ---
JIRA_URL = os.environ.get("JIRA_URL")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")

def extract_cfd_history():
    print("🕰️ Starting the Modernized CFD Time Machine...")
    
    # 🚨 THE FIX: Back to the modern API endpoint!
    url = f"{JIRA_URL}/rest/api/3/search/jql" 
    
    auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Accept": "application/json"}
    
    all_issues = []
    next_page_token = None
    
    # 1. Fetch all tickets and their changelogs using nextPageToken
    while True:
        payload = {
            'jql': JQL_QUERY,
            'maxResults': 100,
            'expand': 'changelog', 
            'fields': ['created', 'status', 'customfield_10012'] 
        }
        
        # Add the token if we are flipping to page 2, 3, etc.
        if next_page_token:
            payload['nextPageToken'] = next_page_token
            
        response = requests.post(url, headers=headers, json=payload, auth=auth)
        
        if response.status_code != 200:
            print(f"🚨 API ERROR: {response.status_code}")
            print(response.text) 
            break
            
        data = response.json()
        issues = data.get('issues', [])
        
        if not issues:
            break
            
        all_issues.extend(issues)
        print(f"📥 Fetched {len(all_issues)} tickets...")
        
        # Grab the token for the next page, or break if we're done
        next_page_token = data.get('nextPageToken')
        if not next_page_token:
            break

    if not all_issues:
        print("⚠️ No issues found. Double check your JQL.")
        return

    print("🔄 Processing changelogs...")
    # 2. Process the changelogs into a daily history log
    records = []
    for issue in all_issues:
        key = issue['key']
        
        # Safely grab the Team Name
        team_field = issue['fields'].get('customfield_10012')
        team = team_field.get('name', 'Unassigned') if isinstance(team_field, dict) else 'Unassigned'
        
        # Parse the changelog to find every status movement
        histories = issue.get('changelog', {}).get('histories', [])
        
        status_changes = []
        for h in histories:
            for item in h['items']:
                if item['field'] == 'status':
                    status_changes.append({
                        'date': pd.to_datetime(h['created']).tz_convert(None).normalize(), 
                        'from': item['fromString'],
                        'to': item['toString']
                    })
        
        # Sort chronologically
        status_changes = sorted(status_changes, key=lambda x: x['date'])
        
        # Figure out what the very first status was on the day it was created
        created_date = pd.to_datetime(issue['fields']['created']).tz_convert(None).normalize()
        initial_status = status_changes[0]['from'] if status_changes and status_changes[0]['from'] else "To Do"
        
        # Record the ticket's birth
        records.append({'Ticket ID': key, 'Team': team, 'Date': created_date, 'Status': initial_status})
        
        # Record every time it moved to a new column
        for change in status_changes:
            records.append({'Ticket ID': key, 'Team': team, 'Date': change['date'], 'Status': change['to']})

    # 3. Save to a new CSV file
    df = pd.DataFrame(records)
    df.to_csv("jira_cfd_data.csv", index=False)
    print(f"✅ Success! Saved {len(df)} historical status transitions to jira_cfd_data.csv")

if __name__ == "__main__":
    extract_cfd_history()