"use client";

import { motion } from "framer-motion";

// Language → color mapping (matching backend)
const LANGUAGE_COLORS: Record<string, string> = {
  Python: "#3572A5",
  JavaScript: "#f1e05a",
  TypeScript: "#3178c6",
  Java: "#b07219",
  Go: "#00ADD8",
  Rust: "#dea584",
  Ruby: "#701516",
  PHP: "#4F5D95",
  C: "#555555",
  "C++": "#f34b7d",
  "C#": "#178600",
  Swift: "#F05138",
  Kotlin: "#A97BFF",
  Dart: "#00B4AB",
  Shell: "#89e051",
  HTML: "#e34c26",
  CSS: "#563d7c",
  SCSS: "#c6538c",
  Vue: "#41b883",
  Svelte: "#ff3e00",
  Docker: "#384d54",
  YAML: "#cb171e",
  JSON: "#292929",
  Markdown: "#083fa1",
  SQL: "#e38c00",
};

interface TechStackBadgesProps {
  techStack: string[];
  languages: Record<string, number>; // language → percentage
}

export default function TechStackBadges({ techStack, languages }: TechStackBadgesProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
      className="space-y-4"
    >
      {/* Tech Stack */}
      <div className="p-5 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xl">
        <h4 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Tech Stack</h4>
        <div className="flex flex-wrap gap-2">
          {techStack.map((tech, i) => (
            <motion.span
              key={`${tech}-${i}`}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.05 * i }}
              className="px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs font-medium"
            >
              {tech}
            </motion.span>
          ))}
        </div>
      </div>

      {/* Language Breakdown */}
      {Object.keys(languages).length > 0 && (
        <div className="p-5 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xl">
          <h4 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Languages</h4>
          
          {/* Language bar */}
          <div className="flex h-3 rounded-full overflow-hidden mb-3 bg-white/5">
            {Object.entries(languages)
              .sort(([, a], [, b]) => b - a)
              .map(([lang, pct]) => (
                <div
                  key={lang}
                  style={{
                    width: `${Math.max(pct, 2)}%`,
                    backgroundColor: LANGUAGE_COLORS[lang] || "#8b949e",
                  }}
                  className="transition-all duration-500"
                  title={`${lang}: ${pct}%`}
                />
              ))}
          </div>

          {/* Language list */}
          <div className="flex flex-wrap gap-x-4 gap-y-1.5">
            {Object.entries(languages)
              .sort(([, a], [, b]) => b - a)
              .slice(0, 8)
              .map(([lang, pct]) => (
                <div key={lang} className="flex items-center gap-1.5 text-xs">
                  <div
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: LANGUAGE_COLORS[lang] || "#8b949e" }}
                  />
                  <span className="text-gray-300">{lang}</span>
                  <span className="text-gray-500">{pct}%</span>
                </div>
              ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}
