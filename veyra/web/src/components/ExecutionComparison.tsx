import { ArrowRight, Check, X, ShieldAlert, AlertTriangle, RefreshCw, Zap } from "lucide-react";

export default function ExecutionComparison() {
  return (
    <section className="py-16 sm:py-20 border-t border-slate-200/80 bg-slate-50/50">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-12">
          <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-500 bg-slate-100 px-2.5 py-1 rounded border border-slate-200">
            Boundary Architecture Comparison
          </span>
          <h2 className="text-2xl sm:text-3xl font-semibold text-slate-900 tracking-tight mt-3">
            Solve tool failures at the boundary, not in the LLM loop.
          </h2>
          <p className="text-sm text-slate-600 mt-2">
            AI agents shouldn&apos;t waste reasoning turns and token budget re-planning trivial schema coercions or crashing on transient timeouts.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-stretch">
          {/* LEFT: Raw Agent Without Veyra */}
          <div className="technical-card p-6 bg-white flex flex-col justify-between border-slate-200/80">
            <div>
              <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
                <div className="flex items-center gap-2">
                  <span className="flex h-2 w-2 rounded-full bg-rose-500" />
                  <h3 className="font-semibold text-slate-900 text-sm">Raw Agent (Before Veyra)</h3>
                </div>
                <span className="text-[11px] font-mono text-slate-400">16.7% Success on Faults</span>
              </div>

              {/* Diagram */}
              <div className="flex flex-col items-center gap-2 my-6 font-mono text-xs text-slate-700">
                <div className="px-3 py-1.5 rounded bg-slate-100 border border-slate-200 font-medium">User Instruction</div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-400 rotate-90" />
                <div className="px-3 py-1.5 rounded bg-slate-100 border border-slate-200 font-medium">Agent Reasons & Proposes Action</div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-400 rotate-90" />
                <div className="px-3 py-1.5 rounded bg-rose-50 border border-rose-200 font-medium text-rose-800">
                  Tool Error (Wrong Type / 503 / 429)
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-400 rotate-90" />
                <div className="px-3 py-1.5 rounded bg-amber-50 border border-amber-200 font-medium text-amber-800">
                  LLM Sees Error → Re-plans From Scratch
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-400 rotate-90" />
                <div className="px-3 py-1.5 rounded bg-slate-100 border border-slate-200 font-medium text-slate-500">
                  Repeat Stall / Unsafe Write Retry
                </div>
              </div>
            </div>

            <div className="border-t border-slate-100 pt-4 space-y-2 text-xs text-slate-600">
              <div className="flex items-start gap-2">
                <X className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
                <span>Every trivial type coercion forces an expensive LLM reasoning re-plan</span>
              </div>
              <div className="flex items-start gap-2">
                <X className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
                <span>Naive retry blindly repeats write mutations, risking duplicate charges</span>
              </div>
              <div className="flex items-start gap-2">
                <X className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
                <span>High latency overhead, context pollution, and frequent trajectory resets</span>
              </div>
            </div>
          </div>

          {/* RIGHT: With Veyra */}
          <div className="technical-card p-6 bg-white flex flex-col justify-between border-emerald-500/30 ring-1 ring-emerald-500/20 shadow-sm">
            <div>
              <div className="flex items-center justify-between border-b border-emerald-100 pb-3 mb-4">
                <div className="flex items-center gap-2">
                  <span className="flex h-2 w-2 rounded-full bg-emerald-500" />
                  <h3 className="font-semibold text-slate-900 text-sm">Agent + Veyra (Boundary Reliability)</h3>
                </div>
                <span className="text-[11px] font-mono text-emerald-600 font-semibold">41.7% (+25pp) Controlled Success</span>
              </div>

              {/* Diagram */}
              <div className="flex flex-col items-center gap-2 my-6 font-mono text-xs text-slate-700">
                <div className="px-3 py-1.5 rounded bg-slate-100 border border-slate-200 font-medium">User Instruction</div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-400 rotate-90" />
                <div className="px-3 py-1.5 rounded bg-slate-100 border border-slate-200 font-medium">Agent Proposes Tool Call</div>
                <ArrowRight className="w-3.5 h-3.5 text-emerald-600 rotate-90" />
                <div className="px-4 py-2 rounded-md bg-emerald-950 text-emerald-300 border border-emerald-800 font-bold text-center">
                  VEYRA: Safe Normalizer & Safe Retry
                  <div className="text-[10px] text-emerald-400 font-normal">0 semantic guessing · 0 unsafe retries</div>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-emerald-600 rotate-90" />
                <div className="px-3 py-1.5 rounded bg-emerald-50 border border-emerald-200 font-medium text-emerald-800">
                  Tool Executes Successfully (200 OK)
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-400 rotate-90" />
                <div className="px-3 py-1.5 rounded bg-slate-900 text-white font-medium">
                  Agent Continues Plan (0 Re-plans Needed)
                </div>
              </div>
            </div>

            <div className="border-t border-slate-100 pt-4 space-y-2 text-xs text-slate-600">
              <div className="flex items-start gap-2">
                <Check className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <span><strong>50% Boundary Recovery Rate</strong>: Solves schema & transient errors invisibly</span>
              </div>
              <div className="flex items-start gap-2">
                <Check className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <span><strong>0 Unsafe Retries</strong>: Strict idempotency checks protect state and payments</span>
              </div>
              <div className="flex items-start gap-2">
                <Check className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <span><strong>15 Agent Re-plans Avoided</strong> in controlled baseline evaluations</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
