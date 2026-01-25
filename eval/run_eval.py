import json
import httpx
import asyncio
from pathlib import Path

BASE_URL = "http://localhost:8001"
REPO_URL = "https://github.com/keleshev/schema"

async def run_eval():
    print(f"Running eval against {BASE_URL}")
    
    # 1. Load Repo
    print("Loading repo...")
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{BASE_URL}/repo/load", json={"repo_url": REPO_URL})
        if r.status_code != 200:
            print("Failed to load repo")
            return
        repo_id = r.json()["repo_id"]
        print(f"Repo loaded: {repo_id}")
        
        # 2. Index
        print("Indexing...")
        await client.post(f"{BASE_URL}/repo/index", json={"repo_id": repo_id})
        
        # 3. Process Prompts
        prompts = json.loads(Path("eval/prompts.json").read_text())
        results = []
        
        for p in prompts:
            print(f"Running {p['id']}: {p['question']}")
            r = await client.post(
                f"{BASE_URL}/chat/ask",
                json={"repo_id": repo_id, "question": p["question"]}
            )
            data = r.json()
            
            # Check citations
            citations = [c["file_path"] for c in data.get("citations", [])]
            ref_match = False
            for expected in p["expected_files"]:
                if any(expected in c for c in citations):
                    ref_match = True
                    break
            
            results.append({
                "id": p["id"],
                "question": p["question"],
                "passed": ref_match,
                "confidence": data.get("confidence", "low"),
                "citations": citations,
                "answer_preview": data.get("answer", "")[:50]
            })
            
        # 4. Report
        print("\n--- Eval Report ---")
        passed = sum(1 for r in results if r["passed"])
        avg_conf = sum(1 if r["confidence"] == "high" else 0.5 if r["confidence"] == "medium" else 0 for r in results) / len(results)
        
        print(f"Success Rate: {passed}/{len(results)}")
        print(f"Avg Confidence: {avg_conf:.2f}")
        
        with open("eval/report.md", "w") as f:
            f.write("# Eval Report\n\n")
            f.write(f"**Success Rate**: {passed}/{len(results)}\n\n")
            f.write(f"**Avg Confidence Score**: {avg_conf:.2f} (0=Low, 1=High)\n\n")
            f.write("| ID | Question | Passed | Confidence | Citations |\n")
            f.write("|---|---|---|---|---|\n")
            for r in results:
                f.write(f"| {r['id']} | {r['question']} | {r['passed']} | {r['confidence']} | {r['citations']} |\n")

if __name__ == "__main__":
    asyncio.run(run_eval())
