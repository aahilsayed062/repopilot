"""Quick test of the full analyze pipeline."""
import asyncio
from app.services.repo_fetcher import clone_repo, cleanup_repo
from app.services.structure_analyzer import analyze_structure, get_key_file_contents, build_tree_text
from app.services.architecture_llm import analyze_architecture
from app.services.graph_builder import build_graph_data, build_dependency_graph

async def test():
    temp_dir = None
    try:
        result = await clone_repo("https://github.com/octocat/Hello-World")
        temp_dir = result["temp_dir"]
        repo_name = result["repo_name"]
        print("1. Clone OK")

        structure = analyze_structure(temp_dir)
        print(f"2. Structure OK: {structure['total_files']} files")

        key_file_contents = get_key_file_contents(temp_dir, structure["key_files"])
        print(f"3. Key files OK: {len(key_file_contents)} files")

        file_tree_text = build_tree_text(structure["file_tree"])
        arch = await analyze_architecture(
            repo_name=repo_name,
            file_tree_text=file_tree_text,
            key_files_content=key_file_contents,
            stats=structure,
        )
        print(f"4. Architecture OK: {arch['summary'][:60]}")

        graph = build_graph_data(
            file_tree=structure["file_tree"],
            analysis=arch,
            all_files=structure["all_files"],
        )
        print(f"5. Graph OK: {graph['totalNodes']} nodes")

        dep_graph = build_dependency_graph(temp_dir, structure["key_files"])
        print(f"6. Deps OK: {dep_graph['totalDeps']} deps")

        print("ALL STEPS PASSED")
    except Exception as e:
        import traceback
        print(f"ERROR at step: {type(e).__name__}: {e}")
        traceback.print_exc()
    finally:
        if temp_dir:
            cleanup_repo(temp_dir)

asyncio.run(test())
