import requests
import json
import time

API_URL = "http://127.0.0.1:8000/chat/ask"
REPO_ID = "repopilot" # Using actual repo name found in data dir

questions = [
    # EASY
    {"level": "Easy", "q": "What does this repo do?"},
    {"level": "Easy", "q": "What frameworks are used in the backend?"},
    {"level": "Easy", "q": "Who are you?"},
    
    # MEDIUM
    {"level": "Medium", "q": "How is the Answerer class implemented?"},
    {"level": "Medium", "q": "Where is the vector store configuration defined?"},
    {"level": "Medium", "q": "How does the health check endpoint work?"},
    {"level": "Medium", "q": "What is the system prompt for the Planner?"},

    # HARD
    {"level": "Hard", "q": "Trace the flow of a chat request from the API to the LLM."},
    {"level": "Hard", "q": "How would I add a new retrieval provider to the codebase?"},
    {"level": "Hard", "q": "What happens if the LLM fails to generate valid JSON in the answerer?"}
]

def run_tests():
    print(f"Running {len(questions)} QA Tests against {API_URL}...\n")
    
    results = []
    
    for i, item in enumerate(questions):
        q = item["q"]
        level = item["level"]
        print(f"[{i+1}/{len(questions)}] [{level}] Asking: {q}")
        
        start_time = time.time()
        try:
            payload = {
                "repo_id": REPO_ID, 
                "question": q,
                "decompose": False
            }
            response = requests.post(API_URL, json=payload, timeout=60)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "")
                citations = data.get("citations", [])
                confidence = data.get("confidence", "unknown")
                
                print(f"   [PASS] Status: 200 ({elapsed:.2f}s)")
                print(f"   Confidence: {confidence}")
                print(f"   Citations: {len(citations)}")
                print(f"   Preview: {answer[:100].replace(chr(10), ' ')}...")
                results.append({"q": q, "status": "PASS", "details": f"{confidence}, {len(citations)} citations"})
            else:
                print(f"   [FAIL] Status: {response.status_code}")
                original_error = response.text
                print(f"   Error: {original_error}")
                results.append({"q": q, "status": "FAIL", "details": f"Status {response.status_code}"})
                
        except Exception as e:
            print(f"   [ERR] Exception: {e}")
            results.append({"q": q, "status": "ERROR", "details": str(e)})
        
        print("-" * 50)
        time.sleep(1) # Slight pause to be nice to rate limits

    print("\n--- Summary ---")
    for r in results:
        print(f"{r['status']} | {r['q'][:40]:<40} | {r['details']}")

if __name__ == "__main__":
    run_tests()
