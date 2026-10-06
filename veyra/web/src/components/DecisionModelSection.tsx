import { ArrowDown, Cpu, ShieldCheck, Play, Layers } from "lucide-react";

export default function DecisionModelSection() {
  return (
    <section className="py-16 sm:py-20 bg-white border-t border-slate-200/80">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-12">
          <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-500 bg-slate-100 px-2.5 py-1 rounded border border-slate-200">
            Model Agnostic Architecture
          </span>
          <h2 className="text-2xl sm:text-3xl font-semibold text-slate-900 tracking-tight mt-3">
            Prediction is separate from execution.
          </h2>
          <p className="text-sm text-slate-600 mt-2">
            Veyra treats decision models as prediction backends that generate action probability distributions over candidates.
          </p>
        </div>

        {/* Diagram Card */}
        <div className="max-w-4xl mx-auto technical-card p-6 sm:p-8 bg-slate-50/50">
          <div className="flex flex-col items-center gap-4">
            {/* Top Node */}
            <div className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-slate-900 text-white font-mono font-semibold text-sm shadow-md">
              <Cpu className="w-4 h-4 text-emerald-400" />
              DecisionModel Interface
            </div>

            <ArrowDown className="w-4 h-4 text-slate-400" />

            {/* Middle Row: Model Backends */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full max-w-2xl text-center font-mono text-xs">
              <div className="p-3 bg-white border border-slate-200 rounded-lg shadow-sm">
                <div className="font-semibold text-slate-900">Heuristic Engine</div>
                <div className="text-[10px] text-slate-500 mt-0.5">Hand-written rules & fallback</div>
              </div>
              <div className="p-3 bg-white border border-slate-900/20 rounded-lg shadow-sm ring-1 ring-slate-900/5">
                <div className="font-semibold text-slate-900 flex items-center justify-center gap-1">
                  Kev-0.8B <span className="text-[9px] bg-slate-100 px-1 py-0.2 rounded text-slate-600">Current</span>
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5">System One HTTP Endpoint</div>
              </div>
              <div className="p-3 bg-slate-100/80 border border-dashed border-slate-300 rounded-lg text-slate-500">
                <div className="font-semibold text-slate-600">Future Models</div>
                <div className="text-[10px] text-slate-400 mt-0.5">Contextual Bandits / Von</div>
              </div>
            </div>

            <ArrowDown className="w-4 h-4 text-slate-400" />

            {/* Probabilities Output */}
            <div className="px-4 py-2 rounded bg-white border border-slate-200 text-xs font-mono text-slate-700 shadow-sm flex items-center gap-2">
              <span className="text-slate-400">Output:</span>
              <span className="font-semibold text-slate-900">Softmax Action Probabilities</span>
            </div>

            <ArrowDown className="w-4 h-4 text-slate-400" />

            {/* Policy Filter */}
            <div className="px-5 py-2.5 rounded-lg bg-emerald-950 text-emerald-200 border border-emerald-800 font-mono text-xs font-semibold flex items-center gap-2 shadow-sm">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              Policy Filter (Constrains & Drops Invalid Actions)
            </div>

            <ArrowDown className="w-4 h-4 text-slate-400" />

            {/* Executor Act */}
            <div className="px-5 py-2.5 rounded-lg bg-slate-900 text-white font-mono text-xs font-semibold flex items-center gap-2 shadow-sm">
              <Play className="w-4 h-4 text-emerald-400" />
              Executor Acts (Tool / Model / Harness Switch)
            </div>
          </div>

          <div className="mt-8 pt-6 border-t border-slate-200/80 text-center">
            <blockquote className="text-xs sm:text-sm text-slate-700 font-medium">
              &ldquo;Veyra separates prediction from execution. A decision model predicts; policy constrains; the executor acts.&rdquo;
            </blockquote>
          </div>
        </div>
      </div>
    </section>
  );
}
