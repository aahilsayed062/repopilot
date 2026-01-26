import sys
import os
from pathlib import Path

# Add backend to path so we can import app
sys.path.append(str(Path(__file__).parents[1] / "backend"))

import asyncio
from app.utils.llm import llm
from app.config import settings

async def test_llm():
    print("--- RepoPilot LLM Debug ---")
    print(f"OpenAI Key: {'[SET]' if settings.openai_api_key else '[NOT SET]'}")
    print(f"Gemini Key: {'[SET]' if settings.gemini_api_key else '[NOT SET]'}")
    print(f"Effective Mode: {'Gemini' if settings.gemini_api_key else 'OpenAI' if settings.openai_api_key else 'MOCK'}")
    
    print("\nAttempting chat completion (Text Mode)...")
    try:
        response = await llm.chat_completion([
            {"role": "user", "content": "Hello, are you working?"}
        ])
        print(f"SUCCESS (Text): {response[:50]}...")
    except Exception as e:
        print(f"FAILURE (Text): {e}")

    print("\nAttempting chat completion (JSON Mode)...")
    try:
        # Note: Gemini/OpenAI require strict instruction for JSON usually, but we just test the flag here
        response = await llm.chat_completion([
            {"role": "system", "content": "You are a helper that outputs JSON. output: {'status': 'ok'}"},
            {"role": "user", "content": "Status?"}
        ], json_mode=True)
        print(f"SUCCESS (JSON): {response[:50]}...")
    except Exception as e:
        print(f"FAILURE (JSON): {e}")

    print("\nAttempting General Knowledge Query (Mocking Answerer Logic)...")
    # This is a bit of an integration test simulation
    from app.services.answerer import answerer
    try:
        # Pass empty chunks to trigger fallback logic
        response = await answerer.answer("How do I write a Python decorator?", [])
        print(f"SUCCESS (General): Answer length {len(response.answer)}")
        print(f"Preview: {response.answer[:100]}...")
    except Exception as e:
        print(f"FAILURE (General): {e}")

if __name__ == "__main__":
    asyncio.run(test_llm())
