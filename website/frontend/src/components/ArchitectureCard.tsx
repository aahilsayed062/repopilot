"use client";

import { motion } from "framer-motion";
import { Brain, GitFork, Layers, Zap, FileCode2, ArrowRightLeft } from "lucide-react";
import type { AnalyzeResponse } from "@/lib/api";

interface ArchitectureCardProps {
  data: AnalyzeResponse;
}

export default function ArchitectureCard({ data }: ArchitectureCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      {/* Summary */}
      <div className="p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xl">
        <div className="flex items-center gap-3 mb-3">
          <Brain size={20} className="text-emerald-400" />
          <h3 className="text-lg font-semibold text-white">Summary</h3>
        </div>
        <p className="text-gray-300 leading-relaxed">{data.summary}</p>
      </div>

      {/* Architecture Pattern */}
      <div className="p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xl">
        <div className="flex items-center gap-3 mb-3">
          <Layers size={20} className="text-blue-400" />
          <h3 className="text-lg font-semibold text-white">Architecture</h3>
        </div>
        <span className="inline-block px-3 py-1 rounded-full bg-blue-500/20 border border-blue-500/30 text-blue-300 text-sm font-medium">
          {data.architecture_pattern}
        </span>
      </div>

      {/* Key Components */}
      {data.components.length > 0 && (
        <div className="p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xl">
          <div className="flex items-center gap-3 mb-4">
            <GitFork size={20} className="text-purple-400" />
            <h3 className="text-lg font-semibold text-white">Key Components</h3>
          </div>
          <div className="space-y-3">
            {data.components.map((comp, i) => (
              <div key={i} className="flex gap-3 p-3 rounded-xl bg-white/5 border border-white/5">
                <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center">
                  <FileCode2 size={14} className="text-purple-400" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-white text-sm">{comp.name}</span>
                    <span className="text-xs text-gray-500 font-mono">{comp.path}</span>
                  </div>
                  <p className="text-gray-400 text-sm mt-0.5">{comp.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Entry Points */}
      {data.entry_points.length > 0 && (
        <div className="p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xl">
          <div className="flex items-center gap-3 mb-3">
            <Zap size={20} className="text-yellow-400" />
            <h3 className="text-lg font-semibold text-white">Entry Points</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {data.entry_points.map((ep, i) => (
              <span key={i} className="px-3 py-1 rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-yellow-300 text-xs font-mono">
                {ep}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Data Flow */}
      {data.data_flow && (
        <div className="p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xl">
          <div className="flex items-center gap-3 mb-3">
            <ArrowRightLeft size={20} className="text-cyan-400" />
            <h3 className="text-lg font-semibold text-white">Data Flow</h3>
          </div>
          <p className="text-gray-300 text-sm leading-relaxed">{data.data_flow}</p>
        </div>
      )}

      {/* README Summary */}
      {data.readme_summary && (
        <div className="p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xl">
          <div className="flex items-center gap-3 mb-3">
            <FileCode2 size={20} className="text-orange-400" />
            <h3 className="text-lg font-semibold text-white">README Summary</h3>
          </div>
          <p className="text-gray-300 text-sm leading-relaxed">{data.readme_summary}</p>
        </div>
      )}
    </motion.div>
  );
}
