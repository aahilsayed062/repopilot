"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft, Github, ExternalLink, Share2, Check } from "lucide-react";
import Link from "next/link";

import { analyzeRepo, type AnalyzeResponse } from "@/lib/api";
import UrlInput from "@/components/UrlInput";
import LoadingState from "@/components/LoadingState";
import StatsPanel from "@/components/StatsPanel";
import ArchitectureCard from "@/components/ArchitectureCard";
import TechStackBadges from "@/components/TechStackBadges";
import FileExplorer from "@/components/FileExplorer";
import CodebaseGraph from "@/components/CodebaseGraph";
import ArchitectureFlowDiagram from "@/components/ArchitectureFlowDiagram";
import DependencyGraph from "@/components/DependencyGraph";

function AnalyzeContent() {
  const searchParams = useSearchParams();
  const [data, setData] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [loadingPct, setLoadingPct] = useState(0);
  const [activeTab, setActiveTab] = useState<"overview" | "graph" | "files" | "deps">("overview");
  const [copied, setCopied] = useState(false);

  const handleAnalyze = useCallback(async (url: string) => {
    setError("");
    setData(null);
    setIsLoading(true);
    setLoadingStep(0);
    setLoadingPct(1);

    // Smooth real-time progress feedback while backend analysis runs.
    let currentPct = 1;
    const startedAt = Date.now();
    const progressTimer = setInterval(() => {
      const elapsedSec = (Date.now() - startedAt) / 1000;
      const targetPct =
        elapsedSec < 3
          ? 5 + elapsedSec * 12
          : elapsedSec < 8
            ? 40 + (elapsedSec - 3) * 6
            : 70 + Math.min((elapsedSec - 8) * 3, 25);
      currentPct = Math.max(currentPct, Math.min(95, targetPct));
      setLoadingPct(Math.floor(currentPct));
      setLoadingStep(
        currentPct < 25 ? 0 : currentPct < 55 ? 1 : currentPct < 85 ? 2 : 3
      );
    }, 200);

    try {
      const result = await analyzeRepo({ github_url: url });
      setLoadingPct(100);
      setLoadingStep(3);
      setData(result);
      setActiveTab("overview");
    } catch (e: any) {
      setError(e.message || "Analysis failed. Please check the URL and try again.");
    } finally {
      clearInterval(progressTimer);
      setIsLoading(false);
    }
  }, []);

  // Auto-analyze if URL is in query params
  useEffect(() => {
    const url = searchParams.get("url");
    if (url && !data && !isLoading) {
      handleAnalyze(url);
    }
  }, [searchParams, handleAnalyze, data, isLoading]);

  const handleShare = () => {
    if (data) {
      const shareUrl = `${window.location.origin}/analyze?url=https://github.com/${data.repo_name}`;
      navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      {/* Top bar */}
      <header className="sticky top-0 z-50 border-b border-white/5 bg-[#0a0a0f]/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4 flex-1 min-w-0">
            <Link href="/" className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors">
              <ArrowLeft size={16} />
              <span className="text-sm">Back</span>
            </Link>
            {data && (
              <div className="flex items-center gap-2 text-sm min-w-0">
                <span className="text-gray-600">|</span>
                <Github size={14} className="text-gray-400" />
                <span className="text-white font-semibold truncate">{data.repo_name}</span>
              </div>
            )}
            {data && (
              <div className="hidden lg:block w-[420px] max-w-[40vw] ml-2">
                <UrlInput
                  onSubmit={handleAnalyze}
                  isLoading={isLoading}
                  compact
                  showExamples={false}
                  className="max-w-none"
                />
              </div>
            )}
          </div>
          {data && (
            <div className="flex items-center gap-2">
              <a
                href={`https://github.com/${data.repo_name}`}
                target="_blank"
                rel="noopener noreferrer"
                className="p-2 rounded-lg bg-white/5 border border-white/10 text-gray-400 hover:text-white transition-all"
                title="View on GitHub"
              >
                <ExternalLink size={14} />
              </a>
              <button
                onClick={handleShare}
                className="p-2 rounded-lg bg-white/5 border border-white/10 text-gray-400 hover:text-white transition-all"
                title="Copy share link"
              >
                {copied ? <Check size={14} className="text-emerald-400" /> : <Share2 size={14} />}
              </button>
            </div>
          )}
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* URL Input (shown when no data) */}
        {!data && !isLoading && (
          <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6">
            <motion.h1
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-3xl md:text-4xl font-bold text-center"
            >
              Analyze a Repository
            </motion.h1>
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.1 }}
              className="text-gray-400 text-center max-w-md"
            >
              Paste any public GitHub URL to get an AI-powered architecture analysis with interactive visualizations.
            </motion.p>
            <UrlInput onSubmit={handleAnalyze} isLoading={isLoading} />
            {error && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="mt-4 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm max-w-lg text-center"
              >
                {error}
              </motion.div>
            )}
          </div>
        )}

        {/* Loading */}
        {isLoading && <LoadingState step={loadingStep} progressPct={loadingPct} />}

        {/* Results */}
        {data && !isLoading && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
            {/* Stats bar */}
            <StatsPanel stats={data.stats} repoName={data.repo_name} branch={data.branch} />

            {/* Tab navigation */}
            <div className="flex items-center gap-1 p-1 rounded-xl bg-white/5 border border-white/10 w-fit">
              {(["overview", "graph", "files", "deps"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all capitalize ${
                    activeTab === tab
                      ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                      : "text-gray-400 hover:text-white hover:bg-white/5"
                  }`}
                >
                  {tab === "deps" ? "Dependencies" : tab}
                </button>
              ))}
            </div>

            {/* Tab content */}
            {activeTab === "overview" && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="space-y-6">
                  <ArchitectureCard data={data} />
                </div>
                <div className="space-y-6">
                  <TechStackBadges techStack={data.tech_stack} languages={data.stats.languages_pct} />
                  <ArchitectureFlowDiagram data={data} />
                </div>
              </div>
            )}

            {activeTab === "graph" && (
              <CodebaseGraph data={data} className="min-h-[500px]" />
            )}

            {activeTab === "files" && (
              <FileExplorer tree={data.file_tree} />
            )}

            {activeTab === "deps" && (
              <DependencyGraph
                dependencies={data.dependency_graph.dependencies}
                devDependencies={data.dependency_graph.devDependencies}
                categories={data.dependency_graph.categories}
              />
            )}

          </motion.div>
        )}
      </main>
    </div>
  );
}

export default function AnalyzePage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#0a0a0f]" />}>
      <AnalyzeContent />
    </Suspense>
  );
}
