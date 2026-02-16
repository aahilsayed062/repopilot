"""
Dynamic Multi-Agent Router.
Analyzes user query and decides which agents to invoke.
"""
import json
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel
from app.utils.llm import llm
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AgentAction(str, Enum):
    EXPLAIN = "EXPLAIN"        # Q&A -> Retriever + Answerer
    GENERATE = "GENERATE"      # Code Gen -> Retriever + Generator
    TEST = "TEST"              # PyTest -> Retriever + TestGenerator
    DECOMPOSE = "DECOMPOSE"    # Complex -> Planner + multiple sub-flows
    REFUSE = "REFUSE"          # Insufficient info -> Safe refusal


class RoutingDecision(BaseModel):
    primary_action: AgentAction
    secondary_actions: List[AgentAction] = []
    reasoning: str
    confidence: float  # 0.0-1.0
    should_decompose: bool = False
    parallel_agents: List[AgentAction] = []  # agents that can run in parallel
    skip_agents: List[str] = []  # agents explicitly skipped


class AgentRouter:
    ROUTING_PROMPT = """You are a routing controller for RepoPilot.
Analyze the user query and decide which agents should handle it.

Available agents:
- EXPLAIN: Answer questions about the codebase (Q&A)
- GENERATE: Generate new code or modify existing code
- TEST: Generate PyTest test cases
- DECOMPOSE: Break complex queries into sub-questions first
- REFUSE: When the query is outside scope or unsafe

Rules:
- Simple questions -> EXPLAIN only (skip DECOMPOSE, skip GENERATE)
- "Add X" / "Create X" / "Implement X" -> GENERATE (may add TEST in parallel)
- "Write tests for X" -> TEST only
- Complex multi-part questions -> DECOMPOSE first, then EXPLAIN
- "Refactor X and add tests" -> GENERATE + TEST in parallel
- Unsafe/irrelevant queries -> REFUSE

Return JSON:
{
  "primary_action": "EXPLAIN|GENERATE|TEST|DECOMPOSE|REFUSE",
  "secondary_actions": ["TEST"],  
  "reasoning": "Why this routing",
  "confidence": 0.85,
  "should_decompose": false,
  "parallel_agents": ["TEST"],
  "skip_agents": ["DECOMPOSE"]
}"""

    async def route(self, query: str, repo_context: str = "") -> RoutingDecision:
        """Decide which agents to invoke for this query."""
        messages = [
            {"role": "system", "content": self.ROUTING_PROMPT},
            {"role": "user", "content": f"Query: {query}\nRepo context: {repo_context or 'General'}"}
        ]
        
        try:
            response = await llm.chat_completion(messages, json_mode=True, provider_override="ollama_b")
            data = json.loads(response)
            return RoutingDecision(**data)
        except Exception as e:
            logger.error("routing_failed", error=str(e))
            # Fallback: heuristic routing
            return self._heuristic_route(query)
    
    def _heuristic_route(self, query: str) -> RoutingDecision:
        """Fast fallback if LLM routing fails."""
        q = query.lower()
        
        gen_keywords = ["add", "create", "implement", "build", "write code", "generate", "refactor", "modify", "change"]
        test_keywords = ["test", "pytest", "unittest", "write tests"]
        refuse_keywords = ["delete prod", "drop database", "rm -rf"]
        
        if any(k in q for k in refuse_keywords):
            return RoutingDecision(primary_action=AgentAction.REFUSE, reasoning="Unsafe operation detected", confidence=0.95)
        
        if any(k in q for k in test_keywords):
            return RoutingDecision(primary_action=AgentAction.TEST, reasoning="Test generation request", confidence=0.9)
        
        if any(k in q for k in gen_keywords):
            return RoutingDecision(
                primary_action=AgentAction.GENERATE,
                secondary_actions=[AgentAction.TEST],
                parallel_agents=[AgentAction.TEST],
                reasoning="Code generation with parallel test gen",
                confidence=0.85
            )
        
        if len(q.split()) > 20:
            return RoutingDecision(
                primary_action=AgentAction.DECOMPOSE,
                secondary_actions=[AgentAction.EXPLAIN],
                should_decompose=True,
                reasoning="Complex query needs decomposition",
                confidence=0.7
            )
        
        return RoutingDecision(primary_action=AgentAction.EXPLAIN, reasoning="Simple Q&A", confidence=0.8, skip_agents=["GENERATE", "TEST", "DECOMPOSE"])


agent_router = AgentRouter()
