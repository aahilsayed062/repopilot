/**
 * API Client — Backend communication for RepoPilot Website.
 * All calls go through Next.js rewrites → backend.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined" && window.location.hostname === "localhost"
    ? "http://localhost:8001"
    : "/api");

export interface AnalyzeRequest {
  github_url: string;
  branch?: string;
}

export interface ComponentInfo {
  name: string;
  path: string;
  description: string;
}

export interface GraphNode {
  id: string;
  type: "file" | "directory";
  name: string;
  path: string;
  language: string | null;
  color: string;
  size: number;
  depth: number;
  childCount: number;
  complexity?: string;
  heatColor?: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
}

export interface DependencyInfo {
  name: string;
  version: string;
  type: "runtime" | "dev";
  ecosystem: string;
  category: string;
}

export interface RepoStats {
  total_files: number;
  total_lines: number;
  languages: Record<string, { files: number; lines: number }>;
  languages_pct: Record<string, number>;
  directory_depth: number;
  structure_type: string;
}

export interface FileTreeNode {
  name: string;
  type: "file" | "directory";
  path?: string;
  language?: string;
  size?: number;
  children?: FileTreeNode[];
}

export interface AnalyzeResponse {
  repo_name: string;
  branch: string;
  summary: string;
  tech_stack: string[];
  architecture_pattern: string;
  components: ComponentInfo[];
  entry_points: string[];
  data_flow: string;
  mermaid_diagram: string;
  readme_summary: string | null;
  stats: RepoStats;
  file_tree: FileTreeNode;
  graph: {
    nodes: GraphNode[];
    edges: GraphEdge[];
    components: { nodeId: string; name: string; description: string; path: string }[];
    entryPoints: { nodeId: string; path: string }[];
    totalNodes: number;
    totalEdges: number;
  };
  dependency_graph: {
    dependencies: DependencyInfo[];
    devDependencies: DependencyInfo[];
    categories: Record<string, string[]>;
    totalDeps: number;
    totalDevDeps: number;
  };
  key_files: { name: string; path: string; language: string }[];
}

export interface HealthResponse {
  status: string;
  version: string;
  gemini_configured: boolean;
}

export async function analyzeRepo(request: AnalyzeRequest): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Analysis failed (${res.status})`);
  }

  return res.json();
}

export async function checkHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error("Backend unavailable");
  return res.json();
}
