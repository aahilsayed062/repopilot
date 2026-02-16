"""
Iterative PyTest-Driven Refinement Loop.
Generates code → tests → runs → refines based on failures.

Round 2 Feature: Self-correcting code generation with automated test verification.
"""
import asyncio
import json
import subprocess
import tempfile
import os
from typing import Optional, List
from pydantic import BaseModel, Field
from app.utils.llm import llm
from app.utils.logger import get_logger
from app.services.generator import generator, GenerationResponse
from app.services.test_generator import test_generator

logger = get_logger(__name__)
MAX_ITERATIONS = 4


# ─── Response Models ───────────────────────────────────────────────

class IterationResult(BaseModel):
    """Snapshot of a single generate-test-refine iteration."""
    iteration: int
    code_snippet: str           # truncated for response size
    tests_snippet: str          # truncated for response size
    test_output: str
    tests_passed: bool
    failures: List[str] = []
    refinement_action: str = ""


class RefinementResult(BaseModel):
    """Final output of the refinement loop."""
    success: bool
    total_iterations: int
    final_code: str
    final_tests: str
    iteration_log: List[IterationResult]
    final_test_output: str


# ─── Refinement Loop ───────────────────────────────────────────────

class RefinementLoop:
    """
    Orchestrates the iterative refinement cycle:
      1. Generate code via the existing Generator service
      2. Generate tests via the existing TestGenerator service
      3. Execute tests in a sandboxed temp directory
      4. If tests fail, feed errors back to the LLM for a fix
      5. Repeat up to MAX_ITERATIONS times
    """

    REFINE_PROMPT = """You are a code refinement agent.
The previous code generation produced code that FAILED its tests.

TEST FAILURES:
{failures}

ORIGINAL CODE:
{code}

ORIGINAL TESTS:
{tests}

Analyze the failures and fix EITHER the code OR the tests (decide which is wrong).
Return JSON:
{{
  "fix_target": "code" or "tests",
  "reasoning": "Why this fix",
  "fixed_code": "the corrected code if fix_target is code, otherwise empty string",
  "fixed_tests": "the corrected tests if fix_target is tests, otherwise empty string"
}}"""

    # ── Public API ─────────────────────────────────────────────────

    async def run_refinement(
        self,
        repo_id: str,
        request: str,
        chat_history: Optional[List[dict]] = None,
    ) -> RefinementResult:
        """Run the full generate → test → refine loop."""
        iteration_log: List[IterationResult] = []
        current_code = ""
        current_tests = ""

        for i in range(1, MAX_ITERATIONS + 1):
            logger.info("refinement_iteration", iteration=i, repo_id=repo_id)

            # ── Step 1: Generate code (first iteration only) ──────
            if i == 1:
                try:
                    gen_result = await generator.generate(
                        repo_id, request, chat_history
                    )
                    current_code = self._extract_code_from_generation(gen_result)
                    logger.info("initial_code_generated", length=len(current_code))
                except Exception as e:
                    logger.error("code_generation_failed", error=str(e))
                    return RefinementResult(
                        success=False,
                        total_iterations=0,
                        final_code="",
                        final_tests="",
                        iteration_log=[],
                        final_test_output=f"Code generation failed: {e}",
                    )

            # ── Step 2: Generate tests (first iteration only) ─────
            if i == 1 or not current_tests:
                try:
                    test_result = await test_generator.generate_tests(
                        repo_id=repo_id,
                        custom_request=(
                            f"Generate pytest tests for this code:\n"
                            f"```python\n{current_code[:2000]}\n```"
                        ),
                    )
                    current_tests = test_result.get("tests", "")
                    logger.info("tests_generated", length=len(current_tests))
                except Exception as e:
                    logger.error("test_generation_failed", error=str(e))
                    current_tests = ""

            # ── Step 3: Execute tests ─────────────────────────────
            test_output, passed, failures = await self._run_pytest(
                current_code, current_tests
            )

            iteration = IterationResult(
                iteration=i,
                code_snippet=(
                    current_code[:500] + "..."
                    if len(current_code) > 500
                    else current_code
                ),
                tests_snippet=(
                    current_tests[:500] + "..."
                    if len(current_tests) > 500
                    else current_tests
                ),
                test_output=test_output[:1000],
                tests_passed=passed,
                failures=failures,
            )

            if passed:
                iteration.refinement_action = "Tests passed — no refinement needed"
                iteration_log.append(iteration)
                logger.info("tests_passed", iteration=i)
                break

            # ── Step 4: Refine via LLM ────────────────────────────
            logger.info("refining", iteration=i, failure_count=len(failures))
            refined = await self._refine(current_code, current_tests, test_output)

            if refined.get("fix_target") == "code":
                fixed = refined.get("fixed_code", "")
                if fixed:
                    current_code = fixed
                iteration.refinement_action = (
                    f"Fixed CODE: {refined.get('reasoning', 'N/A')}"
                )
            else:
                fixed = refined.get("fixed_tests", "")
                if fixed:
                    current_tests = fixed
                iteration.refinement_action = (
                    f"Fixed TESTS: {refined.get('reasoning', 'N/A')}"
                )

            iteration_log.append(iteration)

        final_passed = iteration_log[-1].tests_passed if iteration_log else False

        return RefinementResult(
            success=final_passed,
            total_iterations=len(iteration_log),
            final_code=current_code,
            final_tests=current_tests,
            iteration_log=iteration_log,
            final_test_output=(
                iteration_log[-1].test_output if iteration_log else ""
            ),
        )

    # ── Private helpers ────────────────────────────────────────────

    def _extract_code_from_generation(self, gen_result: GenerationResponse) -> str:
        """Pull raw code from the GenerationResponse diffs."""
        parts: List[str] = []
        for diff in gen_result.diffs:
            if diff.code:
                parts.append(f"# File: {diff.file_path}\n{diff.code}")
            elif diff.content:
                parts.append(f"# File: {diff.file_path}\n{diff.content}")
            elif diff.diff:
                parts.append(f"# File: {diff.file_path}\n{diff.diff}")
        return "\n\n".join(parts) if parts else gen_result.plan

    async def _run_pytest(
        self, code: str, tests: str
    ) -> tuple:
        """
        Run pytest in a temporary directory.
        Returns (output_text, passed_bool, failure_lines).

        Uses mkdtemp + manual cleanup to avoid WinError 5 (Access Denied)
        that occurs with TemporaryDirectory context manager on Windows when
        subprocess file handles are not yet released.
        """
        tmpdir = tempfile.mkdtemp(prefix="repopilot_test_")
        try:
            # Write the generated code
            code_file = os.path.join(tmpdir, "solution.py")
            test_file = os.path.join(tmpdir, "test_solution.py")

            with open(code_file, "w", encoding="utf-8") as f:
                f.write(code)

            # Prepend sys.path so tests can import solution
            test_with_import = (
                f"import sys, os\n"
                f"sys.path.insert(0, os.path.dirname(__file__))\n"
                f"{tests}"
            )
            with open(test_file, "w", encoding="utf-8") as f:
                f.write(test_with_import)

            try:
                result = subprocess.run(
                    ["python", "-m", "pytest", test_file,
                     "-v", "--tb=short", "--no-header"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=tmpdir,
                )
                output = result.stdout + result.stderr
                passed = result.returncode == 0

                # Extract failure lines
                failures: List[str] = []
                for line in output.split("\n"):
                    stripped = line.strip()
                    if any(kw in stripped for kw in
                           ["FAILED", "ERROR", "AssertionError",
                            "AssertionError", "ModuleNotFoundError",
                            "ImportError", "SyntaxError"]):
                        failures.append(stripped)

                return output, passed, failures

            except subprocess.TimeoutExpired:
                return (
                    "Test execution timed out (30s limit)",
                    False,
                    ["Timeout"],
                )
            except FileNotFoundError:
                return (
                    "pytest not found — install with: pip install pytest",
                    False,
                    ["pytest not installed"],
                )
            except Exception as e:
                return f"Error running tests: {e}", False, [str(e)]
        finally:
            # Clean up temp directory; on Windows, retry if files are still locked
            import shutil
            import time as _time
            for attempt in range(3):
                try:
                    shutil.rmtree(tmpdir, ignore_errors=False)
                    break
                except (PermissionError, OSError):
                    if attempt < 2:
                        _time.sleep(0.5)
                    else:
                        # Last resort: ignore cleanup errors
                        shutil.rmtree(tmpdir, ignore_errors=True)

    async def _refine(
        self, code: str, tests: str, failure_output: str
    ) -> dict:
        """Ask the LLM to fix either the code or the tests."""
        prompt = self.REFINE_PROMPT.format(
            failures=failure_output[:2000],
            code=code[:3000],
            tests=tests[:2000],
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a debugging expert. "
                    "Fix the failing code or tests. Return valid JSON only."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response = await llm.chat_completion(messages, json_mode=True)
            return json.loads(response)
        except Exception as e:
            logger.error("refinement_llm_failed", error=str(e))
            return {
                "fix_target": "tests",
                "reasoning": f"LLM refinement failed: {e}",
                "fixed_tests": tests,
                "fixed_code": "",
            }


# Global singleton
refinement_loop = RefinementLoop()
