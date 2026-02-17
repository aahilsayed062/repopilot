"use client";

import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronRight, File, Folder, FolderOpen } from "lucide-react";
import type { FileTreeNode } from "@/lib/api";

// Language → color mapping
const LANG_COLORS: Record<string, string> = {
  Python: "#3572A5", JavaScript: "#f1e05a", TypeScript: "#3178c6",
  Java: "#b07219", Go: "#00ADD8", Rust: "#dea584", Ruby: "#701516",
  PHP: "#4F5D95", "C++": "#f34b7d", "C#": "#178600", Swift: "#F05138",
  HTML: "#e34c26", CSS: "#563d7c", Shell: "#89e051", Docker: "#384d54",
  YAML: "#cb171e", JSON: "#292929", Markdown: "#083fa1",
};

interface FileExplorerProps {
  tree: FileTreeNode;
  className?: string;
}

export default function FileExplorer({ tree, className = "" }: FileExplorerProps) {
  return (
    <div className={`p-4 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xl overflow-auto max-h-[600px] ${className}`}>
      <h4 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">File Explorer</h4>
      <div className="font-mono text-sm">
        {tree.children?.map((child, i) => (
          <TreeNode key={i} node={child} depth={0} />
        ))}
      </div>
    </div>
  );
}

function TreeNode({ node, depth }: { node: FileTreeNode; depth: number }) {
  const [isOpen, setIsOpen] = useState(depth < 1);
  const isDir = node.type === "directory";
  const hasChildren = isDir && node.children && node.children.length > 0;

  const langColor = node.language ? LANG_COLORS[node.language] || "#8b949e" : undefined;

  // Format file size
  const sizeLabel = useMemo(() => {
    if (!node.size || node.size === 0) return "";
    if (node.size < 1024) return `${node.size}B`;
    if (node.size < 1024 * 1024) return `${(node.size / 1024).toFixed(1)}K`;
    return `${(node.size / (1024 * 1024)).toFixed(1)}M`;
  }, [node.size]);

  return (
    <div>
      <div
        className={`flex items-center gap-1.5 py-0.5 px-1 rounded cursor-pointer hover:bg-white/5 transition-colors group ${
          isDir ? "text-gray-200" : "text-gray-400"
        }`}
        style={{ paddingLeft: `${depth * 16 + 4}px` }}
        onClick={() => isDir && setIsOpen(!isOpen)}
      >
        {/* Expand chevron for dirs */}
        {isDir ? (
          <ChevronRight
            size={14}
            className={`text-gray-500 transition-transform flex-shrink-0 ${isOpen ? "rotate-90" : ""}`}
          />
        ) : (
          <span className="w-3.5" /> // Spacer for alignment
        )}

        {/* Icon */}
        {isDir ? (
          isOpen ? (
            <FolderOpen size={14} className="text-blue-400 flex-shrink-0" />
          ) : (
            <Folder size={14} className="text-blue-400 flex-shrink-0" />
          )
        ) : (
          <File size={14} className="text-gray-500 flex-shrink-0" />
        )}

        {/* Name */}
        <span className="truncate text-xs">{node.name}</span>

        {/* Language dot */}
        {langColor && !isDir && (
          <div
            className="w-2 h-2 rounded-full flex-shrink-0 ml-auto"
            style={{ backgroundColor: langColor }}
            title={node.language || ""}
          />
        )}

        {/* File size */}
        {!isDir && sizeLabel && (
          <span className="text-[10px] text-gray-600 ml-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
            {sizeLabel}
          </span>
        )}
      </div>

      {/* Children */}
      <AnimatePresence>
        {isOpen && hasChildren && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden"
          >
            {node.children!.map((child, i) => (
              <TreeNode key={i} node={child} depth={depth + 1} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
