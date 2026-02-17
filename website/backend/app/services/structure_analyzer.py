"""
Structure Analyzer Service — Build file tree + language stats.

Zero LLM tokens — purely local analysis:
- Walk file tree, classify every file by language
- Compute stats: total files, lines of code per language, directory depth
- Detect common patterns: src/, tests/, docs/, config/, monorepo
- Identify key files: README.md, package.json, requirements.txt, etc.
- Build a JSON tree structure for the frontend graph
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from collections import defaultdict

from app.utils.logger import get_logger

logger = get_logger(__name__)

# File extension → language mapping
EXTENSION_MAP: Dict[str, str] = {
    ".py": "Python", ".pyx": "Python", ".pyi": "Python",
    ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".c": "C", ".h": "C",
    ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".hpp": "C++",
    ".cs": "C#",
    ".swift": "Swift",
    ".kt": "Kotlin", ".kts": "Kotlin",
    ".scala": "Scala",
    ".r": "R", ".R": "R",
    ".lua": "Lua",
    ".dart": "Dart",
    ".ex": "Elixir", ".exs": "Elixir",
    ".erl": "Erlang",
    ".hs": "Haskell",
    ".clj": "Clojure",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".sql": "SQL",
    ".html": "HTML", ".htm": "HTML",
    ".css": "CSS", ".scss": "SCSS", ".sass": "Sass", ".less": "Less",
    ".json": "JSON",
    ".yaml": "YAML", ".yml": "YAML",
    ".xml": "XML",
    ".md": "Markdown", ".mdx": "Markdown",
    ".txt": "Text",
    ".toml": "TOML",
    ".ini": "INI",
    ".cfg": "INI",
    ".dockerfile": "Docker",
    ".proto": "Protobuf",
    ".graphql": "GraphQL", ".gql": "GraphQL",
    ".vue": "Vue",
    ".svelte": "Svelte",
}

# Key config/entry file names to detect
KEY_FILES: Set[str] = {
    "README.md", "readme.md", "README.rst",
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "requirements.txt", "Pipfile", "pyproject.toml", "setup.py", "setup.cfg",
    "Cargo.toml", "Cargo.lock",
    "go.mod", "go.sum",
    "pom.xml", "build.gradle", "build.gradle.kts",
    "Gemfile", "Gemfile.lock",
    "composer.json",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "Makefile", "CMakeLists.txt",
    ".env.example", ".env",
    "tsconfig.json", "jsconfig.json",
    "webpack.config.js", "vite.config.ts", "vite.config.js",
    "next.config.js", "next.config.ts", "next.config.mjs",
    "nuxt.config.ts", "nuxt.config.js",
    "tailwind.config.js", "tailwind.config.ts",
    ".eslintrc.js", ".eslintrc.json", "eslint.config.mjs",
    ".prettierrc", ".prettierrc.json",
    "vercel.json", "netlify.toml",
    "railway.json",
    "Procfile",
    "app.yaml", "app.yml",
    ".github/workflows", "CI",
}

# Directories to skip
SKIP_DIRS: Set[str] = {
    ".git", "node_modules", "__pycache__", ".next", ".nuxt",
    "dist", "build", ".cache", ".vscode", ".idea",
    "venv", ".venv", "env", ".env",
    "vendor", "target", "bin", "obj",
    ".tox", ".pytest_cache", ".mypy_cache",
    "coverage", ".nyc_output",
    "eggs", "*.egg-info",
}

# Common architecture patterns to detect
PATTERN_DIRS = {
    "src": "source",
    "lib": "library",
    "tests": "testing", "test": "testing", "spec": "testing", "__tests__": "testing",
    "docs": "documentation", "doc": "documentation",
    "config": "configuration", "configs": "configuration",
    "scripts": "scripts",
    "migrations": "database",
    "models": "models", "entities": "models",
    "controllers": "controllers", "handlers": "controllers",
    "routes": "routing", "router": "routing", "api": "api",
    "services": "services",
    "utils": "utilities", "helpers": "utilities", "common": "utilities",
    "middleware": "middleware",
    "components": "ui-components",
    "pages": "pages",
    "app": "application",
    "public": "static-assets", "static": "static-assets", "assets": "static-assets",
    "templates": "templates", "views": "views",
}


def analyze_structure(repo_dir: str) -> Dict[str, Any]:
    """
    Analyze a repository's structure and return comprehensive stats.
    Returns file tree, language stats, key files, and detected patterns.
    """
    repo_path = Path(repo_dir)
    
    file_tree = _build_file_tree(repo_path, repo_path)
    language_stats = defaultdict(lambda: {"files": 0, "lines": 0})
    total_files = 0
    total_lines = 0
    max_depth = 0
    key_files_found: List[Dict[str, str]] = []
    detected_patterns: List[str] = []
    all_files: List[Dict[str, Any]] = []
    
    for dirpath, dirnames, filenames in os.walk(repo_dir):
        # Skip ignored directories
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        
        rel_dir = os.path.relpath(dirpath, repo_dir)
        depth = rel_dir.count(os.sep) + 1 if rel_dir != "." else 0
        max_depth = max(max_depth, depth)
        
        # Detect architecture patterns from directory names
        dir_name = os.path.basename(dirpath)
        if dir_name in PATTERN_DIRS and depth <= 2:
            pattern = PATTERN_DIRS[dir_name]
            if pattern not in detected_patterns:
                detected_patterns.append(pattern)
        
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(filepath, repo_dir).replace("\\", "/")
            
            # Detect language
            ext = os.path.splitext(filename)[1].lower()
            language = EXTENSION_MAP.get(ext, None)
            
            # Special cases for files without extensions
            if not language:
                if filename == "Dockerfile":
                    language = "Docker"
                elif filename == "Makefile":
                    language = "Makefile"
                elif filename == "Procfile":
                    language = "Procfile"
            
            # Count lines
            line_count = 0
            file_size = 0
            try:
                file_size = os.path.getsize(filepath)
                if language and file_size < 1024 * 1024:  # < 1MB
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        line_count = sum(1 for _ in f)
            except (OSError, UnicodeDecodeError):
                pass
            
            if language:
                language_stats[language]["files"] += 1
                language_stats[language]["lines"] += line_count
                total_lines += line_count
            
            total_files += 1
            
            # Check if key file
            if filename in KEY_FILES:
                key_files_found.append({
                    "name": filename,
                    "path": rel_path,
                    "language": language or "Config",
                })
            
            all_files.append({
                "path": rel_path,
                "name": filename,
                "language": language,
                "lines": line_count,
                "size": file_size,
            })
    
    # Compute language percentages
    languages_pct = {}
    if total_files > 0:
        code_files = sum(s["files"] for s in language_stats.values())
        for lang, stats in sorted(language_stats.items(), key=lambda x: x[1]["files"], reverse=True):
            pct = round((stats["files"] / code_files * 100), 1) if code_files > 0 else 0
            languages_pct[lang] = pct
    
    # Detect monorepo or special structure
    top_dirs = [d for d in os.listdir(repo_dir) 
                if os.path.isdir(os.path.join(repo_dir, d)) and d not in SKIP_DIRS]
    
    structure_type = "standard"
    if any(d in ["packages", "apps", "libs", "modules"] for d in top_dirs):
        structure_type = "monorepo"
    elif "frontend" in top_dirs and "backend" in top_dirs:
        structure_type = "fullstack"
    elif "src" in top_dirs and len(top_dirs) <= 5:
        structure_type = "standard"
    
    return {
        "total_files": total_files,
        "total_lines": total_lines,
        "directory_depth": max_depth,
        "languages": dict(language_stats),
        "languages_pct": languages_pct,
        "key_files": key_files_found,
        "detected_patterns": detected_patterns,
        "structure_type": structure_type,
        "file_tree": file_tree,
        "all_files": all_files,
    }


def _build_file_tree(path: Path, root: Path, depth: int = 0, max_depth: int = 8) -> Dict[str, Any]:
    """Build a nested JSON tree of the repository structure."""
    if depth > max_depth:
        return {"name": path.name, "type": "directory", "children": [], "truncated": True}
    
    name = path.name if depth > 0 else "/"
    rel_path = str(path.relative_to(root)).replace("\\", "/") if depth > 0 else ""
    
    if path.is_file():
        ext = path.suffix.lower()
        language = EXTENSION_MAP.get(ext)
        size = 0
        try:
            size = path.stat().st_size
        except OSError:
            pass
        return {
            "name": name,
            "type": "file",
            "path": rel_path,
            "language": language,
            "size": size,
        }
    
    children = []
    try:
        entries = sorted(path.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        for entry in entries:
            if entry.name in SKIP_DIRS:
                continue
            if entry.name.startswith(".") and entry.name not in {".github", ".env.example"}:
                continue
            children.append(_build_file_tree(entry, root, depth + 1, max_depth))
    except PermissionError:
        pass
    
    return {
        "name": name,
        "type": "directory",
        "path": rel_path,
        "children": children,
    }


def get_key_file_contents(repo_dir: str, key_files: List[Dict[str, str]], max_total_chars: int = 50000) -> Dict[str, str]:
    """
    Read contents of key files for LLM analysis.
    Limits total characters to stay within token budget.
    """
    contents = {}
    total_chars = 0
    
    # Priority order for reading
    priority_names = [
        "README.md", "readme.md",
        "package.json", "requirements.txt", "pyproject.toml",
        "Cargo.toml", "go.mod", "pom.xml", "Gemfile",
        "Dockerfile", "docker-compose.yml",
        "tsconfig.json", "next.config.ts", "next.config.js",
        "vercel.json", "railway.json",
        "Makefile",
    ]
    
    # Sort key files by priority
    sorted_files = sorted(
        key_files,
        key=lambda f: priority_names.index(f["name"]) if f["name"] in priority_names else 999
    )
    
    for kf in sorted_files:
        if total_chars >= max_total_chars:
            break
        filepath = os.path.join(repo_dir, kf["path"])
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(10000)  # Max 10K chars per file
                contents[kf["path"]] = content
                total_chars += len(content)
        except (OSError, UnicodeDecodeError):
            pass
    
    return contents


def build_tree_text(file_tree: Dict[str, Any], indent: str = "", max_lines: int = 500) -> str:
    """Convert file tree to indented text representation for LLM prompt (token-efficient)."""
    lines = []
    _tree_to_lines(file_tree, indent, lines, max_lines)
    return "\n".join(lines)


def _tree_to_lines(node: Dict[str, Any], indent: str, lines: List[str], max_lines: int):
    """Recursive tree to text."""
    if len(lines) >= max_lines:
        return
    
    if node["type"] == "file":
        lang_suffix = f"  [{node.get('language', '')}]" if node.get("language") else ""
        lines.append(f"{indent}{node['name']}{lang_suffix}")
    else:
        if node["name"] != "/":
            lines.append(f"{indent}{node['name']}/")
        children = node.get("children", [])
        child_indent = indent + "  " if node["name"] != "/" else indent
        for child in children:
            _tree_to_lines(child, child_indent, lines, max_lines)
