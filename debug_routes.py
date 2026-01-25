import sys
from pathlib import Path
sys.path.append("backend")

from app.main import app
from fastapi.routing import APIRoute

print("Registered Routes:")
for route in app.routes:
    if isinstance(route, APIRoute):
        print(f"{route.methods} {route.path}")
