"use client";

import { useState, useMemo, useCallback, useRef } from "react";
import { motion } from "framer-motion";
import { ZoomIn, ZoomOut, Maximize2, Thermometer, FolderTree, FileCode2 } from "lucide-react";
import type { AnalyzeResponse } from "@/lib/api";

interface CodebaseGraphProps {
  data: AnalyzeResponse;
  className?: string;
}

interface TreeLayoutNode {
  id: string;
  name: string;
  path: string;
  type: "file" | "directory";
  language: string | null;
  color: string;
  heatColor?: string;
  size: number;
  x: number;
  y: number;
  depth: number;
  childCount: number;
  children: TreeLayoutNode[];
  isEntryPoint: boolean;
  isComponent: boolean;
  componentName?: string;
}

// Layout constants
const NODE_HEIGHT = 28;
const INDENT_WIDTH = 24;
const NODE_RADIUS = 5;

export default function CodebaseGraph({ data, className = "" }: CodebaseGraphProps) {
  const [zoom, setZoom] = useState(1);
  const [panX, setPanX] = useState(0);
  const [panY, setPanY] = useState(0);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [showFiles, setShowFiles] = useState(false);
  const [hoveredNode, setHoveredNode] = useState<TreeLayoutNode | null>(null);
  const [collapsedPaths, setCollapsedPaths] = useState<Set<string>>(new Set());
  const containerRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);
  const lastMouse = useRef({ x: 0, y: 0 });

  // Build entry point and component path sets for highlighting
  const entryPointPaths = useMemo(() => {
    return new Set(data.entry_points);
  }, [data.entry_points]);

  const componentPaths = useMemo(() => {
    const map = new Map<string, string>();
    data.components.forEach((c) => map.set(c.path.replace(/\/$/, ""), c.name));
    return map;
  }, [data.components]);

  // Flatten the tree into layout nodes with x, y positions
  const layoutNodes = useMemo(() => {
    const nodes: TreeLayoutNode[] = [];
    let yIndex = 0;

    function walk(node: any, depth: number) {
      const path = node.path || "";
      const isCollapsed = collapsedPaths.has(path);
      const isDir = node.type === "directory";
      const isImportantFile = entryPointPaths.has(path) || componentPaths.has(path.replace(/\/$/, ""));

      if (!isDir && !showFiles && !isImportantFile) {
        return;
      }

      const layoutNode: TreeLayoutNode = {
        id: `n_${yIndex}`,
        name: node.name,
        path,
        type: node.type,
        language: node.language || null,
        color: node.language
          ? (LANG_COLORS[node.language] || "#8b949e")
          : isDir
            ? "#58a6ff"
            : "#8b949e",
        heatColor: getHeatColor(node.size || 0),
        size: node.size || 0,
        x: depth * INDENT_WIDTH,
        y: yIndex * NODE_HEIGHT,
        depth,
        childCount: node.children?.length || 0,
        children: [],
        isEntryPoint: entryPointPaths.has(path),
        isComponent: componentPaths.has(path.replace(/\/$/, "")),
        componentName: componentPaths.get(path.replace(/\/$/, "")),
      };

      nodes.push(layoutNode);
      yIndex++;

      if (isDir && !isCollapsed && node.children) {
        for (const child of node.children) {
          walk(child, depth + 1);
        }
      }
    }

    // Walk from the root's children (skip root itself)
    if (data.file_tree.children) {
      for (const child of data.file_tree.children) {
        walk(child, 0);
      }
    }

    return nodes;
  }, [data.file_tree, collapsedPaths, entryPointPaths, componentPaths, showFiles]);

  const toggleCollapse = useCallback((path: string) => {
    setCollapsedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  // Pan handlers
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 0) { // left click
      isDragging.current = true;
      lastMouse.current = { x: e.clientX, y: e.clientY };
    }
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (isDragging.current) {
      const dx = e.clientX - lastMouse.current.x;
      const dy = e.clientY - lastMouse.current.y;
      setPanX((p) => p + dx);
      setPanY((p) => p + dy);
      lastMouse.current = { x: e.clientX, y: e.clientY };
    }
  }, []);

  const handleMouseUp = useCallback(() => {
    isDragging.current = false;
  }, []);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    setZoom((z) => Math.max(0.3, Math.min(3, z + delta)));
  }, []);

  const resetView = useCallback(() => {
    setZoom(1);
    setPanX(0);
    setPanY(0);
  }, []);

  const totalHeight = layoutNodes.length * NODE_HEIGHT + 40;
  const totalWidth = Math.max(...layoutNodes.map((n) => n.x + 300), 600);

  return (
    <div className={`relative rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xl overflow-hidden ${className}`}>
      {/* Toolbar */}
      <div className="absolute top-3 right-3 z-10 flex items-center gap-1.5">
        <button
          onClick={() => setShowFiles((v) => !v)}
          className={`p-2 rounded-lg transition-all ${
            showFiles ? "bg-cyan-500/20 text-cyan-300" : "bg-white/5 text-gray-400 hover:text-white"
          } border border-white/10`}
          title={showFiles ? "Show directories-focused view" : "Show all files"}
        >
          {showFiles ? <FileCode2 size={14} /> : <FolderTree size={14} />}
        </button>
        <button
          onClick={() => setShowHeatmap(!showHeatmap)}
          className={`p-2 rounded-lg transition-all ${
            showHeatmap ? "bg-orange-500/20 text-orange-400" : "bg-white/5 text-gray-400 hover:text-white"
          } border border-white/10`}
          title="Toggle complexity heatmap"
        >
          <Thermometer size={14} />
        </button>
        <button
          onClick={() => setZoom((z) => Math.min(3, z + 0.2))}
          className="p-2 rounded-lg bg-white/5 border border-white/10 text-gray-400 hover:text-white transition-all"
          title="Zoom in"
        >
          <ZoomIn size={14} />
        </button>
        <button
          onClick={() => setZoom((z) => Math.max(0.3, z - 0.2))}
          className="p-2 rounded-lg bg-white/5 border border-white/10 text-gray-400 hover:text-white transition-all"
          title="Zoom out"
        >
          <ZoomOut size={14} />
        </button>
        <button
          onClick={resetView}
          className="p-2 rounded-lg bg-white/5 border border-white/10 text-gray-400 hover:text-white transition-all"
          title="Fit to view"
        >
          <Maximize2 size={14} />
        </button>
      </div>

      {/* Graph canvas */}
      <div
        ref={containerRef}
        className="w-full h-[500px] cursor-grab active:cursor-grabbing select-none"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
      >
        <svg
          width="100%"
          height="100%"
          viewBox={`${-panX / zoom} ${-panY / zoom} ${800 / zoom} ${500 / zoom}`}
          className="overflow-visible"
        >
          <g transform={`translate(20, 20)`}>
            {/* Edges (lines connecting parent to children) */}
            {layoutNodes.map((node, i) => {
              if (i === 0) return null;
              // Find parent (previous node with depth = node.depth - 1)
              let parentNode = null;
              for (let j = i - 1; j >= 0; j--) {
                if (layoutNodes[j].depth === node.depth - 1 && layoutNodes[j].type === "directory") {
                  parentNode = layoutNodes[j];
                  break;
                }
              }
              if (!parentNode) return null;

              return (
                <line
                  key={`edge_${i}`}
                  x1={parentNode.x + NODE_RADIUS + 3}
                  y1={parentNode.y + NODE_HEIGHT / 2}
                  x2={node.x}
                  y2={node.y + NODE_HEIGHT / 2}
                  stroke="rgba(255,255,255,0.06)"
                  strokeWidth={1}
                />
              );
            })}

            {/* Nodes */}
            {layoutNodes.map((node) => {
              const isDir = node.type === "directory";
              const isCollapsed = collapsedPaths.has(node.path);
              const nodeColor = showHeatmap && !isDir ? (node.heatColor || "#8b949e") : node.color;
              const isHighlighted = node.isEntryPoint || node.isComponent;
              const displayName = truncateLabel(node.name, isDir ? 34 : 30);
              const labelOffset = Math.min(displayName.length, 30) * 6.2;

              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x}, ${node.y})`}
                  className="cursor-pointer"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (isDir) toggleCollapse(node.path);
                    else setHoveredNode(node);
                  }}
                  onMouseEnter={() => setHoveredNode(node)}
                  onMouseLeave={() => setHoveredNode(null)}
                >
                  {/* Highlight bg for components/entry points */}
                  {isHighlighted && (
                    <rect
                      x={-4}
                      y={2}
                      width={250}
                      height={NODE_HEIGHT - 4}
                      rx={6}
                      fill={node.isEntryPoint ? "rgba(250,204,21,0.08)" : "rgba(168,85,247,0.08)"}
                      stroke={node.isEntryPoint ? "rgba(250,204,21,0.2)" : "rgba(168,85,247,0.2)"}
                      strokeWidth={1}
                    />
                  )}

                  {/* Node shape */}
                  {isDir ? (
                    <rect
                      x={2}
                      y={NODE_HEIGHT / 2 - 6}
                      width={12}
                      height={12}
                      rx={3}
                      fill={nodeColor}
                      opacity={0.85}
                      stroke={hoveredNode?.id === node.id ? "white" : "transparent"}
                      strokeWidth={1.2}
                    />
                  ) : (
                    <circle
                      cx={NODE_RADIUS + 3}
                      cy={NODE_HEIGHT / 2}
                      r={NODE_RADIUS}
                      fill={nodeColor}
                      opacity={0.75}
                      stroke={hoveredNode?.id === node.id ? "white" : "transparent"}
                      strokeWidth={1.3}
                    />
                  )}

                  {/* Collapse indicator for dirs */}
                  {isDir && node.childCount > 0 && (
                    <text
                      x={8}
                      y={NODE_HEIGHT / 2 + 1}
                      textAnchor="middle"
                      dominantBaseline="central"
                      fill="white"
                      fontSize={8}
                      fontWeight="bold"
                    >
                      {isCollapsed ? "+" : "−"}
                    </text>
                  )}

                  {/* Label */}
                  <text
                    x={NODE_RADIUS * 2 + 10}
                    y={NODE_HEIGHT / 2}
                    dominantBaseline="central"
                    fill={isDir ? "#e6edf3" : "#8b949e"}
                    fontSize={11}
                    fontFamily="monospace"
                    fontWeight={isDir ? 600 : 400}
                  >
                    {displayName}{isDir ? "/" : ""}
                    {isDir && isCollapsed && node.childCount > 0 && (
                      <tspan fill="#484f58" fontSize={9}>{` (${node.childCount})`}</tspan>
                    )}
                  </text>

                  {/* Entry point / component badge */}
                  {node.isEntryPoint && (
                    <text
                      x={NODE_RADIUS * 2 + 10 + labelOffset + 10}
                      y={NODE_HEIGHT / 2}
                      dominantBaseline="central"
                      fill="#facc15"
                      fontSize={9}
                    >
                      ⚡ entry
                    </text>
                  )}
                  {node.isComponent && (
                    <text
                      x={NODE_RADIUS * 2 + 10 + labelOffset + 10}
                      y={NODE_HEIGHT / 2}
                      dominantBaseline="central"
                      fill="#a855f7"
                      fontSize={9}
                    >
                      ◆ {node.componentName}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
        </svg>
      </div>

      {/* Hover tooltip */}
      {hoveredNode && !isDragging.current && (
        <motion.div
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          className="absolute bottom-3 left-3 z-10 p-3 rounded-xl bg-black/80 border border-white/10 backdrop-blur-xl text-xs max-w-xs"
        >
          <div className="text-white font-mono font-medium">{hoveredNode.path || hoveredNode.name}</div>
          {hoveredNode.language && (
            <div className="flex items-center gap-1.5 mt-1">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: hoveredNode.color }} />
              <span className="text-gray-400">{hoveredNode.language}</span>
            </div>
          )}
          {hoveredNode.size > 0 && (
            <div className="text-gray-500 mt-0.5">
              Size: {hoveredNode.size < 1024 ? `${hoveredNode.size}B` : `${(hoveredNode.size / 1024).toFixed(1)}KB`}
            </div>
          )}
        </motion.div>
      )}

      {/* Legend */}
      <div className="absolute bottom-3 right-3 z-10 flex items-center gap-3 text-[10px] text-gray-500">
        <div className="flex items-center gap-1">
          <div className="w-3 h-2 rounded-sm bg-blue-400/70" /> Directory
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full bg-gray-300/70" /> File
        </div>
        {showHeatmap && (
          <>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-green-500" /> Simple
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-yellow-500" /> Medium
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-orange-500" /> Complex
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-red-500" /> Very Complex
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// Language colors
const LANG_COLORS: Record<string, string> = {
  Python: "#3572A5", JavaScript: "#f1e05a", TypeScript: "#3178c6",
  Java: "#b07219", Go: "#00ADD8", Rust: "#dea584", Ruby: "#701516",
  PHP: "#4F5D95", "C++": "#f34b7d", "C#": "#178600", Swift: "#F05138",
  HTML: "#e34c26", CSS: "#563d7c", Shell: "#89e051", Docker: "#384d54",
  YAML: "#cb171e", JSON: "#292929", Markdown: "#083fa1",
};

function getHeatColor(size: number): string {
  if (size < 1000) return "#22c55e";     // green
  if (size < 5000) return "#eab308";     // yellow
  if (size < 15000) return "#f97316";    // orange
  return "#ef4444";                       // red
}

function truncateLabel(text: string, max: number): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1)}…`;
}
