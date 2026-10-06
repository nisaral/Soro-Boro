"use client";

import { useState } from "react";
import { ArrowRight, Code2, Copy, Check, FileCheck, RefreshCcw } from "lucide-react";

export default function HandoffV1Visual() {
  const [copied, setCopied] = useState(false);

  const sampleHandoffJson = `{
  "version": "v1.0",
  "task_id": "tb2-task-8492",
  "source_harness": "native-react",
  "target_harness": "repair-harness",
  "state_summary": {
    "failed_actions": [
      {
        "action": "TOOL_CALL(patch_code)",
        "error": "SyntaxError: invalid syntax on line 47",
        "timestamp": "09:41:05.110"
      }
    ],
    "open_subgoals": [
      "Fix socket timeout async await in src/payment/gateway.py"
    ],
    "verification": {
      "last_suite": "pytest tests/test_gateway.py",
      "status": "FAILED",
      "failed_tests": ["test_gateway_timeout"]
    },
    "artifacts": [
      { "path": "src/payment/gateway.py", "modified": true, "bytes": 4820 }
    ],
    "budget": {
      "usd_used": 0.117,
      "usd_remaining": 0.883,
      "steps_taken": 5,
      "max_steps": 30
    }
  }
}`;

  const copyCode = () => {
    navigator.clipboard.writeText(sampleHandoffJson);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section className="py-16 sm:py-20 bg-slate-50/70 border-t border-slate-200/80">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          {/* Left Text Explanation */}
          <div className="lg:col-span-5 space-y-5">
            <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-500 bg-slate-100 px-2.5 py-1 rounded border border-slate-200">
              State Specification
            </span>
            <h2 className="text-2xl sm:text-3xl font-semibold text-slate-900 tracking-tight">
              HandoffV1 Portable State Contract
            </h2>
            <blockquote className="p-4 rounded-lg bg-white border-l-4 border-slate-900 text-xs sm:text-sm text-slate-700 font-medium italic shadow-sm">
              &ldquo;Veyra treats cross-harness handoff as a state-contract problem, not a prompt-copying problem.&rdquo;
            </blockquote>
            <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
              When an agent harness stalls or hits an execution barrier, Veyra compiles `events.jsonl` into a frozen `HandoffV1` JSON payload. This preserves structural context, workspace diffs, and verification failures across runtime boundaries without ballooning prompt history.
            </p>

            {/* Pipeline Step Indicator */}
            <div className="flex items-center gap-2 pt-2 text-xs font-mono">
              <div className="px-3 py-1.5 rounded bg-white border border-slate-200 text-slate-800 font-semibold shadow-sm">
                Harness A (Native)
              </div>
              <ArrowRight className="w-4 h-4 text-emerald-600 shrink-0" />
              <div className="px-3 py-1.5 rounded bg-slate-900 text-emerald-400 font-semibold shadow-sm">
                HandoffV1 Compiler
              </div>
              <ArrowRight className="w-4 h-4 text-emerald-600 shrink-0" />
              <div className="px-3 py-1.5 rounded bg-white border border-slate-200 text-slate-800 font-semibold shadow-sm">
                Harness B (Repair)
              </div>
            </div>
          </div>

          {/* Right Technical JSON Card */}
          <div className="lg:col-span-7">
            <div className="bg-slate-950 rounded-xl overflow-hidden border border-slate-800 shadow-xl">
              <div className="flex items-center justify-between px-4 py-3 bg-slate-900 border-b border-slate-800 text-xs font-mono text-slate-300">
                <div className="flex items-center gap-2">
                  <Code2 className="w-4 h-4 text-emerald-400" />
                  <span>schemas/handoff.v1.json</span>
                  <span className="text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800 px-1.5 py-0.5 rounded">
                    Validated Schema
                  </span>
                </div>
                <button
                  onClick={copyCode}
                  className="flex items-center gap-1.5 text-slate-400 hover:text-white transition-colors bg-slate-800 px-2 py-1 rounded"
                >
                  {copied ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-400" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" /> Copy JSON
                    </>
                  )}
                </button>
              </div>

              <div className="p-4 sm:p-5 overflow-x-auto">
                <pre className="text-xs font-mono text-slate-200 leading-relaxed">
                  <code>{sampleHandoffJson}</code>
                </pre>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
