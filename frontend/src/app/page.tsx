"use client";

import { useState, useRef, useEffect } from "react";

// Types
interface Citation {
  file_path: string;
  line_range: string;
  snippet: string;
  why: string;
}

interface FileDiff {
  file_path: string;
  content?: string;
  diff: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  confidence?: string;
  assumptions?: string[];
  // Generation fields
  plan?: string;
  diffs?: FileDiff[];
  tests?: string;
}

interface RepoStats {
  total_files: number;
  languages: Record<string, number>;
  total_size_bytes: number;
}

interface RepoFile {
  file_path: string;
}

export default function Home() {
  // Repo State
  const [repoUrl, setRepoUrl] = useState("https://github.com/keleshev/schema");
  const [repoId, setRepoId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<string>("");
  const [isIndexed, setIsIndexed] = useState(false);
  const [stats, setStats] = useState<RepoStats | null>(null);
  const [files, setFiles] = useState<RepoFile[]>([]);

  // Chat State
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isChatLoading, setIsChatLoading] = useState(false);

  // Check Health
  useEffect(() => {
    fetch("/api/health")
      .then(r => r.json())
      .then(d => {
        if (d.mock_mode) {
          setStatus("⚠️ SYSTEM IN MOCK MODE (No API Keys Found)");
        }
      })
      .catch(() => setStatus("❌ BACKEND UNREACHABLE"));
  }, []);

  // Load Repo
  const loadRepo = async () => {
    setIsLoading(true);
    setStatus("Loading repository...");
    try {
      const res = await fetch("/api/repo/load", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl }),
      });
      const data = await res.json();

      if (!res.ok) throw new Error(data.detail || "Failed to load");

      setRepoId(data.repo_id);
      setStats(data.stats);
      setStatus(`Loaded ${data.repo_name} @ ${data.commit_hash.substring(0, 8)}`);

      // Auto-index
      await indexRepo(data.repo_id);

    } catch (e: any) {
      setStatus(`Error: ${e.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Index Repo
  const indexRepo = async (id: string) => {
    setStatus("Indexing repository...");
    try {
      const res = await fetch("/api/repo/index", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_id: id }),
      });
      const data = await res.json();

      if (!res.ok) throw new Error(data.detail || "Failed to index");

      setIsIndexed(true);
      setStatus(`Ready! Indexed ${data.chunk_count} chunks.`);

      // Get files
      const statusRes = await fetch(`/api/repo/status?repo_id=${id}&include_files=true`);
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        setFiles(statusData.files || []);
      }

    } catch (e: any) {
      setStatus(`Error indexing: ${e.message}`);
    }
  };

  // Chat
  const sendMessage = async () => {
    if (!input.trim() || !repoId) return;

    const userMsg = { role: "user" as const, content: input };
    setMessages(prev => [...prev, userMsg]);
    const currentInput = input;
    setInput("");
    setIsChatLoading(true);

    try {
      // Check for /generate command
      if (currentInput.startsWith("/generate ")) {
        const request = currentInput.replace("/generate ", "");
        const res = await fetch("/api/chat/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ repo_id: repoId, request: request }),
        });
        const data = await res.json();

        if (!res.ok) throw new Error(data.detail || "Failed to generate");

        setMessages(prev => [...prev, {
          role: "assistant",
          content: `**Plan**:\n${data.plan}\n\n**Generated Tests**:\n\`\`\`python\n${data.tests}\n\`\`\``,
          diffs: data.diffs,
          citations: data.citations?.map((c: string) => ({ file_path: c, line_range: "", snippet: "", why: "Context" }))
        }]);
      } else {
        // Normal chat
        const res = await fetch("/api/chat/ask", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ repo_id: repoId, question: userMsg.content }),
        });
        const data = await res.json();

        if (!res.ok) throw new Error(data.detail || "Failed to get answer");

        setMessages(prev => [...prev, {
          role: "assistant",
          content: data.answer,
          citations: data.citations,
          confidence: data.confidence,
          assumptions: data.assumptions
        }]);
      }

    } catch (e: any) {
      setMessages(prev => [...prev, {
        role: "assistant",
        content: `Error: ${e.message}`
      }]);
    } finally {
      setIsChatLoading(false);
    }
  };

  return (
    <main className="min-h-screen p-8 bg-gray-50 text-gray-900 font-sans">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-indigo-600">
            RepoPilot AI
          </h1>
          <div className="text-sm text-gray-500">
            {status}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Panel: Repo Control */}
          <div className="lg:col-span-1 space-y-4">
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
              <h2 className="text-lg font-semibold mb-4">Repository</h2>
              <div className="space-y-3">
                <input
                  type="text"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  placeholder="https://github.com/..."
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                />
                <button
                  onClick={loadRepo}
                  disabled={isLoading}
                  className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors font-medium"
                >
                  {isLoading ? "Loading..." : "Load Repository"}
                </button>
              </div>

              {stats && (
                <div className="mt-6 space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Files</span>
                    <span className="font-medium">{stats.total_files}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Size</span>
                    <span className="font-medium">{(stats.total_size_bytes / 1024 / 1024).toFixed(2)} MB</span>
                  </div>
                  <div className="pt-2 border-t">
                    <div className="text-xs text-gray-400 mb-1">Languages</div>
                    <div className="flex flex-wrap gap-1">
                      {Object.keys(stats.languages).slice(0, 5).map(lang => (
                        <span key={lang} className="px-2 py-1 bg-gray-100 rounded text-xs text-gray-600">
                          {lang}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* File Browser (Mini) */}
            {files.length > 0 && (
              <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 h-96 flex flex-col">
                <h2 className="text-lg font-semibold mb-4">Files</h2>
                <div className="flex-1 overflow-y-auto space-y-1 text-sm">
                  {files.map((f, i) => (
                    <div key={i} className="truncate text-gray-600 hover:text-blue-600 cursor-default" title={f.file_path}>
                      {f.file_path}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="bg-blue-50 p-4 rounded-xl border border-blue-100 text-sm text-blue-800">
              <strong>Tip:</strong> Use <code>/generate &lt;request&gt;</code> to create code patches.
            </div>
          </div>

          {/* Right Panel: Chat */}
          <div className="lg:col-span-2 flex flex-col h-[calc(100vh-12rem)] bg-white rounded-xl shadow-sm border border-gray-100">
            <div className="p-4 border-b">
              <h2 className="text-lg font-semibold">Assistant</h2>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-6">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full text-gray-400 space-y-2">
                  <div className="p-4 bg-gray-50 rounded-full">
                    💬
                  </div>
                  <p>Load a repository and start asking questions.</p>
                </div>
              )}

              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[85%] rounded-2xl p-4 ${msg.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-50 text-gray-800'
                    }`}>
                    <div className="whitespace-pre-wrap has-markdown">{msg.content}</div>

                    {/* Diffs */}
                    {msg.diffs && msg.diffs.length > 0 && (
                      <div className="mt-4 space-y-2">
                        <div className="text-xs font-semibold opacity-70">Proposed Changes</div>
                        {msg.diffs.map((diff, k) => (
                          <div key={k} className="text-xs bg-white p-2 rounded border border-gray-200 overflow-x-auto">
                            <div className="font-mono font-bold text-gray-700 mb-1">{diff.file_path}</div>
                            <pre className="text-green-700 font-mono">{diff.diff}</pre>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Citations */}
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="mt-4 pt-4 border-t border-gray-200/50 space-y-2">
                        <div className="text-xs font-semibold opacity-70">Citations</div>
                        {msg.citations.map((cit, j) => (
                          <div key={j} className="text-xs bg-white/50 p-2 rounded border border-gray-200/50">
                            <div className="font-mono text-blue-600 mb-1">
                              {cit.file_path}{cit.line_range ? `:${cit.line_range}` : ''}
                            </div>
                            {cit.snippet && <div className="opacity-80 italic">"{cit.snippet}"</div>}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Meta */}
                    {msg.role === 'assistant' && msg.confidence && (
                      <div className="mt-2 text-[10px] opacity-50 flex gap-2">
                        <span>Confidence: {msg.confidence}</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {isChatLoading && (
                <div className="flex justify-start">
                  <div className="bg-gray-50 rounded-2xl p-4 text-gray-500 animate-pulse">
                    Generating answer...
                  </div>
                </div>
              )}
            </div>

            <div className="p-4 border-t">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                  placeholder={isIndexed ? "Ask a question or /generate <request>" : "Load and index a repo first..."}
                  disabled={!isIndexed || isChatLoading}
                  className="flex-1 px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none disabled:bg-gray-50"
                />
                <button
                  onClick={sendMessage}
                  disabled={!isIndexed || isChatLoading}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium"
                >
                  Send
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
