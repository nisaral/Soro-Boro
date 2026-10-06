"use client";

import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { GATE1_BENCHMARK_DATA, TOOLMISUSE_BENCHMARK_DATA } from "@/lib/benchmarkData";
import { BarChart3, AlertCircle, Info, ArrowRight, ShieldCheck, CheckCircle2, ShieldAlert, Terminal } from "lucide-react";

export default function BenchmarksPage() {
  return (
    <div className="min-h-screen flex flex-col bg-[#fcfcfc] text-slate-900">
      <Navbar />

      <main className="flex-grow py-12 sm:py-16">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          {/* Header */}
          <div className="max-w-3xl mb-10 space-y-3">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-md bg-slate-100 border border-slate-200 text-xs font-mono text-slate-700">
              <BarChart3 className="w-3.5 h-3.5 text-slate-500" />
              <span>Evaluation & Empirical Results</span>
              <span className="badge-measured">MEASURED BASELINE</span>
            </div>

            <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900">
              Veyra Benchmark Suite
            </h1>

            <p className="text-sm text-slate-600 leading-relaxed">
              Empirical evidence evaluating Veyra&apos;s tool-boundary reliability across controlled synthetic faults (Tier 0) and replayable fault injection (ToolMisuseBench Tier 1).
            </p>

            <div className="p-4 rounded-lg bg-emerald-50 border border-emerald-200/80 text-xs text-emerald-900 flex items-start gap-3 shadow-sm">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <strong className="font-semibold block mb-0.5">Boundary Recovery Definition:</strong>
                BoundaryRecovery = (failures resolved without new agent planning) / (failures eligible for boundary resolution).
                The denominator is defined by benchmark fault metadata, avoiding circular recovery claims.
              </div>
            </div>
          </div>

          {/* TIER 1: TOOLMISUSEBENCH TABLE */}
          <div className="technical-card p-6 sm:p-8 bg-white mb-12 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-4 mb-6">
              <div>
                <span className="text-xs font-mono font-semibold text-emerald-600 uppercase tracking-wider">Tier 1 External Benchmark</span>
                <h2 className="text-xl font-bold text-slate-900 mt-0.5">ToolMisuseBench — 4-Arm Comparative Evaluation</h2>
              </div>
              <span className="text-xs font-mono px-2.5 py-1 rounded bg-slate-100 border border-slate-200 text-slate-700">
                60 Fault-Injected Scenarios
              </span>
            </div>

            <div className="overflow-x-auto mb-6">
              <table className="w-full text-left text-xs font-mono border-collapse">
                <thead>
                  <tr className="bg-slate-900 text-slate-100 border-b border-slate-800">
                    <th className="py-3 px-4 font-semibold">System Arm</th>
                    <th className="py-3 px-4 font-semibold text-right">Task Success</th>
                    <th className="py-3 px-4 font-semibold text-right">Boundary Recovery</th>
                    <th className="py-3 px-4 font-semibold text-right">Unsafe Retries</th>
                    <th className="py-3 px-4 font-semibold text-right">Agent Re-plans</th>
                    <th className="py-3 px-4 font-semibold text-right">Total Tool Calls</th>
                    <th className="py-3 px-4 font-semibold text-right">Verdict</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {TOOLMISUSE_BENCHMARK_DATA.map((row, idx) => {
                    const isVeyra = row.arm === "veyra";
                    return (
                      <tr key={idx} className={isVeyra ? "bg-emerald-50/60 font-semibold text-slate-900" : "hover:bg-slate-50 text-slate-700"}>
                        <td className="py-3.5 px-4 font-sans font-medium">
                          <div className="flex items-center gap-2">
                            {isVeyra && <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />}
                            <span>{row.name}</span>
                          </div>
                          <span className="text-[11px] text-slate-500 font-normal font-sans block mt-0.5">
                            {row.description}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <span className={isVeyra ? "text-emerald-700 font-bold text-sm" : "text-slate-600"}>
                            {row.task_success_rate.toFixed(1)}%
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <span className={isVeyra ? "text-emerald-700 font-bold" : "text-slate-400"}>
                            {row.boundary_recovery_rate.toFixed(1)}%
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <span className={row.unsafe_retries > 0 ? "text-rose-600 font-bold bg-rose-50 px-2 py-0.5 rounded border border-rose-200" : "text-emerald-600"}>
                            {row.unsafe_retries}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-right text-slate-800">
                          {row.agent_replans}
                        </td>
                        <td className="py-3.5 px-4 text-right text-slate-600">
                          {row.total_tool_calls}
                        </td>
                        <td className="py-3.5 px-4 text-right font-sans">
                          <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                            isVeyra
                              ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                              : row.status === "UNSAFE"
                              ? "bg-rose-100 text-rose-800 border border-rose-200"
                              : "bg-slate-100 text-slate-700 border border-slate-200"
                          }`}>
                            {row.status}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-700 space-y-2">
              <div className="font-semibold text-slate-900">Key Empirical Findings:</div>
              <ul className="list-disc list-inside space-y-1 text-slate-600 leading-relaxed">
                <li><strong>+25.0 percentage-point absolute improvement</strong>: Veyra increases task success from 16.7% to 41.7% under identical prompt and model conditions.</li>
                <li><strong>15 Agent Re-plans Avoided</strong>: Boundary safely normalized argument types and retried idempotent transient errors without polluting LLM context.</li>
                <li><strong>Strict Zero Unsafe Retries</strong>: Naive retry caused 40 unsafe write retries on payment operations; Veyra strictly halted with structured diagnostics.</li>
              </ul>
            </div>
          </div>

          {/* TIER 0: UNIT / SYNTHETIC CORRECTNESS */}
          <div className="technical-card p-6 sm:p-8 bg-white mb-12 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-4 mb-6">
              <div>
                <span className="text-xs font-mono font-semibold text-slate-500 uppercase tracking-wider">Tier 0 Correctness Validation</span>
                <h2 className="text-xl font-bold text-slate-900 mt-0.5">Synthetic Engineering Safety Invariants</h2>
              </div>
              <span className="text-xs font-mono px-2.5 py-1 rounded bg-emerald-50 border border-emerald-200 text-emerald-700 font-semibold">
                100% Invariants Verified
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="p-5 rounded-lg border border-slate-200 bg-slate-50/50">
                <div className="flex items-center gap-2 mb-2">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  <span className="font-bold text-slate-900 text-sm">False Interventions</span>
                </div>
                <div className="text-3xl font-bold text-slate-900 mb-1">0</div>
                <p className="text-xs text-slate-600">Clean, valid tool calls pass through the execution boundary completely untouched.</p>
              </div>

              <div className="p-5 rounded-lg border border-slate-200 bg-slate-50/50">
                <div className="flex items-center gap-2 mb-2">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  <span className="font-bold text-slate-900 text-sm">Unsafe Retries</span>
                </div>
                <div className="text-3xl font-bold text-emerald-700 mb-1">0</div>
                <p className="text-xs text-slate-600">Write operations, unknown states, and 403s are strictly never retried under any condition.</p>
              </div>

              <div className="p-5 rounded-lg border border-slate-200 bg-slate-50/50">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span className="font-bold text-slate-900 text-sm">Classification Accuracy</span>
                </div>
                <div className="text-3xl font-bold text-emerald-700 mb-1">100.0%</div>
                <p className="text-xs text-slate-600">Across 200+ synthetic cases covering schema, transient, rate limit, precondition, and auth.</p>
              </div>
            </div>
          </div>

          {/* HISTORICAL GATE 1 SECTION */}
          <div className="technical-card p-6 sm:p-8 bg-white">
            <h2 className="text-base font-semibold text-slate-900 mb-2">
              Historical Reference: Terminal-Bench 2.0 Leaderboard Analysis (Gate 1)
            </h2>
            <p className="text-xs text-slate-600 mb-6 leading-relaxed">
              Pre-registered cross-harness oracle evaluation on 89 static tasks. Evaluated to establish the ceiling effect of model capability vs harness switching before the tool boundary pivot.
            </p>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono border-collapse">
                <thead>
                  <tr className="bg-slate-100 text-slate-700 border-b border-slate-200">
                    <th className="py-2.5 px-3 font-semibold">Model Cohort</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Fixed Best</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Oracle</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Null (Best-of-m)</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Net Headroom</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Verdict</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-600">
                  {GATE1_BENCHMARK_DATA.map((row, i) => (
                    <tr key={i} className="hover:bg-slate-50">
                      <td className="py-2.5 px-3 font-sans font-medium text-slate-900">{row.model_cohort}</td>
                      <td className="py-2.5 px-3 text-right">{row.best_pass_rate.toFixed(1)}%</td>
                      <td className="py-2.5 px-3 text-right text-emerald-700 font-semibold">{row.oracle_rate.toFixed(1)}%</td>
                      <td className="py-2.5 px-3 text-right">{row.null_rate.toFixed(1)}%</td>
                      <td className="py-2.5 px-3 text-right font-bold text-slate-900">{row.net_headroom.toFixed(2)}pp</td>
                      <td className="py-2.5 px-3 text-right">
                        <span className="px-2 py-0.5 rounded text-[10px] bg-slate-100 text-slate-700 border border-slate-200">
                          {row.verdict}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
