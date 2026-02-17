"use client";

import { motion } from "framer-motion";
import { Files, Code2, Layers, FolderTree } from "lucide-react";
import type { RepoStats } from "@/lib/api";

interface StatsPanelProps {
  stats: RepoStats;
  repoName: string;
  branch: string;
}

export default function StatsPanel({ stats, repoName, branch }: StatsPanelProps) {
  const statCards = [
    {
      label: "Files",
      value: stats.total_files.toLocaleString(),
      icon: Files,
      color: "text-blue-400",
      bg: "bg-blue-500/10",
      border: "border-blue-500/20",
    },
    {
      label: "Lines of Code",
      value: stats.total_lines.toLocaleString(),
      icon: Code2,
      color: "text-emerald-400",
      bg: "bg-emerald-500/10",
      border: "border-emerald-500/20",
    },
    {
      label: "Languages",
      value: Object.keys(stats.languages).length.toString(),
      icon: Layers,
      color: "text-purple-400",
      bg: "bg-purple-500/10",
      border: "border-purple-500/20",
    },
    {
      label: "Max Depth",
      value: stats.directory_depth.toString(),
      icon: FolderTree,
      color: "text-orange-400",
      bg: "bg-orange-500/10",
      border: "border-orange-500/20",
    },
  ];

  return (
    <div className="space-y-4">
      {/* Repo identity bar */}
      <div className="flex items-center gap-3 px-1">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-gray-300 font-semibold">{repoName}</span>
          <span className="text-gray-600">·</span>
          <span className="text-gray-500 font-mono text-xs">{branch}</span>
          <span className="text-gray-600">·</span>
          <span className="px-2 py-0.5 rounded-md bg-white/5 border border-white/10 text-gray-400 text-xs capitalize">
            {stats.structure_type}
          </span>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {statCards.map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 * i }}
            className={`p-4 rounded-xl ${stat.bg} border ${stat.border} backdrop-blur-xl`}
          >
            <div className="flex items-center gap-2 mb-1">
              <stat.icon size={14} className={stat.color} />
              <span className="text-xs text-gray-400 uppercase tracking-wider">{stat.label}</span>
            </div>
            <div className={`text-2xl font-bold ${stat.color}`}>{stat.value}</div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
