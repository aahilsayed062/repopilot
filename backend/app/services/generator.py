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
    chat_history: List[dict] = Field(default_factory=list)


class FileDiff(BaseModel):
    file_path: str
    where_to_paste: Optional[str] = None
    code: Optional[str] = None
    content: Optional[str] = None
    diff: str


class GenerationResponse(BaseModel):
    plan: str
    patterns_followed: List[str] = Field(default_factory=list)
    diffs: List[FileDiff]
    tests: str
    citations: List[str]
    paste_instructions: List[str] = Field(default_factory=list)


class Generator:
    """
    Generates code changes and tests.
    """
    
    SYSTEM_PROMPT = """You are RepoPilot, a code assistant.

RULES:
- If the user provides [Existing File Content], you MUST preserve ALL existing content and only make the requested changes (append, modify, delete lines, etc). Do NOT rewrite the file from scratch.
- If no existing content is provided, write new code from scratch.

Respond with JSON:
{"plan": "brief description of what you will do", "changes": [{"file_path": "filename.ext", "code": "the COMPLETE updated file content with changes applied", "diff": "+ added line 1\n+ added line 2\n- removed line"}], "test_file_content": "test code if applicable"}

CRITICAL:
- "code" must contain the FULL final file content (existing content + your changes merged together)
- "diff" must show ONLY the new/changed/removed lines with +/- prefixes — NEVER include unchanged existing content in diff
- For example, if the user says "append a note to README.md" and the file is 50 lines long, the diff should be ONLY: "+ \n+ > Note: dont touch this file" — NOT the entire 50 lines of existing content
- Write REAL working code, no placeholders
"""

    COMPLEXITY_MARKERS = (
        "architecture",
        "end-to-end",
        "refactor",
        "migration",
        "multiple files",
        "across",
        "pipeline",
        "integration",
        "security",
        "performance",
    )

    def _is_complex_request(self, request: str) -> bool:
        q = (request or "").lower()
        if len(q) > 140:
            return True
        return any(marker in q for marker in self.COMPLEXITY_MARKERS)

    def _format_recent_history(self, chat_history: List[dict], limit: int = 5) -> str:
        if not chat_history:
            return ""
        lines: List[str] = []
        for turn in chat_history[-limit:]:
            if isinstance(turn, dict):
                role_value = turn.get("role", "")
                content_value = turn.get("content", "")
            else:
                role_value = getattr(turn, "role", "")
                content_value = getattr(turn, "content", "")

            role = str(role_value).strip().lower()
            if role not in {"user", "assistant"}:
                continue
            content = str(content_value).strip()
            if not content:
                continue
            label = "User" if role == "user" else "Assistant"
            lines.append(f"{label}: {content}")
        return "\n".join(lines)

    def _derive_paste_instructions(self, diffs: List[FileDiff]) -> List[str]:
        instructions: List[str] = []
        for i, diff in enumerate(diffs, start=1):
            where = (diff.where_to_paste or "").strip()
            if where:
                instructions.append(f"{i}. `{diff.file_path}` -> {where}")
            else:
                instructions.append(
                    f"{i}. `{diff.file_path}` -> apply the provided diff in this file."
                )
        return instructions
    
    async def generate(
        self,
        repo_id: str,
        request: str,
        chat_history: Optional[List[dict]] = None,
    ) -> GenerationResponse:
        logger.info("generating_code_start", repo_id=repo_id, request=request)
        
        # 1. Retrieve Context
        retrieval_k = 4 if self._is_complex_request(request) else 3
        retrieval_query = request
        recent_history = self._format_recent_history(chat_history or [], limit=5)
        if recent_history:
            retrieval_query = (
                f"Current task: {request}\n"
                f"Recent conversation context:\n{recent_history}"
            )

        chunks = await retriever.retrieve(repo_id, retrieval_query, k=retrieval_k)
        
        if not chunks:
            return GenerationResponse(
                plan="I could not find any relevant code to modify. Please try a more specific request or ensure the repo is indexed.",
                diffs=[],
                tests="",
                citations=[],
                paste_instructions=[],
            )
            
        context_str = self._format_context(chunks)
        
        # 2. Call LLM
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Context:\n{context_str}\n\n"
                    f"Recent conversation context:\n{recent_history or 'None'}\n\n"
                    f"User Request: {request}"
                ),
            },
        ]
        
        try:
            response_text = await llm.chat_completion(messages, json_mode=True, max_tokens=1024)
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
                data = {
                    "plan": plan,
                    "changes": [],
                    "test_file_content": "",
                    "paste_instructions": [],
                }
            
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
                file_code = change.get("code")
                file_diff = change.get("diff", "")
                # Fallback: if code is empty but diff has content, use diff as code
                if not file_code and file_diff:
                    file_code = file_diff
                diffs.append(FileDiff(
                    file_path=change.get("file_path", "unknown"),
                    where_to_paste=change.get("where_to_paste"),
                    code=file_code,
                    diff=file_diff
                ))
            paste_instructions = data.get("paste_instructions")
            if not isinstance(paste_instructions, list):
                paste_instructions = []
            paste_instructions = [
                str(item).strip() for item in paste_instructions if str(item).strip()
            ]
            if not paste_instructions and diffs:
                paste_instructions = self._derive_paste_instructions(diffs)
            
            citations = list(set(c.metadata.file_path for c in chunks))
            
            return GenerationResponse(
                plan=data.get("plan", "No plan provided"),
                patterns_followed=data.get("patterns_followed", []),
                diffs=diffs,
                tests=data.get("test_file_content", ""),
                citations=citations,
                paste_instructions=paste_instructions,
            )
            
        except Exception as e:
            logger.error("generation_error", error=str(e))
            return GenerationResponse(
                plan=f"Error analyzing code: {e}",
                patterns_followed=[],
                diffs=[],
                tests="",
                citations=[],
                paste_instructions=[],
            )

    def _format_context(self, chunks: List[Chunk]) -> str:
        parts = []
        for c in chunks:
            # Truncate content to avoid token overflow (keep larger than answerer for code gen)
            content = c.content
            if len(content) > 1500:
                content = content[:1500] + "... [truncated]"
            
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
