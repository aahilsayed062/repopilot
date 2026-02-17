"use client";

import { useState, FormEvent } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Github, Loader2 } from "lucide-react";

interface UrlInputProps {
  onSubmit: (url: string) => void;
  isLoading?: boolean;
  className?: string;
  compact?: boolean;
  showExamples?: boolean;
}

export default function UrlInput({
  onSubmit,
  isLoading = false,
  className = "",
  compact = false,
  showExamples = true,
}: UrlInputProps) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError("");

    const trimmed = url.trim();
    if (!trimmed) {
      setError("Please enter a GitHub URL");
      return;
    }

    // Basic validation
    const pattern = /^(https?:\/\/)?(www\.)?github\.com\/[^/]+\/[^/]+/;
    if (!pattern.test(trimmed)) {
      setError("Invalid GitHub URL. Example: https://github.com/user/repo");
      return;
    }

    onSubmit(trimmed);
  };

  return (
    <motion.form
      onSubmit={handleSubmit}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 }}
      className={`w-full max-w-2xl ${className}`}
    >
      <div className="relative flex items-center">
        {/* GitHub icon */}
        <div className="absolute left-4 text-gray-400">
          <Github size={20} />
        </div>

        {/* Input */}
        <input
          type="text"
          value={url}
          onChange={(e) => { setUrl(e.target.value); setError(""); }}
          placeholder="https://github.com/owner/repo"
          disabled={isLoading}
          className={`w-full px-12 ${compact ? "py-2.5 rounded-xl text-sm" : "py-4 rounded-2xl text-lg"} bg-white/5 border border-white/10 text-white placeholder-gray-500
                     focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50
                     disabled:opacity-50 disabled:cursor-not-allowed
                     backdrop-blur-xl transition-all`}
        />

        {/* Submit button */}
        <button
          type="submit"
          disabled={isLoading || !url.trim()}
          className={`absolute right-2 ${compact ? "px-3 py-1.5 text-xs rounded-lg" : "px-5 py-2.5 text-sm rounded-xl"} bg-emerald-500 hover:bg-emerald-600 
                     text-white font-semibold text-sm transition-all
                     disabled:opacity-40 disabled:cursor-not-allowed
                     flex items-center gap-2 group`}
        >
          {isLoading ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              Analyzing...
            </>
          ) : (
            <>
              Analyze
              <ArrowRight size={16} className="group-hover:translate-x-0.5 transition-transform" />
            </>
          )}
        </button>
      </div>

      {/* Error message */}
      {error && (
        <motion.p
          initial={{ opacity: 0, y: -5 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-2 text-sm text-red-400 pl-4"
        >
          {error}
        </motion.p>
      )}

      {/* Example repos */}
      {showExamples && (
        <div className="flex flex-wrap gap-2 mt-3 pl-1">
          <span className="text-xs text-gray-500">Try:</span>
          {["facebook/react", "tiangolo/fastapi", "vercel/next.js"].map((repo) => (
            <button
              key={repo}
              type="button"
              onClick={() => setUrl(`https://github.com/${repo}`)}
              className="text-xs text-emerald-400/70 hover:text-emerald-400 transition-colors underline underline-offset-2"
            >
              {repo}
            </button>
          ))}
        </div>
      )}
    </motion.form>
  );
}
