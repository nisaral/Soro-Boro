"use client";

import { useState, useEffect } from "react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { DEMO_TRACE_EVENTS, DEMO_CANDIDATE_ACTIONS } from "@/lib/benchmarkData";
import { TraceEvent, CandidateAction } from "@/lib/types";
import { 
  Play, Pause, RotateCcw, ShieldCheck, ShieldAlert, DollarSign, Activity, 
  Terminal, CheckCircle2, AlertTriangle, ArrowRight, Lock, Eye, X, Layers, Cpu
} from "lucide-react";

export default function DashboardPage() {
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<TraceEvent | null>(DEMO_TRACE_EVENTS[0] || null);

  // Simulated auto playback
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (isPlaying) {
      timer = setInterval(() => {
        setCurrentStepIndex((prev) => {
          const next = (prev + 1) % DEMO_TRACE_EVENTS.length;
          setSelectedEvent(DEMO_TRACE_EVENTS[next]);
          return next;
        });
      }, 2000);
    }
    return () => clearInterval(timer);
  }, [isPlaying]);

  // Derived budget ledger values
  const totalBudget = 1.00;
  const eventsUntilCurrent = DEMO_TRACE_EVENTS.slice(0, currentStepIndex + 1);
  const usedBudget = eventsUntilCurrent.reduce((acc, ev) => acc + ev.cost_delta, 0);
  const remainingBudget = Math.max(0, totalBudget - usedBudget);
  const activeEvent = DEMO_TRACE_EVENTS[currentStepIndex] || DEMO_TRACE_EVENTS[0];

  return (
    <div className="min-h-screen flex flex-col bg-[#fcfcfc] text-slate-900">
      <Navbar />

      <main className="flex-grow py-8 sm:py-12">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          {/* Top Console Bar */}
          <div className="flex flex-wrap items-center justify-between gap-4 pb-6 mb-6 border-b border-slate-200/80">
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold tracking-tight text-slate-900">Veyra Execution Console</h1>
                <span className="badge-demo">DEMO RUN</span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Real-time adaptive execution trace & policy decision monitor
              </p>
            </div>

            {/* Controls */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-medium bg-slate-900 text-white hover:bg-slate-800 rounded shadow-sm transition-colors"
              >
                {isPlaying ? (
                  <>
                    <Pause className="w-3.5 h-3.5 text-amber-400 fill-amber-400" /> Pause Run
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5 text-emerald-400 fill-emerald-400" /> Play Simulation
                  </>
                )}
              </button>
              <button
                onClick={() => {
                  setIsPlaying(false);
                  setCurrentStepIndex(0);
                  setSelectedEvent(DEMO_TRACE_EVENTS[0]);
                }}
                className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-mono bg-white hover:bg-slate-50 text-slate-700 rounded border border-slate-200 transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" /> Reset
              </button>
            </div>
          </div>

          {/* Section 13 & 15: Active Run State & Cost Ledger Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            {/* Active Task Card */}
            <div className="technical-card p-4 bg-white md:col-span-2 flex flex-col justify-between">
              <div>
                <span className="text-[10px] font-mono font-semibold uppercase tracking-wider text-slate-400">Active Task Spec</span>
                <h3 className="font-semibold text-slate-900 text-sm mt-1">Investigate checkout timeout on payment service</h3>
                <div className="flex items-center gap-3 mt-2 text-xs font-mono text-slate-600">
                  <span>Boundary: <strong className="text-slate-900">{activeEvent.harness}</strong></span>
                  <span>Step: <strong className="text-slate-900">{currentStepIndex + 1} / {DEMO_TRACE_EVENTS.length}</strong></span>
                </div>
              </div>
              <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs font-mono">
                <span className="text-slate-500">Current Action:</span>
                <span className="font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                  {activeEvent.type}
                </span>
              </div>
            </div>

            {/* Cost Ledger Widget */}
            <div className="technical-card p-4 bg-white flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono font-semibold uppercase tracking-wider text-slate-400">Execution Overhead</span>
                  <Activity className="w-4 h-4 text-emerald-600" />
                </div>
                <div className="text-2xl font-bold font-mono text-slate-900 mt-1">
                  0.4ms
                </div>
                <div className="text-[11px] text-slate-500">Local boundary intercept</div>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-1.5 mt-2 overflow-hidden">
                <div className="bg-emerald-500 h-full w-full" />
              </div>
            </div>

            {/* RoutePolicy Engine */}
            <div className="technical-card p-4 bg-white flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono font-semibold uppercase tracking-wider text-slate-400">Boundary Policy</span>
                  <Activity className="w-4 h-4 text-emerald-600" />
                </div>
                <div className="text-xl font-bold font-mono text-slate-900 mt-1">
                  Deterministic
                </div>
                <div className="text-[11px] font-mono text-slate-500">RoutePolicy v0.1</div>
              </div>
              <div className="pt-2 flex items-center justify-between text-[11px] font-mono text-slate-600 border-t border-slate-100">
                <span>Invariants: 0 Unsafe Retries</span>
              </div>
            </div>
          </div>

          {/* Section 13 & 14: Candidate Actions & Policy Guardrail View */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 mb-8">
            {/* Candidate Actions Table */}
            <div className="lg:col-span-7 technical-card p-5 bg-white">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
                <h3 className="font-semibold text-slate-900 text-sm">Candidate Actions & Probabilities</h3>
                <span className="text-xs font-mono text-slate-400">Softmax Distribution</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 text-[10px] uppercase">
                    <tr>
                      <th className="py-2 px-3">Candidate Action</th>
                      <th className="py-2 px-3 text-right">Probability</th>
                      <th className="py-2 px-3 text-right">Est. Cost</th>
                      <th className="py-2 px-3 text-center">Risk</th>
                      <th className="py-2 px-3 text-center">Policy Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {DEMO_CANDIDATE_ACTIONS.map((item, i) => (
                      <tr key={i} className={!item.allowed ? "bg-rose-50/40" : "hover:bg-slate-50"}>
                        <td className="py-2.5 px-3 font-medium text-slate-900">{item.name}</td>
                        <td className="py-2.5 px-3 text-right font-bold text-slate-800">
                          {(item.probability * 100).toFixed(0)}%
                        </td>
                        <td className="py-2.5 px-3 text-right text-slate-600">${item.estimated_cost.toFixed(3)}</td>
                        <td className="py-2.5 px-3 text-center">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold uppercase ${
                            item.risk_level === "critical" ? "bg-rose-100 text-rose-800" : "bg-slate-100 text-slate-700"
                          }`}>
                            {item.risk_level}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          {item.allowed ? (
                            <span className="badge-clear">ALLOWED</span>
                          ) : (
                            <span className="badge-stop">BLOCKED</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Section 14: Policy View Visualization */}
            <div className="lg:col-span-5 technical-card p-5 bg-white flex flex-col justify-between border-slate-900/10">
              <div>
                <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-emerald-600" />
                    <h3 className="font-semibold text-slate-900 text-sm">Policy Guardrail Inspection</h3>
                  </div>
                  <span className="text-[10px] font-mono text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                    Active Enforcement
                  </span>
                </div>

                <div className="space-y-3 font-mono text-xs">
                  <div className="p-3 bg-slate-900 text-slate-100 rounded border border-slate-800">
                    <div className="text-[10px] text-slate-400 uppercase">Predicted High Prob Action</div>
                    <div className="text-rose-400 font-bold text-sm mt-0.5 flex items-center justify-between">
                      <span>DELETE_DATABASE</span>
                      <span className="text-xs text-slate-300">Prob: 0.87</span>
                    </div>
                  </div>

                  <div className="p-3 bg-rose-50 border border-rose-200 text-rose-900 rounded space-y-1">
                    <div className="flex items-center gap-1.5 font-bold">
                      <ShieldAlert className="w-4 h-4 text-rose-600" />
                      <span>POLICY BLOCK TRIGGERED</span>
                    </div>
                    <p className="text-[11px] text-rose-700">
                      Reason: Insufficient permission / destructive database drop operation forbidden by strict policy engine.
                    </p>
                  </div>

                  <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-900 rounded flex items-center justify-between">
                    <div>
                      <span className="text-[10px] text-emerald-700 uppercase block font-semibold">Safe Fallback Action</span>
                      <span className="font-bold text-slate-900 text-xs">ASK_USER (Request Human Confirmation)</span>
                    </div>
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-100 text-[11px] text-slate-500">
                Policy guardrails guarantee models never directly trigger raw tools without validation.
              </div>
            </div>
          </div>

          {/* Section 16: Interactive Trace Viewer */}
          <div className="technical-card p-6 bg-white">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4 mb-6">
              <div>
                <h3 className="font-semibold text-slate-900 text-sm">Execution Event Log & Trace Viewer</h3>
                <p className="text-xs text-slate-500 mt-0.5">Click any event to inspect full structured event details</p>
              </div>
              <span className="text-xs font-mono text-slate-400">10 Events Recorded</span>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Event Timeline List */}
              <div className="lg:col-span-6 space-y-2 max-h-[420px] overflow-y-auto pr-2">
                {DEMO_TRACE_EVENTS.map((evt, idx) => {
                  const isSelected = selectedEvent?.id === evt.id;
                  return (
                    <button
                      key={evt.id}
                      onClick={() => {
                        setSelectedEvent(evt);
                        setCurrentStepIndex(idx);
                      }}
                      className={`w-full text-left p-3 rounded-lg border text-xs font-mono transition-all flex items-center justify-between ${
                        isSelected
                          ? "bg-slate-900 text-white border-slate-900 shadow-sm"
                          : "bg-slate-50 hover:bg-slate-100 text-slate-800 border-slate-200/80"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <span className={`text-[10px] ${isSelected ? "text-slate-400" : "text-slate-400"}`}>
                          {evt.timestamp}
                        </span>
                        <span className={`font-bold px-2 py-0.5 rounded text-[10px] ${
                          isSelected ? "bg-slate-800 text-emerald-400" : "bg-white text-slate-900 border border-slate-200"
                        }`}>
                          {evt.type}
                        </span>
                        <span className="truncate max-w-[200px] sm:max-w-[260px] text-slate-300">
                          {evt.summary}
                        </span>
                      </div>
                      <ArrowRight className={`w-3.5 h-3.5 shrink-0 ${isSelected ? "text-emerald-400" : "text-slate-400"}`} />
                    </button>
                  );
                })}
              </div>

              {/* Event Details Drawer */}
              <div className="lg:col-span-6">
                {selectedEvent ? (
                  <div className="bg-slate-950 text-slate-100 rounded-lg p-5 font-mono text-xs border border-slate-800 h-full flex flex-col justify-between shadow-md">
                    <div>
                      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
                        <div className="flex items-center gap-2">
                          <Terminal className="w-4 h-4 text-emerald-400" />
                          <span className="font-bold text-emerald-400 text-sm">{selectedEvent.type}</span>
                          <span className="text-slate-500">[{selectedEvent.id}]</span>
                        </div>
                        <span className="text-slate-400 text-[11px]">{selectedEvent.timestamp}</span>
                      </div>

                      <div className="space-y-3">
                        <div>
                          <div className="text-slate-400 text-[10px] uppercase mb-1">Summary</div>
                          <div className="text-slate-200 font-medium">{selectedEvent.summary}</div>
                        </div>

                        <div>
                          <div className="text-slate-400 text-[10px] uppercase mb-1">Active Harness</div>
                          <div className="text-emerald-300">{selectedEvent.harness}</div>
                        </div>

                        <div>
                          <div className="text-slate-400 text-[10px] uppercase mb-1">Structured Details JSON</div>
                          <pre className="bg-slate-900 p-3 rounded border border-slate-800 text-slate-300 text-[11px] overflow-x-auto">
                            <code>{JSON.stringify(selectedEvent.details, null, 2)}</code>
                          </pre>
                        </div>
                      </div>
                    </div>

                    <div className="pt-3 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400 mt-4">
                      <span>Cost Delta: <strong className="text-emerald-400">${selectedEvent.cost_delta.toFixed(3)}</strong></span>
                      <span>Veyra Event Logger</span>
                    </div>
                  </div>
                ) : (
                  <div className="p-8 text-center text-slate-400 border border-dashed border-slate-200 rounded-lg">
                    Select an event on the left to inspect detailed trace parameters.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
