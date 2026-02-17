"""
Architecture LLM Service — Gemini Flash architecture analysis.

Single-shot LLM call that produces structured architecture analysis:
- One-liner summary
- Tech stack detection
- Architecture pattern identification
- Key components and their roles
- Entry points
- Data flow explanation
- Mermaid.js architecture diagram
- README TL;DR summary
"""

import json
import re
from typing import Dict, Any, Optional

import google.generativeai as genai

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


ARCHITECTURE_PROMPT = """You are an expert software architect. Analyze this repository structure and key files, then produce a comprehensive architecture analysis.

## Repository: {repo_name}

## File Tree:
```
{file_tree}
```

## Key File Contents:
{key_files_content}

## Stats:
- Total files: {total_files}
- Total lines of code: {total_lines}
- Languages: {languages}
- Structure type: {structure_type}

---

Respond with ONLY a valid JSON object (no markdown fences, no extra text) with these exact keys:

{{
  "summary": "One-liner description of what this project does (max 100 words)",
  "tech_stack": ["List", "of", "technologies", "frameworks", "databases", "tools"],
  "architecture_pattern": "e.g., Monolith, Microservices, Monorepo, Full-Stack, CLI Tool, Library, etc.",
  "components": [
    {{
      "name": "Component Name",
      "path": "path/to/component/",
      "description": "What this component does (1-2 sentences)"
    }}
  ],
  "entry_points": ["path/to/main/entry.py", "path/to/other/entry.ts"],
  "data_flow": "Describe how data flows through the system in one paragraph",
  "mermaid_diagram": "graph TD\\n  A[Component] --> B[Component]\\n  ...",
  "readme_summary": "TL;DR of the README if available, else null"
}}

IMPORTANT:
- The mermaid_diagram should be a valid Mermaid.js flowchart showing the main components and their relationships
- Use \\n for newlines in the mermaid diagram string
- Keep the diagram focused on 4-8 main components, not every file
- Make sure the JSON is valid — escape special characters properly
- For tech_stack, include specific versions if visible in config files
"""


async def analyze_architecture(
    repo_name: str,
    file_tree_text: str,
    key_files_content: Dict[str, str],
    stats: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Send repo structure + key files to Gemini Flash for architecture analysis.
    Returns structured JSON with summary, tech stack, components, etc.
    """
    
    if not settings.gemini_api_key:
        logger.warning("no_gemini_key", msg="Returning mock architecture analysis")
        return _mock_response(repo_name, stats)
    
    # Format key files content for the prompt
    key_files_section = ""
    for path, content in key_files_content.items():
        key_files_section += f"\n### {path}\n```\n{content[:5000]}\n```\n"
    
    if not key_files_section:
        key_files_section = "(No key config files found)"
    
    # Format languages
    languages_str = ", ".join(
        f"{lang}: {info['files']} files / {info['lines']} lines" 
        for lang, info in sorted(
            stats.get("languages", {}).items(), 
            key=lambda x: x[1]["files"], 
            reverse=True
        )[:10]
    )
    
    prompt = ARCHITECTURE_PROMPT.format(
        repo_name=repo_name,
        file_tree=file_tree_text,
        key_files_content=key_files_section,
        total_files=stats.get("total_files", 0),
        total_lines=stats.get("total_lines", 0),
        languages=languages_str,
        structure_type=stats.get("structure_type", "unknown"),
    )
    
    try:
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(
            model_name=settings.gemini_chat_model,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=4096,
            ),
        )
        
        response = model.generate_content(prompt)
        
        raw_text = response.text.strip()
        logger.info("gemini_response_received", length=len(raw_text))
        
        # Parse JSON from response (handle markdown fences)
        parsed = _parse_json_response(raw_text)
        
        if parsed:
            # Ensure all expected keys exist
            return _normalize_response(parsed, repo_name, stats)
        else:
            logger.warning("json_parse_failed", raw=raw_text[:500])
            return _mock_response(repo_name, stats)
    
    except Exception as e:
        logger.error("gemini_analysis_failed", error=str(e))
        return _mock_response(repo_name, stats)


def _parse_json_response(raw_text: str) -> Optional[Dict]:
    """Try to extract and parse JSON from LLM response."""
    # Try direct parse
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass
    
    # Try extracting from markdown code fences
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass
    
    # Try finding JSON object boundaries
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw_text[start:end + 1])
        except json.JSONDecodeError:
            pass
    
    return None


def _normalize_response(parsed: Dict, repo_name: str, stats: Dict) -> Dict[str, Any]:
    """Ensure all expected keys exist with proper types."""
    raw_tech_stack = parsed.get("tech_stack", [])
    if isinstance(raw_tech_stack, list):
        tech_stack = [str(item).strip() for item in raw_tech_stack if str(item).strip()]
    elif isinstance(raw_tech_stack, str):
        tech_stack = [raw_tech_stack.strip()] if raw_tech_stack.strip() else []
    else:
        tech_stack = []

    raw_components = parsed.get("components", [])
    components = []
    if isinstance(raw_components, list):
        for idx, comp in enumerate(raw_components):
            if not isinstance(comp, dict):
                continue
            name = str(comp.get("name", f"Component {idx + 1}")).strip() or f"Component {idx + 1}"
            path = str(comp.get("path", "")).strip()
            description = str(comp.get("description", "")).strip() or "No description provided."
            components.append({
                "name": name,
                "path": path,
                "description": description,
            })

    raw_entry_points = parsed.get("entry_points", [])
    if isinstance(raw_entry_points, list):
        entry_points = [str(item).strip() for item in raw_entry_points if str(item).strip()]
    elif isinstance(raw_entry_points, str):
        entry_points = [raw_entry_points.strip()] if raw_entry_points.strip() else []
    else:
        entry_points = []

    data_flow = parsed.get("data_flow", "")
    if not isinstance(data_flow, str):
        data_flow = str(data_flow)

    mermaid_diagram = parsed.get("mermaid_diagram", "")
    if not isinstance(mermaid_diagram, str):
        mermaid_diagram = str(mermaid_diagram)

    return {
        "summary": parsed.get("summary", f"Repository {repo_name}"),
        "tech_stack": tech_stack,
        "architecture_pattern": parsed.get("architecture_pattern", "Unknown"),
        "components": components,
        "entry_points": entry_points,
        "data_flow": data_flow,
        "mermaid_diagram": mermaid_diagram,
        "readme_summary": parsed.get("readme_summary"),
    }


def _mock_response(repo_name: str, stats: Dict) -> Dict[str, Any]:
    """Return a mock response when Gemini is not available."""
    top_langs = list(stats.get("languages", {}).keys())[:5]
    return {
        "summary": f"Repository {repo_name} — a software project using {', '.join(top_langs) if top_langs else 'unknown languages'}.",
        "tech_stack": top_langs,
        "architecture_pattern": stats.get("structure_type", "Standard").title(),
        "components": [
            {"name": "Source Code", "path": "src/", "description": "Main application source code"}
        ],
        "entry_points": [],
        "data_flow": "Unable to analyze data flow without LLM API key. Set GEMINI_API_KEY to enable full analysis.",
        "mermaid_diagram": f"graph TD\n  A[{repo_name}] --> B[Source Code]\n  B --> C[Output]",
        "readme_summary": None,
    }
