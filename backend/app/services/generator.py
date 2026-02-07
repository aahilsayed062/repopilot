"""
code_generator.py - Generates code patches (M8).
"""

import json
from typing import List, Optional
from pydantic import BaseModel, Field

from app.utils.logger import get_logger
from app.utils.llm import llm
from app.services.retriever import retriever
from app.models.chunk import Chunk

logger = get_logger(__name__)


class CodeGenerationRequest(BaseModel):
    repo_id: str
    request: str


class FileDiff(BaseModel):
    file_path: str
    content: Optional[str] = None
    diff: str


class GenerationResponse(BaseModel):
    plan: str
    patterns_followed: List[str] = []
    diffs: List[FileDiff]
    tests: str
    citations: List[str]


class Generator:
    """
    Generates code changes and tests.
    """
    
    SYSTEM_PROMPT = """You are RepoPilot, a senior software engineer.
    Your task is to allow the user to modify the codebase based on their request.
    
    You will be provided with:
    1. The User Request
    2. Relevant Code Context (Chunks from the repository)
    
    You must output a JSON response with the following structure:
    {
        "plan": "Detailed step-by-step implementation plan (markdown)",
        "patterns_followed": ["List of specific patterns identified and followed (e.g., 'Using Repository Pattern', 'Error handling via middleware')"],
        "changes": [
            {
                "file_path": "path/to/file.ext",
                "diff": "Unified diff or search/replace block showing the changes"
            }
        ],
        "test_file_content": "Full content of a new or updated test file to verify these changes"
    }
    
    Rules:
    - Base your changes ONLY on the provided context.
    - Analyze the provided context for coding patterns (naming conventions, error handling, project structure) and explicitly state which patterns you are following in 'patterns_followed'.
    - If you need to create a new file, specify it in 'changes' with the full content as the diff.
    - Keep changes minimal and focused.
    - Match the existing code style (indentation, naming).
    - If you lack sufficient context to make the change safely, state that in the plan.
    """
    
    async def generate(self, repo_id: str, request: str) -> GenerationResponse:
        logger.info("generating_code_start", repo_id=repo_id, request=request)
        
        # 1. Retrieve Context
        # Reduced k from 10 to 4 to avoid rate limits
        chunks = await retriever.retrieve(repo_id, request, k=4)
        
        if not chunks:
            return GenerationResponse(
                plan="I could not find any relevant code to modify. Please try a more specific request or ensure the repo is indexed.",
                diffs=[],
                tests="",
                citations=[]
            )
            
        context_str = self._format_context(chunks)
        
        # 2. Call LLM
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context_str}\n\nUser Request: {request}"}
        ]
        
        try:
            response_text = await llm.chat_completion(messages, json_mode=True)
            # Clean up markdown code blocks if present
            clean_text = response_text.strip()
            if clean_text.startswith("```"):
                import re
                clean_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", clean_text, flags=re.MULTILINE)
            clean_text = clean_text.strip()

            if not clean_text.startswith("{"):
                clean_text = f"{{{clean_text}}}"

            try:
                data = json.loads(clean_text)
            except json.JSONDecodeError:
                # Try simple regex fallback for plan/changes matching if strict parsing fails
                import re
                plan_match = re.search(r'"plan":\s*"(.*?)(?<!\\)"', clean_text, re.DOTALL)
                plan = plan_match.group(1) if plan_match else "Error parsing plan"
                data = {"plan": plan, "changes": [], "test_file_content": ""}
            
            # Helper to extract patterns if missing
            if "patterns_followed" not in data or not data["patterns_followed"]:
                import re
                patterns_match = re.search(r'"patterns_followed":\s*\[(.*?)\]', clean_text, re.DOTALL)
                patterns_followed = []
                if patterns_match:
                    try:
                        # cleanup quotes and split
                        content = patterns_match.group(1)
                        patterns_followed = [p.strip().strip('"').strip("'") for p in content.split(',')]
                    except Exception:
                        pass
                data["patterns_followed"] = patterns_followed
            
            # 3. Parse and Return
            diffs = []
            for change in data.get("changes", []):
                diffs.append(FileDiff(
                    file_path=change.get("file_path", "unknown"),
                    diff=change.get("diff", "")
                ))
            
            citations = list(set(c.metadata.file_path for c in chunks))
            
            return GenerationResponse(
                plan=data.get("plan", "No plan provided"),
                patterns_followed=data.get("patterns_followed", []),
                diffs=diffs,
                tests=data.get("test_file_content", ""),
                citations=citations
            )
            
        except Exception as e:
            logger.error("generation_error", error=str(e))
            return GenerationResponse(
                plan=f"Error analyzing code: {e}",
                patterns_followed=[],
                diffs=[],
                tests="",
                citations=[]
            )

    def _format_context(self, chunks: List[Chunk]) -> str:
        parts = []
        for c in chunks:
            # Truncate content to avoid token overflow (keep larger than answerer for code gen)
            content = c.content
            if len(content) > 1000:
                content = content[:1000] + "... [truncated]"
            
            parts.append(
                f"File: {c.metadata.file_path}\n"
                f"Lines: {c.metadata.start_line}-{c.metadata.end_line}\n"
                f"```\n{content}\n```"
            )
        return "\n---\n".join(parts)

    async def generate_tests(self, repo_id: str, target_file: Optional[str], target_function: Optional[str], custom_request: Optional[str]) -> dict:
        """Generate PyTest cases."""
        logger.info("generating_tests_start", repo_id=repo_id, target=target_file)
        
        # 1. Retrieve Context
        query = f"tests for {target_file}" if target_file else "existing tests patterns"
        if target_function:
            query += f" and function {target_function}"
        
        chunks = await retriever.retrieve(repo_id, query, k=5)
        
        context_str = self._format_context(chunks)
        
        # 2. Call LLM
        prompt = f"""
        Generate PyTest test cases for the following context.
        
        Target File: {target_file or "General"}
        Target Function: {target_function or "N/A"}
        User Request: {custom_request or "Generate comprehensive tests"}
        
        Rules:
        1. Use 'pytest' framework.
        2. Mock external dependencies (DB, APIs) if needed.
        3. Follow existing test patterns seen in context.
        4. Include edge cases.
        
        Return JSON:
        {{
            "success": true,
            "tests": "python code for tests",
            "test_file_name": "test_filename.py",
            "explanation": "Why these tests were chosen",
            "coverage_notes": ["Note 1", "Note 2"]
        }}
        """
        
        messages = [
            {"role": "system", "content": "You are a QA automation expert specializing in PyTest."},
            {"role": "user", "content": f"Context:\n{context_str}\n\n{prompt}"}
        ]
        
        try:
            response_text = await llm.chat_completion(messages, json_mode=True)
            # Parse JSON safely
            import re
            clean_text = response_text.strip()
            if clean_text.startswith("```"):
                clean_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", clean_text, flags=re.MULTILINE)
            clean_text = clean_text.strip()
            
            if not clean_text.startswith("{"):
                clean_text = f"{{{clean_text}}}"
                
            data = json.loads(clean_text)
            return data
            
        except Exception as e:
            logger.error("test_generation_error", error=str(e))
            return {
                "success": False,
                "tests": "",
                "test_file_name": "",
                "explanation": f"Failed to generate tests: {e}",
                "coverage_notes": []
            }

generator = Generator()
