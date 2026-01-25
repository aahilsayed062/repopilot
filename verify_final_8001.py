import httpx
import asyncio
import json
import os

PORT = 8001
BASE_URL = f"http://localhost:{PORT}"
REPO_REMOTE = "https://github.com/keleshev/schema"

async def main():
    async with httpx.AsyncClient() as client:
        log = []
        def pr(s):
            print(s)
            log.append(s)
            
        pr(f"Verifying against {BASE_URL}")
        
        # 1. Health
        try:
            h = await client.get(f"{BASE_URL}/health")
            pr(f"Health: {h.json()}")
        except Exception as e:
            pr(f"Health check failed: {e}")
            return

        # 2. Ingestion (Remote) - Tests Bug B
        pr(f"\n--- Testing Bug B: Ingestion ({REPO_REMOTE}) ---")
        try:
            r = await client.post(f"{BASE_URL}/repo/load", json={"repo_url": REPO_REMOTE}, timeout=60)
            if r.status_code == 200:
                data = r.json()
                repo_id = data["repo_id"]
                pr(f"✅ Ingestion SUCCESS: {repo_id}")
                
                # 3. Indexing
                pr("Indexing...")
                r_idx = await client.post(f"{BASE_URL}/repo/index", json={"repo_id": repo_id}, timeout=60)
                pr(f"Index Status: {r_idx.status_code}")
                
                # 4. Generation - Tests Bug C
                pr("\n--- Testing Bug C: Generation ---")
                gen_req = {"repo_id": repo_id, "request": "Add a simple hello world function to schema.py"}
                r_gen = await client.post(f"{BASE_URL}/chat/generate", json=gen_req, timeout=60)
                if r_gen.status_code == 200:
                    pr("✅ Generation SUCCESS")
                    pr(f"Plan Preview: {r_gen.json().get('plan', '')[:50]}...")
                else:
                    pr(f"❌ Generation FAILED: {r_gen.status_code} {r_gen.text}")
            else:
                pr(f"❌ Ingestion FAILED: {r.status_code} {r.text}")
        except Exception as e:
            pr(f"Exception during ingestion: {e}")

        with open("final_verification_8001.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(log))

if __name__ == "__main__":
    asyncio.run(main())
