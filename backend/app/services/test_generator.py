"""
PyTest Generator Service - Generates test cases for repository code.
"""

import json
from typing import List, Optional

from app.utils.logger import get_logger
from app.utils.llm import llm
from app.models.chunk import Chunk
from app.services.retriever import retriever
from app.services.repo_manager import repo_manager

logger = get_logger(__name__)


class TestGenerator:
    """
    Generates PyTest test cases based on repository code.
    """
    
    SYSTEM_PROMPT = """You are a test generation expert. Your task is to generate PyTest test cases for the given code.

Rules:
1. Generate tests that follow PyTest conventions (test_ prefix, assert statements)
2. Include edge cases, error handling, and typical use cases
3. If existing tests are provided, match their style and patterns
4. Use descriptive test names that explain what is being tested
5. Add docstrings to each test explaining the test purpose
6. Use fixtures where appropriate
7. Include both positive and negative test cases

Return your response as a JSON object:
{
    "tests": "The complete PyTest code as a string",
    "test_file_name": "suggested filename like test_module.py",
    "explanation": "Brief explanation of what tests were generated",
    "coverage_notes": ["list of what's covered", "and what might need more tests"]
}
"""

    async def generate_tests(
        self, 
        repo_id: str, 
        target_file: Optional[str] = None,
        target_function: Optional[str] = None,
        custom_request: Optional[str] = None
    ) -> dict:
        """
        Generate PyTest test cases for a file or function.
        
        Args:
            repo_id: Repository ID
            target_file: Specific file to generate tests for
            target_function: Specific function to test
            custom_request: Custom test generation request
        """
        logger.info(
            "generating_tests",
            repo_id=repo_id,
            target_file=target_file,
            target_function=target_function
        )
        
        # Build search query
        if target_function:
            query = f"function {target_function} implementation"
        elif target_file:
            query = f"code in {target_file}"
        elif custom_request:
            query = custom_request
        else:
            query = "main functionality and core functions"
        
        # Retrieve relevant code chunks
        chunks = await retriever.retrieve(repo_id, query, k=10)
        
        # Also try to find existing tests for style matching
        test_chunks = await retriever.retrieve(repo_id, "test pytest unittest", k=3)
        
        # Build context
        code_context = self._build_context(chunks, "Source Code")
        test_context = self._build_context(test_chunks, "Existing Tests (for style reference)")
        
        # Build user message
        user_message = f"""
{code_context}

{test_context}

Task: Generate comprehensive PyTest test cases for the code above.
"""
        
        if target_file:
            user_message += f"\nFocus on: {target_file}"
        if target_function:
            user_message += f"\nSpecifically test the function: {target_function}"
        if custom_request:
            user_message += f"\nAdditional requirements: {custom_request}"
        
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
        
        try:
            response_text = await llm.chat_completion(messages, json_mode=True)
            
            try:
                data = json.loads(response_text)
                return {
                    "success": True,
                    "tests": data.get("tests", ""),
                    "test_file_name": data.get("test_file_name", "test_generated.py"),
                    "explanation": data.get("explanation", ""),
                    "coverage_notes": data.get("coverage_notes", []),
                    "source_files": [c.file_path for c in chunks[:5]]
                }
            except json.JSONDecodeError:
                # Fallback - treat as raw test code
                return {
                    "success": True,
                    "tests": response_text,
                    "test_file_name": "test_generated.py",
                    "explanation": "Generated test code",
                    "coverage_notes": [],
                    "source_files": [c.file_path for c in chunks[:5]]
                }
                
        except Exception as e:
            logger.error("test_generation_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "tests": "",
                "test_file_name": "",
                "explanation": f"Failed to generate tests: {str(e)}",
                "coverage_notes": []
            }
    
    def _build_context(self, chunks: List[Chunk], title: str) -> str:
        """Build context string from chunks."""
        if not chunks:
            return f"### {title}\nNo relevant code found."
        
        parts = [f"### {title}"]
        for i, chunk in enumerate(chunks):
            parts.append(
                f"\n[{i+1}] File: {chunk.file_path} (Lines {chunk.line_range})\n"
                f"```\n{chunk.content}\n```"
            )
        return "\n".join(parts)


# Global instance
test_generator = TestGenerator()
