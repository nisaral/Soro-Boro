import Link from "next/link";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import HeroExecutionVisual from "@/components/HeroExecutionVisual";
import ExecutionComparison from "@/components/ExecutionComparison";
import CoreCapabilities from "@/components/CoreCapabilities";
import DeveloperExperience from "@/components/DeveloperExperience";
import CurrentStatus from "@/components/CurrentStatus";
import RoadmapSection from "@/components/RoadmapSection";
import GithubIcon from "@/components/GithubIcon";
import { TOOLMISUSE_BENCHMARK_DATA } from "@/lib/benchmarkData";
import { ArrowRight, BookOpen, Sparkles, Shield, BarChart3, Terminal, CheckCircle2, AlertTriangle, RefreshCw } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col bg-[#fcfcfc] text-slate-900">
      <Navbar />

      <main className="flex-grow">
        {/* HERO SECTION */}
        <section className="relative pt-12 sm:pt-16 pb-16 sm:pb-20 technical-grid-bg border-b border-slate-200/80">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-3xl mx-auto space-y-4 mb-10">
              {/* Badge */}
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-100 border border-slate-200/80 text-xs font-mono text-slate-700">
                <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
                <span>Veyra v0.1 — Tool-Boundary Reliability Layer</span>
                <span className="text-slate-400">|</span>
                <span className="text-slate-500">Apache-2.0</span>
              </div>

              {/* Main Headline */}
              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-slate-900 leading-[1.1]">
                Agent proposes. <br className="hidden sm:inline" />
                Veyra resolves. <br className="hidden sm:inline" />
                Tool executes.
              </h1>

              {/* Tagline & Subtitle */}
              <p className="text-base sm:text-lg text-slate-600 leading-relaxed max-w-2xl mx-auto">
                A vendor-neutral, drop-in execution boundary layer for existing AI agents. Validates parameters, classifies failures into 7 structured kinds, recovers safe faults without agent re-planning, and strictly guarantees zero unsafe retries.
              </p>

              {/* Primary & Secondary CTAs */}
              <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
                <Link
                  href="/dashboard"
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium text-white bg-slate-900 hover:bg-slate-800 shadow-md transition-all"
                >
                  <Sparkles className="w-4 h-4 text-emerald-400" />
                  Explore Live Trace
                </Link>
                <Link
                  href="/benchmarks"
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium text-slate-800 bg-white hover:bg-slate-50 border border-slate-200 shadow-sm transition-all"
                >
                  <BarChart3 className="w-4 h-4 text-slate-500" />
                  ToolMisuseBench Results (+25pp)
                </Link>
                <Link
                  href="/docs"
                  className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors"
                >
                  <BookOpen className="w-4 h-4" />
                  Docs
                </Link>
                <Link
                  href="/github"
                  className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors"
                >
                  <GithubIcon className="w-4 h-4" />
                  GitHub
                </Link>
              </div>
            </div>

            {/* HERO VISUAL CONTAINER */}
            <HeroExecutionVisual />
          </div>
        </section>

        {/* WHY: EXECUTION COMPARISON */}
        <ExecutionComparison />

        {/* CONTROLLED BENCHMARK SECTION (ToolMisuseBench) */}
        <section className="py-16 sm:py-20 bg-white border-t border-slate-200/80">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="max-w-3xl mb-10 space-y-2">
              <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-500 bg-slate-100 px-2.5 py-1 rounded border border-slate-200">
                Tier 1 Controlled Baseline Evidence
              </span>
              <h2 className="text-2xl sm:text-3xl font-semibold text-slate-900 tracking-tight">
                Empirical Evaluation on ToolMisuseBench
              </h2>
              <p className="text-sm text-slate-600 leading-relaxed">
                Controlled comparison holding model, tools, prompt, task budget, and environment identical across four system arms. Only execution boundary logic varies.
              </p>
            </div>

            {/* Benchmark Table */}
            <div className="technical-card overflow-hidden bg-white border-slate-200/90 shadow-sm mb-6">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono border-collapse">
                  <thead>
                    <tr className="bg-slate-900 text-slate-100 border-b border-slate-800">
                      <th className="py-3 px-4 font-semibold">System Arm</th>
                      <th className="py-3 px-4 font-semibold text-right">Task Success</th>
                      <th className="py-3 px-4 font-semibold text-right">Boundary Recovery</th>
                      <th className="py-3 px-4 font-semibold text-right">Unsafe Retries</th>
                      <th className="py-3 px-4 font-semibold text-right">Agent Re-plans</th>
                      <th className="py-3 px-4 font-semibold text-right">Verdict</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {TOOLMISUSE_BENCHMARK_DATA.map((row, idx) => {
                      const isVeyra = row.arm === "veyra";
                      return (
                        <tr key={idx} className={isVeyra ? "bg-emerald-50/50 font-semibold text-slate-900" : "hover:bg-slate-50 text-slate-700"}>
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
            </div>

            {/* Metric Callouts */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-lg bg-emerald-50 border border-emerald-200/80">
                <div className="text-2xl font-bold text-emerald-800">+25.0%</div>
                <div className="text-xs text-emerald-900 font-medium mt-0.5">Absolute Success Gain</div>
                <p className="text-[11px] text-emerald-700 mt-1">41.7% task success vs 16.7% raw agent on identical fault-injected conditions.</p>
              </div>
              <div className="p-4 rounded-lg bg-slate-50 border border-slate-200">
                <div className="text-2xl font-bold text-slate-900">15 Re-plans</div>
                <div className="text-xs text-slate-800 font-medium mt-0.5">Agent Reasoning Cycles Avoided</div>
                <p className="text-[11px] text-slate-600 mt-1">Boundary recovered schema coercions and idempotent transient faults invisibly.</p>
              </div>
              <div className="p-4 rounded-lg bg-emerald-50 border border-emerald-200/80">
                <div className="text-2xl font-bold text-emerald-800">0 Unsafe Retries</div>
                <div className="text-xs text-emerald-900 font-medium mt-0.5">Strict Safety Invariant</div>
                <p className="text-[11px] text-emerald-700 mt-1">Naive retry committed 40 unsafe write retries; Veyra strictly halts on non-idempotent writes.</p>
              </div>
            </div>
          </div>
        </section>

        {/* HOW: CORE CAPABILITIES */}
        <CoreCapabilities />

        {/* DEVELOPER EXPERIENCE & CODE */}
        <DeveloperExperience />

        {/* EVIDENCE: WHAT'S WORKING TODAY */}
        <CurrentStatus />

        {/* ROADMAP */}
        <RoadmapSection />

        {/* FINAL GITHUB CTA SECTION */}
        <section className="py-16 sm:py-20 bg-slate-900 text-white">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center space-y-6">
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">
              Build with Veyra.
            </h2>
            <p className="text-slate-400 max-w-xl mx-auto text-sm sm:text-base leading-relaxed">
              Open-source tool-boundary reliability middleware for Python functions and MCP tool servers.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
              <Link
                href="/github"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg text-sm font-semibold text-slate-900 bg-white hover:bg-slate-100 shadow-md transition-all"
              >
                <GithubIcon className="w-4 h-4" />
                GitHub Repository
              </Link>
              <Link
                href="/docs"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg text-sm font-medium text-slate-300 hover:text-white border border-slate-700 hover:bg-slate-800 transition-all"
              >
                <BookOpen className="w-4 h-4" />
                Documentation
              </Link>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
