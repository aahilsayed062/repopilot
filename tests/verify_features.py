
import asyncio
import json
import logging
import sys
from unittest.mock import MagicMock, AsyncMock

# Mock setup
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))

sys.modules['app.config'] = MagicMock()
sys.modules['app.utils.logger'] = MagicMock()
sys.modules['app.utils.llm'] = MagicMock()
sys.modules['app.services.retriever'] = MagicMock()
sys.modules['chromadb'] = MagicMock()

# Now import services
from app.services.answerer import answerer
from app.services.generator import generator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_explainability():
    print("\n--- Testing Explainability (Dynamic 'why') ---")
    
    # Mock LLM response with 'why' fields
    mock_response = json.dumps({
        "answer": "The user is authenticated in the auth_service.py file.",
        "citations": [
            {"file_path": "auth_service.py", "line_range": "L10-L20", "snippet": "def login()...", "why": "Contains the login function definition"}
        ],
        "confidence": "high"
    })
    
    # Mock LLM client
    from app.utils.llm import llm
    llm.chat_completion = AsyncMock(return_value=mock_response)
    
    # Mock Chunk
    chunk = MagicMock()
    chunk.content = "def login(): pass"
    chunk.file_path = "auth_service.py"
    chunk.line_range = "L10-L20"
    
    response = await answerer.answer("How is login handled?", [chunk])
    
    citation = response.citations[0]
    # Citation is likely a Pydantic model or dict depending on implementation
    # Based on answerer.py, it returns ChatResponse with Citation objects
    citation_why = getattr(citation, 'why', None) or citation.get('why')
    print(f"Citation Why: {citation_why}")
    
    if citation_why == "Contains the login function definition":
        print("✅ Explainability Test PASSED")
    else:
        print(f"❌ Explainability Test FAILED. Got: {citation_why}")

async def test_pattern_alignment():
    print("\n--- Testing Pattern Alignment ---")
    
    # Mock LLM response with patterns_followed
    mock_response = json.dumps({
        "plan": "Use Factory Pattern",
        "patterns_followed": ["Factory Pattern", "Dependency Injection"],
        "changes": [],
        "test_file_content": ""
    })
    
    from app.utils.llm import llm
    llm.chat_completion = AsyncMock(return_value=mock_response)
    
    # Mock Retriever
    from app.services.retriever import retriever
    mock_chunk = MagicMock()
    mock_chunk.metadata.file_path = "test.py"
    mock_chunk.content = "code"
    retriever.retrieve = AsyncMock(return_value=[mock_chunk])
    
    response = await generator.generate("repo_id", "Add a user factory")
    
    print(f"Patterns Followed: {response.patterns_followed}")
    
    if "Factory Pattern" in response.patterns_followed:
        print("✅ Pattern Alignment Test PASSED")
    else:
        print("❌ Pattern Alignment Test FAILED")

async def test_pytest_generation():
    print("\n--- Testing PyTest Generation ---")
    
    # Mock LLM response for tests
    mock_response = json.dumps({
        "success": True,
        "tests": "def test_login(): assert True",
        "test_file_name": "test_auth.py",
        "explanation": "Testing login success path",
        "coverage_notes": ["Happy path covered"]
    })
    
    from app.utils.llm import llm
    llm.chat_completion = AsyncMock(return_value=mock_response)
    
    result = await generator.generate_tests("repo_id", "auth_service.py", None, None)
    
    print(f"Generated Tests: {result['tests'][:20]}...")
    
    if result['success'] and "def test_login" in result['tests']:
        print("✅ PyTest Generation Test PASSED")
    else:
        print("❌ PyTest Generation Test FAILED")

async def main():
    await test_explainability()
    await test_pattern_alignment()
    await test_pytest_generation()

if __name__ == "__main__":
    asyncio.run(main())
