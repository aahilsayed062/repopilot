"""
Analyze Route — POST /api/analyze

Main endpoint: accepts a GitHub URL, clones the repo, analyzes structure,
calls Gemini for architecture analysis, builds graph data, cleans up.
"""

import time
import hashlib
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.models.analyze import AnalyzeRequest, AnalyzeResponse
from app.services.repo_fetcher import clone_repo, cleanup_repo, parse_github_url
from app.services.structure_analyzer import (
    analyze_structure, 
    get_key_file_contents, 
    build_tree_text,
)
from app.services.architecture_llm import analyze_architecture
from app.services.graph_builder import build_graph_data, build_dependency_graph
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/analyze", tags=["analyze"])

# Simple in-memory cache (keyed by repo URL)
_analysis_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours


@router.post("", response_model=AnalyzeResponse)
async def analyze_repo(request: AnalyzeRequest):
    """
    Analyze a GitHub repository.
    
    1. Clone the repo (shallow, --depth 1)
    2. Scan file tree + compute language stats (zero LLM tokens)
    3. Read key config files
    4. Send structure + key files to Gemini Flash for architecture analysis
    5. Build graph visualization data
    6. Build dependency graph
    7. Cleanup cloned repo
    8. Return structured response
    """
    start_time = time.time()
    
    # Check cache
    cache_key = f"{request.github_url}:{request.branch or 'default'}"
    cached = _analysis_cache.get(cache_key)
    if cached and (time.time() - cached["_timestamp"]) < CACHE_TTL_SECONDS:
        logger.info("cache_hit", repo=request.github_url)
        response_data = {k: v for k, v in cached.items() if not k.startswith("_")}
        return AnalyzeResponse(**response_data)
    
    temp_dir = None
    
    try:
        # Step 1: Clone
        logger.info("step_1_clone", url=request.github_url)
        clone_result = await clone_repo(request.github_url, request.branch)
        temp_dir = clone_result["temp_dir"]
        repo_name = clone_result["repo_name"]
        branch = clone_result["branch"]
        
        # Step 2: Structure analysis (zero LLM tokens)
        logger.info("step_2_structure", repo=repo_name)
        structure = analyze_structure(temp_dir)
        
        # Step 3: Read key files
        logger.info("step_3_key_files", count=len(structure["key_files"]))
        key_file_contents = get_key_file_contents(temp_dir, structure["key_files"])
        
        # Step 4: LLM architecture analysis
        logger.info("step_4_llm_analysis", repo=repo_name)
        file_tree_text = build_tree_text(structure["file_tree"])
        architecture = await analyze_architecture(
            repo_name=repo_name,
            file_tree_text=file_tree_text,
            key_files_content=key_file_contents,
            stats=structure,
        )
        
        # Step 5: Build graph data
        logger.info("step_5_graph", repo=repo_name)
        graph = build_graph_data(
            file_tree=structure["file_tree"],
            analysis=architecture,
            all_files=structure["all_files"],
        )
        
        # Step 6: Build dependency graph
        logger.info("step_6_dependencies", repo=repo_name)
        dep_graph = build_dependency_graph(temp_dir, structure["key_files"])
        
        elapsed = time.time() - start_time
        logger.info("analysis_complete", repo=repo_name, elapsed_s=f"{elapsed:.1f}")
        
        # Build response
        response_data = {
            "repo_name": repo_name,
            "branch": branch,
            "summary": architecture["summary"],
            "tech_stack": architecture["tech_stack"],
            "architecture_pattern": architecture["architecture_pattern"],
            "components": architecture["components"],
            "entry_points": architecture["entry_points"],
            "data_flow": architecture["data_flow"],
            "mermaid_diagram": architecture["mermaid_diagram"],
            "readme_summary": architecture.get("readme_summary"),
            "stats": {
                "total_files": structure["total_files"],
                "total_lines": structure["total_lines"],
                "languages": structure["languages"],
                "languages_pct": structure["languages_pct"],
                "directory_depth": structure["directory_depth"],
                "structure_type": structure["structure_type"],
            },
            "file_tree": structure["file_tree"],
            "graph": graph,
            "dependency_graph": dep_graph,
            "key_files": structure["key_files"],
        }
        
        # Cache result
        _analysis_cache[cache_key] = {**response_data, "_timestamp": time.time()}
        
        # Limit cache size
        if len(_analysis_cache) > 100:
            oldest_key = min(_analysis_cache, key=lambda k: _analysis_cache[k]["_timestamp"])
            del _analysis_cache[oldest_key]
        
        return AnalyzeResponse(**response_data)
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TimeoutError as e:
        raise HTTPException(status_code=408, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("analyze_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    finally:
        # Step 7: Cleanup
        if temp_dir:
            cleanup_repo(temp_dir)
