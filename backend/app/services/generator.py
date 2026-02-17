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
{"plan": "brief description of what you will do", "changes": [{"file_path": "filename.ext", "code": "the COMPLETE updated file content with changes applied", "diff": "+ added line 1\n+ added line 2\n- removed line"}], "test_file_content": ""}

IMPORTANT for test_file_content:
- Set test_file_content to an empty string "" (tests are generated separately)
- Do NOT write placeholder text in test_file_content

CRITICAL:
- "code" must contain the FULL final file content (existing content + your changes merged together)
- "code" must be COMPLETE and READY TO RUN — include ALL necessary imports, headers (#include), class definitions, main functions, etc.
- For C/C++ files: include all #include directives, add "using namespace std;" after includes for readability, full class/struct definitions, and a main() function if appropriate
- For Python files: include all import statements and complete class/function definitions
- NEVER generate just a code snippet — always generate a COMPLETE, COMPILABLE/RUNNABLE file
- FUNCTION ORDER: Always define helper/utility functions BEFORE the functions that call them. For example, if main() calls processData(), define processData() first, then main(). This ensures correct compilation in C/C++ and logical reading order.
- "diff" must show ONLY the new/changed/removed lines with +/- prefixes — NEVER include unchanged existing content in diff
- Write REAL working code, no placeholders
- NEVER use comments like "# implement here", "# TODO", "# ...", or "pass" as method bodies
- Every function/method MUST have a COMPLETE, WORKING implementation with actual logic
- Do NOT leave any method empty or stub — write the full algorithm
- Do NOT wrap code values in markdown fences (```). Return raw code only in the "code" field.
- When the user provides [Existing File Content], use the SAME file_path as the existing file. Do NOT create a new file — update the existing one.
- When fixing/correcting code, preserve the original file_path and apply changes to that file.
- ACCURACY: Implement EXACTLY what the user asked for. Read the user's request carefully and match the algorithm/feature name precisely. Do NOT substitute a different algorithm.
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

    # Well-known algorithm names for extraction
    _ALGORITHM_NAMES = [
        "merge sort", "mergesort", "quick sort", "quicksort",
        "insertion sort", "bubble sort", "selection sort",
        "heap sort", "heapsort", "radix sort", "counting sort",
        "bucket sort", "shell sort", "tim sort", "timsort",
        "binary search", "linear search", "interpolation search",
        "depth first search", "breadth first search", "dfs", "bfs",
        "dijkstra", "bellman ford", "floyd warshall", "kruskal",
        "prim", "topological sort", "a star", "minimax",
        "knapsack", "fibonacci", "factorial", "tower of hanoi",
        "linked list", "doubly linked list", "binary tree",
        "binary search tree", "avl tree", "red black tree",
        "hash table", "hash map", "stack", "queue",
        "priority queue", "trie", "segment tree",
        "singly linked list", "circular linked list",
    ]

    _LANG_EXTENSIONS = {
        "c++": ".cpp", "cpp": ".cpp", "c plus plus": ".cpp",
        "python": ".py", "py": ".py",
        "java": ".java", "javascript": ".js", "js": ".js",
        "typescript": ".ts", "ts": ".ts",
        "c#": ".cs", "csharp": ".cs", "c sharp": ".cs",
        "go": ".go", "golang": ".go",
        "rust": ".rs", "ruby": ".rb", "php": ".php",
        "swift": ".swift", "kotlin": ".kt",
    }

    # C/C++ file extensions that need namespace post-processing
    _CPP_EXTENSIONS = {".cpp", ".cc", ".cxx", ".c++", ".hpp", ".h"}

    def _is_complex_request(self, request: str) -> bool:
        q = (request or "").lower()
        if len(q) > 140:
            return True
        return any(marker in q for marker in self.COMPLEXITY_MARKERS)

    def _extract_algorithm_hint(self, request: str) -> str:
        """Extract the specific algorithm/data-structure name the user asked for."""
        q = (request or "").lower()
        # Return the longest matching name (e.g. 'binary search tree' over 'binary search')
        matches = [a for a in self._ALGORITHM_NAMES if a in q]
        if matches:
            return max(matches, key=len)
        return ""

    def _detect_language_ext(self, request: str) -> str:
        """Detect target programming language from the request and return extension."""
        q = (request or "").lower()
        for lang, ext in self._LANG_EXTENSIONS.items():
            if lang in q:
                return ext
        return ".py"  # default

    @staticmethod
    def _postprocess_cpp_code(code: str) -> str:
        """Add 'using namespace std;' to C++ code if it has std includes but lacks it."""
        if not code:
            return code
        if "using namespace std" in code:
            return code
        # Only add if the code has C++ standard library includes
        if "#include" not in code:
            return code
        lines = code.split("\n")
        last_include_idx = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("#include"):
                last_include_idx = i
        if last_include_idx >= 0:
            lines.insert(last_include_idx + 1, "\nusing namespace std;")
            return "\n".join(lines)
        return code

    def _fix_file_path(self, file_path: str, request: str) -> str:
        """Fix file_path when LLM used wrong name (e.g. quick_sort.cpp for insertion sort request)."""
        algo = self._extract_algorithm_hint(request)
        if not algo:
            return file_path
        # Get the extension from the original path, or detect from request
        ext = ""
        if "." in file_path:
            ext = "." + file_path.rsplit(".", 1)[1]
        else:
            ext = self._detect_language_ext(request)
        correct_name = algo.replace(" ", "_") + ext
        # Only fix if the current path doesn't already match the algorithm
        algo_slug = algo.replace(" ", "_")
        if algo_slug not in file_path.lower().replace(" ", "_"):
            logger.warning("fix_file_path", original=file_path, corrected=correct_name, algo=algo)
            return correct_name
        return file_path

    def _is_cpp_file(self, file_path: str) -> bool:
        """Check if file_path is a C/C++ file."""
        if not file_path:
            return False
        ext = "." + file_path.rsplit(".", 1)[1] if "." in file_path else ""
        return ext.lower() in self._CPP_EXTENSIONS

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

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Remove markdown code fences (```python ... ```) that LLMs wrap around code values."""
        if not text:
            return text
        import re
        stripped = text.strip()
        # Match opening ```<lang>\n ... closing ```
        stripped = re.sub(r"^```[a-zA-Z]*\s*\n?", "", stripped)
        stripped = re.sub(r"\n?```\s*$", "", stripped)
        return stripped.strip()

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
        
        # 2. Build user message — inject algorithm hint to prevent RAG poisoning
        algo_hint = self._extract_algorithm_hint(request)
        if algo_hint:
            algo_warning = (
                f"\n\n*** CRITICAL INSTRUCTION ***\n"
                f"The user wants: {algo_hint.upper()}.\n"
                f"You MUST implement {algo_hint.upper()} — NOT any other algorithm.\n"
                f"The context code above is for REFERENCE ONLY (style, language, structure).\n"
                f"Do NOT copy/reuse any algorithm from the context. Write {algo_hint} from scratch.\n"
                f"Name the file: {algo_hint.replace(' ', '_')}{self._detect_language_ext(request)}\n"
                f"*** END CRITICAL INSTRUCTION ***\n"
            )
        else:
            algo_warning = ""

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Context:\n{context_str}\n\n"
                    f"Recent conversation context:\n{recent_history or 'None'}\n\n"
                    f"User Request: {request}"
                    f"{algo_warning}"
                ),
            },
        ]
        
        try:
            response_text = await llm.chat_completion(messages, json_mode=True, max_tokens=4096)
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
                # JSON may have been truncated by max_tokens — attempt repair
                import re
                logger.warning("generate_json_parse_failed_attempting_repair",
                               raw_len=len(clean_text))
                
                # Try to repair truncated JSON by closing open structures
                repaired = clean_text.rstrip()
                # Remove trailing incomplete string value
                repaired = re.sub(r',\s*"[^"]*$', '', repaired)
                # Close any open strings, arrays, objects
                open_braces = repaired.count('{') - repaired.count('}')
                open_brackets = repaired.count('[') - repaired.count(']')
                # If we're inside a string, close it
                if repaired.count('"') % 2 != 0:
                    repaired += '"'
                for _ in range(open_brackets):
                    repaired += ']'
                for _ in range(open_braces):
                    repaired += '}'
                
                try:
                    data = json.loads(repaired)
                    logger.info("generate_json_repair_success")
                except json.JSONDecodeError:
                    # Last resort: regex extraction
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
            raw_changes = data.get("changes", [])
            if not isinstance(raw_changes, list):
                raw_changes = []
            for idx, change in enumerate(raw_changes):
                # Guard: LLM sometimes returns strings instead of dicts
                if isinstance(change, str):
                    logger.warning("generate_change_is_string", index=idx)
                    change = {"file_path": "generated_code.py", "code": change, "diff": change}
                if not isinstance(change, dict):
                    logger.warning("generate_change_bad_type", index=idx, type=type(change).__name__)
                    continue
                raw_file_path = change.get("file_path", "unknown")
                file_code = self._strip_code_fences(change.get("code") or "")
                file_diff = self._strip_code_fences(change.get("diff", ""))
                # Fallback: if code is empty but diff has content, use diff as code
                if not file_code and file_diff:
                    file_code = file_diff

                # Post-process: fix file_path if LLM used wrong algorithm name
                fixed_path = self._fix_file_path(raw_file_path, request)

                # Post-process: add 'using namespace std;' for C++ files
                if self._is_cpp_file(fixed_path):
                    file_code = self._postprocess_cpp_code(file_code)

                diffs.append(FileDiff(
                    file_path=fixed_path,
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
            
            # Validate test content — reject obvious placeholders
            raw_tests = self._strip_code_fences(data.get("test_file_content", ""))
            tests = self._validate_test_content(raw_tests)
            
            return GenerationResponse(
                plan=data.get("plan", "No plan provided"),
                patterns_followed=data.get("patterns_followed", []),
                diffs=diffs,
                tests=tests,
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

    # Placeholder / non-code phrases that small models tend to echo back
    _TEST_PLACEHOLDERS = {
        "test code if applicable",
        "test code here",
        "write tests here",
        "your test code here",
        "insert test code",
        "placeholder",
        "n/a",
        "none",
        "no tests",
        "no test",
        "not applicable",
        "actual pytest code here",
        "...actual pytest code here...",
    }

    def _validate_test_content(self, raw: str) -> str:
        """Return empty string if the LLM echoed a placeholder instead of real test code."""
        if not raw:
            return ""
        text = raw.strip()

        # Check against known placeholders (case-insensitive)
        if text.lower() in self._TEST_PLACEHOLDERS:
            logger.warning("test_content_placeholder_detected", preview=text[:80])
            return ""

        # Minimal heuristic: real Python test code should have at least
        # a def or import statement; plain English sentences are not code
        has_code_marker = any(kw in text for kw in ("def ", "import ", "class ", "assert "))
        if not has_code_marker and len(text) < 200:
            logger.warning("test_content_not_code", preview=text[:80])
            return ""

        return text


generator = Generator()
