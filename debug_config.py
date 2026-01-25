import sys
from pathlib import Path
sys.path.append("backend")

from app.config import settings

print(f"OpenAI Key: {settings.openai_api_key}")
print(f"Gemini Key: {settings.gemini_api_key}")
print(f"Mock Mode: {settings.use_mock_embeddings}")
