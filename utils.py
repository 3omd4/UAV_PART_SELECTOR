import requests
import base64
import json
import streamlit as st
import requests

def fetch_uavs_fyi():
    """Fetches components from UAVs.fyi API."""
    url = "https://www.uavs.fyi/api/v1/components.json"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return {}

def fetch_uas_forge():
    """Fetches parts dataset from UAS-Forge / droneclear_forge repo."""
    url = "https://raw.githubusercontent.com/DroneWuKong/forge-data/main/parts.json"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return {}

def sync_external_data(session_state, local_file="custom_database.json"):
    """
    Pulls remote datasets, normalizes keys to match CATEGORIES,
    and commits updates to both session_state and custom_database.json.
    """
    valid_categories = ["MOTORS", "FLIGHT_CONTROLLERS", "SBCS", "INTEGRATED_BOARDS", "FRAMES", "BATTERIES"]
    
    uavs_data = fetch_uavs_fyi()
    forge_data = fetch_uas_forge()
    
    added_count = 0
    
    for payload in [uavs_data, forge_data]:
        if not isinstance(payload, dict):
            continue
            
        for raw_cat, items in payload.items():
            cat = raw_cat.upper()
            if cat in valid_categories and isinstance(items, dict):
                for part_name, part_specs in items.items():
                    if part_name not in session_state[cat]:
                        session_state[cat][part_name] = part_specs
                        added_count += 1
                    else:
                        session_state[cat][part_name].update(part_specs)

    # Persist the merged session state back to local JSON
    export_payload = {cat: session_state[cat] for cat in valid_categories}
    with open(local_file, "w", encoding="utf-8") as f:
        json.dump(export_payload, f, indent=2)
        
    return added_count
    
def commit_to_github(payload_dict, target_file="custom_database.json"):
    if "GITHUB_TOKEN" not in st.secrets or "GITHUB_REPO" not in st.secrets:
        return False, "GitHub credentials missing in st.secrets."
    token = st.secrets["GITHUB_TOKEN"]
    repo = st.secrets["GITHUB_REPO"]
    url = f"https://api.github.com/repos/{repo}/contents/{target_file}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}
    
    res = requests.get(url, headers=headers)
    sha = res.json().get("sha") if res.status_code == 200 else None
    
    b64_content = base64.b64encode(json.dumps(payload_dict, indent=2).encode("utf-8")).decode("utf-8")
    data = {"message": f"Update {target_file} from web UI", "content": b64_content}
    if sha:
        data["sha"] = sha
        
    put_res = requests.put(url, headers=headers, json=data)
    if put_res.status_code in [200, 201]:
        return True, "Successfully committed updates to GitHub repository."
    return False, f"API Error: {put_res.json().get('message', 'Failed to commit')}"