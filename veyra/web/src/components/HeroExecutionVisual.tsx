"use client";

import { useState, useEffect } from "react";
import { DEMO_EXECUTION_NODES } from "@/lib/benchmarkData";
import { ExecutionNode } from "@/lib/types";
import { Play, Pause, ChevronRight, CheckCircle2, AlertTriangle, ShieldCheck, DollarSign, Activity, Zap } from "lucide-react";

export default function HeroExecutionVisual() {
  const [selectedIndex, setSelectedIndex] = useState(4); // Default to 'Normalizer'
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isPlaying) {
      interval = setInterval(() => {
        setSelectedIndex((prev) => (prev + 1) % DEMO_EXECUTION_NODES.length);
      }, 2400);
    }
    return () => clearInterval(interval);
  }, [isPlaying]);

  const activeNode: ExecutionNode = DEMO_EXECUTION_NODES[selectedIndex];

  return (
    <div className="w-full technical-card p-4 sm:p-6 bg-white overflow-hidden shadow-sm">
      {/* Top Controller Bar */}
      <div className="flex items-center justify-between border-b border-slate-100 pb-4 mb-5">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="text-xs font-mono font-medium text-slate-700">Tool-Boundary Execution Lifecycle</span>
          <span className="badge-demo">TRACE SIMULATION</span>
        </div>
        <button
          onClick={() => setIsPlaying(!isPlaying)}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 rounded border border-slate-200 transition-colors"
        >
          {isPlaying ? (
            <>
              <Pause className="w-3 h-3 text-amber-600 fill-amber-600" /> Pause Trace
            </>
          ) : (
            <>
              <Play className="w-3 h-3 text-emerald-600 fill-emerald-600" /> Step Trace Auto
            </>
          )}
        </button>
      </div>

      {/* Interactive 8-Stage Node Pipeline */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2 mb-6">
        {DEMO_EXECUTION_NODES.map((node, index) => {
          const isSelected = selectedIndex === index;
          return (
            <button
              key={node.id}
              onClick={() => {
                setIsPlaying(false);
                setSelectedIndex(index);
              }}
              className={`flex flex-col items-start p-2.5 rounded-lg border text-left transition-all relative ${
                isSelected
                  ? "bg-slate-900 text-white border-slate-900 shadow-md ring-2 ring-slate-900/10"
                  : "bg-slate-50 hover:bg-slate-100 text-slate-800 border-slate-200/80"
              }`}
            >
              <div className="flex items-center justify-between w-full mb-1">
                <span className={`text-[10px] font-mono font-semibold ${isSelected ? "text-emerald-400" : "text-slate-400"}`}>
                  0{index + 1}
                </span>
                {isSelected && (
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                )}
              </div>
              <span className="text-xs font-semibold tracking-tight">{node.label}</span>
              <span className={`text-[10px] truncate max-w-full ${isSelected ? "text-slate-300" : "text-slate-500"}`}>
                {node.subtitle}
              </span>
            </button>
          );
        })}
      </div>

      {/* Selected Node Details Drawer */}
      <div className="bg-slate-950 text-slate-100 rounded-lg p-4 sm:p-5 font-mono text-xs border border-slate-800 shadow-inner">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <span className="text-emerald-400 font-bold text-sm">[{activeNode.label.toUpperCase()}]</span>
            <span className="text-slate-400">Boundary Step 0{selectedIndex + 1} of 08</span>
          </div>
          <div className="flex items-center gap-3 text-slate-400 text-[11px]">
            <span>Engine: <strong className="text-slate-200">{activeNode.decision.model}</strong></span>
            <span>Overhead: <strong className="text-emerald-400">{activeNode.decision.latency_ms}ms</strong></span>
            <span>Status: <strong className="text-emerald-400">ACTIVE</strong></span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Left Column: Inputs & Decision Options */}
          <div className="space-y-3">
            <div>
              <div className="text-slate-400 text-[10px] uppercase tracking-wider mb-1">Boundary State & Payload</div>
              <div className="bg-slate-900/90 rounded p-2.5 border border-slate-800/80 text-slate-300">
                {Object.entries(activeNode.inputs).map(([k, v]) => (
                  <div key={k} className="flex items-start gap-2 py-0.5">
                    <span className="text-slate-500 font-medium min-w-[90px]">{k}:</span>
                    <span className="text-slate-200 truncate">{typeof v === "object" ? JSON.stringify(v) : String(v)}</span>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="text-slate-400 text-[10px] uppercase tracking-wider mb-1">Candidate Evaluation & Probabilities</div>
              <div className="bg-slate-900/90 rounded p-2.5 border border-slate-800/80 space-y-1.5">
                {activeNode.probabilities.map((item, i) => (
                  <div key={i} className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-300 flex items-center gap-1.5">
                      {!item.allowed && <AlertTriangle className="w-3 h-3 text-amber-400" />}
                      {item.name}
                    </span>
                    <div className="flex items-center gap-2">
                      <div className="w-16 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                        <div
                          className={`h-full ${item.allowed ? "bg-emerald-400" : "bg-rose-500 opacity-60"}`}
                          style={{ width: `${item.prob * 100}%` }}
                        />
                      </div>
                      <span className={`min-w-[32px] text-right ${item.allowed ? "text-emerald-400" : "text-rose-400 line-through"}`}>
                        {(item.prob * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right Column: Policy Constraints & Result */}
          <div className="space-y-3">
            <div>
              <div className="text-slate-400 text-[10px] uppercase tracking-wider mb-1">Safety Constraints & Invariants</div>
              <div className="bg-slate-900/90 rounded p-2.5 border border-slate-800/80 space-y-1">
                {activeNode.policy_constraints.map((rule, i) => (
                  <div key={i} className="flex items-start justify-between text-[11px] py-0.5">
                    <span className="text-slate-300 flex items-center gap-1.5">
                      <ShieldCheck className={`w-3 h-3 ${rule.status === "passed" ? "text-emerald-400" : "text-rose-400"}`} />
                      {rule.rule}
                    </span>
                    <span className={`text-[10px] px-1.5 py-0.2 rounded font-semibold ${
                      rule.status === "passed" ? "bg-emerald-950 text-emerald-300 border border-emerald-800" : "bg-rose-950 text-rose-300 border border-rose-800"
                    }`}>
                      {rule.status.toUpperCase()}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="text-slate-400 text-[10px] uppercase tracking-wider mb-1">Resolved Boundary Action</div>
              <div className="bg-slate-900/90 rounded p-2.5 border border-slate-800/80 space-y-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-slate-400 text-[11px]">Action:</span>
                  <span className="text-emerald-300 font-bold bg-slate-950 px-2 py-0.5 rounded border border-slate-800 truncate">
                    {activeNode.selected_action}
                  </span>
                </div>
                <div className="text-[11px] text-slate-300 pt-1 border-t border-slate-800 flex items-start gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                  <span>{activeNode.result.observation}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
