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
            if item.get("type") == "file" and item.get("name", "").endswith(".json"):
                files_to_download.append(item)
            elif item.get("type") == "dir":
                files_to_download.extend(_fetch_github_directory_recursive(item["url"], headers))
    except Exception:
        pass
    return files_to_download

def ingest_forge_data():
    """
    Recursively fetches, flattens, and normalizes external hardware datasets from UAS-Forge.
    Ensures all links, weights, and specifications map correctly to internal application schemas.
    """
    api_url = "https://api.github.com/repos/DroneWuKong/forge-data/contents/parts"
    headers = {"Accept": "application/vnd.github.v3+json"}
    
    if "GITHUB_TOKEN" in st.secrets:
        headers["Authorization"] = f"Bearer {st.secrets['GITHUB_TOKEN']}"
        
    try:
        files = _fetch_github_directory_recursive(api_url, headers)
        if not files:
            return False, "No JSON files found in remote repository path.", 0
            
        added_count = 0
        
        for file_obj in files:
            raw_url = file_obj.get("download_url")
            if not raw_url:
                continue
                
            raw_res = requests.get(raw_url, timeout=10)
            if raw_res.status_code != 200:
                continue
                
            try:
                external_data = raw_res.json()
            except json.JSONDecodeError:
                continue
                
            # Flatten lists or category-wrapped dictionaries into a clean {name: specs} mapping
            parts_dict = {}
            if isinstance(external_data, list):
                for item in external_data:
                    if isinstance(item, dict):
                        name = item.get("name") or item.get("model") or item.get("id") or item.get("part_name")
                        if name:
                            parts_dict[str(name)] = item
            elif isinstance(external_data, dict):
                # Check if the dict is wrapped in a top-level category key (e.g., {"motors": {...}})
                if len(external_data) == 1 and isinstance(list(external_data.values())[0], dict):
                    inner_val = list(external_data.values())[0]
                    if any(isinstance(v, dict) for v in inner_val.values()):
                        parts_dict = inner_val
                    else:
                        parts_dict = external_data
                else:
                    parts_dict = external_data
            
            for part_name, specs in parts_dict.items():
                if not isinstance(specs, dict):
                    continue
                    
                path_lower = file_obj.get("path", "").lower()
                target_cat = None
                
                # Category Routing Heuristics
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
                    normalized = dict(specs)
                    normalized["source"] = "UAS-Forge (External)"
                    
                    # 1. Normalize Vendor Links for Clickable LinkColumns
                    raw_url_val = (
                        normalized.get("buy_url") or 
                        normalized.get("url") or 
                        normalized.get("link") or 
                        normalized.get("website") or 
                        normalized.get("store_url") or 
                        ""
                    )
                    normalized["buy_url"] = str(raw_url_val) if raw_url_val else "https://github.com/DroneWuKong/forge-data"
                    
                    # 2. Normalize Weights
                    w_val = normalized.get("weight") or normalized.get("weight_g") or normalized.get("mass") or 0.0
                    normalized["weight"] = float(w_val) if w_val else 0.0
                    normalized["weight_g"] = float(w_val) if w_val else 0.0
                    
                    # 3. Normalize Pricing
                    p_val = normalized.get("price_usd") or normalized.get("price") or normalized.get("cost") or 0.0
                    try:
                        p_float = float(p_val)
                    except Exception:
                        p_float = 0.0
                    normalized["price_usd"] = p_float
                    normalized["price_egp"] = p_float * 50.0
                    
                    st.session_state[target_cat][str(part_name)] = normalized
                    added_count += 1
                    
        if added_count == 0:
            return False, "Fetched files, but none mapped to application categories.", 0
            
        return True, "Data successfully ingested and normalized.", added_count
        
    except Exception as e:
        return False, f"Pipeline exception: {str(e)}", 0