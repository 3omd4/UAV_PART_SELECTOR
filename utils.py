import requests
import base64
import json
import streamlit as st

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

def _fetch_github_directory_recursive(url, headers):
    """Recursively fetches all file metadata inside a GitHub directory."""
    files_to_download = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return files_to_download
            
        for item in res.json():
            if item["type"] == "file" and item["name"].endswith(".json"):
                files_to_download.append(item)
            elif item["type"] == "dir":
                # Recursively extract files from subdirectories
                files_to_download.extend(_fetch_github_directory_recursive(item["url"], headers))
    except Exception:
        pass
    return files_to_download

def ingest_forge_data():
    """
    Fetches JSON component datasets from DroneWuKong/forge-data repository.
    Handles recursive directories, array/dict normalization, and rate limiting.
    """
    api_url = "https://api.github.com/repos/DroneWuKong/forge-data/contents/parts"
    headers = {"Accept": "application/vnd.github.v3+json"}
    
    if "GITHUB_TOKEN" in st.secrets:
        headers["Authorization"] = f"Bearer {st.secrets['GITHUB_TOKEN']}"
        
    try:
        # Step 1: Recursively map the directory tree
        files = _fetch_github_directory_recursive(api_url, headers)
        
        if not files:
            # Check if rate limit was exceeded by doing a direct test
            test_res = requests.get(api_url, headers=headers)
            if test_res.status_code == 403:
                return False, "GitHub API Rate Limit Exceeded. Add GITHUB_TOKEN to st.secrets.", 0
            return False, f"No JSON files found at target. API Status: {test_res.status_code}", 0
            
        added_count = 0
        
        for file_obj in files:
            raw_url = file_obj.get("download_url")
            if not raw_url:
                continue
                
            raw_res = requests.get(raw_url, timeout=10)
            if raw_res.status_code == 200:
                try:
                    external_parts = raw_res.json()
                except json.JSONDecodeError:
                    continue
                
                # Step 2: Normalize Arrays to Dictionaries
                if isinstance(external_parts, list):
                    temp_dict = {}
                    for item in external_parts:
                        if isinstance(item, dict):
                            # Try multiple common name keys
                            name = item.get("name") or item.get("model") or item.get("id") or item.get("part_name")
                            if name:
                                temp_dict[name] = item
                    external_parts = temp_dict
                
                if not isinstance(external_parts, dict):
                    continue
                    
                # Step 3: Schema Mapping Logic
                for part_name, specs in external_parts.items():
                    target_cat = None
                    path_lower = file_obj.get("path", "").lower()
                    
                    if "motor" in path_lower or "kv" in specs:
                        target_cat = "MOTORS"
                    elif "batter" in path_lower or "lipo" in path_lower or "mah" in specs:
                        target_cat = "BATTERIES"
                    elif "sbc" in path_lower or "companion" in path_lower or "ai_tops" in specs:
                        target_cat = "SBCS"
                    elif "fc" in path_lower or "flight_controller" in path_lower or "mcu" in specs:
                        target_cat = "FLIGHT_CONTROLLERS"
                    elif "frame" in path_lower or "wheelbase" in specs or "wheelbase_mm" in specs:
                        target_cat = "FRAMES"
                    elif "integrated" in path_lower or "arch" in specs:
                        target_cat = "INTEGRATED_BOARDS"
                        
                    if target_cat and target_cat in st.session_state:
                        # Safety: ensure specs is a dict before assignment
                        if not isinstance(specs, dict):
                            continue
                            
                        specs["source"] = "UAS-Forge (External)"
                        
                        # Normalize dual weight representations
                        w_val = specs.get("weight") or specs.get("weight_g") or 0.0
                        specs["weight"] = w_val
                        specs["weight_g"] = w_val
                        
                        # Normalize price representations
                        if "price_usd" not in specs and "price" in specs:
                            specs["price_usd"] = specs["price"]
                            specs["price_egp"] = float(specs["price"]) * 50.0 
                        elif "price_usd" in specs and "price_egp" not in specs:
                            specs["price_egp"] = float(specs["price_usd"]) * 50.0
                            
                        st.session_state[target_cat][part_name] = specs
                        added_count += 1
                                
        if added_count == 0:
            return False, f"Fetched {len(files)} files, but no schemas matched app categories.", 0
            
        return True, "Data successfully ingested.", added_count
        
    except Exception as e:
        return False, f"Pipeline exception: {str(e)}", 0