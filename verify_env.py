import sys
import os
from dotenv import load_dotenv

load_dotenv()

print(f"Python: {sys.version}")
print(f"CWD: {os.getcwd()}")

try:
    import google.generativeai as genai
    print("✅ google.generativeai imported")
    key = os.getenv("GEMINI_API_KEY")
    if key:
        print(f"✅ GEMINI_API_KEY found: {key[:5]}...")
        genai.configure(api_key=key)
        # Try a quick call
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content("Hello")
        print("✅ Gemini API Call Successful")
    else:
        print("❌ GEMINI_API_KEY NOT found in env")

except ImportError:
    print("❌ google.generativeai NOT installed")
except Exception as e:
    print(f"❌ Gemini Error: {e}")

try:
    import fastapi
    import uvicorn
    import chromadb
    print("✅ Core dependencies found")
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
