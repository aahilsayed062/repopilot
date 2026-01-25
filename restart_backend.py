import os
import subprocess
import time
import sys
import urllib.request
import json
from pathlib import Path

# Load .env manually
env = os.environ.copy()
env_path = Path(".env")
if env_path.exists():
    print(f"Loading .env from {env_path.absolute()}")
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            if "=" in line:
                key, val = line.split("=", 1)
                env[key.strip()] = val.strip()

print(f"DEBUG: GEMINI_API_KEY in env: {'GEMINI_API_KEY' in env}")

PORT = 8001


def get_pids_on_port(port: int):
    try:
        output = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True).decode()
        pids = set()
        for line in output.splitlines():
            if "LISTENING" in line:
                parts = line.split()
                pid = parts[-1]
                if pid.isdigit():
                    pids.add(pid)
        return sorted(pids)
    except Exception:
        return []

pids = get_pids_on_port(PORT)
if pids:
    print(f"Killing processes on port {PORT}: {', '.join(pids)}")
    for pid in pids:
        os.system(f"taskkill /PID {pid} /F")
    time.sleep(2)

print("Starting new backend with ENV...")
# FORCE Mock Mode off if key is present? No, config handles it.
cmd = [
    r".\venv\Scripts\python.exe",
    "-m",
    "uvicorn",
    "app.main:app",
    "--host",
    "0.0.0.0",
    "--port",
    str(PORT),
    "--app-dir",
    "backend"
]
with open("backend.log", "w") as out:
    subprocess.Popen(cmd, stdout=out, stderr=out, env=env)

print("Backend started. Waiting for health check...")

started = False
for i in range(10):
    time.sleep(2)
    try:
        with urllib.request.urlopen(f"http://localhost:{PORT}/health") as response:
            data = json.loads(response.read().decode())
            print(f"Health Check: {data}")
            if not data.get('mock_mode'):
                print("Server running in REAL mode.")
                started = True
                break
            else:
                print("Server running in MOCK mode. Retrying...")
    except Exception as e:
        print(f"Health check failed: {e}")

if not started:
    print("Failed to start in Real Mode or Timed Out.")


