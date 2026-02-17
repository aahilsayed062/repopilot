"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { Package, Wrench, Database, TestTube2, Palette, Shield, Globe } from "lucide-react";
import type { DependencyInfo } from "@/lib/api";

interface DependencyGraphProps {
  dependencies: DependencyInfo[];
  devDependencies: DependencyInfo[];
  categories: Record<string, string[]>;
}

const CATEGORY_CONFIG: Record<string, { icon: typeof Package; color: string; bg: string; border: string }> = {
  Framework: { icon: Package, color: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/20" },
  Database: { icon: Database, color: "text-green-400", bg: "bg-green-500/10", border: "border-green-500/20" },
  Testing: { icon: TestTube2, color: "text-yellow-400", bg: "bg-yellow-500/10", border: "border-yellow-500/20" },
  "UI/Animation": { icon: Palette, color: "text-pink-400", bg: "bg-pink-500/10", border: "border-pink-500/20" },
  DevTools: { icon: Wrench, color: "text-orange-400", bg: "bg-orange-500/10", border: "border-orange-500/20" },
  Auth: { icon: Shield, color: "text-purple-400", bg: "bg-purple-500/10", border: "border-purple-500/20" },
  "API/HTTP": { icon: Globe, color: "text-cyan-400", bg: "bg-cyan-500/10", border: "border-cyan-500/20" },
  Other: { icon: Package, color: "text-gray-400", bg: "bg-gray-500/10", border: "border-gray-500/20" },
};

export default function DependencyGraph({ dependencies, devDependencies, categories }: DependencyGraphProps) {
  const allDeps = useMemo(() => [...dependencies, ...devDependencies], [dependencies, devDependencies]);

  if (allDeps.length === 0) return null;

  const sortedCategories = useMemo(() => {
    return Object.entries(categories).sort(([, a], [, b]) => b.length - a.length);
  }, [categories]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xl"
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Package size={20} className="text-emerald-400" />
          <h3 className="text-lg font-semibold text-white">Dependencies</h3>
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-500">
          <span>{dependencies.length} runtime</span>
          <span>·</span>
          <span>{devDependencies.length} dev</span>
        </div>
      </div>

      {/* Category groups */}
      <div className="space-y-4">
        {sortedCategories.map(([category, deps]) => {
          const config = CATEGORY_CONFIG[category] || CATEGORY_CONFIG.Other;
          const Icon = config.icon;

          return (
            <div key={category}>
              <div className="flex items-center gap-2 mb-2">
                <Icon size={14} className={config.color} />
                <span className={`text-xs font-semibold uppercase tracking-wider ${config.color}`}>
                  {category}
                </span>
                <span className="text-xs text-gray-600">({deps.length})</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {deps.map((depName, depIndex) => {
                  const dep = allDeps.find((d) => d.name === depName);
                  const isDev = dep?.type === "dev";
                  return (
                    <span
                      key={`${category}-${depName}-${depIndex}`}
                      className={`px-2.5 py-1 rounded-lg text-xs font-mono ${config.bg} border ${config.border} ${
                        isDev ? "opacity-60" : ""
                      }`}
                      title={`${depName}${dep?.version ? ` @ ${dep.version}` : ""}${isDev ? " (dev)" : ""}`}
                    >
                      {depName}
                      {dep?.version && dep.version !== "*" && (
                        <span className="text-gray-500 ml-1 text-[10px]">{dep.version}</span>
                      )}
                    </span>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}
