import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import GithubIcon from "@/components/GithubIcon";
import { BookOpen, ExternalLink, Code2, ShieldCheck, Terminal } from "lucide-react";

export default function GitHubPage() {
  return (
    <div className="min-h-screen flex flex-col bg-[#fcfcfc] text-slate-900">
      <Navbar />

      <main className="flex-grow py-16 sm:py-24">
        <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 text-center space-y-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-100 border border-slate-200 text-xs font-mono text-slate-700">
            <GithubIcon className="w-3.5 h-3.5" />
            <span>Open Source Repository</span>
            <span className="text-slate-400">|</span>
            <span className="text-slate-500">Apache-2.0</span>
          </div>

          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight text-slate-900">
            Build with Veyra.
          </h1>

          <p className="text-base sm:text-lg text-slate-600 max-w-2xl mx-auto leading-relaxed">
            Open-source adaptive execution for tool-using agents under cost, risk, and state constraints.
          </p>

          {/* Action CTAs */}
          <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
            <a
              href="https://github.com/nisaral/EB-JEPA/tree/main/veyra"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg text-sm font-semibold text-white bg-slate-900 hover:bg-slate-800 shadow-md transition-all"
            >
              <GithubIcon className="w-4 h-4 text-white" />
              Open Veyra on GitHub
              <ExternalLink className="w-3.5 h-3.5 text-slate-400" />
            </a>
            <a
              href="/docs"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg text-sm font-semibold text-slate-800 bg-white hover:bg-slate-50 border border-slate-200 shadow-sm transition-all"
            >
              <BookOpen className="w-4 h-4 text-slate-500" />
              Read the Docs
            </a>
          </div>

          {/* Technical Repository Overview */}
          <div className="technical-card p-6 bg-white text-left text-xs font-mono space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <span className="font-semibold text-slate-900 text-sm">Standalone Repository Structure</span>
              <span className="text-slate-400">veyra/ main branch</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-slate-700">
              <div className="p-3 bg-slate-50 border border-slate-200 rounded space-y-1">
                <div className="font-bold text-slate-900 flex items-center gap-1.5">
                  <Code2 className="w-3.5 h-3.5 text-slate-600" /> Python Sidecar SDK
                </div>
                <p className="text-[11px] text-slate-500">
                  Harness adapters (Native, Repair, LangGraph), decision backends, HandoffV1 compiler, and CLI.
                </p>
              </div>

              <div className="p-3 bg-slate-50 border border-slate-200 rounded space-y-1">
                <div className="font-bold text-slate-900 flex items-center gap-1.5">
                  <Terminal className="w-3.5 h-3.5 text-slate-600" /> Go Execution Kernel
                </div>
                <p className="text-[11px] text-slate-500">
                  Task loop engine, gRPC server, policy evaluator, budget ledger, and event log storage.
                </p>
              </div>
            </div>

            <div className="pt-2 text-center text-slate-500 text-[11px]">
              Licensed under Apache License 2.0 · Built for principled AI systems research & infrastructure.
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
