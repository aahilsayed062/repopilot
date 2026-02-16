import asyncio

from app.models.chat import ChatRequest
from app.routes import chat as chat_routes
from app.services.agent_router import AgentAction, RoutingDecision
from app.services.evaluator import CodeEvaluator, ControllerVerdict
from app.services.generator import CodeGenerationRequest


class _Dumpable:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self):
        return self._payload


def test_smart_runs_evaluation_when_explain_and_generate(monkeypatch):
    async def fake_route(_question):
        return RoutingDecision(
            primary_action=AgentAction.EXPLAIN,
            secondary_actions=[AgentAction.GENERATE],
            reasoning="Need both explanation and generation",
            confidence=0.92,
            skip_agents=[],
        )

    async def fake_explain(_request):
        return {
            "answer": "Explanation branch answer",
            "citations": [],
            "confidence": "medium",
            "assumptions": [],
        }

    async def fake_generate(_request):
        return {
            "plan": "Generated changes",
            "diffs": [{"file_path": "app.py", "diff": "+print('ok')"}],
            "tests": "def test_ok(): assert True",
            "citations": ["app.py"],
        }

    async def fake_evaluate_generation(**_kwargs):
        return _Dumpable(
            {
                "enabled": True,
                "critic": {"provider": "ollama", "score": 8.1, "issues": [], "feedback": "", "suggested_changes": []},
                "defender": {"provider": "gemini", "score": 7.9, "issues": [], "feedback": "", "suggested_changes": []},
                "controller": {
                    "decision": "MERGE_FEEDBACK",
                    "reasoning": "Good with small fixes",
                    "final_score": 8.0,
                    "confidence": 0.78,
                    "merged_issues": ["minor naming"],
                    "priority_fixes": ["rename helper"],
                    "improved_code_by_file": [{"file_path": "app.py", "code": "print('ok')"}],
                },
            }
        )

    async def fake_impact_analyze(**_kwargs):
        return _Dumpable(
            {
                "directly_changed": ["app.py"],
                "indirectly_affected": [],
                "risk_level": "LOW",
                "risks": [],
                "recommendations": ["Run tests"],
            }
        )

    monkeypatch.setattr("app.services.agent_router.agent_router.route", fake_route)
    monkeypatch.setattr(chat_routes, "_run_explain", fake_explain)
    monkeypatch.setattr(chat_routes, "_run_generate", fake_generate)
    monkeypatch.setattr("app.services.evaluator.evaluator.evaluate_generation", fake_evaluate_generation)
    monkeypatch.setattr("app.services.impact_analyzer.impact_analyzer.analyze", fake_impact_analyze)

    request = ChatRequest(repo_id="repo-x", question="implement feature")
    result = asyncio.run(chat_routes.smart_chat(request))

    assert result["answer"] == "Explanation branch answer"
    assert "evaluation" in result
    assert result["evaluation"]["controller"]["decision"] == "MERGE_FEEDBACK"
    assert result["evaluation_improved_code"][0]["file_path"] == "app.py"
    assert "impact" in result
    assert result["impact"]["risk_level"] == "LOW"


def test_evaluator_degrades_when_reviewers_timeout(monkeypatch):
    evaluator = CodeEvaluator()
    evaluator.REVIEWER_TIMEOUT_SECONDS = 0.01

    async def slow_reviewer(**_kwargs):
        await asyncio.sleep(0.05)
        return None

    async def fake_controller(**_kwargs):
        return ControllerVerdict(
            decision="REQUEST_REVISION",
            reasoning="Fallback from timeout path",
            final_score=0.0,
            confidence=0.3,
            merged_issues=[],
            priority_fixes=[],
            improved_code_by_file=[],
        )

    monkeypatch.setattr(evaluator, "_run_reviewer", slow_reviewer)
    monkeypatch.setattr(evaluator, "_run_controller", fake_controller)

    result = asyncio.run(
        evaluator.evaluate_generation(
            request_text="add validation",
            generated_diffs=[{"file_path": "svc.py", "diff": "+pass"}],
            tests_text="",
            context="",
        )
    )

    assert result.enabled is True
    assert result.critic is None
    assert result.defender is None
    assert result.controller.decision == "REQUEST_REVISION"


def test_evaluate_endpoint_returns_controller_payload(monkeypatch):
    async def fake_evaluate_generation(**_kwargs):
        return _Dumpable(
            {
                "enabled": True,
                "critic": None,
                "defender": None,
                "controller": {
                    "decision": "ACCEPT_ORIGINAL",
                    "reasoning": "Looks good",
                    "final_score": 8.6,
                    "confidence": 0.88,
                    "merged_issues": [],
                    "priority_fixes": [],
                    "improved_code_by_file": [],
                },
            }
        )

    monkeypatch.setattr("app.services.evaluator.evaluator.evaluate_generation", fake_evaluate_generation)

    payload = chat_routes.EvaluateRequest(
        request_text="ship this",
        generated_diffs=[{"file_path": "main.py", "diff": "+print(1)"}],
    )
    result = asyncio.run(chat_routes.evaluate_generation(payload))

    assert result["enabled"] is True
    assert result["controller"]["decision"] == "ACCEPT_ORIGINAL"


def test_refine_endpoint_returns_refinement_contract(monkeypatch):
    async def fake_run_refinement(**_kwargs):
        return _Dumpable(
            {
                "success": True,
                "total_iterations": 2,
                "final_code": "print('done')",
                "final_tests": "def test_done(): assert True",
                "iteration_log": [],
                "final_test_output": "2 passed",
            }
        )

    monkeypatch.setattr("app.services.refinement_loop.refinement_loop.run_refinement", fake_run_refinement)

    request = CodeGenerationRequest(repo_id="repo-x", request="improve module", chat_history=[])
    result = asyncio.run(chat_routes.refine_code(request))

    assert result["success"] is True
    assert result["total_iterations"] == 2
    assert "final_code" in result


def test_smart_defers_test_and_skips_when_revision_recommended(monkeypatch):
    async def fake_route(_question):
        return RoutingDecision(
            primary_action=AgentAction.GENERATE,
            secondary_actions=[AgentAction.TEST],
            parallel_agents=[AgentAction.TEST],
            reasoning="Generate and test",
            confidence=0.9,
            skip_agents=[],
        )

    async def fake_generate(_request):
        return {
            "plan": "Generated changes",
            "diffs": [{"file_path": "svc.py", "diff": "+print('ok')"}],
            "tests": "def test_ok(): assert True",
            "citations": ["svc.py"],
        }

    async def fake_evaluate_generation(**_kwargs):
        return _Dumpable(
            {
                "enabled": True,
                "critic": None,
                "defender": None,
                "controller": {
                    "decision": "REQUEST_REVISION",
                    "reasoning": "Needs fixes first",
                    "final_score": 4.2,
                    "confidence": 0.7,
                    "merged_issues": ["validation missing"],
                    "priority_fixes": ["add validation"],
                    "improved_code_by_file": [],
                },
            }
        )

    called = {"test": 0}

    async def fake_test(_request, extra_context=""):
        called["test"] += 1
        return {"success": True, "tests": "def test_x(): pass"}

    monkeypatch.setattr("app.services.agent_router.agent_router.route", fake_route)
    monkeypatch.setattr(chat_routes, "_run_generate", fake_generate)
    monkeypatch.setattr(chat_routes, "_run_test", fake_test)
    monkeypatch.setattr("app.services.evaluator.evaluator.evaluate_generation", fake_evaluate_generation)

    request = ChatRequest(repo_id="repo-x", question="implement feature with tests")
    result = asyncio.run(chat_routes.smart_chat(request))

    assert called["test"] == 0
    assert result["test"]["skipped"] is True
    assert "finalized_generation" in result
    assert "TEST" in result["agents_skipped"]
    assert "TEST" not in result["agents_used"]
