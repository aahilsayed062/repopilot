"""
PyTest Generator Service - Generates test cases for repository code.
"""

import json
import re
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

            data = self._parse_test_response(response_text)

            return {
                "success": True,
                "tests": self._clean_tests(data.get("tests", "")),
                "test_file_name": data.get("test_file_name", "test_generated.py"),
                "explanation": data.get("explanation", "Generated test code"),
                "coverage_notes": data.get("coverage_notes", []),
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

    def _parse_test_response(self, response_text: str) -> dict:
        """Parse LLM response for test generation with robust fallback."""
        raw = response_text.strip()

        # Strategy 1: direct parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Strategy 2: strip markdown fences
        clean = re.sub(r'^```(?:json)?\s*\n?', '', raw, flags=re.MULTILINE)
        clean = re.sub(r'\n?```\s*$', '', clean, flags=re.MULTILINE)
        clean = clean.strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            pass

        # Strategy 3: find outermost { ... } block
        brace_match = re.search(r'\{', clean)
        if brace_match:
            start = brace_match.start()
            depth = 0
            in_str = False
            esc = False
            end_pos = start
            for i in range(start, len(clean)):
                ch = clean[i]
                if esc:
                    esc = False
                    continue
                if ch == '\\':
                    esc = True
                    continue
                if ch == '"':
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        end_pos = i
                        break
            if depth == 0:
                try:
                    return json.loads(clean[start:end_pos + 1])
                except json.JSONDecodeError:
                    pass

        # Strategy 4: regex extract 'tests' field
        tests_match = re.search(r'"tests"\s*:\s*"((?:[^"\\]|\\.)*)"', clean, re.DOTALL)
        if tests_match:
            tests_code = tests_match.group(1).replace('\\"', '"').replace('\\n', '\n')
            return {"tests": tests_code, "test_file_name": "test_generated.py",
                    "explanation": "Generated test code", "coverage_notes": []}

        # Strategy 5: extract Python test code directly from raw response
        code_blocks = re.findall(r'```(?:python)?\n(.*?)```', raw, re.DOTALL)
        for block in code_blocks:
            if 'def test_' in block or 'import pytest' in block:
                return {"tests": block.strip(), "test_file_name": "test_generated.py",
                        "explanation": "Generated test code", "coverage_notes": []}

        # Last resort: if raw text looks like Python test code, use it directly
        if 'def test_' in raw or 'import pytest' in raw:
            return {"tests": self._clean_tests(raw), "test_file_name": "test_generated.py",
                    "explanation": "Generated test code", "coverage_notes": []}

        logger.warning("test_response_unparseable", text_preview=raw[:200])
        return {"tests": raw, "test_file_name": "test_generated.py",
                "explanation": "Generated test code (raw)", "coverage_notes": []}

    def _build_context(self, chunks: List[Chunk], title: str) -> str:
        """Build context string from chunks, truncating to avoid TPM limits."""
        if not chunks:
            return f"### {title}\nNo relevant code found."

        parts = [f"### {title}"]
        for i, chunk in enumerate(chunks):
            content = chunk.content[:800] + "\n... [truncated]" if len(chunk.content) > 800 else chunk.content
            parts.append(f"\n[{i+1}] File: {chunk.file_path} (Lines {chunk.line_range})\n```\n{content}\n```")
        return "\n".join(parts)

    def _clean_tests(self, tests: str) -> str:
        """Strip markdown fences and nested JSON from test code."""
        if not tests:
            return ""

        text = tests.strip()
        text = re.sub(r'^```(?:python)?\s*\n?', '', text)
        text = re.sub(r'\n?```\s*$', '', text)

        # Handle case where tests field contains nested JSON
        if text.lstrip().startswith('{'):
            try:
                data = json.loads(text)
                if isinstance(data, dict) and 'tests' in data:
                    return self._clean_tests(data['tests'])
            except json.JSONDecodeError:
                pass

        return text.strip()


# Global instance
test_generator = TestGenerator()
