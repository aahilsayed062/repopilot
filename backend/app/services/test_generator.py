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
        custom_request: Optional[str] = None,
        generated_code: Optional[List[dict]] = None
    ) -> dict:
        """
        Generate PyTest test cases for a file or function.

        Args:
            repo_id: Repository ID
            target_file: Specific file to generate tests for
            target_function: Specific function to test
            custom_request: Custom test generation request
            generated_code: List of {"file_path": str, "content": str} dicts
                            with the just-generated code to write tests for
        """
        logger.info(
            "generating_tests",
            repo_id=repo_id,
            target_file=target_file,
            target_function=target_function,
            has_generated_code=bool(generated_code)
        )

        # ── If we have generated code, build chunks from it directly ──
        if generated_code:
            chunks = []
            for gc in generated_code:
                fp = gc.get("file_path", "unknown")
                content = gc.get("content", "")
                if content:
                    chunk = Chunk(
                        id=f"gen_{fp}",
                        content=content,
                        file_path=fp,
                        repo_id=repo_id,
                        start_line=1,
                        end_line=content.count("\n") + 1,
                        chunk_type="generated",
                    )
                    chunks.append(chunk)
            # Infer target_file from first generated file if not set
            if not target_file and chunks:
                target_file = chunks[0].file_path
        else:
            # Build search query from whatever info we have
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
            tests_code = self._clean_tests(data.get("tests", ""))

            # Validate: if LLM returned garbage/placeholder, use template fallback
            if not self._is_valid_test_code(tests_code):
                logger.warning("llm_tests_invalid_using_template", preview=tests_code[:120])
                tests_code = self._generate_template_tests(chunks, target_file, custom_request)

            # Derive a sensible test file name
            default_name = "test_generated.py"
            if target_file:
                base = target_file.rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
                stem = base.rsplit('.', 1)[0]
                default_name = f"test_{stem}.py"

            return {
                "success": True,
                "tests": tests_code,
                "test_file_name": data.get("test_file_name", default_name),
                "explanation": data.get("explanation", "Generated test code"),
                "coverage_notes": data.get("coverage_notes", []),
                "source_files": [c.file_path for c in chunks[:5]]
            }

        except Exception as e:
            logger.error("test_generation_failed", error=str(e))
            # Even on exception, try template fallback
            try:
                fallback_tests = self._generate_template_tests(chunks, target_file, custom_request)
                if fallback_tests:
                    return {
                        "success": True,
                        "tests": fallback_tests,
                        "test_file_name": "test_generated.py",
                        "explanation": "Template-based test generation (LLM unavailable)",
                        "coverage_notes": ["Basic functionality tests"],
                        "source_files": [c.file_path for c in chunks[:5]]
                    }
            except Exception:
                pass
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

    # Phrases that indicate the LLM echoed a placeholder instead of real code
    _PLACEHOLDER_PHRASES = {
        "actual pytest code here",
        "test code if applicable",
        "test code here",
        "write tests here",
        "your test code here",
        "insert test code",
        "placeholder",
        "python code for tests",
    }

    def _is_valid_test_code(self, code: str) -> bool:
        """Check if LLM-generated test code is actually valid Python test code."""
        if not code or len(code.strip()) < 30:
            return False
        text = code.strip()
        lower = text.lower()

        # Reject known placeholder phrases
        for phrase in self._PLACEHOLDER_PHRASES:
            if phrase in lower:
                return False

        # Must contain at least one test function definition
        if 'def test_' not in text:
            return False

        # Must have at least one assert statement or pytest call
        has_assert = 'assert ' in text or 'pytest.' in text or 'raise' in text
        if not has_assert:
            return False

        # Verify it's syntactically valid Python
        import ast
        try:
            ast.parse(text)
        except SyntaxError:
            return False

        return True

    def _generate_template_tests(
        self,
        chunks: List[Chunk],
        target_file: Optional[str] = None,
        custom_request: Optional[str] = None,
    ) -> str:
        """Generate guaranteed-valid template-based Python tests as fallback.

        For Python source code: generates import + call tests.
        For C/C++ source code: generates subprocess compile & run tests.
        For other code: generates basic smoke tests.
        """
        # Detect language from chunks or target file
        file_paths = [c.file_path for c in chunks if c.file_path] if chunks else []
        if target_file:
            file_paths.insert(0, target_file)

        # Detect if the code is C/C++
        cpp_exts = {'.cpp', '.cc', '.cxx', '.c', '.h', '.hpp'}
        py_exts = {'.py'}

        is_cpp = any(
            '.' + fp.rsplit('.', 1)[-1].lower() in cpp_exts
            for fp in file_paths if '.' in fp
        )
        is_python = any(
            '.' + fp.rsplit('.', 1)[-1].lower() in py_exts
            for fp in file_paths if '.' in fp
        )

        # Extract function names from chunks
        functions = self._extract_function_names(chunks)

        if is_cpp:
            return self._template_cpp_tests(file_paths, chunks, functions, custom_request)
        elif is_python:
            return self._template_python_tests(file_paths, chunks, functions, custom_request)
        else:
            return self._template_generic_tests(file_paths, chunks, functions, custom_request)

    def _extract_function_names(self, chunks: List[Chunk]) -> List[str]:
        """Extract function/method names from code chunks."""
        names = []
        if not chunks:
            return names
        for chunk in chunks:
            content = chunk.content or ""
            # Python functions
            for m in re.finditer(r'def\s+(\w+)\s*\(', content):
                name = m.group(1)
                if not name.startswith('_'):
                    names.append(name)
            # C/C++ functions
            for m in re.finditer(r'(?:void|int|float|double|string|bool|auto|char)\s+(\w+)\s*\(', content):
                name = m.group(1)
                if name not in ('main', 'if', 'for', 'while'):
                    names.append(name)
        return list(dict.fromkeys(names))[:10]  # unique, max 10

    def _template_python_tests(
        self, file_paths: List[str], chunks: List[Chunk],
        functions: List[str], custom_request: Optional[str]
    ) -> str:
        """Generate Python import & call tests."""
        # Find the module name from the file path
        module = "solution"
        if file_paths:
            base = file_paths[0].rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
            if base.endswith('.py'):
                module = base[:-3]

        lines = [
            "import pytest",
            "import sys",
            "import os",
            "",
            "# Ensure the module is importable",
            "sys.path.insert(0, os.path.dirname(__file__))",
            "",
            f"",
            f"class Test{module.title().replace('_', '')}:",
            f'    """Auto-generated tests for {module}."""',
            "",
        ]

        if functions:
            # Test each discovered function
            for func in functions:
                lines.extend([
                    f"    def test_{func}_exists(self):",
                    f'        \"\"\"Test that {func} function is callable.\"\"\"',
                    f"        try:",
                    f"            import {module}",
                    f"            assert hasattr({module}, '{func}'), '{func} not found in {module}'",
                    f"            assert callable({module}.{func}), '{func} is not callable'",
                    f"        except ImportError:",
                    f"            pytest.skip('{module} not importable')",
                    "",
                ])
        else:
            # Basic importability test
            lines.extend([
                f"    def test_module_imports(self):",
                f'        \"\"\"Test that the module can be imported.\"\"\"',
                f"        try:",
                f"            import {module}",
                f"            assert {module} is not None",
                f"        except ImportError:",
                f"            pytest.skip('{module} not importable')",
                "",
            ])

        lines.extend([
            f"    def test_module_has_content(self):",
            f'        \"\"\"Test that the module is not empty.\"\"\"',
            f"        try:",
            f"            import {module}",
            f"            members = [m for m in dir({module}) if not m.startswith('_')]",
            f"            assert len(members) > 0, 'Module has no public members'",
            f"        except ImportError:",
            f"            pytest.skip('{module} not importable')",
            "",
        ])

        return "\n".join(lines)

    def _template_cpp_tests(
        self, file_paths: List[str], chunks: List[Chunk],
        functions: List[str], custom_request: Optional[str]
    ) -> str:
        """Generate subprocess-based compile & run tests for C++ code."""
        # Find the C++ source file
        cpp_file = "solution.cpp"
        for fp in file_paths:
            if any(fp.endswith(ext) for ext in ('.cpp', '.cc', '.cxx', '.c')):
                cpp_file = fp.rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
                break

        return f'''import pytest
import subprocess
import os
import shutil

# Path to the C++ source file
CPP_FILE = "{cpp_file}"


class TestCppCompilation:
    """Auto-generated tests for C++ code compilation and execution."""

    def _find_cpp_file(self):
        """Locate the C++ source file."""
        # Check current directory and common locations
        for search_dir in [os.getcwd(), os.path.dirname(__file__)]:
            candidate = os.path.join(search_dir, CPP_FILE)
            if os.path.exists(candidate):
                return candidate
        pytest.skip(f"{{CPP_FILE}} not found")

    def _get_compiler(self):
        """Find available C++ compiler."""
        for compiler in ["g++", "clang++", "cl"]:
            if shutil.which(compiler):
                return compiler
        pytest.skip("No C++ compiler found (g++, clang++, or cl)")

    def test_file_exists(self):
        """Test that the C++ source file exists."""
        cpp_path = self._find_cpp_file()
        assert os.path.exists(cpp_path), f"{{CPP_FILE}} does not exist"
        assert os.path.getsize(cpp_path) > 0, f"{{CPP_FILE}} is empty"

    def test_compiles_successfully(self):
        """Test that the C++ code compiles without errors."""
        cpp_path = self._find_cpp_file()
        compiler = self._get_compiler()
        output_name = "test_output.exe" if os.name == "nt" else "test_output"
        output_path = os.path.join(os.path.dirname(cpp_path), output_name)

        try:
            result = subprocess.run(
                [compiler, cpp_path, "-o", output_path, "-std=c++17"],
                capture_output=True, text=True, timeout=30
            )
            assert result.returncode == 0, (
                f"Compilation failed:\\nSTDERR: {{result.stderr}}\\nSTDOUT: {{result.stdout}}"
            )
        finally:
            if os.path.exists(output_path):
                os.remove(output_path)

    def test_runs_without_crash(self):
        """Test that the compiled program runs without crashing."""
        cpp_path = self._find_cpp_file()
        compiler = self._get_compiler()
        output_name = "test_output.exe" if os.name == "nt" else "test_output"
        output_path = os.path.join(os.path.dirname(cpp_path), output_name)

        try:
            # Compile
            comp = subprocess.run(
                [compiler, cpp_path, "-o", output_path, "-std=c++17"],
                capture_output=True, text=True, timeout=30
            )
            if comp.returncode != 0:
                pytest.skip("Compilation failed, cannot test execution")

            # Run
            result = subprocess.run(
                [output_path],
                capture_output=True, text=True, timeout=10,
                input=""
            )
            assert result.returncode == 0, (
                f"Program crashed with exit code {{result.returncode}}:\\n"
                f"STDERR: {{result.stderr}}\\nSTDOUT: {{result.stdout}}"
            )
        finally:
            if os.path.exists(output_path):
                os.remove(output_path)

    def test_produces_output(self):
        """Test that the program produces some output."""
        cpp_path = self._find_cpp_file()
        compiler = self._get_compiler()
        output_name = "test_output.exe" if os.name == "nt" else "test_output"
        output_path = os.path.join(os.path.dirname(cpp_path), output_name)

        try:
            comp = subprocess.run(
                [compiler, cpp_path, "-o", output_path, "-std=c++17"],
                capture_output=True, text=True, timeout=30
            )
            if comp.returncode != 0:
                pytest.skip("Compilation failed")

            result = subprocess.run(
                [output_path],
                capture_output=True, text=True, timeout=10,
                input=""
            )
            stdout = result.stdout.strip()
            assert len(stdout) > 0, "Program produced no output"
        finally:
            if os.path.exists(output_path):
                os.remove(output_path)
'''

    def _template_generic_tests(
        self, file_paths: List[str], chunks: List[Chunk],
        functions: List[str], custom_request: Optional[str]
    ) -> str:
        """Generate generic file-existence tests."""
        file_checks = ""
        for fp in file_paths[:3]:
            base = fp.rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
            safe = re.sub(r'[^a-zA-Z0-9_]', '_', base)
            file_checks += f'''
    def test_{safe}_exists(self):
        """Test that {base} exists."""
        import glob
        matches = glob.glob("**/{base}", recursive=True)
        assert len(matches) > 0, "{base} not found"

'''

        return f'''import pytest
import os


class TestGeneratedCode:
    """Auto-generated smoke tests."""
{file_checks}
    def test_workspace_not_empty(self):
        """Test that workspace has files."""
        files = os.listdir(".")
        assert len(files) > 0, "Workspace is empty"
'''


# Global instance
test_generator = TestGenerator()
