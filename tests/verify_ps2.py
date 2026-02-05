
import requests
import json
import time
import sys

BASE_URL = "http://localhost:8000"
REPO_ID = "f36207ab8c1e" # From previous step
RESULTS_FILE = "ps2_results.json"

TEST_CASES = [
    # --- Grounded Q&A ---
    {"category": "Grounded", "id": 1, "query": "Where is authentication handled?"},
    {"category": "Grounded", "id": 2, "query": "Where is database configuration defined?"},
    {"category": "Grounded", "id": 3, "query": "How are API routes registered?"},
    {"category": "Grounded", "id": 4, "query": "Where is environment/config loaded and validated?"},
    {"category": "Grounded", "id": 5, "query": "How do I add a new API endpoint following repo style?"},
    {"category": "Grounded", "id": 6, "query": "How do I run the project locally?"},
    {"category": "Grounded", "id": 14, "query": "How do I validate data using Schema?", "expected_citations": True},
    
    # --- Decomposition ---
    {"category": "Decomposition", "id": 7, "query": "Add payments support."},
    {"category": "Decomposition", "id": 8, "query": "Refactor to microservices."},
    
    # --- Refusal (Hallucination Bait) ---
    {"category": "Refusal", "id": 9, "query": "Show Kafka configuration"},
    {"category": "Refusal", "id": 10, "query": "Explain Redis cache layer"},
    {"category": "Refusal", "id": 11, "query": "Show GraphQL schema file"},
    
    # --- Generation ---
    {"category": "Generation", "id": 12, "query": "Generate a small endpoint similar to existing patterns", "endpoint": "/chat/generate"},
    {"category": "Generation", "id": 13, "query": "Generate PyTests for that endpoint", "endpoint": "/chat/generate"},
]

def run_verification():
    print(f"Starting PS2 Verification for Repo ID: {REPO_ID}")
    results = {}

    # 1. Indexing
    print("--- Step 1: Indexing ---")
    try:
        resp = requests.post(f"{BASE_URL}/repo/index", json={"repo_id": REPO_ID})
        print(f"Index trigger: {resp.status_code}")
    except Exception as e:
        print(f"Index failed: {e}")
        return

    # 2. Polling
    print("--- Step 2: Waiting for Ready ---")
    start_time = time.time()
    ready = False
    chunks = 0
    while time.time() - start_time < 120:
        try:
            resp = requests.get(f"{BASE_URL}/repo/status", params={"repo_id": REPO_ID})
            data = resp.json()
            is_indexed = data.get("indexed", False)
            chunks = data.get("chunk_count", 0)
            status = "ready" if is_indexed else "indexing"
            print(f"Status: {status}, Chunks: {chunks}")
            if is_indexed:
                ready = True
                break
        except Exception as e:
            print(f"Poll error: {e}")
        time.sleep(2)
    
    results["indexing"] = {"success": ready, "chunks": chunks, "time": time.time() - start_time}
    
    if not ready:
        print("Timeout waiting for indexing.")
        # Proceed anyway to see what happens, or abort?
        # Abort Q&A if not ready is risky, but let's try.
        
    # 3. Running Tests
    print("--- Step 3: Running Test Suite ---")
    test_results = []
    
    for test in TEST_CASES:
        print(f"Running Test {test['id']}: {test['query']} ({test['category']})")
        endpoint = test.get("endpoint", "/chat/ask")
        payload = {"repo_id": REPO_ID, "question": test["query"]} if endpoint == "/chat/ask" else {"repo_id": REPO_ID, "request": test["query"]}
        
        start_q = time.time()
        try:
            resp = requests.post(f"{BASE_URL}{endpoint}", json=payload)
            elapsed = time.time() - start_q
            
            if resp.status_code == 200:
                data = resp.json()
                passed = False
                notes = ""
                
                # Validation Logic
                if test["category"] == "Grounded":
                    cit_count = len(data.get("citations", []))
                    has_ans = len(data.get("answer", "")) > 10
                    passed = cit_count > 0 and has_ans
                    notes = f"Citations: {cit_count}"
                    
                elif test["category"] == "Refusal":
                    ans = data.get("answer", "").lower()
                    # Check for refusal language
                    refusal_terms = ["not find", "no context", "general knowledge", "could not locate"]
                    passed = any(term in ans for term in refusal_terms)
                    notes = "Refused as expected" if passed else "Hallucination warning?"
                    
                elif test["category"] == "Decomposition":
                    # Check if answer contains plan or if internal logs showed decomposition (hard to check via API unless we added a field)
                    # For now check output length and structure
                    passed = len(data.get("answer", "")) > 50
                    
                elif test["category"] == "Generation":
                    plan = data.get("plan", "")
                    diffs = data.get("diffs", [])
                    passed = len(diffs) > 0 or len(plan) > 50
                    notes = f"Diffs: {len(diffs)}"

                test_results.append({
                    "id": test["id"],
                    "category": test["category"],
                    "query": test["query"],
                    "passed": passed,
                    "notes": notes,
                    "response_snippet": str(data)[:200],
                    "elapsed": elapsed
                })
            else:
                test_results.append({"id": test["id"], "passed": False, "notes": f"HTTP {resp.status_code}"})
                
        except Exception as e:
             test_results.append({"id": test["id"], "passed": False, "notes": f"Exception: {e}"})
             
    results["tests"] = test_results
    
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {RESULTS_FILE}")

if __name__ == "__main__":
    run_verification()
