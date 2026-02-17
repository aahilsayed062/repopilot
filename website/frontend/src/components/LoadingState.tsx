"use client";

import { motion } from "framer-motion";
import { Loader2, GitBranch, Search, Brain, BarChart3 } from "lucide-react";

interface LoadingStateProps {
  step?: number; // 0-3 for animation stages
  progressPct?: number;
}

const steps = [
  { icon: GitBranch, label: "Cloning repository...", color: "text-blue-400" },
  { icon: Search, label: "Scanning file structure...", color: "text-purple-400" },
  { icon: Brain, label: "Analyzing architecture with AI...", color: "text-emerald-400" },
  { icon: BarChart3, label: "Building visualizations...", color: "text-orange-400" },
];

export default function LoadingState({ step = 0, progressPct = 0 }: LoadingStateProps) {
  const safePct = Math.max(0, Math.min(100, Math.round(progressPct)));

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-8">
      {/* Spinner */}
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
        className="relative"
      >
        <div className="w-20 h-20 rounded-full border-2 border-white/5" />
        <div className="absolute inset-0 w-20 h-20 rounded-full border-2 border-transparent border-t-emerald-500" />
      </motion.div>

      {/* Steps */}
      <div className="space-y-3 w-full max-w-sm">
        {steps.map((s, i) => {
          const isActive = i === step;
          const isDone = i < step;
          const isPending = i > step;

          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 * i }}
              className={`flex items-center gap-3 p-3 rounded-xl transition-all ${
                isActive ? "bg-white/5 border border-white/10" : ""
              }`}
            >
              {isDone ? (
                <div className="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center">
                  <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
              ) : isActive ? (
                <Loader2 size={18} className={`animate-spin ${s.color}`} />
              ) : (
                <s.icon size={18} className="text-gray-600" />
              )}
              <span
                className={`text-sm ${
                  isDone ? "text-gray-500 line-through" : isActive ? "text-white font-medium" : "text-gray-600"
                }`}
              >
                {s.label}
              </span>
            </motion.div>
          );
        })}
      </div>

      {/* Real-time progress */}
      <div className="w-full max-w-sm space-y-2">
        <div className="flex items-center justify-between text-xs text-gray-400">
          <span>Progress</span>
          <span>{safePct}%</span>
        </div>
        <div className="h-2 rounded-full bg-white/10 overflow-hidden">
          <motion.div
            className="h-full bg-emerald-500"
            animate={{ width: `${safePct}%` }}
            transition={{ duration: 0.25, ease: "easeOut" }}
          />
        </div>
      </div>

      {/* Skeleton cards */}
      <div className="w-full max-w-4xl grid grid-cols-2 md:grid-cols-4 gap-3 opacity-20">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-20 rounded-xl bg-white/5 animate-pulse" />
        ))}
      </div>
    </div>
  );
}
