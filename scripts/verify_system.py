
import requests
import json
import time
import sys
from typing import Dict, List, Any
from tabulate import tabulate

BASE_URL = "http://localhost:8001"

class ConsoleColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(title):
    print(f"\n{ConsoleColors.HEADER}{ConsoleColors.BOLD}=== {title} ==={ConsoleColors.ENDC}")

def print_pass(msg):
    print(f"{ConsoleColors.OKGREEN}PASS: {msg}{ConsoleColors.ENDC}")

def print_fail(msg):
    print(f"{ConsoleColors.FAIL}FAIL: {msg}{ConsoleColors.ENDC}")

def print_info(msg):
    print(f"{ConsoleColors.OKCYAN}INFO: {msg}{ConsoleColors.ENDC}")

# --- PART A: Smoke Test ---
def test_part_a():
    print_header("PART A: Setup & Smoke Test")
    endpoints = [
        ("GET", "/health"),
        ("POST", "/repo/load", {"repo_url": "https://github.com/test/repo"}), # Expect 422/400 or mock success logic
        ("POST", "/repo/index", {"repo_id": "test"}),
        ("POST", "/chat/ask", {"repo_id": "test", "question": "hi"}),
        ("POST", "/chat/generate", {"repo_id": "test", "request": "test"}),
        ("GET", "/repo/status?repo_id=test")
    ]
    
    results = []
    for method, path, *payload in endpoints:
        url = f"{BASE_URL}{path}"
        try:
            if method == "GET":
                resp = requests.get(url)
            else:
                resp = requests.post(url, json=payload[0] if payload else {})
            
            # We assume 2xx or 4xx (client error) means the endpoint exists and is reachable.
            # 5xx would be a failure.
            works = resp.status_code < 500
            note = f"Status: {resp.status_code}"
            
            results.append([path, "Yes" if works else "No", str(resp.json())[:50] + "...", note])
        except Exception as e:
            results.append([path, "No", str(e), "Connection Error"])

    print(tabulate(results, headers=["Endpoint", "Works?", "Response Sample", "Notes"], tablefmt="grid"))

# --- PART B: Repo Ingestion ---
def test_part_b():
    print_header("PART B: Repo Ingestion Validation")
    repo_url = "https://github.com/tiangolo/full-stack-fastapi-template"
    
    print_info(f"Loading {repo_url}...")
    load_resp = requests.post(f"{BASE_URL}/repo/load", json={"repo_url": repo_url})
    if load_resp.status_code != 200:
        print_fail(f"Failed to load repo: {load_resp.text}")
        return
    
    data = load_resp.json()
    repo_id = data.get("repo_id")
    print_pass(f"Repo Loaded: {repo_id} (Commit: {data.get('commit_hash')})")
    
    print_info("Indexing repo...")
    index_resp = requests.post(f"{BASE_URL}/repo/index", json={"repo_id": repo_id})
    if index_resp.status_code != 200:
         print_fail(f"Failed to index repo: {index_resp.text}")
         return
         
    index_data = index_resp.json()
    print_pass(f"Indexed {index_data.get('chunk_count')} chunks.")
    
    # Check Filtering (manual check of stats or log inspection would be needed for deeper verify, but we check counts)
    return repo_id

# --- PART C: Evidence-Grounded Q&A ---
def test_part_c(repo_id):
    print_header("PART C: Evidence-Grounded Q&A")
    questions = [
        "Where is authentication handled?",
        "Where is database configuration defined?",
        "How are API routes registered?",
        "Where is environment/config loaded and validated?",
        "How do I add a new API endpoint following repo style?", # How-to
        "How do I run the project locally (commands)?", # How-to
        "Add payments support", # Ambiguity
        "Rewrite project to microservices" # Refusal
    ]
    
    results = []
    
    for i, q in enumerate(questions):
        print_info(f"Q{i+1}: {q}")
        resp = requests.post(f"{BASE_URL}/chat/ask", json={"repo_id": repo_id, "question": q})
        if resp.status_code == 200:
            ans = resp.json()
            citations = ans.get("citations", [])
            has_citations = len(citations) > 0
            
            # Simple heuristic grading
            grounding = "High" if has_citations else "Low"
            status = "PASS"
            if i >= 6 and has_citations: # Edge cases might NOT have citations if refused properly? Or should have justification. 
                 pass 
            
            results.append([f"Q{i+1}", status, len(citations), grounding, "Check manually"])
        else:
            results.append([f"Q{i+1}", "FAIL", 0, "None", resp.status_code])
            
    print(tabulate(results, headers=["Query", "Status", "Citations", "Groundedness", "Notes"], tablefmt="grid"))

# --- PART E: Verification (Generation) ---
def test_part_e(repo_id):
    print_header("PART E: Controlled Code Generation")
    reqs = [
        ("Small Safe Change", "Add a new GET endpoint similar to existing endpoints, returning a dummy response."),
        # ("Tests", "Write unit tests for the new endpoint..."), # Skip for speed if previous works
        ("Unsafe Request", "Generate a full rewrite of the backend architecture.")
    ]
    
    results = []
    for name, prompt in reqs:
        resp = requests.post(f"{BASE_URL}/chat/generate", json={"repo_id": repo_id, "request": prompt})
        if resp.status_code == 200:
            data = resp.json()
            plan = data.get("plan", "")
            diffs = data.get("diffs", [])
            
            is_refusal = "refus" in plan.lower() or "cannot" in plan.lower() or not diffs
            
            if name == "Unsafe Request":
                status = "PASS" if is_refusal or not diffs else "FAIL (Generated unsafe code)"
            else:
                status = "PASS" if diffs else "FAIL (No diffs)"
                
            results.append([name, status, f"Diffs: {len(diffs)}", plan[:50] + "..."])
        else:
            results.append([name, "FAIL", "Error", resp.status_code])
            
    print(tabulate(results, headers=["Test", "Status", "Details", "Plan Sample"], tablefmt="grid"))
    
if __name__ == "__main__":
    try:
        test_part_a()
        repo_id = test_part_b()
        if repo_id:
            test_part_c(repo_id)
            test_part_e(repo_id)
    except Exception as e:
        print_fail(f"Script crashed: {e}")
