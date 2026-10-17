"use client";

import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import Link from "next/link";
import {
  BarChart3,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Database,
  Layers,
  ArrowRight,
  Info,
  Cpu,
  Zap,
  Sparkles,
  ExternalLink,
  Lock,
} from "lucide-react";

export default function BenchmarksPage() {
  return (
    <div className="min-h-screen flex flex-col bg-[#fcfcfc] text-slate-900">
      <Navbar />

      <main className="flex-grow py-12 sm:py-16">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          {/* Header */}
          <div className="max-w-3xl mb-12 space-y-3">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-md bg-slate-100 border border-slate-200 text-xs font-mono text-slate-700">
              <BarChart3 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Verified Benchmarks · Soro-Kev &amp; Execution Boundary</span>
            </div>

            <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900">
              Verified Model &amp; Runtime Benchmarks
            </h1>

            <p className="text-sm text-slate-600 leading-relaxed">
              Empirical evaluation across two layers: System-One Neural Router accuracy on complex tool catalogs, and deterministic execution safety under transport-level fault injection.
            </p>

            {/* Quick Summary Metric Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-4">
              <div className="p-4 rounded-lg bg-white border border-slate-200 shadow-xs">
                <div className="text-2xl font-bold text-emerald-700 font-mono">94.5%</div>
                <div className="text-xs font-semibold text-slate-900 mt-1">Routing Accuracy</div>
                <div className="text-[11px] text-slate-500">Soro-Kev-4B human holdout</div>
              </div>
              <div className="p-4 rounded-lg bg-white border border-slate-200 shadow-xs">
                <div className="text-2xl font-bold text-emerald-700 font-mono">80 ms</div>
                <div className="text-xs font-semibold text-slate-900 mt-1">Median Latency</div>
                <div className="text-[11px] text-slate-500">Soro-Kev-0.8B on laptop GPU</div>
              </div>
              <div className="p-4 rounded-lg bg-white border border-slate-200 shadow-xs">
                <div className="text-2xl font-bold text-emerald-700 font-mono">0.0%</div>
                <div className="text-xs font-semibold text-slate-900 mt-1">Duplicate Rate</div>
                <div className="text-[11px] text-slate-500">4,000 fault-injected trials</div>
              </div>
              <div className="p-4 rounded-lg bg-white border border-slate-200 shadow-xs">
                <div className="text-2xl font-bold text-emerald-700 font-mono">100%</div>
                <div className="text-xs font-semibold text-slate-900 mt-1">Param Normalization</div>
                <div className="text-[11px] text-slate-500">Deterministic type coercion</div>
              </div>
            </div>
          </div>

          {/* SECTION 1: SORO-KEV SYSTEM-ONE NEURAL ROUTER BENCHMARK */}
          <div className="technical-card p-6 sm:p-8 bg-white mb-12 shadow-sm border border-slate-200 rounded-xl">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4 mb-6">
              <div>
                <span className="text-xs font-mono font-semibold text-emerald-600 uppercase tracking-wider flex items-center gap-1.5">
                  <Cpu className="w-3.5 h-3.5" />
                  Model Performance · System-One Pointer Routing
                </span>
                <h2 className="text-xl font-bold text-slate-900 mt-0.5">
                  Soro-Kev-4B &amp; Soro-Kev-0.8B vs. Baselines
                </h2>
              </div>
              <div className="flex items-center gap-2">
                <a
                  href="https://huggingface.co/nisaralll/soro-kev-4b"
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs font-mono px-3 py-1.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 font-semibold flex items-center gap-1 hover:bg-emerald-100 transition-colors"
                >
                  <span>4B on Hugging Face</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
                <a
                  href="https://huggingface.co/nisaralll/soro-kev-0.8b"
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs font-mono px-3 py-1.5 rounded-lg bg-blue-50 border border-blue-200 text-blue-800 font-semibold flex items-center gap-1 hover:bg-blue-100 transition-colors"
                >
                  <span>0.8B on Hugging Face</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed mb-6">
              Evaluated on Berkeley Function Calling Leaderboard (BFCL) slices and external multi-schema human holdout sets. Soro-Kev models compute hidden-state dot-product pointer attention in a single forward prefill pass without multi-token JSON generation.
            </p>

            {/* Benchmark Table */}
            <div className="overflow-x-auto mb-6">
              <table className="w-full text-left text-xs font-mono border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-slate-700">
                    <th className="py-3 px-4 font-semibold">Evaluation Metric / Slice</th>
                    <th className="py-3 px-4 font-semibold">Heuristic</th>
                    <th className="py-3 px-4 font-semibold">Jared Palmer Kev-0.8B</th>
                    <th className="py-3 px-4 font-semibold text-slate-900 bg-emerald-50/50">Soro-Kev-0.8B (Edge)</th>
                    <th className="py-3 px-4 font-semibold text-emerald-800 bg-emerald-100/60 font-bold">
                      Soro-Kev-4B (Flagship)
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  <tr className="hover:bg-slate-50/50">
                    <td className="py-3 px-4 font-medium text-slate-900">External Human Holdout Accuracy (200 rows)</td>
                    <td className="py-3 px-4 text-slate-500">60.50%</td>
                    <td className="py-3 px-4 text-slate-700">75.00%</td>
                    <td className="py-3 px-4 font-semibold text-slate-900 bg-emerald-50/30">89.00%</td>
                    <td className="py-3 px-4 font-bold text-emerald-700 bg-emerald-100/30">94.50%</td>
                  </tr>
                  <tr className="hover:bg-slate-50/50">
                    <td className="py-3 px-4 font-medium text-slate-900">BFCL Multiple Accuracy (34 rows)</td>
                    <td className="py-3 px-4 text-slate-500">97.06%</td>
                    <td className="py-3 px-4 text-slate-700">100.0%</td>
                    <td className="py-3 px-4 font-semibold text-slate-900 bg-emerald-50/30">100.0%</td>
                    <td className="py-3 px-4 font-bold text-emerald-700 bg-emerald-100/30">100.0%</td>
                  </tr>
                  <tr className="hover:bg-slate-50/50">
                    <td className="py-3 px-4 font-medium text-slate-900">BFCL Live Multiple Accuracy (33 rows)</td>
                    <td className="py-3 px-4 text-slate-500">75.76%</td>
                    <td className="py-3 px-4 text-slate-700">69.70%</td>
                    <td className="py-3 px-4 font-semibold text-slate-900 bg-emerald-50/30">96.97%</td>
                    <td className="py-3 px-4 font-bold text-emerald-700 bg-emerald-100/30">96.97%</td>
                  </tr>
                  <tr className="hover:bg-slate-50/50">
                    <td className="py-3 px-4 font-medium text-slate-900">Argument Key Normalization Rate</td>
                    <td className="py-3 px-4 text-slate-500">42.50%</td>
                    <td className="py-3 px-4 text-slate-400">—</td>
                    <td className="py-3 px-4 font-semibold text-slate-900 bg-emerald-50/30">99.00%</td>
                    <td className="py-3 px-4 font-bold text-emerald-700 bg-emerald-100/30">100.0%</td>
                  </tr>
                  <tr className="hover:bg-slate-50/50">
                    <td className="py-3 px-4 font-medium text-slate-900">Median Inference Latency (Prefill Only)</td>
                    <td className="py-3 px-4 text-slate-500">0.31 ms</td>
                    <td className="py-3 px-4 text-slate-700">110.95 ms</td>
                    <td className="py-3 px-4 font-semibold text-emerald-700 bg-emerald-50/30">80.01 ms</td>
                    <td className="py-3 px-4 font-semibold text-slate-900 bg-emerald-100/30">413.18 ms</td>
                  </tr>
                  <tr className="hover:bg-slate-50/50">
                    <td className="py-3 px-4 font-medium text-slate-900">GPU VRAM Requirement</td>
                    <td className="py-3 px-4 text-slate-500">0 MB</td>
                    <td className="py-3 px-4 text-slate-700">1,612 MB</td>
                    <td className="py-3 px-4 font-semibold text-slate-900 bg-emerald-50/30">1,563 MB</td>
                    <td className="py-3 px-4 font-semibold text-slate-900 bg-emerald-100/30">4,048 MB (NF4)</td>
                  </tr>
                  <tr className="hover:bg-slate-50/50">
                    <td className="py-3 px-4 font-medium text-slate-900">Tool Name Hallucinations</td>
                    <td className="py-3 px-4 text-slate-500">0%</td>
                    <td className="py-3 px-4 text-slate-700">0%</td>
                    <td className="py-3 px-4 font-semibold text-emerald-700 bg-emerald-50/30">0% (Mathematically constrained)</td>
                    <td className="py-3 px-4 font-bold text-emerald-700 bg-emerald-100/30">0% (Mathematically constrained)</td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Schema Format Breakdown */}
            <div className="bg-slate-50 p-4 rounded-lg border border-slate-200">
              <div className="text-xs font-mono font-semibold text-slate-800 mb-2.5">
                Soro-Kev-4B Accuracy Across Tool Schema Protocols:
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5 text-center text-xs font-mono">
                <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs">
                  <div className="text-slate-500 text-[10px] uppercase font-semibold">Agent Skill</div>
                  <div className="text-base font-bold text-emerald-700 mt-0.5">100.0%</div>
                </div>
                <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs">
                  <div className="text-slate-500 text-[10px] uppercase font-semibold">GraphQL RPC</div>
                  <div className="text-base font-bold text-emerald-700 mt-0.5">96.8%</div>
                </div>
                <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs">
                  <div className="text-slate-500 text-[10px] uppercase font-semibold">REST / OpenAPI</div>
                  <div className="text-base font-bold text-emerald-700 mt-0.5">96.2%</div>
                </div>
                <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs">
                  <div className="text-slate-500 text-[10px] uppercase font-semibold">Mixed Catalogs</div>
                  <div className="text-base font-bold text-emerald-700 mt-0.5">94.6%</div>
                </div>
                <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs">
                  <div className="text-slate-500 text-[10px] uppercase font-semibold">MCP JSON</div>
                  <div className="text-base font-bold text-emerald-700 mt-0.5">94.4%</div>
                </div>
                <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs">
                  <div className="text-slate-500 text-[10px] uppercase font-semibold">Python Sig</div>
                  <div className="text-base font-bold text-emerald-700 mt-0.5">87.8%</div>
                </div>
              </div>
            </div>
          </div>

          {/* SECTION 2: EXECUTION BOUNDARY SAFETY (4,000 FAULT TRIALS) */}
          <div className="technical-card p-6 sm:p-8 bg-white mb-12 shadow-sm border border-slate-200 rounded-xl">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-4 mb-6">
              <div>
                <span className="text-xs font-mono font-semibold text-emerald-600 uppercase tracking-wider flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  Deterministic Runtime Safety · 4,000 Injected Fault Trials
                </span>
                <h2 className="text-xl font-bold text-slate-900 mt-0.5">
                  Recovery Strategy Evaluation Under Network &amp; Crash Faults
                </h2>
              </div>
              <span className="text-xs font-mono px-2.5 py-1 rounded bg-slate-100 border border-slate-200 text-slate-700">
                SQLite WAL · Real TCP RST Drops · Stdio MCP · Git Sandbox
              </span>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed mb-6">
              Evaluated across 4 failure regimes: Pre-Commit drops (30%), Post-Commit severed connections (40%), Verifier Probe crashes (15%), and Concurrent Race updates (15%). Holding tools, prompt, task budget, and environment identical across arms.
            </p>

            <div className="overflow-x-auto mb-6">
              <table className="w-full text-left text-xs font-mono border-collapse bg-white rounded border border-slate-200">
                <thead>
                  <tr className="bg-slate-900 text-slate-100 border-b border-slate-800">
                    <th className="py-3 px-4 font-semibold">Execution Strategy</th>
                    <th className="py-3 px-4 font-semibold text-right">Autonomous Success</th>
                    <th className="py-3 px-4 font-semibold text-right">Duplicate Rate</th>
                    <th className="py-3 px-4 font-semibold text-right">Lost-Write Rate</th>
                    <th className="py-3 px-4 font-semibold text-right">Safety Invariant</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  <tr className="bg-emerald-50/90 font-semibold text-slate-900">
                    <td className="py-3 px-4 font-sans font-medium">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                        <span>Soro Boundary (Id-Verified &amp; Probe Backoff)</span>
                      </div>
                      <span className="text-[11px] text-emerald-800 font-normal block mt-0.5">
                        Embeds action_id in payload, probes server state with backoff before safe completion
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right text-emerald-700 font-bold text-sm">100.0%</td>
                    <td className="py-3 px-4 text-right text-emerald-700 font-bold">0.0%</td>
                    <td className="py-3 px-4 text-right text-emerald-700 font-bold">0.0%</td>
                    <td className="py-3 px-4 text-right">
                      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
                        VERIFIED SAFE
                      </span>
                    </td>
                  </tr>

                  <tr className="hover:bg-slate-50 text-slate-700">
                    <td className="py-3 px-4 font-sans font-medium text-slate-800">
                      <div>Native Idempotency Key (Where Supported)</div>
                      <span className="text-[11px] text-slate-500 font-normal block mt-0.5">
                        Relies on server-side deduplication table (Stripe/REST)
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right text-slate-700">92.5%</td>
                    <td className="py-3 px-4 text-right text-emerald-600 font-semibold">0.0%</td>
                    <td className="py-3 px-4 text-right text-amber-600">7.5%</td>
                    <td className="py-3 px-4 text-right">
                      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                        CONDITIONAL
                      </span>
                    </td>
                  </tr>

                  <tr className="hover:bg-slate-50 text-slate-700">
                    <td className="py-3 px-4 font-sans font-medium text-slate-800">
                      <div>No Retry Baseline</div>
                      <span className="text-[11px] text-slate-500 font-normal block mt-0.5">
                        Fails on first network drop without verification
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right text-slate-700">60.0%</td>
                    <td className="py-3 px-4 text-right text-slate-600">0.0%</td>
                    <td className="py-3 px-4 text-right text-rose-600 font-bold">40.0%</td>
                    <td className="py-3 px-4 text-right">
                      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                        INCOMPLETE
                      </span>
                    </td>
                  </tr>

                  <tr className="hover:bg-slate-50 text-slate-700 bg-rose-50/40">
                    <td className="py-3 px-4 font-sans font-medium text-slate-900">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                        <span>Blind Retry (Standard AI Agent Loop)</span>
                      </div>
                      <span className="text-[11px] text-slate-500 font-normal block mt-0.5">
                        Blindly re-executes mutating tool on timeout or network disconnect
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right text-slate-700">52.5%</td>
                    <td className="py-3 px-4 text-right text-rose-600 font-bold bg-rose-100/60 px-2 py-0.5 rounded">
                      39.8% (DUPLICATES)
                    </td>
                    <td className="py-3 px-4 text-right text-slate-600">0.0%</td>
                    <td className="py-3 px-4 text-right">
                      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-100 text-rose-800 border border-rose-300">
                        UNSAFE
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Safety Callout */}
            <div className="p-4 rounded-lg bg-emerald-50 border border-emerald-200/80 text-xs text-emerald-950 flex items-start gap-3">
              <Lock className="w-4 h-4 text-emerald-700 shrink-0 mt-0.5" />
              <div>
                <strong className="font-semibold block mb-0.5 text-emerald-900">
                  Mathematical Invariant: Zero Duplicate Mutations
                </strong>
                Across 2,800 at-risk trials where server writes succeeded before connection severed, Soro produced exactly 0 duplicate operations. The Rule of Three yields a 95% upper confidence bound of &le; 0.43% per target system.
              </div>
            </div>
          </div>

          {/* BOTTOM CTA: GET STARTED */}
          <div className="p-8 rounded-xl bg-slate-900 text-white text-center space-y-4">
            <h3 className="text-xl sm:text-2xl font-bold">Ready to integrate Soro into your agent?</h3>
            <p className="text-xs sm:text-sm text-slate-400 max-w-xl mx-auto">
              Download the fine-tuned weights directly from Hugging Face or install the lightweight Soro client library.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
              <a
                href="https://huggingface.co/nisaralll/soro-kev-4b"
                target="_blank"
                rel="noreferrer"
                className="px-5 py-2.5 rounded-lg text-xs font-semibold text-slate-900 bg-white hover:bg-slate-100 transition-colors inline-flex items-center gap-2"
              >
                <Cpu className="w-4 h-4" />
                Soro-Kev-4B on Hugging Face
              </a>
              <Link
                href="/docs"
                className="px-5 py-2.5 rounded-lg text-xs font-semibold text-slate-300 hover:text-white border border-slate-700 hover:bg-slate-800 transition-colors inline-flex items-center gap-2"
              >
                Read Developer Docs
              </Link>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
