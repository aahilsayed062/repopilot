"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import {
  Send,
  Terminal,
  FolderRoot,
  FileCode,
  ExternalLink,
  Copy,
  Check,
  Loader2,
  AlertCircle,
  CheckCircle2,
  MessageSquare,
  Cpu,
  Info,
  ChevronRight,
  Github,
  Menu,
  X
} from "lucide-react";

// ============================================
// TYPES
// ============================================

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

// ============================================
// HELPER FUNCTIONS
// ============================================

const getLanguageColor = (lang: string): string => {
  const colors: Record<string, string> = {
    python: 'python',
    javascript: 'javascript',
    typescript: 'typescript',
    rust: 'rust',
    go: 'go',
    java: 'java',
    cpp: 'cpp',
    c: 'c',
    ruby: 'ruby',
    php: 'php',
  };
  return colors[lang.toLowerCase()] || 'default';
};

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

// ============================================
// SUB-COMPONENTS
// ============================================

const TypingIndicator = () => (
  <motion.div
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    className="message message-assistant"
  >
    <div className="message-avatar">
      <Cpu size={18} />
    </div>
    <div className="message-bubble">
      <div className="typing-indicator">
        <span></span>
        <span></span>
        <span></span>
      </div>
    </div>
  </motion.div>
);

interface CodeBlockProps {
  code: string;
  language?: string;
}

const CodeBlock = ({ code, language = 'text' }: CodeBlockProps) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="code-block message-enter">
      <div className="code-block-header">
        <span className="code-block-lang">{language}</span>
        <button
          className={`code-copy-btn ${copied ? 'copied' : ''}`}
          onClick={handleCopy}
        >
          {copied ? <><Check size={14} /> Copied!</> : <><Copy size={14} /> Copy</>}
        </button>
      </div>
      <div className="code-block-content p-0">
        <SyntaxHighlighter
          language={language.toLowerCase()}
          style={vscDarkPlus}
          customStyle={{
            margin: 0,
            padding: '16px',
            fontSize: '13px',
            background: 'transparent',
          }}
        >
          {code}
        </SyntaxHighlighter>
      </div>
    </div>
  );
};

interface CitationsProps {
  citations: Citation[];
}

const Citations = ({ citations }: CitationsProps) => (
  <div className="citations-container">
    <div className="citations-title">
      <ExternalLink size={12} />
      Sources Used ({citations.length})
    </div>
    <div className="citations-list">
      {citations.map((cit, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.1 }}
          className="citation-card"
        >
          <div className="citation-content">
            <div className="citation-path">
              {cit.file_path}{cit.line_range ? `:${cit.line_range}` : ''}
            </div>
            {cit.snippet && (
              <div className="citation-snippet">"{cit.snippet}"</div>
            )}
          </div>
        </motion.div>
      ))}
    </div>
  </div>
);

interface DiffsProps {
  diffs: FileDiff[];
}

const Diffs = ({ diffs }: DiffsProps) => (
  <div className="citations-container">
    <div className="citations-title">
      <Terminal size={12} />
      Proposed Changes ({diffs.length} files)
    </div>
    {diffs.map((diff, i) => (
      <div key={i} className="code-block" style={{ marginTop: '8px' }}>
        <div className="code-block-header">
          <span className="code-block-lang">{diff.file_path}</span>
        </div>
        <div className="code-block-content">
          {diff.diff.split('\n').map((line, j) => {
            let className = 'diff-line context';
            if (line.startsWith('+')) className = 'diff-line added';
            else if (line.startsWith('-')) className = 'diff-line removed';
            return <div key={j} className={className}>{line}</div>;
          })}
        </div>
      </div>
    ))}
  </div>
);

// ============================================
// MAIN COMPONENT
// ============================================

export default function Home() {
  // Repo State
  const [repoUrl, setRepoUrl] = useState("https://github.com/keleshev/schema");
  const [repoId, setRepoId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<string>("Initializing...");
  const [statusType, setStatusType] = useState<'default' | 'success' | 'error' | 'warning'>('default');
  const [isIndexed, setIsIndexed] = useState(false);
  const [stats, setStats] = useState<RepoStats | null>(null);
  const [files, setFiles] = useState<RepoFile[]>([]);

  // Chat State
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isChatLoading, setIsChatLoading] = useState(false);

  // UI State
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isChatLoading]);

  // Check Health
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch("/api/health");
        const d = await res.json();
        if (d.mock_mode) {
          setStatus("System: Mock Mode (No API Keys)");
          setStatusType('warning');
        } else {
          setStatus("System: Online & Ready");
          setStatusType('success');
        }
      } catch (e) {
        setStatus("System: Offline (Backend Unreachable)");
        setStatusType('error');
      }
    };
    checkHealth();
  }, []);

  // Load Repo
  const loadRepo = async () => {
    if (!repoUrl.trim()) return;

    setIsLoading(true);
    setStatus("Loading repository...");
    setStatusType('default');

    try {
      const res = await fetch("/api/repo/load", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl }),
      });
      const data = await res.json();

      if (!res.ok) throw new Error(data.detail || "Failed to load repo");

      setRepoId(data.repo_id);
      setStats(data.stats);
      setStatus(`Success: ${data.repo_name} loaded`);
      setStatusType('success');

      // Auto-index
      await indexRepo(data.repo_id);

    } catch (e: unknown) {
      const error = e as Error;
      setStatus(`Error: ${error.message}`);
      setStatusType('error');
    } finally {
      setIsLoading(false);
    }
  };

  // Index Repo
  const indexRepo = async (id: string) => {
    setStatus("Indexing code chunks...");
    setStatusType('default');

    try {
      const res = await fetch("/api/repo/index", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_id: id }),
      });
      const data = await res.json();

      if (!res.ok) throw new Error(data.detail || "Failed index");

      setIsIndexed(true);
      setStatus(`Search Ready • ${data.chunk_count} code chunks`);
      setStatusType('success');

      // Get files
      const statusRes = await fetch(`/api/repo/status?repo_id=${id}&include_files=true`);
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        setFiles(statusData.files || []);
      }

    } catch (e: unknown) {
      const error = e as Error;
      setStatus(`Error: ${error.message}`);
      setStatusType('error');
    }
  };

  // Send Message
  const sendMessage = async () => {
    if (!input.trim() || !repoId) return;

    const userMsg: Message = { role: "user", content: input };
    setMessages(prev => [...prev, userMsg]);
    const currentInput = input;
    setInput("");
    setIsChatLoading(true);

    try {
      if (currentInput.startsWith("/generate ")) {
        const request = currentInput.replace("/generate ", "");
        const res = await fetch("/api/chat/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ repo_id: repoId, request: request }),
        });
        const data = await res.json();

        if (!res.ok) throw new Error(data.detail || "Generation failed");

        setMessages(prev => [...prev, {
          role: "assistant",
          content: data.plan || "I've generated a set of changes based on your request. Review the plan and diffs below:",
          diffs: data.diffs,
          tests: data.tests,
          citations: data.citations?.map((c: string) => ({
            file_path: c,
            line_range: "",
            snippet: "",
            why: "Analysis context"
          }))
        }]);
      } else {
        const res = await fetch("/api/chat/ask", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ repo_id: repoId, question: userMsg.content }),
        });
        const data = await res.json();

        if (!res.ok) throw new Error(data.detail || "Query failed");

        setMessages(prev => [...prev, {
          role: "assistant",
          content: data.answer,
          citations: data.citations,
          confidence: data.confidence,
          assumptions: data.assumptions
        }]);
      }

    } catch (e: unknown) {
      const error = e as Error;
      setMessages(prev => [...prev, {
        role: "assistant",
        content: `Something went wrong: ${error.message}`
      }]);
    } finally {
      setIsChatLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // ============================================
  // RENDER
  // ============================================

  return (
    <div className="app-layout">
      {/* Ambient Background */}
      <div className="ambient-glow" />

      {/* Header */}
      <motion.header
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="glass-header"
      >
        <div className="header-brand">
          <button
            className="md:hidden p-2 -ml-2 text-text-secondary hover:text-text-primary transition-colors"
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            aria-label="Toggle Menu"
          >
            {isSidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <div className="header-logo">
            <Cpu size={22} />
          </div>
          <h1 className="header-title hidden sm:block">RepoPilot</h1>
        </div>

        <div className={`header-status ${statusType}`}>
          {statusType === 'success' && <CheckCircle2 size={14} className="animate-pulse" />}
          {statusType === 'error' && <AlertCircle size={14} />}
          {statusType === 'warning' && <Info size={14} />}
          {statusType === 'default' && <Loader2 size={14} className="animate-spin" />}
          {status}
        </div>

        <div className="flex gap-4">
          <a href="https://github.com/repopilot" target="_blank" className="btn-ghost">
            <Github size={18} />
          </a>
        </div>
      </motion.header>

      {/* Main Content */}
      <div className="main-container">
        {/* Backdrop for mobile */}
        <AnimatePresence>
          {isSidebarOpen && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsSidebarOpen(false)}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[140] md:hidden"
            />
          )}
        </AnimatePresence>

        {/* Sidebar */}
        <aside className={`sidebar ${isSidebarOpen ? 'open' : ''}`}>
          {/* Repository Section */}
          <motion.section
            initial={{ x: -20, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="sidebar-section"
          >
            <h3 className="sidebar-title">
              <Github size={14} />
              Connection
            </h3>
            <div className="repo-input-group">
              <input
                type="text"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://github.com/user/repo"
                className="repo-input"
                onKeyDown={(e) => e.key === 'Enter' && loadRepo()}
              />
              <button
                onClick={loadRepo}
                disabled={isLoading}
                className="btn btn-primary btn-full shadow-glow-coral"
              >
                {isLoading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Connecting...
                  </>
                ) : (
                  'Connect Repository'
                )}
              </button>
            </div>

            {/* Stats */}
            {stats && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="mt-4"
              >
                <div className="stats-grid">
                  <div className="stat-card">
                    <div className="stat-value">{stats.total_files}</div>
                    <div className="stat-label">Files</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-value">{formatBytes(stats.total_size_bytes)}</div>
                    <div className="stat-label">Size</div>
                  </div>
                </div>

                <div className="language-tags">
                  {Object.entries(stats.languages)
                    .sort(([, a], [, b]) => b - a)
                    .slice(0, 5)
                    .map(([lang, count]) => (
                      <span key={lang} className="language-tag">
                        <span className={`language-dot ${getLanguageColor(lang)}`} />
                        {lang}
                      </span>
                    ))}
                </div>
              </motion.div>
            )}
          </motion.section>

          {/* Files Section */}
          <AnimatePresence>
            {files.length > 0 && (
              <motion.section
                initial={{ x: -20, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                exit={{ x: -20, opacity: 0 }}
                transition={{ delay: 0.2 }}
                className="sidebar-section"
              >
                <h3 className="sidebar-title">
                  <FolderRoot size={14} />
                  Code Explorer
                </h3>
                <div className="file-list">
                  {files.slice(0, 40).map((f, i) => (
                    <div key={i} className="file-item group cursor-pointer" title={f.file_path}>
                      <FileCode size={14} className="group-hover:text-brand-periwinkle transition-colors" />
                      <span className="truncate">{f.file_path.split('/').pop()}</span>
                    </div>
                  ))}
                  {files.length > 40 && (
                    <div className="file-item text-tertiary italic text-[11px] justify-center pt-2">
                      + {files.length - 40} additional files
                    </div>
                  )}
                </div>
              </motion.section>
            )}
          </AnimatePresence>

          {/* Tip Box */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="tip-box"
          >
            <strong>Pro Tip:</strong> Use <code>/generate</code> followed by a feature request to see RepoPilot create code patches instantly.
          </motion.div>
        </aside>

        {/* Chat Area */}
        <main className="chat-area">
          <div className="chat-header">
            <h2 className="chat-header-title">
              <MessageSquare size={18} />
              AI Assistant
            </h2>
            {isIndexed && (
              <div className="badge badge-success text-[10px] py-1">
                KNOWLEDGE BASE ACTIVE
              </div>
            )}
          </div>

          {/* Messages */}
          <div className="messages-container">
            <AnimatePresence mode="popLayout">
              {messages.length === 0 ? (
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  key="empty"
                  className="empty-state"
                >
                  <div className="empty-state-icon">
                    <MessageSquare size={36} />
                  </div>
                  <p className="empty-state-text">
                    Welcome to RepoPilot. Connect a repository above to start exploring your code with AI.
                  </p>
                  <div className="flex gap-2 mt-4">
                    {['Explain the architecture', 'How do I add a new endpoint?', 'Find vulnerabilities'].map(q => (
                      <button
                        key={q}
                        onClick={() => setInput(q)}
                        className="btn-ghost text-xs border border-white/5 rounded-full px-4"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </motion.div>
              ) : (
                messages.map((msg, i) => (
                  <motion.div
                    layout
                    key={i}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ type: "spring", damping: 20, stiffness: 100 }}
                    className={`message ${msg.role === 'user' ? 'message-user' : 'message-assistant'}`}
                  >
                    {msg.role === 'assistant' && (
                      <div className="message-avatar">
                        <Cpu size={18} />
                      </div>
                    )}
                    <div className="message-bubble">
                      <div className="message-content">{msg.content}</div>

                      {/* Code in response */}
                      {msg.tests && (
                        <CodeBlock code={msg.tests} language="python" />
                      )}

                      {/* Diffs */}
                      {msg.diffs && msg.diffs.length > 0 && (
                        <Diffs diffs={msg.diffs} />
                      )}

                      {/* Citations */}
                      {msg.citations && msg.citations.length > 0 && (
                        <Citations citations={msg.citations} />
                      )}

                      {/* Confidence */}
                      {msg.role === 'assistant' && msg.confidence && (
                        <div className="message-meta">
                          <span className={`meta-badge ${msg.confidence.toLowerCase()} flex items-center gap-1`}>
                            <Info size={10} />
                            Confidence: {msg.confidence}
                          </span>
                        </div>
                      )}
                    </div>
                  </motion.div>
                ))
              )}

              {/* Typing Indicator */}
              {isChatLoading && <TypingIndicator key="typing" />}
            </AnimatePresence>

            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="input-container">
            <motion.div
              layout
              className="input-wrapper"
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={isIndexed ? "Ask anything about your code..." : "Connecting to repository..."}
                disabled={!isIndexed || isChatLoading}
                className="chat-input"
              />
              <button
                onClick={sendMessage}
                disabled={!isIndexed || isChatLoading || !input.trim()}
                className="send-button"
              >
                <Send size={20} />
              </button>
            </motion.div>
          </div>
        </main>
      </div>
    </div>
  );
}
