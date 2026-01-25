import httpx
import asyncio
import json
import sys
import os

BASE_URL = "http://localhost:8000"
REPO_LOCAL = os.getcwd().replace("\\", "/") # Self

async def test_endpoint(client, method, path, payload=None):
    try:
        if method == "GET":
            r = await client.get(f"{BASE_URL}{path}")
        else:
            r = await client.post(f"{BASE_URL}{path}", json=payload)
        return r
    except Exception as e:
        return f"Error: {e}"

async def main():
    async with httpx.AsyncClient() as client:
        log = []
        def pr(s):
            print(s)
            log.append(s)
            
        # Check health
        h = await test_endpoint(client, "GET", "/health")
        if isinstance(h, str) or h.status_code != 200:
            pr("Server down!")
            with open("verification_results.txt", "w", encoding="utf-8") as f:
                f.write("\n".join(log))
            return
        
        pr(f"Health: {h.json()}")
        
        # Smoke
        pr("\n--- Part A: Smoke Test ---")
        endpoints = [
            ("GET", "/health", None),
        ]
        for method, path, payload in endpoints:
            r = await test_endpoint(client, method, path, payload)
            status = r.status_code if hasattr(r, "status_code") else "Error"
            pr(f"{method} {path} -> {status}")

        # Ingestion (Local)
        pr("\n--- Part B: Ingestion (Self) ---")
        pr(f"Loading {REPO_LOCAL}...")
        r = await client.post(f"{BASE_URL}/repo/load", json={"repo_url": REPO_LOCAL}, timeout=60)
        repo_id = None
        if r.status_code == 200:
            data = r.json()
            repo_id = data["repo_id"]
            pr(f"Repo ID: {repo_id}")
            pr(f"Files: {data['stats']['total_files']}")
            
            # Index
            pr("Indexing...")
            r = await client.post(f"{BASE_URL}/repo/index", json={"repo_id": repo_id}, timeout=60)
            pr(f"Index status: {r.status_code}")
            if r.status_code == 200:
                pr(f"Chunks: {r.json().get('chunk_count')}")
        else:
            pr(f"Failed to load: {r.text}")
        
        if repo_id:
            # Q&A
            pr("\n--- Part C: Q&A ---")
            questions = ["Where is the health endpoint defined?", "How is configuration loaded?"]
            for q in questions:
                pr(f"Q: {q}")
                r = await client.post(f"{BASE_URL}/chat/ask", json={"repo_id": repo_id, "question": q}, timeout=30)
                if r.status_code == 200:
                    ans = r.json()
                    pr(f"A: {ans.get('answer', '')[:100]}...")
                    pr(f"Citations: {len(ans.get('citations', []))}")
                else:
                    pr(f"Error: {r.status_code}")
            
            # Generation
            pr("\n--- Part E: Generation ---")
            req = "Add a new route to main.py"
            pr(f"Req: {req}")
            r = await client.post(f"{BASE_URL}/chat/generate", json={"repo_id": repo_id, "request": req}, timeout=60)
            if r.status_code == 200:
                data = r.json()
                pr(f"Plan: {data.get('plan', '')[:50]}...")
                pr(f"Diffs: {len(data.get('diffs', []))}")
            else:
                pr(f"Error: {r.status_code}")

        with open("verification_results.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(log))

if __name__ == "__main__":
    asyncio.run(main())
