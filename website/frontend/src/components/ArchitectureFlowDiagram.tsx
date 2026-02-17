"use client";

import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { motion } from "framer-motion";
import { GitMerge, Expand, Minimize2 } from "lucide-react";
import type { AnalyzeResponse } from "@/lib/api";

interface ArchitectureFlowDiagramProps {
  data: AnalyzeResponse;
  className?: string;
}

type NodeKind = "start" | "finish" | "entry" | "domain" | "component" | "dependency";

type FlowNode = {
  id: string;
  label: string;
  sub?: string;
  kind: NodeKind;
  stage: number;
};

type FlowEdge = {
  id: string;
  from: string;
  to: string;
};

const STAGE_NAMES = ["Start", "Entrypoints", "Domains", "Components", "Dependencies", "Finish"];
const STAGE_X = 220;
const ROW_Y = 94;
const PADDING_X = 80;
const PADDING_Y = 70;

function truncate(text: string, max: number) {
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1)}…`;
}

function basename(path: string) {
  const p = path.replace(/\\/g, "/");
  return p.split("/").filter(Boolean).pop() || path;
}

function topDir(path: string) {
  const p = path.replace(/\\/g, "/").replace(/^\/+/, "");
  return p.split("/")[0] || "";
}

function dedupe<T>(items: T[], keyFn: (v: T) => string): T[] {
  const seen = new Set<string>();
  const out: T[] = [];
  for (const item of items) {
    const key = keyFn(item);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}

export default function ArchitectureFlowDiagram({ data, className = "" }: ArchitectureFlowDiagramProps) {
  const [fullscreen, setFullscreen] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [tilt, setTilt] = useState({ rx: 0, ry: 0 });
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const graph = useMemo(() => {
    const entryCandidates = dedupe(
      (data.entry_points || []).map((p) => p.trim()).filter(Boolean),
      (v) => v.toLowerCase()
    ).slice(0, 5);

    const fileTreeDirs = (data.file_tree?.children || [])
      .filter((c) => c.type === "directory")
      .map((c) => c.path || c.name)
      .filter(Boolean) as string[];

    const compPaths = dedupe(
      (data.components || [])
        .map((c) => c.path?.trim() || "")
        .filter(Boolean),
      (v) => v.toLowerCase()
    );

    const domainCandidates = dedupe(
      [...fileTreeDirs, ...compPaths].map((p) => topDir(p)).filter(Boolean),
      (v) => v.toLowerCase()
    ).slice(0, 6);

    const componentCandidates = dedupe(
      (data.components || [])
        .map((c, i) => ({
          id: `cmp_${i}`,
          name: c.name?.trim() || basename(c.path || "") || `Component ${i + 1}`,
          path: c.path?.trim() || "",
        }))
        .filter((c) => c.name),
      (v) => `${v.name.toLowerCase()}|${v.path.toLowerCase()}`
    ).slice(0, 10);

    const dependencyCandidates = Object.entries(data.dependency_graph?.categories || {})
      .filter(([, deps]) => Array.isArray(deps) && deps.length > 0)
      .sort(([, a], [, b]) => b.length - a.length)
      .slice(0, 5)
      .map(([name, deps]) => ({ name, count: deps.length }));

    const stageNodes: FlowNode[][] = [
      [{ id: "start", label: "START", sub: data.repo_name, kind: "start", stage: 0 }],
      (entryCandidates.length ? entryCandidates : ["repository root"]).map((ep, i) => ({
        id: `entry_${i}`,
        label: truncate(basename(ep), 18),
        sub: ep,
        kind: "entry" as const,
        stage: 1,
      })),
      (domainCandidates.length ? domainCandidates : ["src"]).map((d, i) => ({
        id: `domain_${i}`,
        label: truncate(d, 18),
        sub: "top-level area",
        kind: "domain" as const,
        stage: 2,
      })),
      (componentCandidates.length
        ? componentCandidates
        : [{ id: "cmp_fallback", name: "Core Logic", path: "src/" }]
      ).map((c, i) => ({
        id: c.id || `cmp_${i}`,
        label: truncate(c.name, 20),
        sub: c.path || undefined,
        kind: "component" as const,
        stage: 3,
      })),
      (dependencyCandidates.length
        ? dependencyCandidates
        : [{ name: "Runtime", count: data.dependency_graph?.dependencies?.length || 0 }]
      ).map((d, i) => ({
        id: `dep_${i}`,
        label: truncate(d.name, 18),
        sub: `${d.count} packages`,
        kind: "dependency" as const,
        stage: 4,
      })),
      [{ id: "finish", label: "FINISH", sub: data.architecture_pattern, kind: "finish", stage: 5 }],
    ];

    const maxRows = Math.max(...stageNodes.map((s) => s.length), 2);
    const chartWidth = PADDING_X * 2 + STAGE_X * (stageNodes.length - 1) + 240;
    const chartHeight = PADDING_Y * 2 + ROW_Y * (maxRows - 1) + 120;

    const points: Record<string, { x: number; y: number; n: FlowNode }> = {};
    stageNodes.forEach((stage, stageIndex) => {
      const offset = (maxRows - stage.length) * 0.5;
      stage.forEach((n, i) => {
        points[n.id] = {
          n,
          x: PADDING_X + stageIndex * STAGE_X,
          y: PADDING_Y + (offset + i) * ROW_Y,
        };
      });
    });

    const edges: FlowEdge[] = [];
    for (let s = 0; s < stageNodes.length - 1; s++) {
      const left = stageNodes[s];
      const right = stageNodes[s + 1];
      if (!left.length || !right.length) continue;
      left.forEach((l, i) => {
        const target = right[i % right.length];
        edges.push({ id: `e_${s}_${l.id}_${target.id}`, from: l.id, to: target.id });
        if (right.length > 1 && i % 2 === 0) {
          const alt = right[(i + 1) % right.length];
          if (alt.id !== target.id) edges.push({ id: `x_${s}_${l.id}_${alt.id}`, from: l.id, to: alt.id });
        }
      });
    }

    const nodes = stageNodes.flat();
    const linked: Record<string, Set<string>> = {};
    nodes.forEach((n) => {
      linked[n.id] = new Set([n.id]);
    });
    edges.forEach((e) => {
      linked[e.from].add(e.to);
      linked[e.to].add(e.from);
    });

    return { nodes, edges, points, width: chartWidth, height: chartHeight, linked };
  }, [data]);

  const selected = selectedNodeId ? graph.nodes.find((n) => n.id === selectedNodeId) || null : null;

  const panel = (
    <div className="flex items-center gap-3 mb-4">
      <GitMerge size={20} className="text-cyan-400" />
      <h3 className="text-lg font-semibold text-white">Architecture Flow</h3>
      <button
        onClick={() => setFullscreen(true)}
        className="ml-auto p-2 rounded-lg bg-white/5 border border-white/10 text-gray-300 hover:text-white transition-all"
        title="Open fullscreen"
      >
        <Expand size={14} />
      </button>
    </div>
  );

  const renderDiagram = (interactive: boolean, fitToContainer: boolean) => (
    <svg
      width={fitToContainer ? "100%" : graph.width}
      height={fitToContainer ? "100%" : graph.height}
      viewBox={`0 0 ${graph.width} ${graph.height}`}
      preserveAspectRatio={fitToContainer ? "xMidYMid meet" : "xMinYMin meet"}
      className={fitToContainer ? "" : "min-w-[1060px]"}
    >
      <defs>
        <marker id="flow-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 z" fill="#8b949e" />
        </marker>
        <filter id="selected-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {STAGE_NAMES.map((name, i) => (
        <g key={name}>
          <text
            x={PADDING_X + i * STAGE_X}
            y={36}
            textAnchor="middle"
            fill="#7d8590"
            fontSize={11}
            fontWeight={700}
            letterSpacing={1}
          >
            {name.toUpperCase()}
          </text>
          <line
            x1={PADDING_X + i * STAGE_X}
            y1={46}
            x2={PADDING_X + i * STAGE_X}
            y2={graph.height - 24}
            stroke="rgba(255,255,255,0.05)"
            strokeDasharray="4 6"
          />
        </g>
      ))}

      {graph.edges.map((e) => {
        const a = graph.points[e.from];
        const b = graph.points[e.to];
        if (!a || !b) return null;
        const dx = Math.max(40, (b.x - a.x) / 2);
        const path = `M ${a.x + 40} ${a.y + 20} C ${a.x + 40 + dx} ${a.y + 20}, ${b.x - 40 - dx} ${b.y + 20}, ${b.x - 40} ${b.y + 20}`;
        const active = selectedNodeId ? e.from === selectedNodeId || e.to === selectedNodeId : false;
        const muted = selectedNodeId ? !active : false;
        return (
          <path
            key={e.id}
            d={path}
            stroke={active ? "#67e8f9" : "#8b949e"}
            strokeWidth={active ? 2.4 : 1.9}
            opacity={muted ? 0.2 : 0.9}
            fill="none"
            markerEnd="url(#flow-arrow)"
          />
        );
      })}

      {graph.nodes.map((n) => {
        const p = graph.points[n.id];
        const terminal = n.kind === "start" || n.kind === "finish";
        const fill =
          n.kind === "start" || n.kind === "finish"
            ? "#115e59"
            : n.kind === "entry"
              ? "#0e7490"
              : n.kind === "domain"
                ? "#1d4ed8"
                : n.kind === "component"
                  ? "#16a34a"
                  : "#7c3aed";
        const stroke =
          n.kind === "start" || n.kind === "finish"
            ? "#2dd4bf"
            : n.kind === "entry"
              ? "#67e8f9"
              : n.kind === "domain"
                ? "#60a5fa"
                : n.kind === "component"
                  ? "#86efac"
                  : "#c4b5fd";
        const radius = terminal ? 34 : 28;
        const selected = selectedNodeId === n.id;
        const related = selectedNodeId ? graph.linked[selectedNodeId]?.has(n.id) : false;
        const muted = selectedNodeId ? !related : false;
        return (
          <g
            key={n.id}
            transform={`translate(${p.x}, ${p.y})`}
            onClick={interactive ? () => setSelectedNodeId((prev) => (prev === n.id ? null : n.id)) : undefined}
            className={interactive ? "cursor-pointer" : ""}
          >
            <circle
              cx={0}
              cy={20}
              r={radius}
              fill={fill}
              stroke={selected ? "#ffffff" : stroke}
              strokeWidth={selected ? 2.8 : 2}
              opacity={muted ? 0.24 : 1}
              filter={selected ? "url(#selected-glow)" : undefined}
            />
            <text x={0} y={16} textAnchor="middle" fill="#e6edf3" fontSize={10.5} fontWeight={700} opacity={muted ? 0.35 : 1}>
              {n.label}
            </text>
            {n.sub && (
              <text x={0} y={30} textAnchor="middle" fill="#c9d1d9" fontSize={8} opacity={muted ? 0.35 : 1}>
                {truncate(n.sub, 26)}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );

  const preview = (
    <div
      className="relative rounded-xl border border-white/10 bg-[#0d1218] h-[330px] overflow-hidden cursor-zoom-in"
      onClick={() => setFullscreen(true)}
      onMouseMove={(e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        const dx = (e.clientX - cx) / rect.width;
        const dy = (e.clientY - cy) / rect.height;
        setTilt({ rx: -dy * 6, ry: dx * 8 });
      }}
      onMouseLeave={() => setTilt({ rx: 0, ry: 0 })}
    >
      <motion.div
        animate={{ rotateX: tilt.rx, rotateY: tilt.ry }}
        transition={{ type: "spring", stiffness: 140, damping: 15, mass: 0.7 }}
        style={{ transformStyle: "preserve-3d", transformPerspective: 1000 }}
        className="w-full h-full"
      >
        {renderDiagram(false, true)}
      </motion.div>
      <div className="absolute bottom-3 right-3 text-[11px] px-2 py-1 rounded bg-black/50 border border-white/10 text-gray-300">
        Click to open interactive view
      </div>
    </div>
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xl ${className}`}
    >
      {panel}
      {preview}

      <div className="mt-3 text-xs text-gray-400">
        Click nodes to highlight relationships. Hover in compact mode for 3D depth. Use expand for full exploration.
      </div>

      {selected && (
        <div className="mt-3 p-3 rounded-xl border border-cyan-500/30 bg-cyan-500/10">
          <div className="text-sm font-semibold text-cyan-200">{selected.label}</div>
          <div className="text-xs text-gray-300 mt-1">{selected.sub || "No additional details available"}</div>
          <div className="text-[11px] text-gray-400 mt-2">
            Stage: {STAGE_NAMES[selected.stage]} • Linked nodes: {graph.linked[selected.id]?.size || 1}
          </div>
        </div>
      )}

      {mounted && fullscreen && createPortal(
        <div className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm p-6" onClick={() => setFullscreen(false)}>
          <div
            className="w-full h-full rounded-2xl border border-white/10 bg-[#0d1218] p-4 flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 mb-3">
              <GitMerge size={18} className="text-cyan-400" />
              <h4 className="text-white font-semibold">Architecture Flow • Interactive</h4>
              <button
                onClick={() => setFullscreen(false)}
                className="ml-auto p-2 rounded-lg bg-white/5 border border-white/10 text-gray-300 hover:text-white"
                title="Close fullscreen"
              >
                <Minimize2 size={14} />
              </button>
            </div>
            <div className="flex-1 overflow-auto rounded-xl border border-white/10">
              {renderDiagram(true, false)}
            </div>
            <div className="mt-2 text-xs text-gray-400">Click nodes to highlight connected flow paths and inspect stage details.</div>
          </div>
        </div>,
        document.body
      )}
    </motion.div>
  );
}
