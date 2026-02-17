"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { GitMerge, Copy, Check } from "lucide-react";

interface MermaidDiagramProps {
  diagram: string;
  className?: string;
}

export default function MermaidDiagram({ diagram, className = "" }: MermaidDiagramProps) {
  const [rendered, setRendered] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(false);
  const [svgMarkup, setSvgMarkup] = useState("");

  useEffect(() => {
    if (!diagram) return;
    setRendered(false);
    setError(false);
    setSvgMarkup("");

    // Dynamically import mermaid
    let cancelled = false;
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: "dark",
          themeVariables: {
            primaryColor: "#10b981",
            primaryTextColor: "#e6edf3",
            primaryBorderColor: "#30363d",
            lineColor: "#484f58",
            secondaryColor: "#1c1c2e",
            tertiaryColor: "#161b22",
            fontSize: "14px",
          },
          flowchart: {
            curve: "basis",
            padding: 15,
          },
        });

        if (cancelled) return;

        const id = `mermaid-${Date.now()}`;
        const { svg } = await mermaid.render(id, diagram);
        
        if (!cancelled) {
          setSvgMarkup(svg);
          setRendered(true);
          setError(false);
        }
      } catch (e) {
        console.warn("Mermaid render failed:", e);
        if (!cancelled) setError(true);
      }
    })();

    return () => { cancelled = true; };
  }, [diagram]);

  const handleCopy = () => {
    navigator.clipboard.writeText(diagram);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!diagram) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xl ${className}`}
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <GitMerge size={20} className="text-cyan-400" />
          <h3 className="text-lg font-semibold text-white">Architecture Diagram</h3>
        </div>
        <button
          onClick={handleCopy}
          className="p-2 rounded-lg bg-white/5 border border-white/10 text-gray-400 hover:text-white transition-all"
          title="Copy Mermaid code"
        >
          {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
        </button>
      </div>

      {error ? (
        /* Fallback: show raw Mermaid code */
        <div className="p-4 rounded-lg bg-black/30 border border-white/5 overflow-x-auto">
          <pre className="text-xs text-gray-400 font-mono whitespace-pre-wrap">{diagram}</pre>
        </div>
      ) : svgMarkup ? (
        <div
          className="w-full overflow-x-auto [&_svg]:max-w-full [&_svg]:h-auto"
          dangerouslySetInnerHTML={{ __html: svgMarkup }}
        />
      ) : (
        <div className="w-full overflow-x-auto [&_svg]:max-w-full [&_svg]:h-auto">
          {!rendered && (
            <div className="h-40 flex items-center justify-center text-gray-500 text-sm">
              Loading diagram...
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
}
