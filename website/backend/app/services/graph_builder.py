"""
Graph Builder Service — Generate graph data for frontend visualization.

Transforms the file tree and architecture analysis into graph-friendly formats:
- Node/edge data for D3.js or React Flow
- Color coding by language/file type
- Complexity heatmap data (size-based)
- Dependency graph from package manifests
"""

import os
import json
from typing import Dict, Any, List, Optional, Set
from collections import defaultdict

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Language → color mapping for graph nodes
LANGUAGE_COLORS: Dict[str, str] = {
    "Python": "#3572A5",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "Java": "#b07219",
    "Go": "#00ADD8",
    "Rust": "#dea584",
    "Ruby": "#701516",
    "PHP": "#4F5D95",
    "C": "#555555",
    "C++": "#f34b7d",
    "C#": "#178600",
    "Swift": "#F05138",
    "Kotlin": "#A97BFF",
    "Scala": "#c22d40",
    "Dart": "#00B4AB",
    "Shell": "#89e051",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "SCSS": "#c6538c",
    "Vue": "#41b883",
    "Svelte": "#ff3e00",
    "Docker": "#384d54",
    "YAML": "#cb171e",
    "JSON": "#292929",
    "Markdown": "#083fa1",
    "SQL": "#e38c00",
    "GraphQL": "#e10098",
}

DEFAULT_COLOR = "#8b949e"


def build_graph_data(
    file_tree: Dict[str, Any],
    analysis: Dict[str, Any],
    all_files: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build graph visualization data from file tree + architecture analysis.
    Returns nodes, edges, and metadata for React Flow / D3.js rendering.
    """
    nodes = []
    edges = []
    node_id_counter = [0]
    
    def _walk_tree(node: Dict[str, Any], parent_id: Optional[str] = None, depth: int = 0):
        node_id = f"node_{node_id_counter[0]}"
        node_id_counter[0] += 1
        
        language = node.get("language")
        color = LANGUAGE_COLORS.get(language, DEFAULT_COLOR) if language else "#30363d"
        
        is_dir = node["type"] == "directory"
        child_count = len(node.get("children", []))
        
        graph_node = {
            "id": node_id,
            "type": "directory" if is_dir else "file",
            "name": node["name"],
            "path": node.get("path", ""),
            "language": language,
            "color": color,
            "size": node.get("size", 0),
            "depth": depth,
            "childCount": child_count,
        }
        
        # Compute complexity score for heatmap (files only)
        if not is_dir:
            size = node.get("size", 0)
            if size < 1000:
                graph_node["complexity"] = "low"
                graph_node["heatColor"] = "#22c55e"  # green
            elif size < 5000:
                graph_node["complexity"] = "medium"
                graph_node["heatColor"] = "#eab308"  # yellow
            elif size < 15000:
                graph_node["complexity"] = "high"
                graph_node["heatColor"] = "#f97316"  # orange
            else:
                graph_node["complexity"] = "very-high"
                graph_node["heatColor"] = "#ef4444"  # red
        
        nodes.append(graph_node)
        
        if parent_id:
            edges.append({
                "id": f"edge_{parent_id}_{node_id}",
                "source": parent_id,
                "target": node_id,
            })
        
        # Process children
        if is_dir:
            for child in node.get("children", []):
                _walk_tree(child, node_id, depth + 1)
    
    _walk_tree(file_tree)
    
    # Build component highlights from architecture analysis
    component_nodes = []
    for comp in analysis.get("components", []):
        if not isinstance(comp, dict):
            continue
        comp_path = str(comp.get("path", "")).rstrip("/")
        matching_node = next(
            (n for n in nodes if n["path"].rstrip("/") == comp_path),
            None
        )
        if matching_node:
            component_nodes.append({
                "nodeId": matching_node["id"],
                "name": str(comp.get("name", "")),
                "description": str(comp.get("description", "")),
                "path": comp_path,
            })
    
    # Highlight entry points
    entry_point_nodes = []
    for ep in analysis.get("entry_points", []):
        ep_path = str(ep)
        matching_node = next(
            (n for n in nodes if n["path"] == ep_path),
            None
        )
        if matching_node:
            entry_point_nodes.append({
                "nodeId": matching_node["id"],
                "path": ep_path,
            })
    
    return {
        "nodes": nodes,
        "edges": edges,
        "components": component_nodes,
        "entryPoints": entry_point_nodes,
        "totalNodes": len(nodes),
        "totalEdges": len(edges),
    }


def build_dependency_graph(
    repo_dir: str,
    key_files: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    Parse dependency manifests and build a dependency network graph.
    Supports: package.json, requirements.txt, go.mod, Cargo.toml, pom.xml
    """
    dependencies: List[Dict[str, Any]] = []
    dev_dependencies: List[Dict[str, Any]] = []
    categories: Dict[str, List[str]] = defaultdict(list)
    
    for kf in key_files:
        filepath = os.path.join(repo_dir, kf["path"])
        name = kf["name"]
        
        try:
            if name == "package.json":
                deps, dev_deps = _parse_package_json(filepath)
                dependencies.extend(deps)
                dev_dependencies.extend(dev_deps)
            elif name in ("requirements.txt", "Pipfile"):
                deps = _parse_requirements_txt(filepath)
                dependencies.extend(deps)
            elif name == "pyproject.toml":
                deps = _parse_pyproject_toml(filepath)
                dependencies.extend(deps)
            elif name == "go.mod":
                deps = _parse_go_mod(filepath)
                dependencies.extend(deps)
            elif name == "Cargo.toml":
                deps = _parse_cargo_toml(filepath)
                dependencies.extend(deps)
        except Exception as e:
            logger.warning("dependency_parse_failed", file=name, error=str(e))
    
    # Categorize known dependencies
    for dep in dependencies + dev_dependencies:
        category = _categorize_dependency(dep["name"])
        dep["category"] = category
        categories[category].append(dep["name"])
    
    return {
        "dependencies": dependencies,
        "devDependencies": dev_dependencies,
        "categories": dict(categories),
        "totalDeps": len(dependencies),
        "totalDevDeps": len(dev_dependencies),
    }


def _parse_package_json(filepath: str):
    """Parse npm package.json."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    deps = [{"name": k, "version": v, "type": "runtime", "ecosystem": "npm"} 
            for k, v in data.get("dependencies", {}).items()]
    dev_deps = [{"name": k, "version": v, "type": "dev", "ecosystem": "npm"} 
                for k, v in data.get("devDependencies", {}).items()]
    return deps, dev_deps


def _parse_requirements_txt(filepath: str):
    """Parse Python requirements.txt."""
    deps = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("-"):
                # Parse: package>=1.0.0 or package==1.0.0 or just package
                parts = line.split(">=")
                if len(parts) == 1:
                    parts = line.split("==")
                if len(parts) == 1:
                    parts = line.split("~=")
                if len(parts) == 1:
                    parts = line.split("<=")
                name = parts[0].strip()
                version = parts[1].strip() if len(parts) > 1 else "*"
                if name:
                    deps.append({"name": name, "version": version, "type": "runtime", "ecosystem": "pip"})
    return deps


def _parse_pyproject_toml(filepath: str):
    """Parse Python pyproject.toml (basic)."""
    deps = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        # Simple regex for dependencies list
        import re
        match = re.search(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
        if match:
            for item in re.findall(r'"([^"]+)"', match.group(1)):
                name = item.split(">=")[0].split("==")[0].split("<")[0].split(">")[0].strip()
                if name:
                    deps.append({"name": name, "version": "*", "type": "runtime", "ecosystem": "pip"})
    except Exception:
        pass
    return deps


def _parse_go_mod(filepath: str):
    """Parse Go go.mod."""
    deps = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            in_require = False
            for line in f:
                line = line.strip()
                if line.startswith("require ("):
                    in_require = True
                    continue
                if in_require and line == ")":
                    in_require = False
                    continue
                if in_require and line:
                    parts = line.split()
                    if len(parts) >= 2:
                        deps.append({"name": parts[0], "version": parts[1], "type": "runtime", "ecosystem": "go"})
    except Exception:
        pass
    return deps


def _parse_cargo_toml(filepath: str):
    """Parse Rust Cargo.toml (basic)."""
    deps = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            in_deps = False
            for line in f:
                line = line.strip()
                if line == "[dependencies]":
                    in_deps = True
                    continue
                if line.startswith("[") and in_deps:
                    in_deps = False
                    continue
                if in_deps and "=" in line:
                    name, version = line.split("=", 1)
                    name = name.strip()
                    version = version.strip().strip('"')
                    if name:
                        deps.append({"name": name, "version": version, "type": "runtime", "ecosystem": "cargo"})
    except Exception:
        pass
    return deps


# Known dependency categories
FRAMEWORK_DEPS = {"react", "next", "vue", "nuxt", "svelte", "angular", "express", "fastapi", "flask", "django", "spring", "rails", "laravel", "gin", "fiber", "actix", "rocket"}
DATABASE_DEPS = {"prisma", "mongoose", "sequelize", "typeorm", "drizzle", "sqlalchemy", "psycopg2", "pymongo", "redis", "chromadb", "pg", "mysql2", "sqlite3"}
TESTING_DEPS = {"jest", "vitest", "mocha", "cypress", "playwright", "pytest", "unittest", "testing-library"}
UI_DEPS = {"tailwindcss", "chakra-ui", "material-ui", "ant-design", "bootstrap", "framer-motion", "gsap", "three", "d3"}
DEVTOOLS_DEPS = {"eslint", "prettier", "typescript", "webpack", "vite", "rollup", "babel", "esbuild", "turbo"}
AUTH_DEPS = {"next-auth", "passport", "jsonwebtoken", "bcrypt", "jose", "clerk"}
API_DEPS = {"axios", "fetch", "httpx", "requests", "graphql", "trpc", "openai", "google-genai"}


def _categorize_dependency(name: str) -> str:
    """Categorize a dependency by name."""
    name_lower = name.lower().replace("@", "").replace("/", "-")
    
    for dep in FRAMEWORK_DEPS:
        if dep in name_lower:
            return "Framework"
    for dep in DATABASE_DEPS:
        if dep in name_lower:
            return "Database"
    for dep in TESTING_DEPS:
        if dep in name_lower:
            return "Testing"
    for dep in UI_DEPS:
        if dep in name_lower:
            return "UI/Animation"
    for dep in DEVTOOLS_DEPS:
        if dep in name_lower:
            return "DevTools"
    for dep in AUTH_DEPS:
        if dep in name_lower:
            return "Auth"
    for dep in API_DEPS:
        if dep in name_lower:
            return "API/HTTP"
    
    return "Other"
