"use client";

import { useState } from "react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { ArrowDown, Cpu, Layers, ShieldCheck, Play, Activity, Database, Server, Code2, ArrowRight, GitFork, RefreshCw, AlertOctagon } from "lucide-react";

export default function ArchitecturePage() {
  const [activeComponent, setActiveComponent] = useState<string>("engine");

  const archNodes = [
    {
      id: "proposal",
      title: "Agent Proposal",
      subtitle: "ExecutableAction Abstraction",
      role: "Boundary Input",
      description: "Captures the agent's proposed tool invocation as a transport-agnostic ExecutableAction with tool name, arguments, and declared metadata.",
      codePath: "python/src/veyra/core/action.py",
    },
    {
      id: "resolver",
      title: "Candidate Resolver",
      subtitle: "ToolRegistry & Declared Equivalents",
      role: "Candidate Generation",
      description: "Resolves candidate tools using normalized registry metadata and explicit developer equivalence ('veyra.equivalent'). Zero automatic semantic guessing.",
      codePath: "python/src/veyra/registry/resolver.py",
    },
    {
      id: "constraints",
      title: "Hard Constraints Filter",
      subtitle: "Permissions, Risk & Health",
      role: "Policy Invariant",
      description: "Strictly filters candidate actions against caller permissions, maximum risk tier, and tool health. Critical Invariant: Router never widens the allowed action space.",
      codePath: "python/src/veyra/registry/resolver.py",
    },
    {
      id: "router",
      title: "RoutePolicy Engine",
      subtitle: "DeterministicRoutePolicy (v0.1)",
      role: "Action Selection",
      description: "Selects among valid candidates using explicit priority and deterministic fallback ordering. Extensible interface for future research policies (TAGE, Process graph, LTR).",
      codePath: "python/src/veyra/policy/deterministic.py",
    },
    {
      id: "normalizer",
      title: "Safe Normalizer",
      subtitle: "Semantics-Preserving Coercion",
      role: "Argument Normalization",
      description: "Safely coerces scalar types ('42' -> 42, 'true' -> True), unique enum casing, and ISO dates. Strictly raises SchemaValidationError on missing arguments or ambiguity.",
      codePath: "python/src/veyra/boundary/validator.py",
    },
    {
      id: "engine",
      title: "Execution Engine",
      subtitle: "Core Runtime Pipeline",
      role: "Execution Orchestrator",
      description: "Orchestrates the entire lifecycle: proposal -> candidates -> hard constraints -> route policy -> normalization -> execution -> outcome classification -> recovery.",
      codePath: "python/src/veyra/execution/engine.py",
    },
    {
      id: "taxonomy",
      title: "7-Tier Failure Taxonomy",
      subtitle: "FailureClassification",
      role: "Structured Diagnostics",
      description: "Classifies failures into SCHEMA_ERROR, TRANSIENT_ERROR, RATE_LIMIT, PRECONDITION_ERROR, AUTHORIZATION_ERROR, UNKNOWN_STATE, or UNKNOWN.",
      codePath: "python/src/veyra/boundary/taxonomy.py",
    },
    {
      id: "recovery",
      title: "Safe Recovery Policy",
      subtitle: "Bounded Retry Engine",
      role: "Boundary Recovery",
      description: "Retries ONLY transient and rate-limit errors when the operation is explicitly declared retryable AND idempotent. Guarantees 0 unsafe retries on non-idempotent writes.",
      codePath: "python/src/veyra/policy/recovery.py",
    },
    {
      id: "trace",
      title: "Trace Sink & Redaction",
      subtitle: "Section 11 Observability",
      role: "Telemetry Logger",
      description: "Captures full execution traces (proposal, candidates, resolved arguments, policy decision, failure kind, latency) with recursive credential redaction.",
      codePath: "python/src/veyra/core/trace.py",
    },
  ];

  const current = archNodes.find((n) => n.id === activeComponent) || archNodes[0];

  return (
    <div className="min-h-screen flex flex-col bg-[#fcfcfc] text-slate-900">
      <Navbar />

      <main className="flex-grow py-12 sm:py-16">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          {/* Header */}
          <div className="max-w-3xl mb-12 space-y-3">
            <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-500 bg-slate-100 px-2.5 py-1 rounded border border-slate-200">
              System Architecture
            </span>
            <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900">
              Tool-Boundary Execution Pipeline
            </h1>
            <p className="text-sm text-slate-600 leading-relaxed">
              Veyra operates strictly at the tool execution boundary outside the agent reasoning loop:
              <br />
              <code className="text-xs font-mono text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200 mt-1 inline-block">
                Agent Proposes → Candidate Resolution → Hard Constraints → RoutePolicy → Resolved Action → Execution → Recovery → Trace
              </code>
            </p>
          </div>

          {/* Interactive Pipeline Diagram */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start mb-16">
            {/* Visual Pipeline Stack */}
            <div className="lg:col-span-6 space-y-2.5">
              <div className="text-xs font-mono font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Execution Pipeline Stages
              </div>

              {archNodes.map((node, i) => {
                const isActive = activeComponent === node.id;
                return (
                  <button
                    key={node.id}
                    onClick={() => setActiveComponent(node.id)}
                    className={`w-full text-left p-3.5 rounded-lg border transition-all flex items-center justify-between group ${
                      isActive
                        ? "bg-slate-900 text-white border-slate-900 shadow-md ring-2 ring-slate-900/10"
                        : "bg-white hover:bg-slate-50 text-slate-800 border-slate-200/80 shadow-sm"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className={`text-[11px] font-mono font-semibold ${isActive ? "text-emerald-400" : "text-slate-400"}`}>
                        0{i + 1}
                      </span>
                      <div>
                        <div className="text-xs font-bold">{node.title}</div>
                        <div className={`text-[11px] ${isActive ? "text-slate-300" : "text-slate-500"}`}>
                          {node.subtitle}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                        isActive ? "bg-slate-800 text-emerald-300 border border-slate-700" : "bg-slate-100 text-slate-600 border border-slate-200"
                      }`}>
                        {node.role}
                      </span>
                      <ArrowRight className={`w-3.5 h-3.5 transition-transform ${isActive ? "text-emerald-400 translate-x-0.5" : "text-slate-300"}`} />
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Component Detail Card */}
            <div className="lg:col-span-6 sticky top-24">
              <div className="technical-card p-6 sm:p-8 bg-white border-slate-200/90 shadow-sm">
                <div className="flex items-center justify-between border-b border-slate-100 pb-4 mb-5">
                  <div>
                    <span className="text-[11px] font-mono font-semibold text-emerald-600 uppercase tracking-wider">
                      Selected Pipeline Component
                    </span>
                    <h2 className="text-xl font-bold text-slate-900 mt-1">{current.title}</h2>
                    <p className="text-xs text-slate-500 font-mono mt-0.5">{current.subtitle}</p>
                  </div>
                  <span className="px-2.5 py-1 text-xs font-mono font-semibold bg-slate-100 border border-slate-200 text-slate-700 rounded">
                    {current.role}
                  </span>
                </div>

                <div className="space-y-4 text-xs text-slate-700 leading-relaxed mb-6">
                  <div>
                    <strong className="text-slate-900 block mb-1 font-mono uppercase text-[11px]">Component Responsibility:</strong>
                    <p className="text-slate-600">{current.description}</p>
                  </div>

                  <div className="pt-2">
                    <strong className="text-slate-900 block mb-1 font-mono uppercase text-[11px]">Source Implementation:</strong>
                    <div className="p-2.5 rounded bg-slate-950 text-slate-200 font-mono text-[11px] border border-slate-800">
                      <code>{current.codePath}</code>
                    </div>
                  </div>
                </div>

                <div className="p-4 rounded-lg bg-emerald-50/60 border border-emerald-200/80 text-[11px] text-emerald-900">
                  <strong className="font-semibold block mb-0.5">Safety Guarantee:</strong>
                  All boundary decisions are deterministic, auditable, and logged to standard execution telemetry. Zero hidden state transitions.
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
