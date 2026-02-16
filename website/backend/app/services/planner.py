from typing import List, Optional
import json
from app.utils.llm import llm
from app.utils.logger import get_logger

logger = get_logger(__name__)


class Planner:
    """
    Analyzes questions to determine if decomposition is needed.
    """
    
    SYSTEM_PROMPT = """You are a query decomposition engine.
    Analyze the user's question about a codebase. 
    If the question is complex (e.g., involves multiple components, architecture, or cross-file dependencies), break it into 2-3 specific sub-questions.
    If the question is simple or direct, return null.
    
    Format: Return a JSON object with a 'sub_questions' list or null.
    Example: {"sub_questions": ["Where is X defined?", "How does Y call X?"]}
    """

    def should_decompose(self, query: str) -> bool:
        """
        Heuristic gate to avoid unnecessary LLM decomposition latency.
        """
        q = (query or "").strip().lower()
        if not q:
            return False
        if len(q) < 90:
            return False

        complex_markers = [
            "architecture",
            "flow",
            "end-to-end",
            "across",
            "interaction",
            "dependency",
            "dependencies",
            "compare",
            "tradeoff",
            "refactor",
            "security",
            "performance",
            "multi",
        ]
        return any(marker in q for marker in complex_markers)
    
    async def decompose(self, query: str) -> Optional[List[str]]:
        """
        Break down complex question into sub-questions using LLM.
        """
        try:
            response = await llm.chat_completion(
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": query}
                ],
                json_mode=True
            )
            
            data = json.loads(response)
            if data and "sub_questions" in data:
                logger.info("query_decomposed", original=query, sub_count=len(data["sub_questions"]))
                return data["sub_questions"]
        except Exception as e:
            logger.error("decomposition_failed", error=str(e))
            
        return None

planner = Planner()
